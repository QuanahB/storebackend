"""Add columns that create_all() will not add to a database that already exists."""

from sqlalchemy import text

from extensions import db


def ensure_sqlite_columns() -> None:
    """Add columns introduced after the first deploy. create_all() leaves old tables as-is."""
    _ensure_order_stripe_columns()
    _ensure_product_image_column()
    _ensure_collection_image_column()


def _ensure_order_stripe_columns() -> None:
    uri = db.engine.url.drivername
    if not uri.startswith("sqlite"):
        return

    rows = db.session.execute(text("PRAGMA table_info(orders)")).all()
    if not rows:
        return
    names = {row[1] for row in rows}
    statements = []
    if "stripe_checkout_session_id" not in names:
        statements.append(
            "ALTER TABLE orders ADD COLUMN stripe_checkout_session_id VARCHAR(255)"
        )
    if "stripe_payment_intent_id" not in names:
        statements.append(
            "ALTER TABLE orders ADD COLUMN stripe_payment_intent_id VARCHAR(255)"
        )
    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


def _ensure_product_image_column() -> None:
    uri = db.engine.url.drivername
    if uri.startswith("sqlite"):
        rows = db.session.execute(text("PRAGMA table_info(products)")).all()
        if not rows or any(row[1] == "image_url" for row in rows):
            return
        db.session.execute(text("ALTER TABLE products ADD COLUMN image_url VARCHAR(2000)"))
        db.session.commit()
        return

    if uri.startswith("postgresql"):
        db.session.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR(2000)")
        )
        db.session.commit()


def _ensure_collection_image_column() -> None:
    uri = db.engine.url.drivername
    if uri.startswith("sqlite"):
        rows = db.session.execute(text("PRAGMA table_info(collections)")).all()
        if not rows or any(row[1] == "image_url" for row in rows):
            return
        db.session.execute(text("ALTER TABLE collections ADD COLUMN image_url VARCHAR(2000)"))
        db.session.commit()
        return

    if uri.startswith("postgresql"):
        db.session.execute(
            text("ALTER TABLE collections ADD COLUMN IF NOT EXISTS image_url VARCHAR(2000)")
        )
        db.session.commit()
