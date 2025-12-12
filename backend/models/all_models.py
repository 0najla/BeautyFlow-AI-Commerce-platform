# models.py - Updated with Cost Sharing Fields
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
from sqlalchemy import Enum as SAEnum, JSON, UniqueConstraint
import enum

# ===== Enums =====
class RoleEnum(enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"
    SUPPLIER = "SUPPLIER"

class ProductStatusEnum(enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"

class ProductOriginEnum(enum.Enum):
    AI = "AI"
    CATALOG = "CATALOG"

class ProductVisibilityEnum(enum.Enum):
    PRIVATE = "PRIVATE"
    SMARTPICK = "SMARTPICK"
    PUBLIC = "PUBLIC"

class OrderStatusEnum(enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class PaymentStatusEnum(enum.Enum):
    INITIATED = "INITIATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class PaymentMethodEnum(enum.Enum):
    CARD = "CARD"
    PAYPAL = "PAYPAL"
    APPLE_PAY = "APPLE_PAY"

class NotifyTypeEnum(enum.Enum):
    SYSTEM = "SYSTEM"
    ORDER = "ORDER"
    PAYMENT = "PAYMENT"
    SECURITY = "SECURITY"

class AIEventEnum(enum.Enum):
    RECOMMENDATION = "RECOMMENDATION"
    PACKAGE_OPTIM = "PACKAGE_OPTIM"
    FRAUD_CHECK = "FRAUD_CHECK"
    NOTIFY = "NOTIFY"

class FormulaBaseEnum(enum.Enum):
    WATER = "WATER"
    SILICONE = "SILICONE"
    OIL = "OIL"
    GEL = "GEL"
    POWDER = "POWDER"
    CREAM = "CREAM"

class CoverageEnum(enum.Enum):
    SHEER = "SHEER"
    MEDIUM = "MEDIUM"
    FULL = "FULL"

class FinishEnum(enum.Enum):
    MATTE = "MATTE"
    NATURAL = "NATURAL"
    DEWY = "DEWY"
    GLOWY = "GLOWY"

class SkinTypeEnum(enum.Enum):
    NORMAL = "NORMAL"
    OILY = "OILY"
    DRY = "DRY"
    COMBINATION = "COMBINATION"
    SENSITIVE = "SENSITIVE"

# ✨ NEW: Shipping Group Status Enum
class ShippingStatusEnum(enum.Enum):
    WAITING = "WAITING"     # Waiting for 5 members
    READY = "READY"         # 5 members complete, ready for payment
    EXPIRED = "EXPIRED"     # Week expired without completion
    PAID = "PAID"           # Payment completed
    SHIPPED = "SHIPPED"     # Shipment dispatched
    CANCELLED = "CANCELLED" # Group cancelled


# ===== Core Tables =====
class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(30), unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(
        SAEnum(
            RoleEnum,
            name="roleenum",
            schema="public"
        ),
        nullable=False,
        default=RoleEnum.USER
    )

    is_2fa_enabled = db.Column(db.Boolean, default=False)
    two_factor_method = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # ============================================================
    # ✅ NEW: Cart Data - JSON string to persist cart across sessions
    # ============================================================
    cart_data = db.Column(db.Text, nullable=True)

    # ============================================================
    # ✨ Cost Sharing / Shipping Group Fields
    # ============================================================
    # Group identifier (e.g., "taif-202412051230-123")
    shipping_group_id = db.Column(db.String(50), nullable=True, index=True)
    
    # City/Region for shipping
    shipping_city = db.Column(db.String(50), nullable=True)
    
    # When user joined the group
    shipping_joined_at = db.Column(db.DateTime, nullable=True)
    
    # Snapshot of cart at join time (JSON)
    shipping_cart_snapshot = db.Column(db.Text, nullable=True)
    
    # Total weight of products (kg)
    shipping_weight = db.Column(db.Numeric(10, 3), nullable=True)
    
    # Total product cost (SAR)
    shipping_product_cost = db.Column(db.Numeric(12, 2), nullable=True)
    
    # User's share of shipping cost (SAR)
    shipping_cost = db.Column(db.Numeric(12, 2), nullable=True)
    
    # Is this user the group creator?
    shipping_is_creator = db.Column(db.Boolean, default=False)
    
    # When the group expires (created_at + 7 days)
    shipping_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Group status for this user
    shipping_status = db.Column(db.String(20), nullable=True)  # waiting/ready/expired/paid/shipped
    
    # Number of times the group was extended
    shipping_extended_count = db.Column(db.Integer, default=0)
    # ============================================================

    # relationships
    orders = db.relationship("Order", back_populates="user", lazy="dynamic")
    notifications = db.relationship("Notification", back_populates="account", lazy="dynamic")

    def __repr__(self):
        return f"<Account {self.id} {self.username} ({self.role.value})>"
    
    # ✨ Helper methods for shipping groups
    def is_in_shipping_group(self):
        """Check if user is currently in an active shipping group"""
        return self.shipping_group_id is not None and self.shipping_status in ['waiting', 'ready', 'WAITING', 'READY']
    
    def clear_shipping_data(self):
        """Clear all shipping group data for this user"""
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
    
    def get_avatar_url(self):
        """Generate avatar URL based on user ID"""
        return f"https://i.pravatar.cc/60?img={self.id % 70}"


class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), unique=True)
    company_name = db.Column(db.String(120))
    contact_name = db.Column(db.String(120))
    rating = db.Column(db.Numeric(2, 1))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    account = db.relationship("Account")
    products = db.relationship("Product", back_populates="supplier", lazy="dynamic")

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.BigInteger, primary_key=True)

    supplier_id = db.Column(db.BigInteger, db.ForeignKey("suppliers.id"))
    owner_user_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"))

    name = db.Column(db.String(160), nullable=False)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)
    image_primary = db.Column(db.Text)

    origin = db.Column(
        SAEnum(
            ProductOriginEnum,
            name="productoriginenum",
            schema="public"
        ),
        nullable=False,
        default=ProductOriginEnum.CATALOG
    )

    visibility = db.Column(
        SAEnum(
            ProductVisibilityEnum,
            name="productvisibilityenum",
            schema="public"
        ),
        nullable=False,
        default=ProductVisibilityEnum.PUBLIC
    )

    status = db.Column(
        SAEnum(
            ProductStatusEnum,
            name="productstatusenum",
            schema="public"
        ),
        nullable=False,
        default=ProductStatusEnum.DRAFT
    )

    is_active = db.Column(db.Boolean, default=True)

    price_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    base_price_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    complexity_factor = db.Column(db.Numeric(5, 2), nullable=False, default=1)
    category_multiplier = db.Column(db.Numeric(5, 2), nullable=False, default=1)
    discount_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    final_price_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    stock_qty = db.Column(db.Integer, default=0)
    category = db.Column(db.String(80))
    brand = db.Column(db.String(80))

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    supplier = db.relationship("Supplier", back_populates="products")
    images = db.relationship("ProductImage", back_populates="product", lazy="dynamic")

    def recalc_price(self):
        self.final_price_sar = round(
            (self.base_price_sar or 0) *
            (self.complexity_factor or 1) *
            (self.category_multiplier or 1) *
            (1 - (self.discount_percent or 0) / 100), 2
        )

