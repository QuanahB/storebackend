"""
Dashboard JSON the MockMSPaint client already fetches.

src/lib/api.ts calls GET /projects, GET /metrics, and GET /activity
and expects the arrays in src/lib/types.ts. Values come from the closet,
not from the bundled Northline sample.
"""

from flask import Blueprint, jsonify

from models import Collection, ContactMessage, Order, Product
from serializers import aware, date_stamp, humanize

dashboard_bp = Blueprint("dashboard", __name__)

LOW_STOCK = 3


@dashboard_bp.get("/projects")
def projects():
    """
    GET /projects

    Each collection is a project so the existing projects page can render
    drop health without a frontend change.
    """
    payload = []
    for collection in Collection.query.order_by(Collection.id).all():
        pieces = list(collection.products)
        payload.append(
            {
                "id": f"col_{collection.slug.replace('-', '_')}",
                "name": collection.name,
                "owner": "OIMADIS studio",
                "status": _status(pieces),
                "updatedAt": _updated_at(pieces, collection),
                "progress": _progress(pieces),
            }
        )
    return jsonify(payload)


@dashboard_bp.get("/metrics")
def metrics():
    """GET /metrics — four cards, values are strings like the frontend type."""
    products = Product.query.all()
    styles = len(products)
    units = sum(product.stock for product in products)
    low = sum(1 for product in products if 0 < product.stock <= LOW_STOCK)
    sold_out = sum(1 for product in products if product.stock <= 0)
    pending_orders = Order.query.filter_by(status="pending").count()
    paid_orders = Order.query.filter(Order.status.in_(("paid", "placed"))).count()
    open_orders = pending_orders + paid_orders
    notes = ContactMessage.query.count()

    if sold_out or low:
        health = "Low"
        health_hint = f"{low} style{'s' if low != 1 else ''} running low, {sold_out} sold out"
    else:
        health = "OK"
        health_hint = "Every style still has stock"

    if open_orders == 0:
        order_hint = "No orders yet"
    elif pending_orders and paid_orders:
        order_hint = f"{pending_orders} awaiting payment, {paid_orders} waiting to ship"
    elif pending_orders:
        order_hint = "Awaiting Stripe payment"
    else:
        order_hint = "Paid and waiting to ship"
    note_hint = "Contact form messages waiting" if notes else "Inbox is clear"

    return jsonify(
        [
            {
                "id": "active",
                "label": "Pieces in stock",
                "value": str(units),
                "hint": f"{styles} styles across the closet",
            },
            {
                "id": "cycle",
                "label": "Open orders",
                "value": str(open_orders),
                "hint": order_hint,
            },
            {
                "id": "open",
                "label": "Unread notes",
                "value": str(notes),
                "hint": note_hint,
            },
            {
                "id": "uptime",
                "label": "Closet health",
                "value": health,
                "hint": health_hint,
            },
        ]
    )


@dashboard_bp.get("/activity")
def activity():
    """GET /activity — recent orders, contact notes, and the catalog seed."""
    events = []

    first = Product.query.order_by(Product.created_at).first()
    if first is not None:
        style_count = Product.query.count()
        drop_count = Collection.query.count()
        events.append(
            {
                "id": "act_catalog",
                "title": "Closet stocked",
                "detail": f"{style_count} handmade pieces are ready across {drop_count} collections.",
                "timestamp": humanize(first.created_at),
                "_at": first.created_at,
            }
        )

    for order in Order.query.order_by(Order.created_at.desc()).limit(12):
        names = ", ".join(f"{item.name} × {item.quantity}" for item in order.items)
        events.append(
            {
                "id": f"act_order_{order.id}",
                "title": f"Order #{order.id} {_order_label(order.status)}",
                "detail": f"{order.shipping_name} · {names}",
                "timestamp": humanize(order.created_at),
                "_at": order.created_at,
            }
        )

    for note in ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(12):
        preview = note.message if len(note.message) <= 120 else note.message[:117] + "..."
        events.append(
            {
                "id": f"act_contact_{note.id}",
                "title": f"Note from {note.name}",
                "detail": preview,
                "timestamp": humanize(note.created_at),
                "_at": note.created_at,
            }
        )

    events.sort(key=lambda event: aware(event["_at"]), reverse=True)
    public = []
    for event in events[:8]:
        public.append(
            {
                "id": event["id"],
                "title": event["title"],
                "detail": event["detail"],
                "timestamp": event["timestamp"],
            }
        )
    return jsonify(public)


def _order_label(status: str) -> str:
    return {
        "pending": "awaiting payment",
        "paid": "paid",
        "placed": "placed",
        "cancelled": "cancelled",
    }.get(status, status)


def _status(pieces: list[Product]) -> str:
    if pieces and all(piece.stock <= 0 for piece in pieces):
        return "done"
    if any(piece.stock <= LOW_STOCK for piece in pieces):
        return "at_risk"
    return "on_track"


def _progress(pieces: list[Product]) -> int:
    initial = sum(piece.initial_stock for piece in pieces)
    if initial <= 0:
        return 0
    sold = initial - sum(piece.stock for piece in pieces)
    return int(round(sold / initial * 100))


def _updated_at(pieces: list[Product], collection: Collection) -> str:
    stamps = [piece.updated_at for piece in pieces if piece.updated_at is not None]
    latest = max(stamps) if stamps else collection.created_at
    return date_stamp(latest)
