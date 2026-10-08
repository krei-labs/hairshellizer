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
from decimal import Decimal
from typing import Any, Optional

from flask import current_app
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class BaseModel(db.Model):
    __abstract__ = True

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

# ---------------------------------------------------------------------------
# Chat status vocabulary
# ---------------------------------------------------------------------------
# Statuses an admin can pick in /admin/chats.
CHAT_STATUSES = ["PENDING", "DELIVERED", "COMPLETE", "INACTIVE"]
# Statuses in which both sides may still send messages.
# "ACTIVE" is the old name for PENDING; rows created before the status
# rename still carry it, so it must keep working.
CHAT_OPEN_STATUSES = ("ACTIVE", "PENDING", "DELIVERED")
# Open statuses that are subject to the 24-hour inquiry expiry.
CHAT_EXPIRING_STATUSES = ("ACTIVE", "PENDING")


# ---------------------------------------------------------------------------
# Users & seller profile
# ---------------------------------------------------------------------------

class User(BaseModel):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="customer")
    _is_active: Mapped[bool] = mapped_column("is_active", Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = value

    cart_items: Mapped[list["CartItem"]] = relationship("CartItem", backref="user", lazy=True, cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship("Order", backref="customer", lazy=True, foreign_keys="Order.customer_id")
    seller_profile: Mapped[Optional["SellerProfile"]] = relationship("SellerProfile", backref="user", uselist=False)
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self):
        return self.role in {"admin", "moderator"}

    @property
    def is_main_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class PasswordResetToken(BaseModel):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="password_reset_tokens")

    @property
    def is_valid(self):
        return self.used_at is None and datetime.utcnow() < self.expires_at


class SellerProfile(BaseModel):
    __tablename__ = "seller_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    store_name: Mapped[str] = mapped_column(String(150), default="HairShellizer")
    description: Mapped[str] = mapped_column(
        Text,
        default=(
            "\"HairShellizer\" derives its name from its two raw organic materials: "
            "natural hair and eggshells. By converting these biodegradable wastes "
            "into fertilizer rich in essential nutrients, HairShellizer provides a "
            "dual benefit: promoting plant vitality and reducing domestic waste."
        ),
    )
    address: Mapped[str] = mapped_column(String(255), default="Brgy. Poblacion 3, Avelino Street, Tanauan City, Batangas")
    phone: Mapped[str] = mapped_column(String(30), default="+63 991 712 5341")
    email: Mapped[str] = mapped_column(String(150), default="hairshellizer@gmail.com")
    facebook_url: Mapped[str] = mapped_column(String(255), default="https://www.facebook.com/share/1c6k1wjVB4/?mibextid=wwXIfr")
    qr_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qr_image_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class Category(BaseModel):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    products: Mapped[list["Product"]] = relationship("Product", backref="category", lazy=True)


class Product(BaseModel):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=75.00)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def in_stock(self):
        return self.stock > 0

    def formatted_price(self):
        return f"\u20b1{self.price:,.2f}"


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

class CartItem(BaseModel):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),)

    def subtotal(self):
        return self.product.price * self.quantity


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

ORDER_STATUSES = ["PENDING", "PROCESSING", "READY_FOR_PICKUP", "SHIPPED",
                   "DELIVERED", "COMPLETED", "CANCELLED"]
PAYMENT_METHODS = ["COD", "COP", "ONLINE"]
PAYMENT_STATUSES = ["UNPAID", "PENDING_VERIFICATION", "PAID", "REJECTED", "NOT_REQUIRED"]


class Order(BaseModel):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    payment_method: Mapped[str] = mapped_column(String(10), nullable=False)
    fulfillment_type: Mapped[str] = mapped_column(String(10), nullable=False, default="delivery")
    shipping_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["OrderItem"]] = relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")
    payment: Mapped[Optional["Payment"]] = relationship("Payment", backref="order", uselist=False, cascade="all, delete-orphan")
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation", backref="order", uselist=False)

    def formatted_total(self):
        return f"\u20b1{self.total_amount:,.2f}"


class OrderItem(BaseModel):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("products.id"), nullable=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

class Payment(BaseModel):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(10), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(25), nullable=False, default="UNPAID")
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class Conversation(BaseModel):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    conversation_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # PENDING | DELIVERED | COMPLETE | INACTIVE  (legacy rows may hold ACTIVE / EXPIRED / CLOSED)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped["User"] = relationship("User", foreign_keys=[customer_id])
    seller: Mapped["User"] = relationship("User", foreign_keys=[seller_id])
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        backref="conversation",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    @property
    def is_open(self):
        """True while messages can still be sent in this conversation."""
        return self.status in CHAT_OPEN_STATUSES

    def refresh_expiration(self):
        """Soft-expire an INQUIRY conversation if its time is up.
        Called whenever a conversation is opened, since the app may run on a
        serverless platform with no background worker."""
        if (self.conversation_type == "INQUIRY" and self.status in CHAT_EXPIRING_STATUSES
                and self.expires_at and datetime.utcnow() > self.expires_at):
            self.status = "INACTIVE"
            db.session.commit()
        return self.status

    @staticmethod
    def expire_stale_inquiries():
        """Expire every overdue inquiry with ONE query. Use this on list pages
        instead of calling refresh_expiration() on each row (which would issue
        a commit and a reload per conversation)."""
        updated = (
            Conversation.query
            .filter(
                Conversation.conversation_type == "INQUIRY",
                getattr(Conversation.status, "in_")(CHAT_EXPIRING_STATUSES),
                Conversation.expires_at.isnot(None),
                Conversation.expires_at < datetime.utcnow(),
            )
            .update({"status": "INACTIVE"}, synchronize_session=False)
        )
        if updated:
            db.session.commit()
        return updated

    @staticmethod
    def new_inquiry(customer_id, seller_id, hours=None):
        if hours is None:
            hours = current_app.config.get("INQUIRY_EXPIRATION_HOURS", 24)
        convo = Conversation(
            customer_id=customer_id,
            seller_id=seller_id,
            conversation_type="INQUIRY",
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(hours=hours),
        )
        db.session.add(convo)
        db.session.commit()
        return convo

    @staticmethod
    def new_order_conversation(customer_id, seller_id, order_id, commit=True):
        """Create the permanent chat for an order. Pass commit=False to make it
        part of the caller's transaction (checkout does this so an order can
        never be saved without its chat)."""
        convo = Conversation(
            customer_id=customer_id,
            seller_id=seller_id,
            order_id=order_id,
            conversation_type="ORDER",
            status="PENDING",
            expires_at=None,
        )
        db.session.add(convo)
        if commit:
            db.session.commit()
        return convo


class Message(BaseModel):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sender: Mapped["User"] = relationship("User")