from sqlalchemy import Index
Index("idx_products_owner_visibility", Product.owner_user_id, Product.visibility)
Index("idx_products_origin", Product.origin)

# ✨ NEW: Index for shipping group queries
Index("idx_accounts_shipping_group", Account.shipping_group_id)
Index("idx_accounts_shipping_city_status", Account.shipping_city, Account.shipping_status)


class ProductImage(db.Model):
    __tablename__ = "product_images"
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    url = db.Column(db.Text, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    product = db.relationship("Product", back_populates="images")


class ProductSpec(db.Model):
    __tablename__ = "product_specs"
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), unique=True, nullable=False)

    formula_base = db.Column(SAEnum(FormulaBaseEnum))
    coverage = db.Column(SAEnum(CoverageEnum))
    finish = db.Column(SAEnum(FinishEnum))

    spf = db.Column(db.Integer)
    pa_rating = db.Column(db.String(10))
    pao_months = db.Column(db.Integer)

    is_hypoallergenic  = db.Column(db.Boolean, default=False)
    is_non_comedogenic = db.Column(db.Boolean, default=False)
    is_fragrance_free  = db.Column(db.Boolean, default=False)
    is_vegan           = db.Column(db.Boolean, default=False)
    is_cruelty_free    = db.Column(db.Boolean, default=False)

    net_content_value = db.Column(db.Numeric(8, 2))
    net_content_unit  = db.Column(db.String(10))
    made_in = db.Column(db.String(80))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())


