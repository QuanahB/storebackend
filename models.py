"""SQL tables for the OIMADIS closet, carts, orders, accounts, and notes."""

from datetime import datetime, timezone

from extensions import db


def utcnow():
    """Timezone-aware timestamp for created/updated columns."""
    return datetime.now(timezone.utc)


class Collection(db.Model):
    """A clothing drop, shown on the collections canvas."""

    __tablename__ = "collections"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    season = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    products = db.relationship("Product", back_populates="collection")


class Product(db.Model):
    """One handmade piece. Category slugs match the Paint toolbox."""

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    # tees, shorts, long-sleeve, pants, hoodies, underwear, sweaters, hats
    category = db.Column(db.String(40), nullable=False)
    collection_id = db.Column(db.Integer, db.ForeignKey("collections.id"), nullable=False)
    sizes = db.Column(db.JSON, nullable=False)
    colors = db.Column(db.JSON, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    initial_stock = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    collection = db.relationship("Collection", back_populates="products")
    cart_items = db.relationship("CartItem", back_populates="product")


class User(db.Model):
    """Shopper account created from the sign-up form."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    orders = db.relationship("Order", back_populates="user")


class Cart(db.Model):
    """Anonymous or signed-in cart. The session cookie stores only cart_id."""

    __tablename__ = "carts"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    items = db.relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
        order_by="CartItem.id",
    )


class CartItem(db.Model):
    """A size-specific line in a cart."""

    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    size = db.Column(db.String(16), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    cart = db.relationship("Cart", back_populates="items")
    product = db.relationship("Product", back_populates="cart_items")


class Order(db.Model):
    """A placed order. Stock is reserved when the row is created."""

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="placed")
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    shipping = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    email = db.Column(db.String(200), nullable=False)
    shipping_name = db.Column(db.String(200), nullable=False)
    shipping_address = db.Column(db.String(300), nullable=False)
    shipping_city = db.Column(db.String(120), nullable=False)
    shipping_postal_code = db.Column(db.String(32), nullable=False)
    shipping_country = db.Column(db.String(80), nullable=False, default="US")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="orders")
    items = db.relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
    )


class OrderItem(db.Model):
    """Snapshot of a cart line at checkout, so later price edits do not rewrite history."""

    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False)
    size = db.Column(db.String(16), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")


class ContactMessage(db.Model):
    """A note from the contact form."""

    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class Video(db.Model):
    """Lookbook or process clip listed on the videos canvas."""

    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    kind = db.Column(db.String(40), nullable=False)  # process | lookbook
    collection_slug = db.Column(db.String(80), nullable=True)
    url = db.Column(db.String(500), nullable=True)
