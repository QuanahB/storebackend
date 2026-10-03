"""Stripe Checkout for the OIMADIS store. The secret key never leaves this process."""

from decimal import Decimal, ROUND_HALF_UP

import stripe
from flask import current_app

from extensions import db
from models import Order, utcnow
from serializers import as_decimal


def configure_stripe() -> str | None:
    """Point the Stripe SDK at this app's secret key. Returns an error message if it is missing."""
    secret = (current_app.config.get("STRIPE_SECRET_KEY") or "").strip()
    if not secret:
        return "STRIPE_SECRET_KEY is not set"
    stripe.api_key = secret
    return None


def to_cents(value) -> int:
    amount = as_decimal(value)
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def create_checkout_session(order: Order) -> stripe.checkout.Session:
    """Open a hosted Checkout page for this pending order."""
    currency = (order.currency or "USD").lower()
    line_items = []
    for item in order.items:
        line_items.append(
            {
                "quantity": item.quantity,
                "price_data": {
                    "currency": currency,
                    "unit_amount": to_cents(item.unit_price),
                    "product_data": {"name": f"{item.name} ({item.size})"},
                },
            }
        )
    if as_decimal(order.shipping) > 0:
        line_items.append(
            {
                "quantity": 1,
                "price_data": {
                    "currency": currency,
                    "unit_amount": to_cents(order.shipping),
                    "product_data": {"name": "Shipping"},
                },
            }
        )

    origin = current_app.config["FRONTEND_ORIGIN"].rstrip("/")
    return stripe.checkout.Session.create(
        mode="payment",
        customer_email=order.email,
        client_reference_id=str(order.id),
        metadata={"order_id": str(order.id)},
        line_items=line_items,
        success_url=f"{origin}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/dashboard?checkout=cancelled",
        idempotency_key=f"order-{order.id}",
    )


def payment_session_is_paid(session) -> bool:
    status = _read(session, "payment_status")
    return status == "paid"


def order_from_session(session) -> Order | None:
    session_id = _read(session, "id")
    if session_id:
        order = Order.query.filter_by(stripe_checkout_session_id=session_id).first()
        if order is not None:
            return order

    metadata = _read(session, "metadata") or {}
    if not isinstance(metadata, dict):
        metadata = dict(metadata)
    raw_id = metadata.get("order_id") or _read(session, "client_reference_id")
    if not raw_id:
        return None
    return db.session.get(Order, int(raw_id))


def fulfill_paid_order(order: Order, session) -> Order:
    """Mark a reserved order paid. Safe to call from the webhook and the confirm URL."""
    if order.status == "paid":
        return order
    if order.status != "pending":
        return order

    payment_intent = _read(session, "payment_intent")
    if isinstance(payment_intent, dict):
        payment_intent = payment_intent.get("id")
    order.status = "paid"
    order.stripe_payment_intent_id = payment_intent or order.stripe_payment_intent_id
    db.session.commit()
    return order


def release_pending_order(order: Order) -> Order:
    """Return reserved stock when Checkout expires before payment."""
    if order.status != "pending":
        return order

    from models import Product

    for item in order.items:
        if item.product_id is None:
            continue
        product = db.session.get(Product, item.product_id)
        if product is None:
            continue
        product.stock += item.quantity
        product.updated_at = utcnow()

    order.status = "cancelled"
    db.session.commit()
    return order


def _read(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
