"""
Database models for HairShellizer.

Design notes:
- One order belongs to exactly one seller (per spec: no multi-vendor split
  orders). In this v1 there is a single seller (the HairShellizer admin
  account), but the schema still carries seller_id so it can grow later.
- Money is stored as Numeric(10, 2) to avoid floating point rounding.
- All "enum-like" fields (roles, statuses) are plain strings validated in
  code rather than native Postgres ENUM types, so they are trivial to
  extend later without a migration that alters an enum type.
"""
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


# ---------------------------------------------------------------------------
# Users & seller profile
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))
    role = db.Column(db.String(20), nullable=False, default="customer")  # customer | admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cart_items = db.relationship("CartItem", backref="user", lazy=True, cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="customer", lazy=True, foreign_keys="Order.customer_id")
    seller_profile = db.relationship("SellerProfile", backref="user", uselist=False)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class SellerProfile(db.Model):
    __tablename__ = "seller_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    store_name = db.Column(db.String(150), default="HairShellizer")
    description = db.Column(db.Text, default=(
        "\"HairShellizer\" derives its name from its two raw organic materials: "
        "natural hair and eggshells. By converting these biodegradable wastes "
        "into fertilizer rich in essential nutrients, HairShellizer provides a "
        "dual benefit: promoting plant vitality and reducing domestic waste."
    ))
    address = db.Column(db.String(255), default="Brgy. Poblacion 3, Avelino Street, Tanauan City, Batangas")
    phone = db.Column(db.String(30), default="+63 991 712 5341")
    email = db.Column(db.String(150), default="hairshellizer@gmail.com")
    facebook_url = db.Column(db.String(255), default="https://www.facebook.com/share/1c6k1wjVB4/?mibextid=wwXIfr")
    qr_image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship("Product", backref="category", lazy=True)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=75.00)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(500))  # ImageKit URL, or static path for seed data
    is_featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def in_stock(self):
        return self.stock > 0

    def formatted_price(self):
        return f"\u20b1{self.price:,.2f}"


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = db.relationship("Product")

    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),)

    def subtotal(self):
        return self.product.price * self.quantity


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

ORDER_STATUSES = ["PENDING", "PROCESSING", "READY_FOR_PICKUP", "SHIPPED",
                   "DELIVERED", "COMPLETED", "CANCELLED"]
PAYMENT_METHODS = ["COD", "COP", "ONLINE"]
PAYMENT_STATUSES = ["UNPAID", "PENDING_VERIFICATION", "PAID", "REJECTED", "NOT_REQUIRED"]


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default="PENDING")
    payment_method = db.Column(db.String(10), nullable=False)  # COD | COP | ONLINE
    fulfillment_type = db.Column(db.String(10), nullable=False, default="delivery")  # delivery | pickup
    shipping_address = db.Column(db.String(255))
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(150))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")
    payment = db.relationship("Payment", backref="order", uselist=False, cascade="all, delete-orphan")
    conversation = db.relationship("Conversation", backref="order", uselist=False)

    def formatted_total(self):
        return f"\u20b1{self.total_amount:,.2f}"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    product_name_snapshot = db.Column(db.String(150), nullable=False)
    price_snapshot = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    payment_method = db.Column(db.String(10), nullable=False)  # COD | COP | ONLINE
    payment_status = db.Column(db.String(25), nullable=False, default="UNPAID")
    reference_number = db.Column(db.String(100))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.DateTime)
    verified_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    verified_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)
    conversation_type = db.Column(db.String(10), nullable=False)  # INQUIRY | ORDER
    status = db.Column(db.String(10), nullable=False, default="ACTIVE")  # ACTIVE | EXPIRED | CLOSED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("User", foreign_keys=[customer_id])
    seller = db.relationship("User", foreign_keys=[seller_id])
    messages = db.relationship("Message", backref="conversation", lazy=True,
                                cascade="all, delete-orphan", order_by="Message.created_at")

    def refresh_expiration(self):
        """Soft-expire an INQUIRY conversation if its time is up.
        Called whenever a conversation is opened or listed, since the app
        may run on a serverless platform with no background worker."""
        if (self.conversation_type == "INQUIRY" and self.status == "ACTIVE"
                and self.expires_at and datetime.utcnow() > self.expires_at):
            self.status = "EXPIRED"
            db.session.commit()
        return self.status

    @staticmethod
    def new_inquiry(customer_id, seller_id, hours=24):
        convo = Conversation(
            customer_id=customer_id,
            seller_id=seller_id,
            conversation_type="INQUIRY",
            status="ACTIVE",
            expires_at=datetime.utcnow() + timedelta(hours=hours),
        )
        db.session.add(convo)
        db.session.commit()
        return convo

    @staticmethod
    def new_order_conversation(customer_id, seller_id, order_id):
        convo = Conversation(
            customer_id=customer_id,
            seller_id=seller_id,
            order_id=order_id,
            conversation_type="ORDER",
            status="ACTIVE",
            expires_at=None,
        )
        db.session.add(convo)
        db.session.commit()
        return convo


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User")
