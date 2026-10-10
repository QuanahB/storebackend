"""
OIMADIS store API for the MockMSPaint frontend.

The Next app loads dashboard data when NEXT_PUBLIC_API_URL is set:

    GET ${NEXT_PUBLIC_API_URL}/projects
    GET ${NEXT_PUBLIC_API_URL}/metrics
    GET ${NEXT_PUBLIC_API_URL}/activity

Shop, collections, videos, cart, checkout, auth, and contact live on this
same origin so the placeholder pages can call them next.

Run (this is the port in MockMSPaint .env.example):

    flask --app app run --port 4000
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

load_dotenv(Path(__file__).resolve().parent / ".env")

from config import Config
from extensions import db
from schema import ensure_sqlite_columns
from seed import seed_if_empty


def database_uri(instance_path: str) -> str:
    """SQLite in instance/ unless DATABASE_URL is set."""
    raw = (os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI") or "").strip()
    if raw:
        if raw.startswith("postgres://"):
            raw = "postgresql+psycopg2://" + raw[len("postgres://") :]
        elif raw.startswith("postgresql://"):
            raw = "postgresql+psycopg2://" + raw[len("postgresql://") :]
        return raw

    os.makedirs(instance_path, exist_ok=True)
    return "sqlite:///" + os.path.join(instance_path, "store.db")


def create_app(config_overrides: dict | None = None) -> Flask:
    """Build the Flask app, create tables, and seed the closet once."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = database_uri(app.instance_path)

    db.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)

    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.board import board_bp
    from routes.cart import cart_bp
    from routes.catalog import catalog_bp
    from routes.checkout import checkout_bp
    from routes.contact import contact_bp
    from routes.dashboard import dashboard_bp

    for blueprint in (
        catalog_bp,
        cart_bp,
        checkout_bp,
        auth_bp,
        contact_bp,
        dashboard_bp,
        admin_bp,
        board_bp,
    ):
        app.register_blueprint(blueprint)

    @app.get("/")
    def index():
        return jsonify(
            name="OIMADIS store API",
            frontend="MockMSPaint",
            frontend_origin=app.config["FRONTEND_ORIGIN"],
            connect="Set NEXT_PUBLIC_API_URL to this origin",
        )

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            database = "connected"
            status = "ok"
            code = 200
        except Exception:
            database = "disconnected"
            status = "error"
            code = 503
        return jsonify(status=status, database=database), code

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        return jsonify(message=error.description or error.name), error.code

    with app.app_context():
        import models  # noqa: F401

        db.create_all()
        ensure_sqlite_columns()
        seed_if_empty()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "4000")))
