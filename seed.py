"""Seed the handmade OIMADIS closet when the database is empty."""

from extensions import db
from models import Collection, Product, Video

# Toolbox labels in MockMSPaint map onto these category slugs.
CATEGORIES = [
    {"slug": "tees", "label": "Tees"},
    {"slug": "shorts", "label": "Shorts"},
    {"slug": "long-sleeve", "label": "Long sleeve"},
    {"slug": "pants", "label": "Pants"},
    {"slug": "hoodies", "label": "Hoodie"},
    {"slug": "underwear", "label": "Underwear"},
    {"slug": "sweaters", "label": "Sweater"},
    {"slug": "hats", "label": "Hat"},
]

COLLECTIONS = [
    {
        "slug": "scribble-drop",
        "name": "Scribble Drop",
        "season": "Fall 2026",
        "description": (
            "Hand-drawn graphics inked in the studio, then printed small-batch "
            "on heavyweight cotton."
        ),
    },
    {
        "slug": "studio-basics",
        "name": "Studio Basics",
        "season": "Always",
        "description": (
            "Blanks cut for painting in: shorts, pants, a cap, and underwear "
            "that can take a splatter."
        ),
    },
    {
        "slug": "night-shift",
        "name": "Night Shift",
        "season": "Fall 2026",
        "description": "Darker layers for late studio hours. Hoodie and wool sweater.",
    },
]

# stock is current units. initial_stock matches it until a checkout sells through.
PRODUCTS = [
    {
        "slug": "scribble-pocket-tee",
        "name": "Scribble Pocket Tee",
        "description": "Black tee with a hand-inked chest pocket scribble. Heavyweight cotton.",
        "price": "48.00",
        "category": "tees",
        "collection": "scribble-drop",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["ink"],
        "stock": 18,
    },
    {
        "slug": "margin-note-tee",
        "name": "Margin Note Tee",
        "description": "Off-white tee with a tiny note along the hem, the way a sketchbook margin looks.",
        "price": "46.00",
        "category": "tees",
        "collection": "scribble-drop",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["paper"],
        "stock": 14,
    },
    {
        "slug": "canvas-walk-shorts",
        "name": "Canvas Walk Shorts",
        "description": "Mid-thigh canvas shorts with a paint-brush loop at the side seam.",
        "price": "54.00",
        "category": "shorts",
        "collection": "studio-basics",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["canvas"],
        "stock": 10,
    },
    {
        "slug": "cutoff-studio-shorts",
        "name": "Cutoff Studio Shorts",
        "description": "Washed cutoffs, raw hem, one back pocket big enough for a pencil.",
        "price": "44.00",
        "category": "shorts",
        "collection": "studio-basics",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["indigo"],
        "stock": 8,
    },
    {
        "slug": "sketch-long-sleeve",
        "name": "Sketch Long Sleeve",
        "description": "Long sleeve with a pencil-line drawing running down the forearm.",
        "price": "62.00",
        "category": "long-sleeve",
        "collection": "scribble-drop",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["ink"],
        "stock": 9,
    },
    {
        "slug": "painters-pants",
        "name": "Painter's Pants",
        "description": "Straight canvas pants with a hammer loop and double-knee patch.",
        "price": "88.00",
        "category": "pants",
        "collection": "studio-basics",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["canvas"],
        "stock": 6,
    },
    {
        "slug": "night-shift-hoodie",
        "name": "Night Shift Hoodie",
        "description": "Heavy black hoodie, silver eyelet at the hood, kangaroo pocket.",
        "price": "98.00",
        "category": "hoodies",
        "collection": "night-shift",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["black"],
        "stock": 7,
    },
    {
        "slug": "splatter-boxer-briefs",
        "name": "Splatter Boxer Briefs",
        "description": "Soft boxer briefs with a small paint-splatter print at the waistband.",
        "price": "28.00",
        "category": "underwear",
        "collection": "studio-basics",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["ink"],
        "stock": 20,
    },
    {
        "slug": "wool-studio-sweater",
        "name": "Wool Studio Sweater",
        "description": "Charcoal wool crew. Only a few left from this knit run.",
        "price": "120.00",
        "category": "sweaters",
        "collection": "night-shift",
        "sizes": ["S", "M", "L"],
        "colors": ["charcoal"],
        "stock": 2,
    },
    {
        "slug": "floppy-paint-cap",
        "name": "Floppy Paint Cap",
        "description": "Unstructured cap with a short brim. One size, cotton twill.",
        "price": "32.00",
        "category": "hats",
        "collection": "studio-basics",
        "sizes": ["OS"],
        "colors": ["canvas"],
        "stock": 15,
    },
]

VIDEOS = [
    {
        "slug": "drawing-the-scribble-pocket",
        "title": "Drawing the scribble pocket",
        "description": "Process clip: pencil to ink on the Scribble Pocket Tee graphic.",
        "kind": "process",
        "collection_slug": "scribble-drop",
    },
    {
        "slug": "studio-basics-lookbook",
        "title": "Studio basics, worn",
        "description": "Lookbook of the canvas shorts, painter's pants, and floppy cap in the studio.",
        "kind": "lookbook",
        "collection_slug": "studio-basics",
    },
    {
        "slug": "cutting-the-night-shift-hoodie",
        "title": "Cutting the night shift hoodie",
        "description": "Pattern cutting and the silver hood eyelet on the Night Shift Hoodie.",
        "kind": "process",
        "collection_slug": "night-shift",
    },
]


def seed_if_empty() -> None:
    """Insert the catalog once. Later checkouts only change stock and orders."""
    if Product.query.first() is not None:
        return

    collections = {}
    for row in COLLECTIONS:
        collection = Collection(
            slug=row["slug"],
            name=row["name"],
            description=row["description"],
            season=row["season"],
        )
        db.session.add(collection)
        collections[row["slug"]] = collection
    db.session.flush()

    for row in PRODUCTS:
        db.session.add(
            Product(
                slug=row["slug"],
                name=row["name"],
                description=row["description"],
                price=row["price"],
                category=row["category"],
                collection_id=collections[row["collection"]].id,
                sizes=row["sizes"],
                colors=row["colors"],
                stock=row["stock"],
                initial_stock=row["stock"],
            )
        )

    for row in VIDEOS:
        db.session.add(
            Video(
                slug=row["slug"],
                title=row["title"],
                description=row["description"],
                kind=row["kind"],
                collection_slug=row["collection_slug"],
                url=None,
            )
        )

    db.session.commit()
