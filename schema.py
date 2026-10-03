"""Add columns that create_all() will not add to a database created before Stripe."""

from sqlalchemy import text

from extensions import db


def ensure_sqlite_columns() -> None:
    """SQLite create_all leaves an existing orders table as-is. Add the Stripe ids."""
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
