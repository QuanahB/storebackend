"""API contract tests for the MockMSPaint store backend."""

import pytest
import stripe

from app import create_app

PROJECT_KEYS = {"id", "name", "owner", "status", "updatedAt", "progress"}
METRIC_KEYS = {"id", "label", "value", "hint"}
ACTIVITY_KEYS = {"id", "title", "detail", "timestamp"}
SHIPPING = {
    "email": "Buyer@Example.com",
    "shipping_name": "Jordan Lee",
    "shipping_address": "12 Canvas St",
    "shipping_city": "Portland",
    "shipping_postal_code": "97201",
}


@pytest.fixture
def app(tmp_path):
    database = tmp_path / "store.db"
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database}",
            "SECRET_KEY": "test-secret",
            "STRIPE_SECRET_KEY": "sk_test_placeholder",
            "STRIPE_WEBHOOK_SECRET": "whsec_test",
        }
    )


class FakeStripeSession:
    def __init__(self, session_id, metadata, client_reference_id):
        self.id = session_id
        self.url = f"https://checkout.stripe.com/c/pay/{session_id}"
        self.payment_status = "unpaid"
        self.payment_intent = None
        self.metadata = metadata
        self.client_reference_id = client_reference_id


@pytest.fixture(autouse=True)
def stripe_checkout(monkeypatch):
    """Keep checkout tests off the real Stripe network."""
    sessions = {}
    counter = {"n": 0}

    def create(**kwargs):
        counter["n"] += 1
        session = FakeStripeSession(
            f"cs_test_{counter['n']}",
            kwargs.get("metadata") or {},
            kwargs.get("client_reference_id"),
        )
        sessions[session.id] = session
        sessions["last"] = session
        sessions["last_kwargs"] = kwargs
        return session

    def retrieve(session_id):
        session = sessions.get(session_id)
        if session is None:
            raise stripe.InvalidRequestError("missing", "session_id")
        return session

    monkeypatch.setattr("stripe.checkout.Session.create", create)
    monkeypatch.setattr("stripe.checkout.Session.retrieve", retrieve)
    return sessions


@pytest.fixture
def client(app):
    return app.test_client()