class ProductSkinType(db.Model):
    __tablename__ = "product_skin_types"
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    skin_type = db.Column(SAEnum(SkinTypeEnum), nullable=False)

    __table_args__ = (
        UniqueConstraint("product_id", "skin_type", name="uq_product_skin_type"),
    )


class ProductIngredient(db.Model):
    __tablename__ = "product_ingredients"
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    ingredient_name = db.Column(db.String(160), nullable=False)
    percentage = db.Column(db.Numeric(5, 2))
    role = db.Column(db.String(80))
    is_allergen = db.Column(db.Boolean, default=False)


class ProductShade(db.Model):
    __tablename__ = "product_shades"
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    shade_name = db.Column(db.String(80), nullable=False)
    hex_color = db.Column(db.String(7))
    image_url = db.Column(db.Text)

 
class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    status = db.Column(SAEnum(OrderStatusEnum), default=OrderStatusEnum.PENDING)
    subtotal_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    shipping_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    customs_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    fsa_fee_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    handling_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    merge_service_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_sar = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    delivery_city = db.Column(db.String(50), nullable=True)
    order_type = db.Column(db.String(20), default='solo')  # solo أو shared
    group_id = db.Column(db.String(100), nullable=True)    # معرف المجموعة للـ Cost Sharing

    user = db.relationship("Account", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", lazy="dynamic", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="order", lazy="dynamic", cascade="all, delete-orphan")

class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.BigInteger, primary_key=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    unit_price_sar = db.Column(db.Numeric(12, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_order_product_once"),
    )

class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.BigInteger, primary_key=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id"), nullable=False)
    method = db.Column(SAEnum(PaymentMethodEnum))
    amount_sar = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(SAEnum(PaymentStatusEnum), default=PaymentStatusEnum.INITIATED)
    txn_ref = db.Column(db.String(120))
    processed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    order = db.relationship("Order", back_populates="payments")

    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    invoice_id = db.Column(db.BigInteger, db.ForeignKey("invoices.id"))
    merge_group_id = db.Column(db.BigInteger, db.ForeignKey("merge_groups.id"))


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    type = db.Column(SAEnum(NotifyTypeEnum), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, server_default=db.func.now())

    account = db.relationship("Account", back_populates="notifications")

class AIEvent(db.Model):
    __tablename__ = "ai_events"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"))
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id"))
    event_type = db.Column(SAEnum(AIEventEnum), nullable=False)
    payload = db.Column(JSON)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

# ========== Profiles ==========
class AccountProfile(db.Model):
    __tablename__ = "account_profiles"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), unique=True, nullable=False)

    full_name = db.Column(db.String(160))
    avatar_url = db.Column(db.Text)

    locale = db.Column(db.String(10), default="ar-SA")
    timezone = db.Column(db.String(64), default="Asia/Riyadh")

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

# ========== Security ==========
class AccountSecurity(db.Model):
    __tablename__ = "account_security"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), unique=True, nullable=False)

    is_2fa_enabled = db.Column(db.Boolean, default=False)
    two_factor_method = db.Column(db.String(30))

    failed_login_attempts = db.Column(db.Integer, default=0)
    last_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    device_fingerprint = db.Column(db.String(120))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

# ========== AI Chat ==========
class AISession(db.Model):
    __tablename__ = "ai_sessions"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    started_at = db.Column(db.DateTime, server_default=db.func.now())
    ended_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="ACTIVE")

