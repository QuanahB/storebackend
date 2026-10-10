"""Staff-only catalog edits. Shoppers never sign in for this."""

import hmac
import re
from decimal import InvalidOperation

from flask import Blueprint, jsonify, request, session

from extensions import db
from models import BoardNote, CartItem, Collection, OrderItem, Product, utcnow
from seed import CATEGORIES
from serializers import as_decimal, product_to_dict

admin_bp = Blueprint("admin", __name__)

CATEGORY_SLUGS = {category["slug"] for category in CATEGORIES}


@admin_bp.get("/admin/session")
def admin_session():
    """GET /admin/session — whether this browser has unlocked the catalog editor."""
    return jsonify(admin=bool(session.get("is_admin")))


@admin_bp.post("/admin/login")
def admin_login():
    """POST /admin/login — body { "password" }. Checks ADMIN_PASSWORD."""
    expected = _admin_password()
    if not expected:
        return jsonify(message="ADMIN_PASSWORD is not set"), 503

    body = request.get_json(silent=True) or {}
    password = str(body.get("password") or "")
    if not password or not hmac.compare_digest(password.encode(), expected.encode()):
        return jsonify(message="Incorrect password."), 401

    session["is_admin"] = True
    session.permanent = True
    return jsonify(admin=True)


@admin_bp.post("/admin/logout")
def admin_logout():
    """POST /admin/logout — locks the catalog editor. The shopper cart stays."""
    session.pop("is_admin", None)
    return jsonify(admin=False)


@admin_bp.delete("/admin/board/<int:note_id>")
def delete_board_note(note_id: int):
    """DELETE /admin/board/:id — staff removes one anonymous note."""
    blocked = _require_admin()
    if blocked:
        return blocked

    note = db.session.get(BoardNote, note_id)
    if note is None:
        return jsonify(message="Note not found"), 404
    db.session.delete(note)
    db.session.commit()
    return jsonify(message="Note removed")


@admin_bp.post("/admin/products")
def create_product():
    """POST /admin/products — add a piece to an existing collection."""
    blocked = _require_admin()
    if blocked:
        return blocked

    body = request.get_json(silent=True) or {}
    parsed, error = _parse_product(body, partial=False)
    if error:
        return error

    slug = parsed.pop("slug")
    collection = parsed.pop("collection")
    product = Product(
        slug=_unique_slug(slug),
        collection_id=collection.id,
        currency="USD",
        initial_stock=parsed["stock"],
        **parsed,
    )
    db.session.add(product)
    db.session.commit()
    return jsonify(product_to_dict(product)), 201


@admin_bp.patch("/admin/products/<int:product_id>")
def update_product(product_id: int):
    """PATCH /admin/products/:id — change the fields included in the body."""
    blocked = _require_admin()
    if blocked:
        return blocked

    product = db.session.get(Product, product_id)
    if product is None:
        return jsonify(message="Product not found"), 404

    body = request.get_json(silent=True) or {}
    if not body:
        return jsonify(message="Send at least one field to change."), 400

    parsed, error = _parse_product(body, partial=True)
    if error:
        return error

    if "slug" in parsed:
        slug = _unique_slug(parsed.pop("slug"), ignore_id=product.id)
        product.slug = slug
    if "collection" in parsed:
        product.collection_id = parsed.pop("collection").id
    if "stock" in parsed and parsed["stock"] > product.initial_stock:
        product.initial_stock = parsed["stock"]

    for key, value in parsed.items():
        setattr(product, key, value)
    product.updated_at = utcnow()
    db.session.commit()
    return jsonify(product_to_dict(product))


@admin_bp.delete("/admin/products/<int:product_id>")
def delete_product(product_id: int):
    """DELETE /admin/products/:id — refused after the piece has been ordered."""
    blocked = _require_admin()
    if blocked:
        return blocked

    product = db.session.get(Product, product_id)
    if product is None:
        return jsonify(message="Product not found"), 404

    if OrderItem.query.filter_by(product_id=product.id).first() is not None:
        return (
            jsonify(message="This piece has already been ordered. Set its stock to 0 instead of deleting it."),
            409,
        )

    CartItem.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()
    return jsonify(message="Product removed")