def test_health_and_index(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json()["database"] == "connected"

    index = client.get("/")
    assert index.status_code == 200
    assert index.get_json()["frontend"] == "MockMSPaint"


def test_catalog_matches_paint_toolbox(client):
    products = client.get("/products").get_json()
    assert len(products) == 10
    categories = {product["category"] for product in products}
    assert categories == {
        "tees",
        "shorts",
        "long-sleeve",
        "pants",
        "hoodies",
        "underwear",
        "sweaters",
        "hats",
    }

    tees = client.get("/products?category=tees").get_json()
    assert len(tees) == 2

    found = client.get("/products?search=wool").get_json()
    assert [product["slug"] for product in found] == ["wool-studio-sweater"]

    sweater = client.get("/products/slug/wool-studio-sweater")
    assert sweater.status_code == 200
    assert sweater.get_json()["stock"] == 2
    assert sweater.get_json()["image_url"].endswith(".svg")

    missing = client.get("/products/9999")
    assert missing.status_code == 404
    assert "message" in missing.get_json()


def test_collections_and_videos(client):
    collections = client.get("/collections").get_json()
    assert [collection["slug"] for collection in collections] == [
        "scribble-drop",
        "studio-basics",
        "night-shift",
    ]

    drop = client.get("/collections/scribble-drop").get_json()
    assert drop["product_count"] == 3
    assert len(drop["products"]) == 3

    videos = client.get("/videos").get_json()
    assert len(videos) == 3
    assert all(video["url"] is None for video in videos)

    image = client.get("/media/painters-pants.svg")
    assert image.status_code == 200
    assert image.mimetype.startswith("image/svg")
    assert b"Painter" in image.data
    assert b"OIMADIS" in image.data


def test_dashboard_shapes_match_frontend_types(client):
    projects = client.get("/projects").get_json()
    assert len(projects) == 3
    for project in projects:
        assert set(project) == PROJECT_KEYS
        assert project["status"] in {"on_track", "at_risk", "done"}
        assert isinstance(project["progress"], int)
        assert len(project["updatedAt"]) == 10

    by_id = {project["id"]: project for project in projects}
    assert by_id["col_night_shift"]["status"] == "at_risk"
    assert by_id["col_scribble_drop"]["status"] == "on_track"
    assert by_id["col_night_shift"]["owner"] == "OIMADIS studio"

    metrics = client.get("/metrics").get_json()
    assert len(metrics) == 4
    for metric in metrics:
        assert set(metric) == METRIC_KEYS
        assert isinstance(metric["value"], str)
    assert metrics[0]["value"] == "109"
    assert metrics[3]["value"] == "Low"

    activity = client.get("/activity").get_json()
    assert activity[0]["title"] == "Closet stocked"
    for item in activity:
        assert set(item) == ACTIVITY_KEYS


def test_cart_checkout_reserves_stock_and_hides_the_order(client, app, stripe_checkout):
    tee = client.get("/products/slug/scribble-pocket-tee").get_json()
    added = client.post(
        "/cart/items",
        json={"product_id": tee["id"], "size": "M", "quantity": 2},
    )
    assert added.status_code == 201
    cart = added.get_json()
    assert cart["item_count"] == 2
    assert cart["subtotal"] == 96.0
    assert cart["shipping"] == 8.0
    assert cart["total"] == 104.0

    line_id = cart["items"][0]["id"]
    updated = client.patch(f"/cart/items/{line_id}", json={"quantity": 1})
    assert updated.status_code == 200
    assert updated.get_json()["total"] == 56.0

    denied = client.post("/checkout", json={"email": "buyer@example.com"})
    assert denied.status_code == 400

    placed = client.post("/checkout", json=SHIPPING)
    assert placed.status_code == 201
    payload = placed.get_json()
    order = payload["order"]
    assert payload["checkout_url"].startswith("https://checkout.stripe.com/")
    assert order["status"] == "pending"
    assert order["email"] == "buyer@example.com"
    assert order["total"] == 56.0
    assert order["items"][0]["size"] == "M"

    line_names = [
        item["price_data"]["product_data"]["name"]
        for item in stripe_checkout["last_kwargs"]["line_items"]
    ]
    assert "Scribble Pocket Tee (M)" in line_names
    assert "Shipping" in line_names
    assert stripe_checkout["last_kwargs"]["customer_email"] == "buyer@example.com"

    assert client.get("/cart").get_json()["item_count"] == 0
    assert client.get(f"/orders/{order['id']}").status_code == 200
    assert client.get("/orders").get_json()[0]["id"] == order["id"]

    stranger = app.test_client()
    assert stranger.get(f"/orders/{order['id']}").status_code == 404

    assert client.get(f"/products/{tee['id']}").get_json()["stock"] == tee["stock"] - 1
    assert client.post("/checkout", json=SHIPPING).status_code == 400

    activity = client.get("/activity").get_json()
    assert any(item["title"] == f"Order #{order['id']} awaiting payment" for item in activity)
    assert client.get("/metrics").get_json()[1]["value"] == "1"
    assert client.get("/metrics").get_json()[1]["hint"] == "Awaiting Stripe payment"

    session_id = stripe_checkout["last"].id
    waiting = client.get(f"/checkout/confirm?session_id={session_id}")
    assert waiting.get_json()["status"] == "pending"

    stripe_checkout["last"].payment_status = "paid"
    stripe_checkout["last"].payment_intent = "pi_test_123"
    paid = client.get(f"/checkout/confirm?session_id={session_id}")
    assert paid.status_code == 200
    assert paid.get_json()["status"] == "paid"
    assert client.get(f"/products/{tee['id']}").get_json()["stock"] == tee["stock"] - 1

    paid_again = client.get(f"/checkout/confirm?session_id={session_id}")
    assert paid_again.get_json()["status"] == "paid"


def test_stock_and_size_limits(client):
    over = client.post(
        "/cart/items",
        json={"slug": "wool-studio-sweater", "quantity": 5},
    )
    assert over.status_code == 400

    bad_size = client.post(
        "/cart/items",
        json={"slug": "floppy-paint-cap", "size": "M"},
    )
    assert bad_size.status_code == 400

    cap = client.post("/cart/items", json={"slug": "floppy-paint-cap"})
    assert cap.status_code == 201
    body = cap.get_json()
    assert body["items"][0]["size"] == "OS"
    assert body["shipping"] == 8.0

    removed = client.delete(f"/cart/items/{body['items'][0]['id']}")
    assert removed.get_json()["item_count"] == 0


def test_free_shipping_over_threshold(client):
    added = client.post("/cart/items", json={"slug": "wool-studio-sweater", "size": "M", "quantity": 1})
    assert added.status_code == 201
    cart = added.get_json()
    assert cart["subtotal"] == 120.0
    assert cart["shipping"] == 0.0
    assert cart["total"] == 120.0


def test_accounts(client, app):
    short = client.post(
        "/auth/sign-up",
        json={"name": "Alex Rivera", "email": "alex@northline.dev", "password": "short"},
    )
    assert short.status_code == 400

    created = client.post(
        "/auth/sign-up",
        json={"name": "Alex Rivera", "email": "Alex@Northline.dev", "password": "password1"},
    )
    assert created.status_code == 201
    user = created.get_json()["user"]
    assert user["initials"] == "AR"
    assert user["email"] == "alex@northline.dev"
    assert client.get("/auth/me").get_json()["user"]["name"] == "Alex Rivera"

    duplicate = client.post(
        "/auth/sign-up",
        json={"name": "Alex Rivera", "email": "alex@northline.dev", "password": "password1"},
    )
    assert duplicate.status_code == 409

    tee = client.get("/products/slug/margin-note-tee").get_json()
    client.post("/cart/items", json={"product_id": tee["id"], "quantity": 1})
    placed = client.post("/checkout", json=SHIPPING)
    order_id = placed.get_json()["order"]["id"]

    client.post("/auth/sign-out")
    assert client.get("/auth/me").status_code == 401

    other = app.test_client()
    rejected = other.post(
        "/auth/sign-in",
        json={"email": "alex@northline.dev", "password": "nope"},
    )
    assert rejected.status_code == 401
    signed_in = other.post(
        "/auth/sign-in",
        json={"email": "alex@northline.dev", "password": "password1"},
    )
    assert signed_in.status_code == 200
    assert other.get(f"/orders/{order_id}").status_code == 200


def test_checkout_requires_a_stripe_key(client, app):
    app.config["STRIPE_SECRET_KEY"] = ""
    tee = client.get("/products/slug/scribble-pocket-tee").get_json()
    client.post("/cart/items", json={"product_id": tee["id"], "quantity": 1})
    response = client.post("/checkout", json=SHIPPING)
    assert response.status_code == 503
    assert "STRIPE_SECRET_KEY" in response.get_json()["message"]
    assert client.get(f"/products/{tee['id']}").get_json()["stock"] == tee["stock"]


def test_stripe_failure_keeps_the_cart(client, monkeypatch):
    def explode(**kwargs):
        raise stripe.StripeError("Stripe is down")

    monkeypatch.setattr("stripe.checkout.Session.create", explode)
    tee = client.get("/products/slug/scribble-pocket-tee").get_json()
    client.post("/cart/items", json={"product_id": tee["id"], "quantity": 1})
    response = client.post("/checkout", json=SHIPPING)
    assert response.status_code == 502
    assert client.get("/cart").get_json()["item_count"] == 1
    assert client.get(f"/products/{tee['id']}").get_json()["stock"] == tee["stock"]


def test_webhook_marks_order_paid_and_expiry_returns_stock(client, stripe_checkout, monkeypatch):
    tee = client.get("/products/slug/scribble-pocket-tee").get_json()
    client.post("/cart/items", json={"product_id": tee["id"], "quantity": 1})
    placed = client.post("/checkout", json=SHIPPING)
    order_id = placed.get_json()["order"]["id"]
    session_id = stripe_checkout["last"].id

    def construct_event(payload, sig, secret):
        return {"type": events["type"], "data": {"object": {"id": session_id}}}

    events = {"type": "checkout.session.completed"}
    monkeypatch.setattr("stripe.Webhook.construct_event", construct_event)

    unpaid = client.post("/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "t=1,v1=test"})
    assert unpaid.status_code == 200
    assert client.get(f"/orders/{order_id}").get_json()["status"] == "pending"

    stripe_checkout["last"].payment_status = "paid"
    stripe_checkout["last"].payment_intent = "pi_test_webhook"
    paid = client.post("/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "t=1,v1=test"})
    assert paid.status_code == 200
    assert client.get(f"/orders/{order_id}").get_json()["status"] == "paid"
    assert client.get(f"/products/{tee['id']}").get_json()["stock"] == tee["stock"] - 1

    events["type"] = "checkout.session.expired"
    expired = client.post("/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "t=1,v1=test"})
    assert expired.status_code == 200
    assert client.get(f"/orders/{order_id}").get_json()["status"] == "paid"
    assert client.get(f"/products/{tee['id']}").get_json()["stock"] == tee["stock"] - 1


def test_expired_checkout_returns_stock(client, stripe_checkout, monkeypatch):
    tee = client.get("/products/slug/margin-note-tee").get_json()
    client.post("/cart/items", json={"product_id": tee["id"], "quantity": 2})
    placed = client.post("/checkout", json=SHIPPING)
    order_id = placed.get_json()["order"]["id"]
    session_id = stripe_checkout["last"].id

    def construct_event(payload, sig, secret):
        return {"type": "checkout.session.expired", "data": {"object": {"id": session_id}}}

    monkeypatch.setattr("stripe.Webhook.construct_event", construct_event)
    response = client.post("/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "t=1,v1=test"})
    assert response.status_code == 200
    assert client.get(f"/orders/{order_id}").get_json()["status"] == "cancelled"
    assert client.get(f"/products/{tee['id']}").get_json()["stock"] == tee["stock"]


def test_webhook_rejects_a_bad_signature(client, monkeypatch):
    def reject(payload, sig, secret):
        raise stripe.SignatureVerificationError("bad signature", sig)

    monkeypatch.setattr("stripe.Webhook.construct_event", reject)
    response = client.post("/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "nope"})
    assert response.status_code == 400


def test_admin_can_add_edit_and_remove_a_piece(client, app):
    app.config["ADMIN_PASSWORD"] = "studio-secret"
    created_body = {
        "name": "Ink Test Tee",
        "description": "A staff-added tee.",
        "price": 40,
        "category": "tees",
        "collection": "scribble-drop",
        "sizes": ["M", "L"],
        "colors": ["ink"],
        "stock": 5,
    }

    locked = client.post("/admin/products", json=created_body)
    assert locked.status_code == 401
    assert client.get("/admin/session").get_json()["admin"] is False

    rejected = client.post("/admin/login", json={"password": "nope"})
    assert rejected.status_code == 401

    signed_in = client.post("/admin/login", json={"password": "studio-secret"})
    assert signed_in.status_code == 200
    assert signed_in.get_json()["admin"] is True

    created = client.post("/admin/products", json=created_body)
    assert created.status_code == 201
    product = created.get_json()
    assert product["slug"] == "ink-test-tee"
    assert product["price"] == 40.0
    assert product["collection"] == "scribble-drop"

    patched = client.patch(
        f"/admin/products/{product['id']}",
        json={"price": 42, "stock": 0, "name": "Ink Test Tee Revised"},
    )
    assert patched.status_code == 200
    assert patched.get_json()["price"] == 42.0
    assert patched.get_json()["stock"] == 0
    assert patched.get_json()["name"] == "Ink Test Tee Revised"

    listed = [item["slug"] for item in client.get("/products").get_json()]
    assert "ink-test-tee" in listed

    removed = client.delete(f"/admin/products/{product['id']}")
    assert removed.status_code == 200
    listed = [item["slug"] for item in client.get("/products").get_json()]
    assert "ink-test-tee" not in listed

    client.post("/admin/logout")
    assert client.get("/admin/session").get_json()["admin"] is False


def test_admin_cannot_delete_an_ordered_piece(client, app):
    app.config["ADMIN_PASSWORD"] = "studio-secret"
    client.post("/admin/login", json={"password": "studio-secret"})
    tee = client.get("/products/slug/scribble-pocket-tee").get_json()
    client.post("/cart/items", json={"product_id": tee["id"], "quantity": 1})
    placed = client.post("/checkout", json=SHIPPING)
    assert placed.status_code == 201

    denied = client.delete(f"/admin/products/{tee['id']}")
    assert denied.status_code == 409
    assert client.get(f"/products/{tee['id']}").status_code == 200


def test_admin_login_requires_a_configured_password(client, app):
    app.config["ADMIN_PASSWORD"] = ""
    response = client.post("/admin/login", json={"password": "studio-secret"})
    assert response.status_code == 503


def test_contact_lands_in_the_activity_feed(client):
    missing = client.post("/contact", json={"name": "Jordan", "email": "not-an-email", "message": "Hi"})
    assert missing.status_code == 400

    sent = client.post(
        "/contact",
        json={"name": "Jordan Lee", "email": "jordan@example.com", "message": "Need a large hoodie."},
    )
    assert sent.status_code == 201

    activity = client.get("/activity").get_json()
    assert activity[0]["title"] == "Note from Jordan Lee"
    assert client.get("/metrics").get_json()[2]["value"] == "1"


def test_browser_origin_is_allowed(client):
    response = client.get("/products", headers={"Origin": "http://localhost:4321"})
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:4321"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"

    blocked = client.get("/products", headers={"Origin": "http://evil.example"})
    assert blocked.headers.get("Access-Control-Allow-Origin") != "http://evil.example"

    preflight = client.options(
        "/cart/items",
        headers={
            "Origin": "http://localhost:4321",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert preflight.status_code in {200, 204}
    assert "POST" in preflight.headers.get("Access-Control-Allow-Methods", "")
