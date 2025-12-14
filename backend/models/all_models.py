"""
============================================================================
BeautyFlow - Database Models
============================================================================
SQLAlchemy models for BeautyFlow beauty import platform.
Contains all database tables, enums, relationships, and indexes.

Author: BeautyFlow Team
Version: 1.0.0
============================================================================
"""

# =============================================================================
# 1. IMPORTS
# =============================================================================

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum as SAEnum, JSON, UniqueConstraint, Index
import enum

# Initialize SQLAlchemy
db = SQLAlchemy()


# =============================================================================
# 2. ENUMS - 
# =============================================================================

# -----------------------------------------------------------------------------
# 2.1 User Role Enum
# -----------------------------------------------------------------------------

class RoleEnum(enum.Enum):
    """User roles in the system."""
    ADMIN = "ADMIN"
    USER = "USER"
    SUPPLIER = "SUPPLIER"


# -----------------------------------------------------------------------------
# 2.2 Product Enums
# -----------------------------------------------------------------------------

class ProductStatusEnum(enum.Enum):
    """Product lifecycle status."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ProductOriginEnum(enum.Enum):
    """How the product was created."""
    AI = "AI"
    CATALOG = "CATALOG"


class ProductVisibilityEnum(enum.Enum):
    """Product visibility level."""
    PRIVATE = "PRIVATE"
    SMARTPICK = "SMARTPICK"
    PUBLIC = "PUBLIC"


# -----------------------------------------------------------------------------
# 2.3 Order Enums
# -----------------------------------------------------------------------------

class OrderStatusEnum(enum.Enum):
    """Order lifecycle status."""
    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


# -----------------------------------------------------------------------------
# 2.4 Payment Enums
# -----------------------------------------------------------------------------

class PaymentStatusEnum(enum.Enum):
    """Payment transaction status."""
    INITIATED = "INITIATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentMethodEnum(enum.Enum):
    """Supported payment methods."""
    CARD = "CARD"
    PAYPAL = "PAYPAL"
    APPLE_PAY = "APPLE_PAY"


# -----------------------------------------------------------------------------
# 2.5 Notification Enum
# -----------------------------------------------------------------------------

class NotifyTypeEnum(enum.Enum):
    """Notification categories."""
    SYSTEM = "SYSTEM"
    ORDER = "ORDER"
    PAYMENT = "PAYMENT"
    SECURITY = "SECURITY"


# -----------------------------------------------------------------------------
# 2.6 Invoice Enum
# -----------------------------------------------------------------------------

class InvoiceTypeEnum(enum.Enum):
    """Invoice types based on shipping method."""
    SOLO = "SOLO"
    SHARED = "SHARED"


# =============================================================================
# 3. CORE TABLES - 
# =============================================================================

# -----------------------------------------------------------------------------
# 3.1 Account (Users)
# -----------------------------------------------------------------------------

class Account(db.Model):
    """
    Main users table.
    Contains: user data, cart, and cost-sharing fields.
    
    """
    __tablename__ = "accounts"

    # === Primary Fields ===
    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(30), unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(
        SAEnum(RoleEnum, name="roleenum", schema="public"),
        nullable=False,
        default=RoleEnum.USER
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # === 2FA Fields ===
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    two_factor_method = db.Column(db.String(30))

    # === Cart Data (JSON string) ===
    cart_data = db.Column(db.Text, nullable=True)

    # === Cost Sharing Fields ===
    shipping_group_id = db.Column(db.String(50), nullable=True, index=True)
    shipping_city = db.Column(db.String(50), nullable=True)
    shipping_joined_at = db.Column(db.DateTime, nullable=True)
    shipping_cart_snapshot = db.Column(db.Text, nullable=True)
    shipping_weight = db.Column(db.Numeric(10, 3), nullable=True)
    shipping_product_cost = db.Column(db.Numeric(12, 2), nullable=True)
    shipping_cost = db.Column(db.Numeric(12, 2), nullable=True)
    shipping_is_creator = db.Column(db.Boolean, default=False)
    shipping_expires_at = db.Column(db.DateTime, nullable=True)
    shipping_status = db.Column(db.String(20), nullable=True)
    shipping_extended_count = db.Column(db.Integer, default=0)

    # === Relationships ===
    orders = db.relationship("Order", back_populates="user", lazy="dynamic")
    notifications = db.relationship("Notification", back_populates="account", lazy="dynamic")

    def __repr__(self):
        return f"<Account {self.id} {self.username}>"

    def is_in_shipping_group(self):
        """Check if user is in an active shipping group."""
        return (
            self.shipping_group_id is not None and 
            self.shipping_status in ['WAITING', 'READY']
        )

    def clear_shipping_data(self):
        """Reset all shipping-related fields."""
        self.shipping_group_id = None
        self.shipping_city = None
        self.shipping_joined_at = None
        self.shipping_cart_snapshot = None
        self.shipping_weight = None
        self.shipping_product_cost = None
        self.shipping_cost = None
        self.shipping_is_creator = False
        self.shipping_expires_at = None
        self.shipping_status = None
        self.shipping_extended_count = 0


# -----------------------------------------------------------------------------
# 3.2 Account Profile
# -----------------------------------------------------------------------------

class AccountProfile(db.Model):
   
    __tablename__ = "account_profiles"

    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("accounts.id"), 
        unique=True, 
        nullable=False
    )
    full_name = db.Column(db.String(160))
    avatar_url = db.Column(db.Text)
    locale = db.Column(db.String(10), default="ar-SA")
    timezone = db.Column(db.String(64), default="Asia/Riyadh")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())


# -----------------------------------------------------------------------------
# 3.3 Account Security
# -----------------------------------------------------------------------------

class AccountSecurity(db.Model):
   
    __tablename__ = "account_security"

    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("accounts.id"), 
        unique=True, 
        nullable=False
    )
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    two_factor_method = db.Column(db.String(30))
    failed_login_attempts = db.Column(db.Integer, default=0)
    last_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    device_fingerprint = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())


# =============================================================================
# 4. PRODUCTS - 
# =============================================================================

class Product(db.Model):
   
    __tablename__ = "products"

    # === Primary Fields ===
    id = db.Column(db.BigInteger, primary_key=True)
    owner_user_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"))

    # === Product Info ===
    name = db.Column(db.String(160), nullable=False)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)
    image_primary = db.Column(db.Text)

    # === Product Status ===
    origin = db.Column(
        SAEnum(ProductOriginEnum, name="productoriginenum", schema="public"),
        nullable=False,
        default=ProductOriginEnum.AI
    )
    visibility = db.Column(
        SAEnum(ProductVisibilityEnum, name="productvisibilityenum", schema="public"),
        nullable=False,
        default=ProductVisibilityEnum.PRIVATE
    )
    status = db.Column(
        SAEnum(ProductStatusEnum, name="productstatusenum", schema="public"),
        nullable=False,
        default=ProductStatusEnum.DRAFT
    )
    is_active = db.Column(db.Boolean, default=True)

    # === Pricing ===
    price_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    base_price_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    complexity_factor = db.Column(db.Numeric(5, 2), nullable=False, default=1)
    category_multiplier = db.Column(db.Numeric(5, 2), nullable=False, default=1)
    discount_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    final_price_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    # === Inventory & Category ===
    stock_qty = db.Column(db.Integer, default=0)
    category = db.Column(db.String(80))
    brand = db.Column(db.String(80))

    # === Timestamps ===
    created_at = db.Column(db.DateTime, server_default=db.func.now())


# =============================================================================
# 5. ORDERS - 
# =============================================================================

# -----------------------------------------------------------------------------
# 5.1 Order
# -----------------------------------------------------------------------------

class Order(db.Model):
   
    __tablename__ = "orders"

    # === Primary Fields ===
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("accounts.id"), 
        nullable=False
    )
    status = db.Column(
        SAEnum(OrderStatusEnum), 
        default=OrderStatusEnum.PENDING
    )

    # === Costs ===
    subtotal_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    shipping_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    customs_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    fsa_fee_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    handling_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    merge_service_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    # === Delivery Info ===
    delivery_city = db.Column(db.String(50), nullable=True)
    order_type = db.Column(db.String(20), default='solo')  # solo / shared
    group_id = db.Column(db.String(100), nullable=True)

    # === Timestamps ===
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # === Relationships ===
    user = db.relationship("Account", back_populates="orders")
    items = db.relationship(
        "OrderItem", 
        back_populates="order", 
        lazy="dynamic", 
        cascade="all, delete-orphan"
    )
    payments = db.relationship(
        "Payment", 
        back_populates="order", 
        lazy="dynamic", 
        cascade="all, delete-orphan"
    )


# -----------------------------------------------------------------------------
# 5.2 Order Item
# -----------------------------------------------------------------------------

class OrderItem(db.Model):
  
    __tablename__ = "order_items"

    id = db.Column(db.BigInteger, primary_key=True)
    order_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("orders.id"), 
        nullable=False
    )
    product_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("products.id"), 
        nullable=False
    )
    qty = db.Column(db.Integer, nullable=False)
    unit_price_sar = db.Column(db.Numeric(12, 2), nullable=False)

    # === Relationships ===
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    # === Constraints ===
    __table_args__ = (
        UniqueConstraint(
            "order_id", 
            "product_id", 
            name="uq_order_product_once"
        ),
    )


# -----------------------------------------------------------------------------
# 5.3 Payment
# -----------------------------------------------------------------------------

class Payment(db.Model):
   
    __tablename__ = "payments"

    id = db.Column(db.BigInteger, primary_key=True)
    order_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("orders.id"), 
        nullable=False
    )
    account_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("accounts.id"), 
        nullable=False
    )

    method = db.Column(SAEnum(PaymentMethodEnum))
    amount_sar = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(
        SAEnum(PaymentStatusEnum), 
        default=PaymentStatusEnum.INITIATED
    )
    txn_ref = db.Column(db.String(120))
    processed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # === Relationships ===
    order = db.relationship("Order", back_populates="payments")


# =============================================================================
# 6. WISHLIST - 
# =============================================================================

# -----------------------------------------------------------------------------
# 6.1 Wishlist
# -----------------------------------------------------------------------------

class Wishlist(db.Model):
   
    __tablename__ = "wishlists"

    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("accounts.id"), 
        nullable=False, 
        unique=True
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now())


# -----------------------------------------------------------------------------
# 6.2 Wishlist Item
# -----------------------------------------------------------------------------

class WishlistItem(db.Model):
    
    __tablename__ = "wishlist_items"

    id = db.Column(db.BigInteger, primary_key=True)
    wishlist_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("wishlists.id"), 
        nullable=False
    )
    product_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("products.id"), 
        nullable=False
    )

    # === Constraints ===
    __table_args__ = (
        UniqueConstraint(
            "wishlist_id", 
            "product_id", 
            name="uq_wishlist_product_once"
        ),
    )


# =============================================================================
# 7. AI CHAT - 
# =============================================================================

# -----------------------------------------------------------------------------
# 7.1 AI Session
# -----------------------------------------------------------------------------

class AISession(db.Model):

    __tablename__ = "ai_sessions"

    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("accounts.id"), 
        nullable=False
    )
    started_at = db.Column(db.DateTime, server_default=db.func.now())
    ended_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="OPEN")  # OPEN / CLOSED


# -----------------------------------------------------------------------------
# 7.2 AI Message
# -----------------------------------------------------------------------------

class AIMessage(db.Model):
    """
    Chat messages (Mika + AI Chat).
    """
    __tablename__ = "ai_messages"

    id = db.Column(db.BigInteger, primary_key=True)
    session_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("ai_sessions.id"), 
        nullable=False
    )
    role = db.Column(db.String(20), nullable=False)  # user / assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


# -----------------------------------------------------------------------------
# 7.3 AI Generation
# -----------------------------------------------------------------------------

class AIGeneration(db.Model):
   
    __tablename__ = "ai_generations"

    id = db.Column(db.BigInteger, primary_key=True)
    session_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("ai_sessions.id"), 
        nullable=False
    )
    product_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("products.id")
    )
    image_url = db.Column(db.Text)
    prompt_json = db.Column(JSON)
    meta_json = db.Column(JSON)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


# =============================================================================
# 8. NOTIFICATIONS - 
# =============================================================================

class Notification(db.Model):
   
    __tablename__ = "notifications"

    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("accounts.id"), 
        nullable=False
    )
    type = db.Column(SAEnum(NotifyTypeEnum), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, server_default=db.func.now())

    # === Relationships ===
    account = db.relationship("Account", back_populates="notifications")


# =============================================================================
# 9. INVOICES - 
# =============================================================================

class Invoice(db.Model):
    
    __tablename__ = "invoices"

    id = db.Column(db.BigInteger, primary_key=True)
    order_id = db.Column(
        db.BigInteger, 
        db.ForeignKey("orders.id")
    )
    invoice_number = db.Column(db.String(40), unique=True, nullable=False)
    invoice_type = db.Column(
        SAEnum(InvoiceTypeEnum), 
        default=InvoiceTypeEnum.SOLO
    )
    issue_date = db.Column(db.DateTime, server_default=db.func.now())

    # === Amounts ===
    subtotal_sar = db.Column(db.Numeric(12, 2), default=0)
    tax_amount = db.Column(db.Numeric(12, 2), default=0)
    fees_amount = db.Column(db.Numeric(12, 2), default=0)
    discount_amount = db.Column(db.Numeric(12, 2), default=0)
    total_sar = db.Column(db.Numeric(12, 2), default=0)

    # === Status ===
    payment_status = db.Column(db.String(20), default="UNPAID")
    created_at = db.Column(db.DateTime, server_default=db.func.now())


# =============================================================================
# 10. DATABASE INDEXES - 
# =============================================================================

# Account indexes
Index("idx_accounts_shipping_group", Account.shipping_group_id)
Index("idx_accounts_shipping_city_status", Account.shipping_city, Account.shipping_status)

# Product indexes
Index("idx_products_owner", Product.owner_user_id)
Index("idx_products_origin", Product.origin)

# AI indexes
Index("idx_ai_messages_session", AIMessage.session_id)
Index("idx_ai_generations_session", AIGeneration.session_id)

# Wishlist indexes
Index("idx_wishlist_account", Wishlist.account_id)