def _admin_password() -> str:
    from flask import current_app

    return (current_app.config.get("ADMIN_PASSWORD") or "").strip()


def _require_admin():
    if not _admin_password():
        return jsonify(message="ADMIN_PASSWORD is not set"), 503
    if not session.get("is_admin"):
        return jsonify(message="Staff sign-in required."), 401
    return None


def _parse_product(body: dict, *, partial: bool):
    parsed = {}
    required = ("name", "description", "price", "category", "collection", "sizes", "stock")
    if not partial:
        missing = [field for field in required if body.get(field) in (None, "", [])]
        if missing:
            return None, (jsonify(message=f"Missing fields: {', '.join(missing)}"), 400)

    if "name" in body or not partial:
        name = str(body.get("name") or "").strip()
        if not name or len(name) > 200:
            return None, (jsonify(message="Name is required."), 400)
        parsed["name"] = name

    if "description" in body or not partial:
        description = str(body.get("description") or "").strip()
        if not description:
            return None, (jsonify(message="Description is required."), 400)
        parsed["description"] = description

    if "price" in body or not partial:
        try:
            price = as_decimal(body.get("price"))
        except (InvalidOperation, ValueError, TypeError):
            return None, (jsonify(message="Price must be a dollar amount."), 400)
        if price <= 0:
            return None, (jsonify(message="Price must be greater than zero."), 400)
        parsed["price"] = price

    if "category" in body or not partial:
        category = str(body.get("category") or "").strip()
        if category not in CATEGORY_SLUGS:
            choices = ", ".join(sorted(CATEGORY_SLUGS))
            return None, (jsonify(message=f"Category must be one of: {choices}"), 400)
        parsed["category"] = category

    if "collection" in body or not partial:
        slug = str(body.get("collection") or "").strip()
        collection = Collection.query.filter_by(slug=slug).first()
        if collection is None:
            return None, (jsonify(message="Collection not found."), 400)
        parsed["collection"] = collection

    if "sizes" in body or not partial:
        sizes, error = _string_list(body.get("sizes"), "sizes")
        if error:
            return None, error
        parsed["sizes"] = sizes

    if "colors" in body:
        colors, error = _string_list(body.get("colors"), "colors")
        if error:
            return None, error
        parsed["colors"] = colors
    elif not partial:
        parsed["colors"] = ["ink"]

    if "stock" in body or not partial:
        stock, error = _whole_number(body.get("stock"), allow_zero=True)
        if error:
            return None, error
        parsed["stock"] = stock

    if "slug" in body and str(body.get("slug") or "").strip():
        parsed["slug"] = _slugify(str(body["slug"]))
    elif not partial:
        parsed["slug"] = _slugify(parsed["name"])

    return parsed, None


def _string_list(raw, field: str):
    if not isinstance(raw, list) or not raw:
        return None, (jsonify(message=f"{field} must be a list of short labels."), 400)
    values = []
    for item in raw:
        label = str(item).strip()
        if not label or len(label) > 40:
            return None, (jsonify(message=f"{field} must be a list of short labels."), 400)
        values.append(label)
    return values, None


def _whole_number(raw, allow_zero: bool):
    if isinstance(raw, bool) or not isinstance(raw, int):
        if isinstance(raw, str) and raw.isdigit():
            raw = int(raw)
        else:
            return None, (jsonify(message="stock must be a whole number."), 400)
    if raw < 0 or (raw == 0 and not allow_zero):
        return None, (jsonify(message="stock must be a whole number."), 400)
    return raw, None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "piece"


def _unique_slug(slug: str, ignore_id: int | None = None) -> str:
    candidate = slug
    number = 2
    while True:
        existing = Product.query.filter_by(slug=candidate).first()
        if existing is None or existing.id == ignore_id:
            return candidate
        candidate = f"{slug[:70]}-{number}"
        number += 1