class AIMessage(db.Model):
    __tablename__ = "ai_messages"
    id = db.Column(db.BigInteger, primary_key=True)
    session_id = db.Column(db.BigInteger, db.ForeignKey("ai_sessions.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class AIGeneration(db.Model):
    __tablename__ = "ai_generations"
    id = db.Column(db.BigInteger, primary_key=True)
    session_id = db.Column(db.BigInteger, db.ForeignKey("ai_sessions.id"), nullable=False)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"))
    image_url = db.Column(db.Text)
    prompt_json = db.Column(JSON)
    meta_json = db.Column(JSON)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class SmartPickPool(db.Model):
    __tablename__ = "smartpick_pool"
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), unique=True, nullable=False)
    added_at = db.Column(db.DateTime, server_default=db.func.now())
    reason = db.Column(db.String(40))

class SmartPickPersonalization(db.Model):
    __tablename__ = "smartpick_personalization"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    pref_json = db.Column(JSON)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    __table_args__ = (UniqueConstraint("account_id", name="uq_sp_persona_account"),)


# ========== Merge Groups ==========

class MergeGroup(db.Model):
    __tablename__ = "merge_groups"
    id = db.Column(db.BigInteger, primary_key=True)
    title = db.Column(db.String(120))
    created_by = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    status = db.Column(db.String(20), default="OPEN")
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class MergeMember(db.Model):
    __tablename__ = "merge_members"
    id = db.Column(db.BigInteger, primary_key=True)
    group_id = db.Column(db.BigInteger, db.ForeignKey("merge_groups.id"), nullable=False)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id"))
    weight_kg = db.Column(db.Numeric(8,3))
    share_percent = db.Column(db.Numeric(5,2))
    joined_at = db.Column(db.DateTime, server_default=db.func.now())
    __table_args__ = (UniqueConstraint("group_id", "account_id", name="uq_merge_member"),)

class ShipmentBatch(db.Model):
    __tablename__ = "shipment_batches"
    id = db.Column(db.BigInteger, primary_key=True)
    group_id = db.Column(db.BigInteger, db.ForeignKey("merge_groups.id"))
    carrier = db.Column(db.String(80))
    tracking_no = db.Column(db.String(120))
    status = db.Column(db.String(20), default="PENDING")
    depart_at = db.Column(db.DateTime)
    arrive_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class ShipmentItem(db.Model):
    __tablename__ = "shipment_items"
    id = db.Column(db.BigInteger, primary_key=True)
    shipment_id = db.Column(db.BigInteger, db.ForeignKey("shipment_batches.id"), nullable=False)
    order_item_id = db.Column(db.BigInteger, db.ForeignKey("order_items.id"), nullable=False)
    weight_kg = db.Column(db.Numeric(8,3))
    volume_cm3 = db.Column(db.Numeric(12,2))

class ShipmentCost(db.Model):
    __tablename__ = "shipment_costs"
    id = db.Column(db.BigInteger, primary_key=True)
    shipment_id = db.Column(db.BigInteger, db.ForeignKey("shipment_batches.id"), nullable=False)
    kind = db.Column(db.String(30), nullable=False)
    amount_sar = db.Column(db.Numeric(12,2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class ShipmentShare(db.Model):
    __tablename__ = "shipment_shares"
    id = db.Column(db.BigInteger, primary_key=True)
    shipment_id = db.Column(db.BigInteger, db.ForeignKey("shipment_batches.id"), nullable=False)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    kind = db.Column(db.String(30), nullable=False)
    amount_sar = db.Column(db.Numeric(12,2), nullable=False, default=0)
    __table_args__ = (UniqueConstraint("shipment_id", "account_id", "kind", name="uq_ship_share"),)

# ========== Promo ==========

class Promo(db.Model):
    __tablename__ = "promos"
    id = db.Column(db.BigInteger, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(160))
    percent_off = db.Column(db.Numeric(5,2))
    sar_off = db.Column(db.Numeric(12,2))
    min_order_sar = db.Column(db.Numeric(12,2))
    max_redemptions = db.Column(db.Integer)
    per_user_limit = db.Column(db.Integer)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class PromoRedemption(db.Model):
    __tablename__ = "promo_redemptions"
    id = db.Column(db.BigInteger, primary_key=True)
    promo_id = db.Column(db.BigInteger, db.ForeignKey("promos.id"), nullable=False)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id"), nullable=False)
    redeemed_at = db.Column(db.DateTime, server_default=db.func.now())
    __table_args__ = (UniqueConstraint("promo_id", "account_id", "order_id", name="uq_promo_use"),)


# ========== Cart & Wishlist ==========
class Cart(db.Model):
    __tablename__ = "carts"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

class CartItem(db.Model):
    __tablename__ = "cart_items"
    id = db.Column(db.BigInteger, primary_key=True)
    cart_id = db.Column(db.BigInteger, db.ForeignKey("carts.id"), nullable=False)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False, default=1)
    unit_price_sar = db.Column(db.Numeric(12,2), nullable=False, default=0)
    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="uq_cart_product_once"),)

