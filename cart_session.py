"""Find or create the cart stored on this browser's session cookie."""

from flask import session

from extensions import db
from models import Cart, Order


def get_or_create_cart() -> Cart:
    """Return the open cart for this session, creating one if needed."""
    cart_id = session.get("cart_id")
    cart = db.session.get(Cart, cart_id) if cart_id else None
    if cart is None:
        cart = Cart()
        db.session.add(cart)
        db.session.commit()
        session["cart_id"] = cart.id
        session.permanent = True
    return cart


def remember_order(order: Order) -> None:
    """Let this browser read the order it just placed."""
    order_ids = list(session.get("order_ids") or [])
    if order.id not in order_ids:
        order_ids.append(order.id)
    session["order_ids"] = order_ids
    session.permanent = True


def can_view_order(order: Order) -> bool:
    """Orders are visible to the shopper who placed them, not to everyone."""
    if order.id in (session.get("order_ids") or []):
        return True
    user_id = session.get("user_id")
    return user_id is not None and order.user_id == user_id
