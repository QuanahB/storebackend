"""Place an order from the current cart and reserve stock."""

from flask import Blueprint, jsonify, request

from cart_session import can_view_order, get_or_create_cart, remember_order
from extensions import db
from models import Order, OrderItem, utcnow
from serializers import as_decimal, order_to_dict, shipping_for

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

    Reserves stock, writes the order, and clears the cart.
    The same browser can then GET /orders/:id.
    """
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
        status="placed",
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

    db.session.commit()
    remember_order(order)
    return jsonify(order=order_to_dict(order)), 201


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