class Wishlist(db.Model):
    __tablename__ = "wishlists"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"
    id = db.Column(db.BigInteger, primary_key=True)
    wishlist_id = db.Column(db.BigInteger, db.ForeignKey("wishlists.id"), nullable=False)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    __table_args__ = (UniqueConstraint("wishlist_id", "product_id", name="uq_wishlist_product_once"),)

# ========== Reviews & Ratings ==========
class ReviewStatusEnum(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(160))
    content = db.Column(db.Text)
    status = db.Column(SAEnum(ReviewStatusEnum), default=ReviewStatusEnum.PENDING)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    __table_args__ = (UniqueConstraint("product_id", "account_id", name="uq_review_once_per_user"),)


# ========== Returns & Refunds ==========
class ReturnStatusEnum(enum.Enum):
    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    RECEIVED = "RECEIVED"
    REFUNDED = "REFUNDED"
    CLOSED = "CLOSED"

class ReturnRequest(db.Model):
    __tablename__ = "return_requests"
    id = db.Column(db.BigInteger, primary_key=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id"), nullable=False)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    reason = db.Column(db.String(160))
    details = db.Column(db.Text)
    status = db.Column(SAEnum(ReturnStatusEnum), default=ReturnStatusEnum.REQUESTED)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class Refund(db.Model):
    __tablename__ = "refunds"
    id = db.Column(db.BigInteger, primary_key=True)
    payment_id = db.Column(db.BigInteger, db.ForeignKey("payments.id"), nullable=False)
    amount_sar = db.Column(db.Numeric(12,2), nullable=False, default=0)
    status = db.Column(SAEnum(PaymentStatusEnum), default=PaymentStatusEnum.REFUNDED)
    processed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

# ========== Support Tickets ==========
class TicketStatusEnum(enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

class SupportTicket(db.Model):
    __tablename__ = "support_tickets"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id"))
    subject = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(SAEnum(TicketStatusEnum), default=TicketStatusEnum.OPEN)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

# ========== Warehouses & Inventory ==========
class Warehouse(db.Model):
    __tablename__ = "warehouses"
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(160))

class InventoryMovementTypeEnum(enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    ADJUST = "ADJUST"

class InventoryMovement(db.Model):
    __tablename__ = "inventory_movements"
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    warehouse_id = db.Column(db.BigInteger, db.ForeignKey("warehouses.id"))
    move_type = db.Column(SAEnum(InventoryMovementTypeEnum), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    ref = db.Column(db.String(160))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

# ========== Tax & Fee Rules ==========

class TaxRule(db.Model):
    __tablename__ = "tax_rules"
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    rate_percent = db.Column(db.Numeric(5,2), nullable=False)
    applies_to = db.Column(db.String(40), nullable=False, default="PRODUCT")
    is_active = db.Column(db.Boolean, default=True)

class FeeRule(db.Model):
    __tablename__ = "fee_rules"
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    amount_sar = db.Column(db.Numeric(12,2), default=0)
    percent = db.Column(db.Numeric(5,2))
    applies_to = db.Column(db.String(40), default="ORDER")
    is_active = db.Column(db.Boolean, default=True)

# ========== Price Rules ==========
class PriceRuleConditionEnum(enum.Enum):
    CATEGORY = "CATEGORY"
    BRAND = "BRAND"
    MIN_QTY = "MIN_QTY"
    MIN_ORDER = "MIN_ORDER"

class PriceRule(db.Model):
    __tablename__ = "price_rules"
    id = db.Column(db.BigInteger, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    condition = db.Column(SAEnum(PriceRuleConditionEnum), nullable=False)
    condition_value = db.Column(db.String(160))
    percent_off = db.Column(db.Numeric(5,2))
    sar_off = db.Column(db.Numeric(12,2))
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

# ========== Webhooks / AuditLog==========
class WebhookEvent(db.Model):
    __tablename__ = "webhook_events"
    id = db.Column(db.BigInteger, primary_key=True)
    kind = db.Column(db.String(80), nullable=False)
    payload = db.Column(JSON)
    status = db.Column(db.String(20), default="PENDING")
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.BigInteger, primary_key=True)
    actor_account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"))
    entity = db.Column(db.String(40))
    entity_id = db.Column(db.BigInteger)
    action = db.Column(db.String(40))
    before_json = db.Column(JSON)
    after_json = db.Column(JSON)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


# ========== Invoice ==========

class InvoiceTypeEnum(enum.Enum):
    SOLO = "SOLO"
    SHARED = "SHARED"

class Invoice(db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.BigInteger, primary_key=True)

    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id"))
    merge_group_id = db.Column(db.BigInteger, db.ForeignKey("merge_groups.id"))

    invoice_number = db.Column(db.String(40), unique=True, nullable=False)
    invoice_type = db.Column(SAEnum(InvoiceTypeEnum), default=InvoiceTypeEnum.SOLO)

    issue_date   = db.Column(db.DateTime, server_default=db.func.now())
    subtotal_sar = db.Column(db.Numeric(12,2), default=0)
    tax_amount   = db.Column(db.Numeric(12,2), default=0)
    fees_amount  = db.Column(db.Numeric(12,2), default=0)
    discount_amount = db.Column(db.Numeric(12,2), default=0)
    total_sar    = db.Column(db.Numeric(12,2), default=0)

    payment_status = db.Column(db.String(20), default="UNPAID")
    created_at  = db.Column(db.DateTime, server_default=db.func.now())

    
# ========== AIFeedback ==========
class AIFeedback(db.Model):
    __tablename__ = "ai_feedback"
    id = db.Column(db.BigInteger, primary_key=True)
    generation_id = db.Column(db.BigInteger, db.ForeignKey("ai_generations.id"), nullable=False)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"), nullable=False)
    feedback_type = db.Column(db.String(20), nullable=False)
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


# ========== AIProductHistory ==========

class AIProductHistory(db.Model):
    __tablename__ = "ai_product_history"
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False)
    account_id = db.Column(db.BigInteger, db.ForeignKey("accounts.id"))
    version = db.Column(db.Integer, default=1)
    description_before = db.Column(db.Text)
    description_after = db.Column(db.Text)
    image_url_before = db.Column(db.Text)
    image_url_after = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


# ========== Indexes ==========
Index("idx_ai_messages_session", AIMessage.session_id)
Index("idx_ai_generations_session", AIGeneration.session_id)
Index("idx_sp_pool_product", SmartPickPool.product_id)
Index("idx_sp_persona_account", SmartPickPersonalization.account_id)

Index("idx_merge_members_group", MergeMember.group_id)
Index("idx_ship_items_shipment", ShipmentItem.shipment_id)
Index("idx_ship_costs_shipment", ShipmentCost.shipment_id)
Index("idx_ship_shares_ship_acc", ShipmentShare.shipment_id, ShipmentShare.account_id)

Index("idx_promos_code", Promo.code)
Index("idx_redemption_promo", PromoRedemption.promo_id)

Index("idx_cart_account", Cart.account_id)
Index("idx_wishlist_account", Wishlist.account_id)
Index("idx_review_product", Review.product_id)
Index("idx_return_order", ReturnRequest.order_id)
Index("idx_refund_payment", Refund.payment_id)
Index("idx_ticket_account", SupportTicket.account_id)
Index("idx_inventory_product", InventoryMovement.product_id)
Index("idx_tax_active", TaxRule.is_active)
Index("idx_fee_active", FeeRule.is_active)
Index("idx_price_rule_active", PriceRule.is_active)
Index("idx_webhook_status", WebhookEvent.status)
Index("idx_audit_entity", AuditLog.entity, AuditLog.entity_id)