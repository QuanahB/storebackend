"""Start Stripe Checkout from the current cart, then record payment."""

import stripe
from flask import Blueprint, current_app, jsonify, request

from cart_session import can_view_order, get_or_create_cart, remember_order
from extensions import db
from models import Order, OrderItem, utcnow
from serializers import as_decimal, order_to_dict, shipping_for
from stripe_payments import (
    configure_stripe,
    create_checkout_session,
    fulfill_paid_order,
    order_from_session,
    payment_session_is_paid,
    release_pending_order,
)

checkout_bp = Blueprint("checkout", __name__)

REQUIRED_FIELDS = (
    "email",
    "shipping_name",
    "shipping_address",
    "shipping_city",
    "shipping_postal_code",
)


@checkout_bp.post("/checkout")
def checkout():
    """
    POST /checkout

    Reserves stock, writes a pending order, and returns a Stripe Checkout URL.
    Stock stays reserved until Stripe reports the session paid or expired.
    """
    error = configure_stripe()
    if error:
        return jsonify(message=error), 503

    body = request.get_json(silent=True) or {}
    missing = [field for field in REQUIRED_FIELDS if not str(body.get(field) or "").strip()]
    if missing:
        return jsonify(message=f"Missing fields: {', '.join(missing)}"), 400

    email = str(body["email"]).strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        return jsonify(message="Enter a valid email."), 400

    cart = get_or_create_cart()
    if not cart.items:
        return jsonify(message="Cart is empty"), 400

    for item in cart.items:
        if item.quantity > item.product.stock:
            return jsonify(message=f"Not enough stock for {item.product.name}"), 400

    subtotal = sum(
        (as_decimal(item.product.price) * item.quantity for item in cart.items),
        start=as_decimal("0"),
    )
    shipping = shipping_for(subtotal)
    order = Order(
        user_id=request_user_id(),
        status="pending",
        subtotal=subtotal,
        shipping=shipping,
        total=subtotal + shipping,
        currency=cart.items[0].product.currency or "USD",
        email=email,
        shipping_name=str(body["shipping_name"]).strip(),
        shipping_address=str(body["shipping_address"]).strip(),
        shipping_city=str(body["shipping_city"]).strip(),
        shipping_postal_code=str(body["shipping_postal_code"]).strip(),
        shipping_country=str(body.get("shipping_country") or "US").strip() or "US",
    )
    db.session.add(order)
    db.session.flush()

    for item in list(cart.items):
        product = item.product
        product.stock -= item.quantity
        product.updated_at = utcnow()
        order.items.append(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                name=product.name,
                slug=product.slug,
                size=item.size,
                quantity=item.quantity,
                unit_price=product.price,
            )
        )
        db.session.delete(item)

    try:
        session = create_checkout_session(order)
    except stripe.StripeError as exc:
        db.session.rollback()
        message = getattr(exc, "user_message", None) or "Stripe could not start checkout."
        return jsonify(message=message), 502

    order.stripe_checkout_session_id = session.id
    db.session.commit()
    remember_order(order)
    return jsonify(checkout_url=session.url, order=order_to_dict(order)), 201


@checkout_bp.get("/checkout/confirm")
def confirm_checkout():
    """
    GET /checkout/confirm?session_id=cs_...

    Asks Stripe whether this Checkout session was paid, then marks the order.
    The webhook does the same job if the shopper closes the tab.
    """
    error = configure_stripe()
    if error:
        return jsonify(message=error), 503

    session_id = (request.args.get("session_id") or "").strip()
    if not session_id:
        return jsonify(message="session_id is required"), 400

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.StripeError as exc:
        message = getattr(exc, "user_message", None) or "Stripe could not confirm this payment."
        return jsonify(message=message), 502

    order = order_from_session(session)
    if order is None:
        return jsonify(message="Order not found for this Stripe session"), 404

    if payment_session_is_paid(session):
        order = fulfill_paid_order(order, session)

    remember_order(order)
    return jsonify(order_to_dict(order))


@checkout_bp.post("/stripe/webhook")
def stripe_webhook():
    """
    POST /stripe/webhook

    Stripe signs this request. Locally:

        stripe listen --forward-to localhost:4000/stripe/webhook
    """
    error = configure_stripe()
    if error:
        return jsonify(message=error), 503

    webhook_secret = (current_app.config.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not webhook_secret:
        return jsonify(message="STRIPE_WEBHOOK_SECRET is not set"), 503

    payload = request.get_data()
    signature = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        return jsonify(message="Invalid Stripe webhook signature"), 400

    event_type = event["type"]
    session_object = event["data"]["object"]
    session_id = session_object.get("id") if isinstance(session_object, dict) else session_object.id
    if not session_id:
        return jsonify(received=True)

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.StripeError as exc:
        message = getattr(exc, "user_message", None) or "Stripe could not load this session."
        return jsonify(message=message), 502

    order = order_from_session(session)
    if order is not None and event_type == "checkout.session.completed" and payment_session_is_paid(session):
        fulfill_paid_order(order, session)
    elif order is not None and event_type == "checkout.session.expired":
        release_pending_order(order)

    return jsonify(received=True)


@checkout_bp.get("/orders/<int:order_id>")
def get_order(order_id: int):
    """GET /orders/:id — only the shopper who placed it."""
    order = db.session.get(Order, order_id)
    if order is None or not can_view_order(order):
        return jsonify(message="Order not found"), 404
    return jsonify(order_to_dict(order))


@checkout_bp.get("/orders")
def list_orders():
    """GET /orders — orders this browser or signed-in account can see."""
    from flask import session

    ids = set(session.get("order_ids") or [])
    user_id = session.get("user_id")
    query = Order.query
    if user_id:
        orders = (
            query.filter((Order.id.in_(ids)) | (Order.user_id == user_id))
            .order_by(Order.id.desc())
            .all()
            if ids
            else query.filter_by(user_id=user_id).order_by(Order.id.desc()).all()
        )
    elif ids:
        orders = query.filter(Order.id.in_(ids)).order_by(Order.id.desc()).all()
    else:
        orders = []
    return jsonify([order_to_dict(order) for order in orders])


def request_user_id():
    from flask import session

    return session.get("user_id")
