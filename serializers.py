"""JSON shapes returned to MockMSPaint."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from flask import current_app

from models import Collection, Order, Product, User


def as_money(value) -> float:
    """Serialize a SQL numeric as a JSON number with cents."""
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(quantized)


def as_decimal(value) -> Decimal:
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def isoformat(value: datetime) -> str:
    return aware(value).isoformat()


def date_stamp(value: datetime) -> str:
    return aware(value).date().isoformat()


def humanize(value: datetime) -> str:
    """Relative time, matching the dashboard copy ('2 hours ago', 'Yesterday')."""
    seconds = int((datetime.now(timezone.utc) - aware(value)).total_seconds())
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        minutes = seconds // 60
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {unit} ago"
    if seconds < 86400:
        hours = seconds // 3600
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit} ago"
    days = seconds // 86400
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    return date_stamp(value)


def shipping_for(subtotal: Decimal) -> Decimal:
    if subtotal <= 0:
        return Decimal("0.00")
    free_over = as_decimal(current_app.config["FREE_SHIPPING_OVER"])
    if subtotal >= free_over:
        return Decimal("0.00")
    return as_decimal(current_app.config["SHIPPING_FLAT"])


def initials_for(name: str) -> str:
    parts = [part for part in name.strip().split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "initials": initials_for(user.name),
    }


def product_to_dict(product: Product) -> dict:
    collection = product.collection
    return {
        "id": product.id,
        "slug": product.slug,
        "name": product.name,
        "description": product.description,
        "price": as_money(product.price),
        "currency": product.currency,
        "category": product.category,
        "collection": collection.slug if collection else None,
        "collection_name": collection.name if collection else None,
        "sizes": list(product.sizes or []),
        "colors": list(product.colors or []),
        "stock": product.stock,
        "image_url": f"/media/{product.slug}.svg",
    }


def collection_to_dict(collection: Collection, *, include_products: bool = False) -> dict:
    payload = {
        "id": collection.id,
        "slug": collection.slug,
        "name": collection.name,
        "description": collection.description,
        "season": collection.season,
        "product_count": len(collection.products),
    }
    if include_products:
        products = sorted(collection.products, key=lambda item: item.id)
        payload["products"] = [product_to_dict(product) for product in products]
    return payload


def cart_to_dict(cart) -> dict:
    items = []
    subtotal = Decimal("0.00")
    count = 0
    currency = "USD"
    for item in cart.items:
        product = item.product
        currency = product.currency or currency
        line = as_decimal(product.price) * item.quantity
        subtotal += line
        count += item.quantity
        items.append(
            {
                "id": item.id,
                "product_id": product.id,
                "size": item.size,
                "quantity": item.quantity,
                "line_total": as_money(line),
                "product": product_to_dict(product),
            }
        )
    shipping = shipping_for(subtotal)
    return {
        "id": cart.id,
        "items": items,
        "item_count": count,
        "subtotal": as_money(subtotal),
        "shipping": as_money(shipping),
        "total": as_money(subtotal + shipping),
        "currency": currency,
    }


def order_to_dict(order: Order) -> dict:
    items = []
    for item in order.items:
        line = as_decimal(item.unit_price) * item.quantity
        items.append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "name": item.name,
                "slug": item.slug,
                "size": item.size,
                "quantity": item.quantity,
                "unit_price": as_money(item.unit_price),
                "line_total": as_money(line),
            }
        )
    return {
        "id": order.id,
        "status": order.status,
        "email": order.email,
        "shipping_name": order.shipping_name,
        "shipping_address": order.shipping_address,
        "shipping_city": order.shipping_city,
        "shipping_postal_code": order.shipping_postal_code,
        "shipping_country": order.shipping_country,
        "subtotal": as_money(order.subtotal),
        "shipping": as_money(order.shipping),
        "total": as_money(order.total),
        "currency": order.currency,
        "created_at": isoformat(order.created_at),
        "items": items,
    }
