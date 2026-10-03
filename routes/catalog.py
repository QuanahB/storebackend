"""Catalog, collections, videos, and paint-style product images."""

from html import escape

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import or_

from extensions import db
from models import Collection, Product, Video
from seed import CATEGORIES
from serializers import as_money, collection_to_dict, product_to_dict

catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.get("/products")
def list_products():
    """
    GET /products

    Query params:
      category    toolbox slug, e.g. tees
      collection  collection slug, e.g. scribble-drop
      search      match on name or description
      in_stock    true to hide sold-out pieces
    """
    query = Product.query

    category = request.args.get("category")
    if category:
        query = query.filter(Product.category == category)

    collection = request.args.get("collection")
    if collection:
        query = query.join(Collection).filter(Collection.slug == collection)

    search = (request.args.get("search") or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(like), Product.description.ilike(like)))

    in_stock = (request.args.get("in_stock") or "").lower()
    if in_stock in {"1", "true", "yes"}:
        query = query.filter(Product.stock > 0)

    products = query.order_by(Product.id).all()
    return jsonify([product_to_dict(product) for product in products])


@catalog_bp.get("/products/<int:product_id>")
def get_product(product_id: int):
    """GET /products/:id"""
    product = db.session.get(Product, product_id)
    if product is None:
        return jsonify(message="Product not found"), 404
    return jsonify(product_to_dict(product))


@catalog_bp.get("/products/slug/<slug>")
def get_product_by_slug(slug: str):
    """GET /products/slug/:slug"""
    product = Product.query.filter_by(slug=slug).first()
    if product is None:
        return jsonify(message="Product not found"), 404
    return jsonify(product_to_dict(product))


@catalog_bp.get("/categories")
def list_categories():
    """GET /categories — the same groups as the Paint toolbox."""
    payload = []
    for category in CATEGORIES:
        count = Product.query.filter_by(category=category["slug"]).count()
        payload.append({**category, "product_count": count})
    return jsonify(payload)


@catalog_bp.get("/collections")
def list_collections():
    """GET /collections"""
    collections = Collection.query.order_by(Collection.id).all()
    return jsonify([collection_to_dict(collection) for collection in collections])


@catalog_bp.get("/collections/<slug>")
def get_collection(slug: str):
    """GET /collections/:slug — drop plus its pieces."""
    collection = Collection.query.filter_by(slug=slug).first()
    if collection is None:
        return jsonify(message="Collection not found"), 404
    return jsonify(collection_to_dict(collection, include_products=True))


@catalog_bp.get("/videos")
def list_videos():
    """GET /videos — process clips and lookbooks. url is null until a file is hosted."""
    videos = Video.query.order_by(Video.id).all()
    return jsonify(
        [
            {
                "id": video.id,
                "slug": video.slug,
                "title": video.title,
                "description": video.description,
                "kind": video.kind,
                "collection": video.collection_slug,
                "url": video.url,
            }
            for video in videos
        ]
    )


@catalog_bp.get("/media/<slug>.svg")
def product_image(slug: str):
    """GET /media/:slug.svg — a Paint-canvas stand-in so the shop has pictures."""
    product = Product.query.filter_by(slug=slug).first()
    if product is None:
        return jsonify(message="Product not found"), 404
    svg = render_product_svg(product)
    return Response(svg, mimetype="image/svg+xml")


def render_product_svg(product: Product) -> str:
    name = escape(product.name)
    category = escape(product.category.replace("-", " "))
    amount = as_money(product.price)
    price = f"${amount:.0f}" if amount == int(amount) else f"${amount:.2f}"
    color = escape((product.colors or ["ink"])[0])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="800" viewBox="0 0 640 800">
  <rect width="640" height="800" fill="#ffffff"/>
  <rect x="28" y="28" width="584" height="744" fill="none" stroke="#000000" stroke-width="3" stroke-dasharray="8 6"/>
  <text x="320" y="360" text-anchor="middle" font-family="Tahoma, sans-serif" font-size="36" fill="#000000">{name}</text>
  <text x="320" y="410" text-anchor="middle" font-family="Tahoma, sans-serif" font-size="22" fill="#000000">{category} · {color}</text>
  <text x="320" y="470" text-anchor="middle" font-family="Tahoma, sans-serif" font-size="28" fill="#000000">{price}</text>
  <text x="320" y="720" text-anchor="middle" font-family="Tahoma, sans-serif" font-size="16" fill="#000000">OIMADIS</text>
</svg>
"""
