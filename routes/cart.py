"""Shopping cart. The session cookie identifies the cart; lines live in SQL."""

from flask import Blueprint, jsonify, request

from cart_session import get_or_create_cart
from extensions import db
from models import CartItem, Product
from serializers import cart_to_dict

cart_bp = Blueprint("cart", __name__)


@cart_bp.get("/cart")
def get_cart():
    """GET /cart"""
    return jsonify(cart_to_dict(get_or_create_cart()))


@cart_bp.delete("/cart")
def clear_cart():
    """DELETE /cart — empty the current cart."""
    cart = get_or_create_cart()
    cart.items.clear()
    db.session.commit()
    return jsonify(message="Cart cleared", **cart_to_dict(cart))


@cart_bp.post("/cart/items")
def add_item():
    """
    POST /cart/items

    Body: { "product_id" or "slug", "quantity"?, "size"? }
    Size defaults to the first size on the piece when omitted.
    """
    body = request.get_json(silent=True) or {}
    product, error = _find_product(body)
    if error:
        return error

    size, error = _resolve_size(product, body.get("size"))
    if error:
        return error

    quantity, error = _parse_quantity(body.get("quantity", 1))
    if error:
        return error

    cart = get_or_create_cart()
    existing = next(
        (item for item in cart.items if item.product_id == product.id and item.size == size),
        None,
    )
    new_quantity = (existing.quantity if existing else 0) + quantity
    if new_quantity > product.stock:
        return jsonify(message=f"Not enough stock for {product.name}"), 400

    if existing is None:
        cart.items.append(
            CartItem(cart_id=cart.id, product_id=product.id, size=size, quantity=new_quantity)
        )
    else:
        existing.quantity = new_quantity

    db.session.commit()
    return jsonify(cart_to_dict(cart)), 201


@cart_bp.patch("/cart/items/<int:item_id>")
def update_item(item_id: int):
    """PATCH /cart/items/:id — body { "quantity": n }. Quantity 0 removes the line."""
    cart = get_or_create_cart()
    item = _item_in_cart(cart, item_id)
    if item is None:
        return jsonify(message="Cart item not found"), 404

    body = request.get_json(silent=True) or {}
    if "quantity" not in body:
        return jsonify(message="quantity is required"), 400

    quantity, error = _parse_quantity(body.get("quantity"), allow_zero=True)
    if error:
        return error

    if quantity == 0:
        cart.items.remove(item)
        db.session.commit()
        return jsonify(cart_to_dict(cart))

    if quantity > item.product.stock:
        return jsonify(message=f"Not enough stock for {item.product.name}"), 400

    item.quantity = quantity
    db.session.commit()
    return jsonify(cart_to_dict(cart))


@cart_bp.delete("/cart/items/<int:item_id>")
def remove_item(item_id: int):
    """DELETE /cart/items/:id"""
    cart = get_or_create_cart()
    item = _item_in_cart(cart, item_id)
    if item is None:
        return jsonify(message="Cart item not found"), 404
    cart.items.remove(item)
    db.session.commit()
    return jsonify(cart_to_dict(cart))


def _item_in_cart(cart, item_id: int):
    return next((item for item in cart.items if item.id == item_id), None)


def _find_product(body):
    if body.get("product_id") is not None:
        product_id, error = _parse_quantity(body.get("product_id"))
        if error:
            return None, (jsonify(message="product_id must be a positive integer"), 400)
        product = db.session.get(Product, product_id)
    elif body.get("slug"):
        product = Product.query.filter_by(slug=str(body["slug"]).strip()).first()
    else:
        return None, (jsonify(message="product_id or slug is required"), 400)

    if product is None:
        return None, (jsonify(message="Product not found"), 404)
    return product, None


def _resolve_size(product: Product, raw):
    sizes = list(product.sizes or [])
    if raw is None or str(raw).strip() == "":
        if not sizes:
            return None, (jsonify(message=f"{product.name} has no sizes"), 400)
        return sizes[0], None
    size = str(raw).strip()
    if size not in sizes:
        return None, (
            jsonify(message=f"Size {size} is not available. Choose from: {', '.join(sizes)}"),
            400,
        )
    return size, None


def _parse_quantity(raw, allow_zero: bool = False):
    if isinstance(raw, bool) or not isinstance(raw, int):
        if isinstance(raw, str) and raw.isdigit():
            raw = int(raw)
        else:
            return None, (jsonify(message="quantity must be a whole number"), 400)
    minimum = 0 if allow_zero else 1
    if raw < minimum:
        return None, (jsonify(message="quantity must be a whole number"), 400)
    return raw, None
