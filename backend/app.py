"""
============================================================================
BeautyFlow - Main Flask Application
============================================================================
Backend server for BeautyFlow beauty import platform.
Handles authentication, AI generation, cart, shipping groups, and payments.

Author: BeautyFlow Team
Version: 1.0.0
============================================================================
"""

# =============================================================================
# 1. IMPORTS
# =============================================================================

# Standard library
import os
import re
import json
import random
import base64
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps

# Third-party
import requests
from dotenv import load_dotenv
from openai import OpenAI
from twilio.rest import Client

# Flask core
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, flash
)
from flask_cors import CORS
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf, validate_csrf, CSRFError
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

# Local models
from models.all_models import (
    db, Account, AccountProfile, AccountSecurity,
    Product, ProductOriginEnum, ProductVisibilityEnum, ProductStatusEnum,
    Order, OrderItem, OrderStatusEnum,
    Payment, PaymentMethodEnum, PaymentStatusEnum,
    Wishlist, WishlistItem,
    AISession, AIMessage, AIGeneration
)


# =============================================================================
# 2. CONFIGURATION
# =============================================================================

# Load environment variables
load_dotenv()

# Directory paths
BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

# Initialize Flask app
app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)

# Flask configuration
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"options": "-csearch_path=public"}
}

# Initialize extensions
CORS(app)
csrf = CSRFProtect(app)
db.init_app(app)
migrate = Migrate(app, db)

# Create database tables
with app.app_context():
    db.create_all()

# Debug output
print("[DEBUG] Template folder:", app.template_folder)
print("[DEBUG] Static folder:", app.static_folder)

# OpenAI Configuration
API_KEY = os.getenv("OPENAI_API_KEY")
print("[DEBUG] OPENAI_API_KEY present:", bool(API_KEY))

if not API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY not found.\n"
        "Add it to backend/.env like:\n"
        "OPENAI_API_KEY=sk-xxxx"
    )

OpenAI_Client = OpenAI(api_key=API_KEY)

# Twilio Configuration
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)
VERIFY_SID = os.getenv("TWILIO_VERIFY_SID")
USE_TWILIO = os.getenv("USE_TWILIO", "0") == "1"


# =============================================================================
# 3. CONSTANTS - SHIPPING & FEES
# =============================================================================

SHIPPING_BASE = 50           # Base shipping fee (SAR)
SHIPPING_PER_ITEM = 5        # Additional fee per item (SAR)
CUSTOMS_RATE = 0.05          # Customs duty rate (5%)
SFDA_FEE = 20                # SFDA fixed fee (SAR)
HANDLING_PER_ITEM = 8        # Handling fee per item (SAR)
TAX_RATE = 0.15              # VAT rate (15%)


# =============================================================================
# 4. CONSTANTS - SUPPORTED CITIES
# =============================================================================

SUPPORTED_CITIES = {
    "riyadh": {
        "name": "الرياض",
        "name_en": "Riyadh",
        "multiplier": 1.0,
        "days_min": 7,
        "days_max": 10
    },
    "jeddah": {
        "name": "جدة",
        "name_en": "Jeddah",
        "multiplier": 0.95,
        "days_min": 5,
        "days_max": 7
    },
    "makkah": {
        "name": "مكة",
        "name_en": "Makkah",
        "multiplier": 0.98,
        "days_min": 5,
        "days_max": 7
    },
    "madinah": {
        "name": "المدينة",
        "name_en": "Madinah",
        "multiplier": 1.02,
        "days_min": 6,
        "days_max": 8
    },
    "dammam": {
        "name": "الدمام",
        "name_en": "Dammam",
        "multiplier": 1.05,
        "days_min": 7,
        "days_max": 10
    },
    "khobar": {
        "name": "الخبر",
        "name_en": "Khobar",
        "multiplier": 1.05,
        "days_min": 7,
        "days_max": 10
    },
    "dhahran": {
        "name": "الظهران",
        "name_en": "Dhahran",
        "multiplier": 1.05,
        "days_min": 7,
        "days_max": 10
    },
    "tabuk": {
        "name": "تبوك",
        "name_en": "Tabuk",
        "multiplier": 1.15,
        "days_min": 10,
        "days_max": 14
    },
    "abha": {
        "name": "أبها",
        "name_en": "Abha",
        "multiplier": 1.20,
        "days_min": 10,
        "days_max": 14
    },
    "khamis": {
        "name": "خميس مشيط",
        "name_en": "Khamis Mushait",
        "multiplier": 1.20,
        "days_min": 10,
        "days_max": 14
    },
    "taif": {
        "name": "الطائف",
        "name_en": "Taif",
        "multiplier": 1.08,
        "days_min": 8,
        "days_max": 12
    },
    "buraidah": {
        "name": "بريدة",
        "name_en": "Buraidah",
        "multiplier": 1.08,
        "days_min": 8,
        "days_max": 12
    },
    "najran": {
        "name": "نجران",
        "name_en": "Najran",
        "multiplier": 1.25,
        "days_min": 12,
        "days_max": 16
    },
    "jubail": {
        "name": "الجبيل",
        "name_en": "Jubail",
        "multiplier": 1.08,
        "days_min": 8,
        "days_max": 11
    },
    "hofuf": {
        "name": "الهفوف",
        "name_en": "Hofuf",
        "multiplier": 1.08,
        "days_min": 8,
        "days_max": 11
    },
    "yanbu": {
        "name": "ينبع",
        "name_en": "Yanbu",
        "multiplier": 1.02,
        "days_min": 7,
        "days_max": 10
    },
    "hail": {
        "name": "حائل",
        "name_en": "Hail",
        "multiplier": 1.12,
        "days_min": 9,
        "days_max": 12
    },
    "jazan": {
        "name": "جازان",
        "name_en": "Jazan",
        "multiplier": 1.18,
        "days_min": 11,
        "days_max": 15
    },
    "arar": {
        "name": "عرعر",
        "name_en": "Arar",
        "multiplier": 1.22,
        "days_min": 12,
        "days_max": 16
    },
    "albaha": {
        "name": "الباحة",
        "name_en": "Al Baha",
        "multiplier": 1.22,
        "days_min": 12,
        "days_max": 16
    },
}


# =============================================================================
# 5. CONSTANTS - PRODUCT PRICING
# =============================================================================

# Base prices by product type (SAR)
BASE_PRICES = {
    "LIPSTICK": 45,
    "MASCARA": 50,
    "BLUSH": 55,
    "FOUNDATION": 65,
    "EYELINER": 40,
    "EYESHADOW": 60,
    "HIGHLIGHTER": 55,
    "BRONZER": 55,
    "PRIMER": 60,
    "SETTING_SPRAY": 50
}

# Price multipliers by formula type
FORMULA_MULT = {
    "WATER": 1.0,
    "OIL": 1.05,
    "CREAM": 1.03,
    "GEL": 1.02,
    "POWDER": 0.98,
    "SILICONE": 1.08
}

# Price multipliers by coverage level
COVERAGE_MULT = {
    "SHEER": 0.95,
    "MEDIUM": 1.0,
    "FULL": 1.05
}

# Price multipliers by finish type
FINISH_MULT = {
    "MATTE": 1.02,
    "NATURAL": 1.0,
    "DEWY": 1.03,
    "GLOWY": 1.04,
    "SATIN": 1.02
}

# Price multipliers by skin type
SKIN_MULT = {
    "NORMAL": 1.0,
    "OILY": 1.02,
    "DRY": 1.03,
    "COMBINATION": 1.03,
    "SENSITIVE": 1.05
}

# Product sizes by type
PRODUCT_SIZES = {
    "LIPSTICK": "3.5g",
    "MASCARA": "8ml",
    "BLUSH": "5g",
    "FOUNDATION": "30ml",
    "EYELINER": "0.5ml",
    "EYESHADOW": "1.5g",
    "HIGHLIGHTER": "8g",
    "BRONZER": "8g",
    "PRIMER": "30ml",
    "SETTING_SPRAY": "60ml"
}

# Maximum product price (SAR)
MAX_PRICE = 150

# =============================================================================
# 6. HELPER FUNCTIONS - DATABASE
# =============================================================================

def ensure_profile_for(account, first_name=None, last_name=None, phone=None):
    """
    Create AccountProfile if missing and update basic fields.
    
    Args:
        account: Account object
        first_name: Optional first name
        last_name: Optional last name
        phone: Optional phone number
    
    Returns:
        tuple: (profile_object, was_created)
    """
    prof = AccountProfile.query.filter_by(account_id=account.id).first()
    created = False

    if not prof:
        prof = AccountProfile(account_id=account.id)
        created = True

    # Build full name from parts
    full_name_parts = []
    if first_name:
        full_name_parts.append(first_name.strip())
    if last_name:
        full_name_parts.append(last_name.strip())
    if full_name_parts:
        prof.full_name = " ".join(full_name_parts)

    if created:
        db.session.add(prof)

    return prof, created


# =============================================================================
# 7. HELPER FUNCTIONS - CART (SESSION & DATABASE)
# =============================================================================

# -----------------------------------------------------------------------------
# 7.1 Cart Session Functions
# -----------------------------------------------------------------------------

def get_cart():
    """
    Get cart dictionary from session.
    
    Returns:
        dict: Cart items {product_id: {name, price, qty, image}}
    """
    return session.get("cart", {})


def save_cart(cart):
    """
    Save cart to both session and database.
    Ensures data persistence across sessions.
    
    Args:
        cart: Cart dictionary to save
    """
    session["cart"] = cart
    session.modified = True

    user_id = session.get("user_id")
    if user_id:
        save_cart_to_db(user_id, cart)


def get_cart_count():
    """
    Get total quantity of items in cart.
    
    Returns:
        int: Total quantity of all items
    """
    cart = get_cart()
    return sum(item["qty"] for item in cart.values())


# -----------------------------------------------------------------------------
# 7.2 Cart Database Functions
# -----------------------------------------------------------------------------

def save_cart_to_db(user_id, cart):
    """
    Persist cart data to database for user.
    Called automatically when cart is modified.
    
    Args:
        user_id: User's account ID
        cart: Cart dictionary to save
    """
    try:
        user = Account.query.get(user_id)
        if user:
            user.cart_data = json.dumps(cart) if cart else None
            db.session.commit()
            print(f"[CART] Saved to DB for user {user_id}: {len(cart)} items")
    except Exception as e:
        print(f"[CART] Error saving to DB: {e}")
        db.session.rollback()


def load_cart_from_db(user_id):
    """
    Load cart data from database on user login.
    Syncs database cart with session.
    
    Args:
        user_id: User's account ID
    
    Returns:
        dict: Loaded cart or empty dict
    """
    try:
        user = Account.query.get(user_id)
        if user and user.cart_data:
            cart = json.loads(user.cart_data)
            session["cart"] = cart
            session.modified = True
            print(f"[CART] Loaded from DB for user {user_id}: {len(cart)} items")
            return cart
    except Exception as e:
        print(f"[CART] Error loading from DB: {e}")
    return {}


def clear_cart_in_db(user_id):
    """
    Clear cart data from database after checkout.
    
    Args:
        user_id: User's account ID
    """
    try:
        user = Account.query.get(user_id)
        if user:
            user.cart_data = None
            db.session.commit()
            print(f"[CART] Cleared in DB for user {user_id}")
    except Exception as e:
        print(f"[CART] Error clearing in DB: {e}")
        db.session.rollback()


# =============================================================================
# 8. HELPER FUNCTIONS - CART CALCULATIONS
# =============================================================================

def calculate_cart_summary(cart):
    """
    Calculate complete cart summary with all fees.
    
    Args:
        cart: Cart dictionary
    
    Returns:
        dict: Summary containing:
            - items_count: Number of unique products
            - total_qty: Total quantity of all items
            - subtotal: Product cost before fees
            - shipping_fee: Base + per-item shipping
            - custom_duties: 5% of subtotal
            - sfda_fee: Fixed SFDA fee
            - handling_fee: Per-item handling
            - shipping: Total shipping costs
            - tax: 15% VAT
            - total: Grand total
    """
    # Return zeros if cart is empty
    if not cart:
        return {
            "items_count": 0,
            "total_qty": 0,
            "subtotal": 0,
            "shipping_fee": 0,
            "custom_duties": 0,
            "sfda_fee": 0,
            "handling_fee": 0,
            "shipping": 0,
            "tax": 0,
            "total": 0
        }

    # Count items and calculate subtotal
    items_count = len(cart)
    total_qty = sum(item.get("qty", 1) for item in cart.values())
    subtotal = sum(
        item.get("price", 0) * item.get("qty", 1)
        for item in cart.values()
    )

    # Calculate individual fees
    shipping_fee = SHIPPING_BASE + (total_qty * SHIPPING_PER_ITEM) if total_qty > 0 else 0
    custom_duties = round(subtotal * CUSTOMS_RATE, 2)
    sfda_fee = SFDA_FEE if total_qty > 0 else 0
    handling_fee = total_qty * HANDLING_PER_ITEM

    # Total shipping = all shipping-related fees
    shipping = shipping_fee + custom_duties + sfda_fee + handling_fee

    # Tax on products + shipping (15% VAT)
    tax = round((subtotal + shipping) * TAX_RATE, 2)

    # Grand total
    total = round(subtotal + shipping + tax, 2)

    return {
        "items_count": items_count,
        "total_qty": total_qty,
        "subtotal": round(subtotal, 2),
        "shipping_fee": shipping_fee,
        "custom_duties": custom_duties,
        "sfda_fee": sfda_fee,
        "handling_fee": handling_fee,
        "shipping": round(shipping, 2),
        "tax": tax,
        "total": total
    }


def calculate_user_share(total_items, product_cost, members_count=1, is_group=False):
    """
    Calculate user's share for cost-sharing groups.
    
    IMPORTANT: Only shipping_fee is split among members!
    Other fees (customs, SFDA, handling) are per-user.
    
    Args:
        total_items: Number of items user has
        product_cost: Total cost of user's products
        members_count: Number of members in group (default: 1)
        is_group: Whether user is in a group (default: False)
    
    Returns:
        dict: Cost breakdown containing:
            - product_cost: User's product total
            - shipping_fee_solo: What user would pay alone
            - shipping_fee_shared: What user pays in group
            - shipping_fee: Actual fee based on group status
            - custom_duties: 5% of product cost
            - sfda_fee: Fixed SFDA fee
            - handling_fee: Per-item handling
            - total_shipping: All shipping costs combined
            - tax: 15% VAT
            - grand_total: Final amount to pay
            - savings: Amount saved by sharing
            - savings_percent: Percentage saved
            - members_count: Number of group members
    """
    # Calculate shipping fee - ONLY THIS IS SPLIT among members
    shipping_fee_solo = SHIPPING_BASE + (total_items * SHIPPING_PER_ITEM)
    
    if members_count > 1:
        shipping_fee_shared = round(shipping_fee_solo / members_count, 2)
    else:
        shipping_fee_shared = shipping_fee_solo

    # Per-user fees (NOT split)
    custom_duties = round(product_cost * CUSTOMS_RATE, 2)
    sfda_fee = SFDA_FEE
    handling_fee = total_items * HANDLING_PER_ITEM

    # Determine which shipping fee to use
    shipping_fee_used = shipping_fee_shared if is_group else shipping_fee_solo
    
    # Total shipping costs
    total_shipping = shipping_fee_used + custom_duties + sfda_fee + handling_fee

    # Tax calculation (15% VAT)
    tax = round((product_cost + total_shipping) * TAX_RATE, 2)

    # Grand total
    grand_total = round(product_cost + total_shipping + tax, 2)

    # Calculate savings from group shipping
    if members_count > 1:
        savings = round(shipping_fee_solo - shipping_fee_shared, 2)
    else:
        savings = 0
    
    if shipping_fee_solo > 0:
        savings_percent = round((savings / shipping_fee_solo) * 100, 1)
    else:
        savings_percent = 0

    return {
        "product_cost": round(product_cost, 2),
        "shipping_fee_solo": shipping_fee_solo,
        "shipping_fee_shared": shipping_fee_shared,
        "shipping_fee": shipping_fee_used,
        "custom_duties": custom_duties,
        "sfda_fee": sfda_fee,
        "handling_fee": handling_fee,
        "total_shipping": round(total_shipping, 2),
        "tax": tax,
        "grand_total": grand_total,
        "savings": savings,
        "savings_percent": savings_percent,
        "members_count": members_count
    }


# =============================================================================
# 9. HELPER FUNCTIONS - SHIPPING
# =============================================================================

def clear_user_shipping_data(user):
    """
    Reset all shipping-related fields for a user.
    Called when user leaves a group or after payment.
    
    Args:
        user: Account object to reset
    """
    user.shipping_group_id = None
    user.shipping_city = None
    user.shipping_joined_at = None
    user.shipping_cart_snapshot = None
    user.shipping_weight = None
    user.shipping_product_cost = None
    user.shipping_is_creator = False
    user.shipping_expires_at = None
    user.shipping_status = None
    user.shipping_extended_count = 0
    user.shipping_cost = None


def generate_group_id(city_key):
    """
    Generate unique group ID with city prefix and timestamp.
    
    Args:
        city_key: City identifier (e.g., "riyadh", "jeddah")
    
    Returns:
        str: Unique group ID (e.g., "riyadh-202412141530-456")
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
    random_suffix = random.randint(100, 999)
    return f"{city_key}-{timestamp}-{random_suffix}"


# =============================================================================
# 10. HELPER FUNCTIONS - AI NAMING
# =============================================================================

def generate_product_name(packaging_desc=None, product_type=None, finish=None):
    """
    Generate creative product name based on description and attributes.
    
    Args:
        packaging_desc: Description of packaging style
        product_type: Type of product (LIPSTICK, MASCARA, etc.)
        finish: Product finish type (optional, not currently used)
    
    Returns:
        str: Generated product name (e.g., "Royal Kiss", "Sweet Bloom")
    """
    # Vibe-based naming words
    vibe_words = {
        "luxury": ["Royal", "Luxe", "Elite", "Diamond", "Velvet", "Gold", "Prestige"],
        "cute": ["Sweet", "Dreamy", "Bloom", "Sugar", "Petal", "Berry", "Honey"],
        "minimal": ["Pure", "Clean", "Soft", "Bare", "Fresh", "Clear", "Essential"],
        "natural": ["Nature", "Organic", "Glow", "Herbal", "Green", "Zen"],
        "bold": ["Bold", "Fierce", "Power", "Edge", "Rebel", "Storm"]
    }

    # Product-specific naming words
    product_words = {
        "LIPSTICK": ["Kiss", "Lip", "Pout", "Velvet"],
        "MASCARA": ["Lash", "Flutter", "Volume", "Drama"],
        "BLUSH": ["Flush", "Glow", "Cheek", "Rose"],
        "FOUNDATION": ["Skin", "Base", "Flawless", "Silk"],
        "EYELINER": ["Line", "Edge", "Define", "Wing"],
        "EYESHADOW": ["Shadow", "Shimmer", "Sparkle"],
        "HIGHLIGHTER": ["Beam", "Radiant", "Glow"],
        "BRONZER": ["Sun", "Bronze", "Warm"],
        "PRIMER": ["Prep", "Prime", "Smooth"],
        "SETTING_SPRAY": ["Set", "Lock", "Fix"]
    }

    # Detect vibe from description
    vibe = "minimal"  # Default vibe
    desc = (packaging_desc or "").lower()

    if any(word in desc for word in ["luxury", "gold", "elegant", "premium", "black"]):
        vibe = "luxury"
    elif any(word in desc for word in ["cute", "pink", "heart", "kawaii", "pastel"]):
        vibe = "cute"
    elif any(word in desc for word in ["natural", "organic", "green", "eco"]):
        vibe = "natural"
    elif any(word in desc for word in ["bold", "dark", "edgy", "red", "strong"]):
        vibe = "bold"

    # Select random words from appropriate lists
    vibe_list = vibe_words.get(vibe, vibe_words["minimal"])
    product_list = product_words.get(product_type, ["Beauty", "Glow", "Luxe"])

    return f"{random.choice(vibe_list)} {random.choice(product_list)}"


# =============================================================================
# 11. HELPER FUNCTIONS - ORDER STATUS
# =============================================================================

def calculate_simulated_status(order_date, current_status):
    """
    Calculate simulated delivery status based on time since order.
    Used for demo/display purposes.
    
    Timeline:
        - 0-3 days: Processing
        - 3-7 days: Shipped
        - 7+ days: Delivered
    
    Args:
        order_date: DateTime when order was placed
        current_status: Current order status string
    
    Returns:
        dict: Status info containing:
            - status: Status text
            - icon: Emoji icon
            - color: Color name
    """
    # Default if no order date
    if not order_date:
        return {
            "status": "Processing",
            "icon": "🔵",
            "color": "blue"
        }

    # If status is already final, return appropriate status
    if current_status in ["DELIVERED", "CANCELLED"]:
        if current_status == "DELIVERED":
            return {
                "status": "Delivered",
                "icon": "🟢",
                "color": "green"
            }
        else:
            return {
                "status": "Cancelled",
                "icon": "🔴",
                "color": "red"
            }

    # Calculate days since order
    now = datetime.utcnow()
    days_since = (now - order_date).days

    # Determine status based on days
    if days_since < 3:
        return {
            "status": "Processing",
            "icon": "🔵",
            "color": "blue"
        }
    elif days_since < 7:
        return {
            "status": "Shipped",
            "icon": "🟡",
            "color": "yellow"
        }
    else:
        return {
            "status": "Delivered",
            "icon": "🟢",
            "color": "green"
        }
    
    # =============================================================================
# 12. ROUTES - PAGES (GET)
# =============================================================================

# -----------------------------------------------------------------------------
# 12.1 Database Health Check
# -----------------------------------------------------------------------------

@app.route("/dbcheck")
def dbcheck():
    """
    Health check endpoint to verify database connection.
    
    Returns:
        str: Success message with DB version or error message
    """
    try:
        with db.engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
        return f"✅ Database Connected Successfully!<br>{version}"
    except Exception as e:
        return f"❌ Database Connection Failed:<br>{e}"


# -----------------------------------------------------------------------------
# 12.2 Home & Main Pages
# -----------------------------------------------------------------------------

@app.route("/", strict_slashes=False)
def home():
    """Redirect root URL to login page."""
    return redirect(url_for("login_page"), code=302)


@app.route("/index", strict_slashes=False)
def home_index():
    """Main homepage after login."""
    return render_template("index.html")


# -----------------------------------------------------------------------------
# 12.3 Design & AI Pages
# -----------------------------------------------------------------------------

@app.route("/design-options", strict_slashes=False)
def design_options():
    """Design options selection page."""
    return render_template("designOptions.html")


@app.route("/AI", methods=["GET"])
def ai_page():
    """AI packaging design page."""
    return render_template("AI.html", cart_count=get_cart_count())


@app.route("/smartPicks", strict_slashes=False)
def smartPicks_page():
    """AI-powered product recommendations page."""
    return render_template("smartPicks.html", cart_count=get_cart_count())


# -----------------------------------------------------------------------------
# 12.4 Cost Sharing & Shipping Pages
# -----------------------------------------------------------------------------

@app.route("/costSharing", methods=["GET"])
def costSharing_page():
    """Cost sharing groups page."""
    return render_template("costSharing.html")


@app.route("/shipment", methods=["GET"])
def shipment_page():
    """Shipment tracking page."""
    return render_template("shipment.html")


# -----------------------------------------------------------------------------
# 12.5 Invoice Pages
# -----------------------------------------------------------------------------

@app.route("/invoice", methods=["GET"])
def invoice_page():
    """Solo order invoice page."""
    return render_template("invoice.html")


@app.route("/invoiceShared", methods=["GET"])
def invoiceShared_page():
    """Shared shipping invoice page."""
    return render_template("invoiceShared.html")


# -----------------------------------------------------------------------------
# 12.6 Payment Page
# -----------------------------------------------------------------------------

@app.route("/payment", strict_slashes=False)
def payment_page():
    """Solo payment page."""
    return render_template("payment.html")


# -----------------------------------------------------------------------------
# 12.7 Info Pages
# -----------------------------------------------------------------------------

@app.route("/about")
def about_page():
    """About us page."""
    return render_template("about.html")


@app.route("/help", methods=["GET"], strict_slashes=False)
def help_page():
    """Help and support page."""
    return render_template("help.html")


# -----------------------------------------------------------------------------
# 12.8 Account Page
# -----------------------------------------------------------------------------

@app.route("/account", methods=["GET"], strict_slashes=False)
def account_page():
    """
    User account/profile page.
    Loads profile data from session.
    """
    profile = session.get("profile", {
        "firstName": "",
        "lastName": "",
        "phone": "",
        "address": ""
    })
    return render_template("account.html", profile=profile)


# =============================================================================
# 13. ROUTES - CART PAGE
# =============================================================================

@app.route("/cart", strict_slashes=False)
def cart_page():
    """
    Display shopping cart page.
    Loads products from session and fetches images from database.
    
    Returns:
        Rendered cart.html template with:
            - items: List of cart items with details
            - subtotal: Products total before fees
            - total_qty: Total quantity of items
            - shipping: Shipping costs
            - tax: Tax amount
            - grand_total: Final total
    """
    cart = get_cart()
    items = []

    print(f"[CART] Loading cart: {len(cart)} items")

    # Process each cart item
    for product_id, cart_item in cart.items():
        try:
            # Try to get product from database for image
            product = Product.query.filter_by(id=product_id).first()

            if product:
                # Product found in database
                item_data = {
                    "id": product_id,
                    "name": cart_item.get("name") or product.name,
                    "price": cart_item.get("price") or float(product.price_sar or 0),
                    "qty": cart_item.get("qty", 1),
                    "image": product.image_primary if product.image_primary else None,
                }
            else:
                # Product not in database, use cart data only
                item_data = {
                    "id": product_id,
                    "name": cart_item.get("name", "Product"),
                    "price": cart_item.get("price", 0),
                    "qty": cart_item.get("qty", 1),
                    "image": None,
                }
                print(f"[CART] Product {product_id} not found in DB")

            items.append(item_data)

        except Exception as e:
            print(f"[CART] Error loading product {product_id}: {e}")
            # Fallback to cart data on error
            items.append({
                "id": product_id,
                "name": cart_item.get("name", "Product"),
                "price": cart_item.get("price", 0),
                "qty": cart_item.get("qty", 1),
                "image": None,
            })

    # Calculate totals
    summary = calculate_cart_summary(cart)

    print(f"[CART] Summary: {len(items)} items, Subtotal: {summary['subtotal']} SAR")

    return render_template(
        "cart.html",
        items=items,
        subtotal=summary["subtotal"],
        total_qty=summary["total_qty"],
        shipping=summary["shipping"],
        tax=summary["tax"],
        total=summary["subtotal"],
        grand_total=summary["total"]
    )


# =============================================================================
# 14. ROUTES - AUTHENTICATION
# =============================================================================

# -----------------------------------------------------------------------------
# 14.1 Login
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/login", methods=["GET", "POST"], strict_slashes=False)
def login_page():
    """
    Handle user login.
    
    GET: Display login form
    POST: Validate credentials and create session
    
    Returns:
        GET: Rendered login.html template
        POST: Redirect to phone verification or login page with error
    """
    # Show login form
    if request.method == "GET":
        return render_template("login.html")

    # Process login
    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()

    # Validate input
    if not email or not password:
        flash("Please enter both email and password.", "error")
        return redirect(url_for("login_page"))

    # Find user by email
    user = Account.query.filter_by(email=email).first()

    if not user:
        flash("You don't have an account, please Sign up first.", "error")
        return redirect(url_for("login_page"))

    # Verify password
    if not check_password_hash(user.password_hash, password):
        flash("Incorrect password, please try again.", "error")
        return redirect(url_for("login_page"))

    # Create session
    session.clear()
    session["user_id"] = int(user.id)
    session["username"] = user.username

    # Load cart from database
    load_cart_from_db(user.id)

    flash("Logged in successfully", "success")
    return redirect(url_for("phone_login"))


# -----------------------------------------------------------------------------
# 14.2 Signup
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/signup", methods=["GET", "POST"], strict_slashes=False)
def signup():
    """
    Handle user registration.
    
    GET: Display signup form
    POST: Create new account with validation
    
    Returns:
        GET: Rendered signup.html template
        POST: Redirect to login page on success or signup page with error
    """
    # Show signup form
    if request.method == "GET":
        return render_template("signup.html")

    # Get form data
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip() or None
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or password

    # Validate required fields
    if not username or not email or not password:
        flash("Please fill username, email, and password.", "error")
        return redirect(url_for("signup"))

    # Validate password length
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("signup"))

    # Validate password match
    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("signup"))

    # Create user account
    pwd_hash = generate_password_hash(password)
    user = Account(
        username=username,
        email=email,
        phone_number=phone,
        password_hash=pwd_hash
    )

    db.session.add(user)

    try:
        db.session.flush()
        ensure_profile_for(user, first_name=username)
        db.session.commit()
        flash("Account created! Please login.", "success")
        return redirect(url_for("login_page"))
    except IntegrityError:
        db.session.rollback()
        flash("Username or email already exists.", "error")
        return redirect(url_for("signup"))
    except Exception:
        db.session.rollback()
        flash("Unexpected error.", "error")
        return redirect(url_for("signup"))


# -----------------------------------------------------------------------------
# 14.3 Logout
# -----------------------------------------------------------------------------

@app.route("/logout", methods=["GET"], strict_slashes=False, endpoint="logout")
def logout():
    """
    Log out user and clear session.
    Cart data is preserved in database for next login.
    
    Returns:
        Redirect to login page
    """
    user_id = session.get("user_id")
    if user_id:
        print(f"[AUTH] User {user_id} logging out, cart preserved in database")

    session.clear()
    return redirect(url_for("login_page"))


# =============================================================================
# 15. ROUTES - PHONE VERIFICATION (OTP)
# =============================================================================

# -----------------------------------------------------------------------------
# 15.1 Phone Login Page
# -----------------------------------------------------------------------------

@app.get("/phone_login")
def phone_login():
    """
    Phone number entry page for 2FA.
    
    Returns:
        Rendered phone_login.html template
    """
    return render_template("phone_login.html")


# -----------------------------------------------------------------------------
# 15.2 Verify Page
# -----------------------------------------------------------------------------

@app.get("/verify")
def verify_page():
    """
    OTP code entry page.
    Redirects to phone_login if no phone in session.
    
    Returns:
        Rendered verify.html template with masked phone number
    """
    phone_full = session.get("phone_full")
    if not phone_full:
        return redirect(url_for("phone_login"))

    # Mask phone number for display (show last 2 digits only)
    masked = phone_full[:-4] + "**"
    return render_template("verify.html", phone_mask=masked)


# -----------------------------------------------------------------------------
# 15.3 Send OTP
# -----------------------------------------------------------------------------

@csrf.exempt
@app.post("/send_otp")
def send_otp():
    """
    Send OTP code to user's phone via SMS.
    Validates KSA phone format (05xxxxxxxx or 5xxxxxxxx).
    
    Returns:
        Redirect to verify page on success or phone_login on error
    """
    raw_phone = (request.form.get("phone") or "").strip()

    # Normalize phone number to +966 format
    digits = re.sub(r"\D+", "", raw_phone)

    # Remove country code if present
    if digits.startswith("966"):
        digits = digits[3:]

    # Remove leading zero if present
    if digits.startswith("05") and len(digits) == 10:
        digits = digits[1:]

    # Validate format (must start with 5 and be 9 digits)
    if digits.startswith("5") and len(digits) == 9:
        phone_full = f"+966{digits}"
    else:
        flash("Phone number format is invalid. Use 05xxxxxxxx.", "error")
        return redirect(url_for("phone_login"))

    # Save phone to session
    session["phone_full"] = phone_full

    # Dev mode - skip actual SMS
    if not USE_TWILIO:
        print(f"[DEV MODE] Would send OTP to: {phone_full}")
        flash("DEV mode: set USE_TWILIO=1 to send real SMS.", "success")
        return redirect(url_for("verify_page"))

    # Send OTP via Twilio
    try:
        twilio_client.verify.v2.services(VERIFY_SID).verifications.create(
            to=phone_full,
            channel="sms"
        )
        flash("OTP sent via SMS", "success")
        return redirect(url_for("verify_page"))
    except Exception as e:
        print(f"[Twilio ERROR] {repr(e)}")
        flash("Failed to send SMS. Check console/logs.", "error")
        return redirect(url_for("phone_login"))


# -----------------------------------------------------------------------------
# 15.4 Verify OTP
# -----------------------------------------------------------------------------

@csrf.exempt
@app.post("/verify")
def verify_submit():
    """
    Verify OTP code entered by user.
    On success, enables 2FA for the account.
    
    Returns:
        Redirect to home on success or verify page on error
    """
    # Check if user is logged in
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    code = (request.form.get("code") or "").strip()
    phone_full = session.get("phone_full")

    # Check if phone is in session
    if not phone_full:
        flash("Session expired. Send OTP again.", "error")
        return redirect(url_for("phone_login"))

    # Verify the code
    try:
        if USE_TWILIO:
            # Production: Verify with Twilio
            check = twilio_client.verify.v2.services(VERIFY_SID).verification_checks.create(
                to=phone_full,
                code=code
            )
            if check.status != "approved":
                flash("Incorrect OTP code", "error")
                return redirect(url_for("verify_page"))
        else:
            # Dev mode: Check against session OTP
            expected = session.get("otp")
            if not expected or code != expected:
                flash("Incorrect OTP code", "error")
                return redirect(url_for("verify_page"))
    except Exception as e:
        print(f"[Verify ERROR] {repr(e)}")
        flash("Verification failed. Try again.", "error")
        return redirect(url_for("verify_page"))

    # Update user account with verified phone
    user = Account.query.get(session["user_id"])
    if user:
        # Update phone number
        if user.phone_number != phone_full:
            user.phone_number = phone_full

        # Enable 2FA
        sec = AccountSecurity.query.filter_by(account_id=user.id).first()
        if not sec:
            sec = AccountSecurity(account_id=user.id)
            db.session.add(sec)
        sec.is_2fa_enabled = True
        sec.two_factor_method = "sms"
        db.session.commit()

    # Clear OTP session data
    session.pop("phone_full", None)
    session.pop("otp", None)

    flash("Phone verified", "success")
    return redirect(url_for("home_index"))


# -----------------------------------------------------------------------------
# 15.5 Resend OTP
# -----------------------------------------------------------------------------

@csrf.exempt
@app.post("/resend_otp")
def resend_otp():
    """
    Resend OTP code to user's phone.
    
    Returns:
        Redirect to verify page
    """
    phone_full = session.get("phone_full")
    if not phone_full:
        return redirect(url_for("phone_login"))

    try:
        if USE_TWILIO:
            # Production: Send via Twilio
            twilio_client.verify.v2.services(VERIFY_SID).verifications.create(
                to=phone_full,
                channel="sms"
            )
            flash("A new OTP has been sent.", "success")
        else:
            # Dev mode: Generate random code
            otp = f"{random.randint(0, 999999):06d}"
            session["otp"] = otp
            print(f"[DEV RESEND] OTP -> {otp} to {phone_full}")
            flash("DEV mode: new code printed in console.", "success")
    except Exception as e:
        print(f"[Resend ERROR] {repr(e)}")
        flash("Failed to resend code. Try again.", "error")

    return redirect(url_for("verify_page"))


# =============================================================================
# 16. ROUTES - PROFILE
# =============================================================================

# -----------------------------------------------------------------------------
# 16.1 Save Profile
# -----------------------------------------------------------------------------

@app.route("/profile/save", methods=["POST"], strict_slashes=False)
def profile_save():
    """
    Save user profile data.
    Validates CSRF token, phone format, and required fields.
    
    Accepts:
        - JSON or form data with firstName, lastName, phone, address
    
    Returns:
        JSON response or redirect based on request type
    """
    # Get CSRF token from multiple sources
    csrf_token = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
        or (
            (request.get_json(silent=True) or {}).get("csrf_token")
            if request.is_json
            else None
        )
    )

    # Validate CSRF token
    try:
        if not csrf_token:
            raise CSRFError("Missing CSRF token.")
        validate_csrf(csrf_token)
    except Exception as e:
        if request.is_json:
            return jsonify({"ok": False, "error": "CSRF_ERROR", "message": str(e)}), 400
        flash("CSRF token invalid. Try again.", "error")
        return redirect(url_for("account_page"))

    # Get form data
    data = request.get_json(silent=True) or request.form.to_dict()
    first = (data.get("firstName") or "").strip()
    last = (data.get("lastName") or "").strip()
    addr = (data.get("address") or "").strip()
    raw_phone = (data.get("phone") or "").strip()
    digits = re.sub(r"\D+", "", raw_phone)

    # Validate phone (KSA format: 5xxxxxxxx - 9 digits starting with 5)
    if not re.fullmatch(r"5\d{8}", digits or ""):
        msg = "Phone must be 9 digits and start with 5 (KSA)."
        if request.is_json:
            return jsonify({"ok": False, "error": "PHONE_INVALID", "message": msg}), 400
        flash(msg, "error")
        return redirect(url_for("account_page"))

    # Validate required fields
    if not first or not last:
        msg = "First and last name are required."
        if request.is_json:
            return jsonify({"ok": False, "error": "NAME_REQUIRED", "message": msg}), 400
        flash(msg, "error")
        return redirect(url_for("account_page"))

    # Save to session
    session["profile"] = {
        "firstName": first,
        "lastName": last,
        "phone": digits,
        "address": addr
    }

    # Return response
    if request.is_json:
        return jsonify({
            "ok": True,
            "message": "Profile saved successfully",
            "profile": session["profile"]
        }), 200

    flash("Profile saved", "success")
    return redirect(url_for("account_page"))


# -----------------------------------------------------------------------------
# 16.2 Contact Form
# -----------------------------------------------------------------------------

@app.route("/contact", methods=["POST"], strict_slashes=False)
def submit_contact():
    """
    Handle contact form submission.
    
    Note: Form data available but not stored.
    Can add email/DB storage later.
    
    Returns:
        Redirect to help page with success message
    """
    # Form data available for future use:
    # first = request.form.get("first_name")
    # last = request.form.get("last_name")
    # email = request.form.get("email")
    # msg = request.form.get("message")

    flash("Message received", "success")
    return redirect(url_for("help_page"))
# =============================================================================
# 17. API - CART OPERATIONS
# =============================================================================

# -----------------------------------------------------------------------------
# 17.1 Add to Cart
# -----------------------------------------------------------------------------

@csrf.exempt
@app.post("/cart/add")
def cart_add():
    """
    Add product to cart or increment quantity if exists.
    
    Accepts JSON or form data with:
        - id/product_id/productId/sku: Product identifier
        - name/title/product_name: Product name
        - price/amount/sar: Product price
    
    Returns:
        JSON: {ok, cart_count, cart_total, total_qty, shipping, tax, grand_total}
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    # Get product ID from various possible field names
    product_id = str(
        data.get("id")
        or data.get("product_id")
        or data.get("productId")
        or data.get("sku")
        or ""
    ).strip()

    # Get product name from various possible field names
    name = (
        data.get("name")
        or data.get("title")
        or data.get("product_name")
        or ""
    ).strip()

    # Get price from various possible field names
    raw_price = data.get("price") or data.get("amount") or data.get("sar") or 0
    try:
        price = float(raw_price)
    except (TypeError, ValueError):
        price = 0.0

    # Validate product ID
    if not product_id:
        return jsonify({"ok": False, "error": "MISSING_ID"}), 400

    # Get current cart
    cart = get_cart()

    # Update cart
    if product_id in cart:
        # Increment quantity for existing item
        cart[product_id]["qty"] += 1
        print(f"[CART] Increased qty for {product_id}")
    else:
        # Add new item
        cart[product_id] = {
            "id": product_id,
            "name": name or "AI Product",
            "price": price,
            "image": f"DB:{product_id}",  # Marker to load from DB
            "qty": 1,
        }
        print(f"[CART] Added new item: {product_id}")

    # Save cart and calculate summary
    save_cart(cart)
    summary = calculate_cart_summary(cart)

    return jsonify({
        "ok": True,
        "cart_count": len(cart),
        "cart_total": summary["subtotal"],
        "cart_subtotal": summary["subtotal"],
        "total_qty": summary["total_qty"],
        "shipping": summary["shipping"],
        "tax": summary["tax"],
        "grand_total": summary["total"]
    })


# -----------------------------------------------------------------------------
# 17.2 Remove from Cart
# -----------------------------------------------------------------------------

@csrf.exempt
@app.post("/cart/remove")
def cart_remove():
    """
    Remove product from cart completely.
    
    Accepts JSON with:
        - id: Product identifier to remove
    
    Returns:
        JSON: {ok, cart_count, cart_total, total_qty, shipping, tax, grand_total}
    """
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("id") or "").strip()

    # Validate product ID
    if not product_id:
        return jsonify({"ok": False, "error": "MISSING_ID"}), 400

    # Get current cart
    cart = get_cart()

    # Remove item if exists
    if product_id in cart:
        del cart[product_id]
        print(f"[CART] Removed {product_id}")
    else:
        print(f"[CART] Product {product_id} not in cart")

    # Save cart and calculate summary
    save_cart(cart)
    summary = calculate_cart_summary(cart)

    return jsonify({
        "ok": True,
        "cart_count": len(cart),
        "cart_total": summary["subtotal"],
        "cart_subtotal": summary["subtotal"],
        "total_qty": summary["total_qty"],
        "shipping": summary["shipping"],
        "tax": summary["tax"],
        "grand_total": summary["total"]
    })


# -----------------------------------------------------------------------------
# 17.3 Update Cart Quantity
# -----------------------------------------------------------------------------

@csrf.exempt
@app.post("/cart/update_qty")
def cart_update_qty():
    """
    Increment or decrement item quantity in cart.
    If quantity reaches 0, item is removed from cart.
    
    Accepts JSON with:
        - id: Product identifier
        - action: "inc" to increase, "dec" to decrease
    
    Returns:
        JSON: {ok, removed, item_qty, cart_count, cart_total, ...}
    """
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("id") or "").strip()
    action = (data.get("action") or "").strip()

    # Validate input
    if not product_id or action not in {"inc", "dec"}:
        return jsonify({"ok": False, "error": "BAD_REQUEST"}), 400

    # Get current cart
    cart = get_cart()

    # Check if product exists in cart
    if product_id not in cart:
        return jsonify({"ok": False, "error": "NOT_FOUND"}), 404

    item = cart[product_id]
    removed = False

    # Update quantity based on action
    if action == "inc":
        item["qty"] += 1
    elif action == "dec":
        item["qty"] -= 1
        # Remove item if quantity reaches 0
        if item["qty"] <= 0:
            del cart[product_id]
            removed = True

    # Save cart and calculate summary
    save_cart(cart)
    summary = calculate_cart_summary(cart)

    return jsonify({
        "ok": True,
        "removed": removed,
        "item_qty": 0 if removed else item["qty"],
        "cart_count": len(cart),
        "cart_total": summary["subtotal"],
        "cart_subtotal": summary["subtotal"],
        "total_qty": summary["total_qty"],
        "shipping": summary["shipping"],
        "tax": summary["tax"],
        "grand_total": summary["total"]
    })


# -----------------------------------------------------------------------------
# 17.4 Get Cart Count
# -----------------------------------------------------------------------------

@app.route("/cart/count", methods=["GET"])
def cart_count():
    """
    Get total quantity of items in cart.
    
    Returns:
        JSON: {count: int}
    """
    cart = get_cart()
    count = sum(item.get("qty", 1) for item in cart.values())
    return jsonify({"count": count})


# =============================================================================
# 18. API - AI GENERATION
# =============================================================================

# -----------------------------------------------------------------------------
# 18.1 Generate AI Packaging
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/ai/generate", methods=["POST"])
def ai_generate_packaging():
    """
    Generate AI packaging design using gpt-image-1.
    
    Accepts JSON with:
        - prompt: Design prompt text (required)
        - context: Optional context (e.g., "custom-packaging")
        - vibe: Optional style (e.g., "luxury", "cute")
    
    Returns:
        JSON: {ok, image_url, product: {id, name, price_sar, size}}
    """
    try:
        data = request.get_json(silent=True) or {}
        prompt_raw = (data.get("prompt") or "").strip()

        # Validate prompt
        if not prompt_raw:
            return jsonify({"ok": False, "message": "Empty prompt"}), 400

        # Check authentication
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "message": "Please login"}), 401

        print(f"[AI] Prompt received: {prompt_raw[:100]}...")

        # Generate image with gpt-image-1
        result = OpenAI_Client.images.generate(
            model="gpt-image-1",
            prompt=prompt_raw,
            size="1024x1024",
        )

        b64_data = result.data[0].b64_json
        image_url = f"data:image/png;base64,{b64_data}"

        # -----------------------------------------------------------------
        # Extract Product Attributes from Prompt
        # -----------------------------------------------------------------

        prompt_upper = prompt_raw.upper()
        prompt_lower = prompt_raw.lower()

        # Extract product type
        product_type = "LIPSTICK"  # Default
        product_types = [
            "LIPSTICK", "MASCARA", "BLUSH", "FOUNDATION", "EYELINER",
            "EYESHADOW", "HIGHLIGHTER", "BRONZER", "PRIMER"
        ]
        for pt in product_types:
            if pt in prompt_upper:
                product_type = pt
                break
        if "SETTING" in prompt_upper:
            product_type = "SETTING_SPRAY"

        # Extract formula type
        formula = "CREAM"  # Default
        formula_keywords = {
            "water": "WATER",
            "oil": "OIL",
            "gel": "GEL",
            "powder": "POWDER",
            "silicone": "SILICONE"
        }
        for keyword, value in formula_keywords.items():
            if keyword in prompt_lower:
                formula = value
                break

        # Extract coverage level
        coverage = "MEDIUM"  # Default
        if "sheer" in prompt_lower:
            coverage = "SHEER"
        elif "full" in prompt_lower:
            coverage = "FULL"

        # Extract finish type
        finish = "NATURAL"  # Default
        finish_keywords = {
            "matte": "MATTE",
            "dewy": "DEWY",
            "glowy": "GLOWY",
            "satin": "SATIN"
        }
        for keyword, value in finish_keywords.items():
            if keyword in prompt_lower:
                finish = value
                break

        # Extract skin type
        skin_type = "NORMAL"  # Default
        skin_keywords = {
            "oily": "OILY",
            "dry": "DRY",
            "combination": "COMBINATION",
            "sensitive": "SENSITIVE"
        }
        for keyword, value in skin_keywords.items():
            if keyword in prompt_lower:
                skin_type = value
                break

        # -----------------------------------------------------------------
        # Calculate Dynamic Price
        # -----------------------------------------------------------------

        base_price = BASE_PRICES.get(product_type, 50)
        calculated_price = (
            base_price
            * FORMULA_MULT.get(formula, 1)
            * COVERAGE_MULT.get(coverage, 1)
            * FINISH_MULT.get(finish, 1)
            * SKIN_MULT.get(skin_type, 1)
        )

        # Round to nearest 5, cap at MAX_PRICE
        final_price = min(round(calculated_price / 5) * 5, MAX_PRICE)
        product_size = PRODUCT_SIZES.get(product_type, "10g")

        print(f"[AI] Price: base={base_price}, calculated={calculated_price:.2f}, final={final_price}")
        print(f"[AI] Product: {product_type}, Size: {product_size}")

        # -----------------------------------------------------------------
        # Extract Packaging Description
        # -----------------------------------------------------------------

        packaging_desc = ""
        if "Packaging:" in prompt_raw:
            packaging_desc = prompt_raw.split("Packaging:")[-1].split(".")[0].strip()

        # Generate creative product name
        product_name = generate_product_name(packaging_desc, product_type, finish)
        print(f"[AI] Generated name: {product_name}")

        # -----------------------------------------------------------------
        # Save Product to Database
        # -----------------------------------------------------------------

        product = Product(
            owner_user_id=user_id,
            name=product_name,
            sku=f"AI-{user_id}-{int(datetime.utcnow().timestamp())}-{random.randint(1000, 9999)}",
            description=prompt_raw,
            image_primary=image_url,
            origin=ProductOriginEnum.AI,
            visibility=ProductVisibilityEnum.PRIVATE,
            status=ProductStatusEnum.DRAFT,
            price_sar=float(final_price),
            base_price_sar=float(base_price),
            complexity_factor=1,
            category_multiplier=1,
            discount_percent=0,
            final_price_sar=float(final_price),
            category="AI-CUSTOM",
            brand="BeautyFlow AI",
        )

        db.session.add(product)
        db.session.flush()

        # -----------------------------------------------------------------
        # Save AI Session & Generation Record
        # -----------------------------------------------------------------

        # Get or create AI session
        session_obj = AISession.query.filter_by(
            account_id=user_id,
            status="OPEN"
        ).order_by(AISession.id.desc()).first()

        if not session_obj:
            session_obj = AISession(account_id=user_id, status="OPEN")
            db.session.add(session_obj)
            db.session.flush()

        # Save generation record
        gen = AIGeneration(
            session_id=session_obj.id,
            product_id=product.id,
            image_url=image_url,
            prompt_json={
                "prompt": prompt_raw,
                "packaging_desc": packaging_desc
            },
            meta_json={
                "model": "dall-e-2",
                "context": data.get("context"),
                "vibe": data.get("vibe"),
                "specs": {
                    "product_type": product_type,
                    "formula": formula,
                    "coverage": coverage,
                    "finish": finish,
                    "skin_type": skin_type
                }
            }
        )
        db.session.add(gen)
        db.session.commit()

        print("[AI] Product saved to database successfully")

        return jsonify({
            "ok": True,
            "image_url": image_url,
            "product": {
                "id": product.id,
                "name": product.name,
                "price_sar": final_price,
                "size": product_size
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        print("[AI] ERROR:")
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": "OPENAI_ERROR",
            "message": str(e)
        }), 500


# -----------------------------------------------------------------------------
# 18.2 Update Product Name
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/ai/product/update-name", methods=["POST"])
def ai_update_product_name():
    """
    Update product name in database.
    
    Accepts JSON with:
        - product_id: Product identifier (required)
        - name: New product name (required)
    
    Returns:
        JSON: {ok, message, product_id, old_name, new_name}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        product_id = data.get("product_id")
        new_name = (data.get("name") or "").strip()

        # Validate input
        if not product_id or not new_name:
            return jsonify({"ok": False, "message": "Product ID and name required"}), 400

        # Find product (owned by user first, then any)
        product = Product.query.filter_by(id=product_id, owner_user_id=user_id).first()

        if not product:
            product = Product.query.filter_by(id=product_id).first()
            if not product:
                return jsonify({"ok": False, "message": "Product not found"}), 404

        # Update name
        old_name = product.name
        product.name = new_name
        db.session.commit()

        print(f"[AI] Product {product_id} name: '{old_name}' -> '{new_name}'")

        return jsonify({
            "ok": True,
            "message": "Name updated",
            "product_id": product_id,
            "old_name": old_name,
            "new_name": new_name
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": str(e)}), 500


# =============================================================================
# 19. API - AI HISTORY
# =============================================================================

@app.route("/ai/history", methods=["GET"])
def ai_history():
    """
    Get user's last 20 AI-generated products.
    
    Returns:
        JSON: {ok, history: [{id, name, image_url, created_at, price_sar, size}]}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Not logged in"}), 401

    try:
        # Query user's AI-generated products
        products = Product.query.filter_by(
            owner_user_id=user_id,
            origin=ProductOriginEnum.AI
        ).order_by(Product.created_at.desc()).limit(20).all()

        # Build history list
        history = [{
            "id": p.id,
            "name": p.name,
            "image_url": p.image_primary,
            "created_at": p.created_at.isoformat(),
            "price_sar": float(p.price_sar or 0),
            "size": "10g"
        } for p in products]

        return jsonify({"ok": True, "history": history})

    except Exception as e:
        print(f"[AI] Error in history: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# =============================================================================
# 20. API - FAVORITES (WISHLIST)
# =============================================================================

# -----------------------------------------------------------------------------
# 20.1 Add to Favorites
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/ai/favorites/add", methods=["POST"])
def ai_favorites_add():
    """
    Add product to user's favorites/wishlist.
    
    Accepts JSON with:
        - product_id: Product identifier (required)
    
    Returns:
        JSON: {ok, message, already_exists?}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json()
        product_id = data.get("product_id")

        if not product_id:
            return jsonify({"ok": False, "message": "Product ID is required"}), 400

    except Exception as e:
        return jsonify({"ok": False, "message": "Invalid request"}), 400

    # Verify product exists
    product = Product.query.filter_by(id=product_id).first()
    if not product:
        return jsonify({"ok": False, "message": "Product not found"}), 404

    # Get or create wishlist for user
    wishlist = Wishlist.query.filter_by(account_id=user_id).first()
    if not wishlist:
        wishlist = Wishlist(account_id=user_id)
        db.session.add(wishlist)
        db.session.flush()

    # Check if already in favorites
    existing = WishlistItem.query.filter_by(
        wishlist_id=wishlist.id,
        product_id=product_id
    ).first()

    if existing:
        return jsonify({
            "ok": True,
            "message": "Already in favorites",
            "already_exists": True
        })

    # Add to favorites
    try:
        item = WishlistItem(wishlist_id=wishlist.id, product_id=product_id)
        db.session.add(item)
        db.session.commit()
        return jsonify({"ok": True, "message": "Added to favorites successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": f"Database error: {str(e)}"}), 500


# -----------------------------------------------------------------------------
# 20.2 Get Favorites
# -----------------------------------------------------------------------------

@app.route("/ai/favorites", methods=["GET"])
def ai_favorites_get():
    """
    Get user's favorite products.
    
    Returns:
        JSON: {ok, favorites: [{id, name, image_url, price_sar, created_at}]}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        # Get user's wishlist
        wishlist = Wishlist.query.filter_by(account_id=user_id).first()

        if not wishlist:
            return jsonify({"ok": True, "favorites": []})

        # Get wishlist items
        items = WishlistItem.query.filter_by(wishlist_id=wishlist.id).all()

        # Build favorites list with product details
        favorites = []
        for item in items:
            product = Product.query.filter_by(id=item.product_id).first()
            if product:
                favorites.append({
                    "id": product.id,
                    "name": product.name,
                    "image_url": product.image_primary,
                    "price_sar": float(product.price_sar or 0),
                    "created_at": product.created_at.isoformat() if product.created_at else None
                })

        return jsonify({"ok": True, "favorites": favorites})

    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 20.3 Remove from Favorites
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/ai/favorites/remove", methods=["POST"])
def ai_favorites_remove():
    """
    Remove product from favorites.
    
    Accepts JSON with:
        - product_id: Product identifier (required)
    
    Returns:
        JSON: {ok, message}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json()
        product_id = data.get("product_id")

        if not product_id:
            return jsonify({"ok": False, "message": "Product ID is required"}), 400

        # Get user's wishlist
        wishlist = Wishlist.query.filter_by(account_id=user_id).first()
        if not wishlist:
            return jsonify({"ok": False, "message": "Wishlist not found"}), 404

        # Find item in wishlist
        item = WishlistItem.query.filter_by(
            wishlist_id=wishlist.id,
            product_id=product_id
        ).first()

        if not item:
            return jsonify({"ok": False, "message": "Item not in favorites"}), 404

        # Remove item
        db.session.delete(item)
        db.session.commit()

        return jsonify({"ok": True, "message": "Removed from favorites"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": str(e)}), 500


# =============================================================================
# 21. API - PRODUCTS
# =============================================================================

# -----------------------------------------------------------------------------
# 21.1 Get Product Image
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/products/<int:product_id>/image", methods=["GET"])
def get_product_image(product_id):
    """
    Get product image from database.
    
    Args:
        product_id: Product identifier (URL parameter)
    
    Returns:
        JSON: {ok, product_id, name, image_url, price_sar}
    """
    try:
        product = Product.query.get(product_id)

        if not product:
            return jsonify({
                "ok": False,
                "message": "Product not found",
                "image_url": None
            }), 404

        return jsonify({
            "ok": True,
            "product_id": product_id,
            "name": product.name,
            "image_url": product.image_primary,
            "price_sar": float(product.price_sar or 0)
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "message": str(e),
            "image_url": None
        }), 500


# -----------------------------------------------------------------------------
# 21.2 Get Cart Products with Images
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/cart/products", methods=["GET"])
def get_cart_products_with_images():
    """
    Get cart products with images from database.
    
    Returns:
        JSON: {ok, products: [{id, name, price, qty, image_url}], count}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        cart = get_cart()
        products = []

        # Process each cart item
        for product_id, cart_item in cart.items():
            product = Product.query.filter_by(id=product_id).first()

            if product:
                # Product found in database
                products.append({
                    "id": product_id,
                    "name": product.name or cart_item.get("name", "Product"),
                    "price": float(product.price_sar or cart_item.get("price", 0)),
                    "qty": cart_item.get("qty", 1),
                    "image_url": product.image_primary
                })
            else:
                # Product not in database
                products.append({
                    "id": product_id,
                    "name": cart_item.get("name", "Product"),
                    "price": cart_item.get("price", 0),
                    "qty": cart_item.get("qty", 1),
                    "image_url": None
                })

        return jsonify({
            "ok": True,
            "products": products,
            "count": len(products)
        })

    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500
    
    # =============================================================================
# 22. API - COST SHARING
# =============================================================================

# -----------------------------------------------------------------------------
# 22.1 Load Cost Sharing Data
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/cost-sharing/load", methods=["GET"])
def cost_sharing_load():
    """
    Load cart data for cost sharing page.
    Returns cart summary, solo vs shared pricing, and available cities.
    
    Returns:
        JSON: {
            ok, cart_empty, summary, shipping_solo, shipping_shared,
            potential_savings, savings_percent, in_group, group_id,
            user_status, cities
        }
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        # Get cart and calculate summary
        cart = get_cart()
        cart_summary = calculate_cart_summary(cart)
        cart_empty = cart_summary["total_qty"] == 0
        total_weight = round(cart_summary["total_qty"] * 0.1, 2)

        # Calculate solo shipping (1 member)
        solo_share = calculate_user_share(
            cart_summary["total_qty"],
            cart_summary["subtotal"],
            members_count=1,
            is_group=False
        )

        # Calculate shared shipping (5 members)
        shared_share = calculate_user_share(
            cart_summary["total_qty"],
            cart_summary["subtotal"],
            members_count=5,
            is_group=True
        )

        # Check if user is in a group
        user = Account.query.get(user_id)
        user_status = (user.shipping_status or "").upper() if user else ""
        in_group = bool(
            user and 
            user.shipping_group_id and 
            user_status and 
            user_status != "PAID"
        )

        return jsonify({
            "ok": True,
            "cart_empty": cart_empty,
            "summary": {
                "items_count": cart_summary["items_count"],
                "total_qty": cart_summary["total_qty"],
                "total_weight": total_weight,
                "subtotal": cart_summary["subtotal"],
                "shipping_fee": cart_summary["shipping_fee"],
                "custom_duties": cart_summary["custom_duties"],
                "sfda_fee": cart_summary["sfda_fee"],
                "handling_fee": cart_summary["handling_fee"],
                "shipping": cart_summary["shipping"],
                "tax": cart_summary["tax"],
                "total": cart_summary["total"],
                "tax_rate": 15
            },
            "shipping_solo": {
                "shipping_fee": solo_share["shipping_fee"],
                "per_person": solo_share["shipping_fee"],
                "total_shipping": solo_share["total_shipping"],
                "grand_total": solo_share["grand_total"]
            },
            "shipping_shared": {
                "shipping_fee": shared_share["shipping_fee"],
                "per_person": shared_share["shipping_fee"],
                "total_shipping": shared_share["total_shipping"],
                "grand_total": shared_share["grand_total"],
                "members_count": 5
            },
            "potential_savings": shared_share["savings"],
            "savings_percent": shared_share["savings_percent"],
            "in_group": in_group,
            "group_id": user.shipping_group_id if in_group else None,
            "user_status": user_status,
            "cities": [
                {"key": k, "name": v["name"], "name_en": v["name_en"]}
                for k, v in SUPPORTED_CITIES.items()
            ]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 22.2 Calculate Cost Sharing
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/cost-sharing/calculate", methods=["POST"])
def cost_sharing_calculate():
    """
    Calculate shipping cost for specific city and member count.
    
    Accepts JSON with:
        - city: City key (default: "riyadh")
        - members: Number of members (default: 5)
    
    Returns:
        JSON: {ok, cart_empty, city, shipping, shipping_solo, product_cost, tax, savings, savings_percent}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        city_key = (data.get("city") or "riyadh").lower()
        members_count = data.get("members", 5)

        # Validate city
        if city_key not in SUPPORTED_CITIES:
            return jsonify({"ok": False, "message": "City not supported"}), 400

        # Get cart and city info
        cart = get_cart()
        city_info = SUPPORTED_CITIES[city_key]
        cart_summary = calculate_cart_summary(cart)

        # Handle empty cart
        if cart_summary["total_qty"] == 0:
            return jsonify({
                "ok": True,
                "cart_empty": True,
                "city": {
                    "key": city_key,
                    "name": city_info["name"],
                    "name_en": city_info["name_en"],
                    "delivery_days": f"{city_info['days_min']}-{city_info['days_max']}"
                },
                "shipping": {"per_person": 0, "shipping_fee": 0},
                "shipping_solo": {"per_person": 0, "shipping_fee": 0},
                "product_cost": 0,
                "tax": 0,
                "savings": 0,
                "savings_percent": 0
            })

        # Calculate solo and shared pricing
        solo_share = calculate_user_share(
            cart_summary["total_qty"],
            cart_summary["subtotal"],
            members_count=1,
            is_group=False
        )

        shared_share = calculate_user_share(
            cart_summary["total_qty"],
            cart_summary["subtotal"],
            members_count=members_count,
            is_group=True
        )

        return jsonify({
            "ok": True,
            "cart_empty": False,
            "city": {
                "key": city_key,
                "name": city_info["name"],
                "name_en": city_info["name_en"],
                "delivery_days": f"{city_info['days_min']}-{city_info['days_max']}"
            },
            "shipping": {
                "shipping_fee": shared_share["shipping_fee"],
                "per_person": shared_share["shipping_fee"],
                "total_shipping": shared_share["total_shipping"],
                "grand_total": shared_share["grand_total"],
                "members_count": members_count
            },
            "shipping_solo": {
                "shipping_fee": solo_share["shipping_fee"],
                "per_person": solo_share["shipping_fee"],
                "total_shipping": solo_share["total_shipping"],
                "grand_total": solo_share["grand_total"]
            },
            "product_cost": cart_summary["subtotal"],
            "tax": shared_share["tax"],
            "savings": shared_share["savings"],
            "savings_percent": shared_share["savings_percent"]
        })

    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


# =============================================================================
# 23. API - SHIPPING GROUPS
# =============================================================================

# -----------------------------------------------------------------------------
# 23.1 Get Available Groups
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/available", methods=["GET"])
def groups_available():
    """
    Get available groups to join for a specific city.
    
    Query params:
        - city: City key (default: "riyadh")
    
    Returns:
        JSON: {ok, city, city_name, groups: [...], total_groups}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        city_key = (request.args.get("city") or "riyadh").lower()

        # Validate city
        if city_key not in SUPPORTED_CITIES:
            return jsonify({"ok": False, "message": "City not supported"}), 400

        # Query groups: WAITING status, not full, not expired
        groups_query = db.session.query(
            Account.shipping_group_id,
            Account.shipping_city,
            Account.shipping_expires_at,
            db.func.count(Account.id).label('members_count'),
            db.func.sum(Account.shipping_weight).label('total_weight'),
            db.func.min(Account.shipping_joined_at).label('created_at')
        ).filter(
            Account.shipping_city == city_key,
            Account.shipping_status == "WAITING",
            Account.shipping_group_id.isnot(None),
            Account.shipping_expires_at > datetime.utcnow()
        ).group_by(
            Account.shipping_group_id,
            Account.shipping_city,
            Account.shipping_expires_at
        ).having(
            db.func.count(Account.id) < 5
        ).all()

        # Build groups list
        groups = []
        for g in groups_query:
            # Calculate time remaining
            if g.shipping_expires_at:
                time_left = g.shipping_expires_at - datetime.utcnow()
                days_left = time_left.days
                hours_left = time_left.seconds // 3600
                time_left_str = f"{days_left}d {hours_left}h" if days_left > 0 else f"{hours_left}h"
            else:
                time_left_str = "N/A"

            # Estimate potential savings
            estimated_savings = round((SHIPPING_BASE + 50 * SHIPPING_PER_ITEM) * 0.8, 2)

            groups.append({
                "group_id": g.shipping_group_id,
                "city": city_key,
                "members_count": g.members_count,
                "spots_left": 5 - g.members_count,
                "created_at": g.created_at.isoformat() if g.created_at else None,
                "expires_at": g.shipping_expires_at.isoformat() if g.shipping_expires_at else None,
                "time_left": time_left_str,
                "potential_savings": estimated_savings
            })

        return jsonify({
            "ok": True,
            "city": city_key,
            "city_name": SUPPORTED_CITIES[city_key]["name_en"],
            "groups": groups,
            "total_groups": len(groups)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 23.2 Create Group
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/create", methods=["POST"])
def groups_create():
    """
    Create a new shipping group.
    
    Accepts JSON with:
        - city: City key (required)
    
    Returns:
        JSON: {ok, message, group: {group_id, city, city_name, members_count, ...}}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        city_key = (data.get("city") or "").lower()

        # Validate city
        if not city_key or city_key not in SUPPORTED_CITIES:
            return jsonify({"ok": False, "message": "Please select a valid city"}), 400

        # Get user
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # Check if already in active group
        user_status = (user.shipping_status or "").upper()
        if user.shipping_group_id and user_status in ["WAITING", "READY"]:
            return jsonify({
                "ok": False,
                "message": "You are already in a group. Leave it first.",
                "current_group": user.shipping_group_id
            }), 400

        # Check cart is not empty
        cart = get_cart()
        if not cart:
            return jsonify({
                "ok": False,
                "message": "Your cart is empty. Add products first!"
            }), 400

        cart_summary = calculate_cart_summary(cart)
        if cart_summary["total_qty"] == 0:
            return jsonify({
                "ok": False,
                "message": "Your cart is empty. Add products first!"
            }), 400

        # Prepare cart snapshot
        total_weight = round(cart_summary["total_qty"] * 0.1, 2)
        total_cost = cart_summary["subtotal"]

        cart_items = []
        for product_id, cart_item in cart.items():
            product = Product.query.filter_by(id=product_id).first()
            if product:
                cart_items.append({
                    "id": product_id,
                    "name": product.name,
                    "price": float(product.price_sar or cart_item.get("price", 0)),
                    "qty": cart_item.get("qty", 1)
                })

        # Generate group ID and calculate shipping
        group_id = generate_group_id(city_key)
        user_share = calculate_user_share(
            cart_summary["total_qty"],
            total_cost,
            members_count=1,
            is_group=True
        )

        # Update user record
        user.shipping_group_id = group_id
        user.shipping_city = city_key
        user.shipping_joined_at = datetime.utcnow()
        user.shipping_cart_snapshot = json.dumps(cart_items)
        user.shipping_weight = total_weight
        user.shipping_product_cost = total_cost
        user.shipping_is_creator = True
        user.shipping_expires_at = datetime.utcnow() + timedelta(days=7)
        user.shipping_status = "WAITING"
        user.shipping_extended_count = 0
        user.shipping_cost = user_share["shipping_fee"]

        db.session.commit()

        city_info = SUPPORTED_CITIES[city_key]

        return jsonify({
            "ok": True,
            "message": "Group created successfully!",
            "group": {
                "group_id": group_id,
                "city": city_key,
                "city_name": city_info["name_en"],
                "members_count": 1,
                "your_weight": total_weight,
                "your_product_cost": total_cost,
                "shipping_fee": user_share["shipping_fee"],
                "expires_at": user.shipping_expires_at.isoformat(),
                "delivery_days": f"{city_info['days_min']}-{city_info['days_max']}",
                "status": "WAITING"
            }
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 23.3 Join Group
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/join", methods=["POST"])
def groups_join():
    """
    Join an existing shipping group.
    
    Accepts JSON with:
        - group_id: Group identifier (required)
    
    Returns:
        JSON: {ok, message, group: {group_id, city, members_count, ...}}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        group_id = data.get("group_id")

        # Validate group ID
        if not group_id:
            return jsonify({"ok": False, "message": "Group ID is required"}), 400

        # Get user
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # Check if already in group
        user_status = (user.shipping_status or "").upper()
        if user.shipping_group_id and user_status in ["WAITING", "READY"]:
            return jsonify({"ok": False, "message": "You are already in a group"}), 400

        # Find group members
        group_members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status == "WAITING"
        ).all()

        # Validate group
        if not group_members:
            return jsonify({"ok": False, "message": "Group not found or expired"}), 404

        if len(group_members) >= 5:
            return jsonify({"ok": False, "message": "Group is full"}), 400

        # Check if group expired
        first_member = group_members[0]
        if first_member.shipping_expires_at and first_member.shipping_expires_at < datetime.utcnow():
            return jsonify({"ok": False, "message": "Group has expired"}), 400

        city_key = first_member.shipping_city

        # Check cart is not empty
        cart = get_cart()
        if not cart:
            return jsonify({
                "ok": False,
                "message": "Your cart is empty. Add products first!"
            }), 400

        cart_summary = calculate_cart_summary(cart)
        if cart_summary["total_qty"] == 0:
            return jsonify({
                "ok": False,
                "message": "Your cart is empty. Add products first!"
            }), 400

        # Prepare cart snapshot
        total_weight = round(cart_summary["total_qty"] * 0.1, 2)
        total_cost = cart_summary["subtotal"]

        cart_items = []
        for product_id, cart_item in cart.items():
            product = Product.query.filter_by(id=product_id).first()
            if product:
                cart_items.append({
                    "id": product_id,
                    "name": product.name,
                    "price": float(product.price_sar or cart_item.get("price", 0)),
                    "qty": cart_item.get("qty", 1)
                })

        new_members_count = len(group_members) + 1

        # Calculate new shipping cost
        user_share = calculate_user_share(
            cart_summary["total_qty"],
            total_cost,
            members_count=new_members_count,
            is_group=True
        )

        # Update user record
        user.shipping_group_id = group_id
        user.shipping_city = city_key
        user.shipping_joined_at = datetime.utcnow()
        user.shipping_cart_snapshot = json.dumps(cart_items)
        user.shipping_weight = total_weight
        user.shipping_product_cost = total_cost
        user.shipping_is_creator = False
        user.shipping_expires_at = first_member.shipping_expires_at
        user.shipping_status = "WAITING"
        user.shipping_extended_count = 0
        user.shipping_cost = user_share["shipping_fee"]

        db.session.flush()

        # Update shipping costs for all existing members
        for member in group_members:
            try:
                member_cart = json.loads(member.shipping_cart_snapshot or "[]")
                member_items = (
                    sum(item.get("qty", 1) for item in member_cart)
                    if isinstance(member_cart, list)
                    else 0
                )
            except:
                member_items = int(float(member.shipping_weight or 0) / 0.1)

            member_share = calculate_user_share(
                member_items,
                float(member.shipping_product_cost or 0),
                members_count=new_members_count,
                is_group=True
            )
            member.shipping_cost = member_share["shipping_fee"]

        # If group is now complete (5 members), change everyone to READY
        if new_members_count >= 5:
            for member in group_members:
                member.shipping_status = "READY"
            user.shipping_status = "READY"

        db.session.commit()

        city_info = SUPPORTED_CITIES[city_key]

        return jsonify({
            "ok": True,
            "message": "Joined group successfully!",
            "group": {
                "group_id": group_id,
                "city": city_key,
                "city_name": city_info["name_en"],
                "members_count": new_members_count,
                "your_weight": total_weight,
                "your_shipping_fee": user_share["shipping_fee"],
                "is_complete": new_members_count >= 5,
                "expires_at": user.shipping_expires_at.isoformat() if user.shipping_expires_at else None,
                "status": user.shipping_status
            }
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 23.4 Leave Group
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/leave", methods=["POST"])
def groups_leave():
    """
    Leave current shipping group.
    Only allowed if group is not complete (less than 5 members).
    
    Returns:
        JSON: {ok, message}
    """
    if "user_id" not in session:
        return jsonify({"ok": False, "message": "Not logged in"}), 401

    user_id = session["user_id"]

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # Check if in a group
        if not user.shipping_group_id:
            return jsonify({"ok": False, "message": "You're not in any group"}), 400

        group_id = user.shipping_group_id
        user_status = (user.shipping_status or "").upper()

        # Cannot leave after payment
        if user_status == "PAID":
            return jsonify({
                "ok": False,
                "message": "You have already paid. Cannot leave after payment."
            }), 400

        # Count active members
        active_members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY"])
        ).count()

        # Cannot leave complete group
        if active_members >= 5:
            return jsonify({
                "ok": False,
                "message": "Cannot leave a complete group. All 5 members must proceed together."
            }), 400

        # Clear shipping data
        clear_user_shipping_data(user)
        db.session.commit()

        return jsonify({"ok": True, "message": "Left group successfully"})

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 23.5 Get My Group Details
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/my-group", methods=["GET"])
def groups_my_group():
    """
    Get detailed information about user's current group.
    
    Returns:
        JSON: {ok, in_group, user_confirmed, group, members, your_info, cost_breakdown}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        user_status = (user.shipping_status or "").upper()

        # Check if user is in active group
        if not user.shipping_group_id or user_status not in ["WAITING", "READY"]:
            return jsonify({
                "ok": True,
                "in_group": False,
                "status": user_status or None,
                "message": "You are not in any active group"
            })

        group_id = user.shipping_group_id

        # Get all group members
        members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY", "PAID"])
        ).order_by(Account.shipping_joined_at).all()

        # Build members list and count statuses
        members_list = []
        total_weight = 0
        total_product_cost = 0
        paid_count = 0
        waiting_count = 0
        ready_count = 0

        for m in members:
            member_status = (m.shipping_status or "WAITING").upper()

            # Count by status
            if member_status == "PAID":
                paid_count += 1
            elif member_status == "READY":
                ready_count += 1
            else:
                waiting_count += 1

            # Add to members list
            members_list.append({
                "id": m.id,
                "username": m.username or f"User{m.id}",
                "is_creator": m.shipping_is_creator,
                "is_you": m.id == user_id,
                "weight": float(m.shipping_weight or 0),
                "product_cost": float(m.shipping_product_cost or 0),
                "shipping_cost": float(m.shipping_cost or 0),
                "joined_at": m.shipping_joined_at.isoformat() if m.shipping_joined_at else None,
                "avatar": f"https://i.pravatar.cc/60?img={m.id % 70}",
                "status": member_status,
                "is_paid": member_status == "PAID",
                "is_ready": member_status == "READY",
                "is_waiting": member_status == "WAITING"
            })

            # Sum totals
            total_weight += float(m.shipping_weight or 0)
            total_product_cost += float(m.shipping_product_cost or 0)

        # Get city info
        city_key = user.shipping_city or "riyadh"
        city_info = SUPPORTED_CITIES.get(city_key, SUPPORTED_CITIES["riyadh"])

        # Calculate time remaining
        time_left = None
        if user.shipping_expires_at:
            delta = user.shipping_expires_at - datetime.utcnow()
            if delta.total_seconds() > 0:
                days = delta.days
                hours = delta.seconds // 3600
                time_left = f"{days}d {hours}h" if days > 0 else f"{hours}h"
            else:
                time_left = "Expired"

        # Calculate user's costs
        try:
            cart_snapshot = json.loads(user.shipping_cart_snapshot or "[]")
            user_items = (
                sum(item.get("qty", 1) for item in cart_snapshot)
                if isinstance(cart_snapshot, list)
                else 0
            )
        except:
            user_items = int(float(user.shipping_weight or 0) / 0.1)

        active_members_count = waiting_count + ready_count

        # Current share (with group)
        current_share = calculate_user_share(
            user_items,
            float(user.shipping_product_cost or 0),
            members_count=max(active_members_count, 1),
            is_group=True
        )

        # Solo share (without group)
        solo_share = calculate_user_share(
            user_items,
            float(user.shipping_product_cost or 0),
            members_count=1,
            is_group=False
        )

        # Group status
        group_status = "READY" if active_members_count >= 5 else "WAITING"

        return jsonify({
            "ok": True,
            "in_group": True,
            "user_confirmed": user_status == "READY",
            "group": {
                "group_id": group_id,
                "city": city_key,
                "city_name": city_info["name_en"],
                "city_name_ar": city_info["name"],
                "status": group_status,
                "is_complete": active_members_count >= 5,
                "members_count": active_members_count,
                "total_members": len(members),
                "spots_left": max(0, 5 - active_members_count),
                "total_weight": round(total_weight, 2),
                "total_product_cost": round(total_product_cost, 2),
                "expires_at": user.shipping_expires_at.isoformat() if user.shipping_expires_at else None,
                "time_left": time_left,
                "can_extend": (user.shipping_extended_count or 0) < 2,
                "extended_count": user.shipping_extended_count or 0,
                "delivery_days": f"{city_info['days_min']}-{city_info['days_max']}",
                "paid_count": paid_count,
                "waiting_count": waiting_count,
                "ready_count": ready_count
            },
            "members": members_list,
            "your_info": {
                "is_creator": user.shipping_is_creator,
                "weight": float(user.shipping_weight or 0),
                "product_cost": float(user.shipping_product_cost or 0),
                "shipping_fee": current_share["shipping_fee"],
                "shipping_fee_solo": solo_share["shipping_fee"],
                "savings": current_share["savings"],
                "savings_percent": current_share["savings_percent"],
                "status": user_status,
                "is_paid": user_status == "PAID",
                "is_ready": user_status == "READY"
            },
            "cost_breakdown": {
                "shipping_fee_solo": solo_share["shipping_fee"],
                "shipping_fee_shared": current_share["shipping_fee"],
                "custom_duties": current_share["custom_duties"],
                "sfda_fee": current_share["sfda_fee"],
                "handling_fee": current_share["handling_fee"],
                "total_shipping": current_share["total_shipping"],
                "tax": current_share["tax"],
                "grand_total": current_share["grand_total"]
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 23.6 Extend Group Deadline
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/extend", methods=["POST"])
def groups_extend():
    """
    Extend group deadline by 1 week.
    Maximum 2 extensions allowed. Only group creator can extend.
    
    Returns:
        JSON: {ok, message, new_expires_at, extensions_remaining}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # Validate user is in a group
        if not user.shipping_group_id or not user.shipping_status:
            return jsonify({"ok": False, "message": "You are not in any group"}), 400

        # Only creator can extend
        if not user.shipping_is_creator:
            return jsonify({"ok": False, "message": "Only group creator can extend"}), 403

        # Check extension limit
        if (user.shipping_extended_count or 0) >= 2:
            return jsonify({"ok": False, "message": "Maximum extensions reached (2)"}), 400

        group_id = user.shipping_group_id

        # Get all active members
        members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY"])
        ).all()

        # Set new expiration date
        new_expires = datetime.utcnow() + timedelta(days=7)

        # Update all members
        for member in members:
            member.shipping_expires_at = new_expires
            member.shipping_extended_count = (member.shipping_extended_count or 0) + 1

        db.session.commit()

        return jsonify({
            "ok": True,
            "message": "Group extended by 1 week!",
            "new_expires_at": new_expires.isoformat(),
            "extensions_remaining": 2 - (user.shipping_extended_count or 0)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 23.7 Ship Now (Mark Group Ready)
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/ship-now", methods=["POST"])
def groups_ship_now():
    """
    Mark group as ready for payment with current members.
    Only group creator can initiate shipping.
    
    Returns:
        JSON: {ok, message, members_count, status}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # Validate user is in a group
        if not user.shipping_group_id or not user.shipping_status:
            return jsonify({"ok": False, "message": "You are not in any group"}), 400

        # Only creator can initiate shipping
        if not user.shipping_is_creator:
            return jsonify({
                "ok": False,
                "message": "Only group creator can initiate shipping"
            }), 403

        group_id = user.shipping_group_id

        # Update all waiting members to ready
        members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status == "WAITING"
        ).all()

        for member in members:
            member.shipping_status = "READY"

        db.session.commit()

        return jsonify({
            "ok": True,
            "message": "Group is now ready for payment!",
            "members_count": len(members),
            "status": "READY"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": str(e)}), 500


# =============================================================================
# 24. API - PAYMENT PROCESSING
# =============================================================================

@csrf.exempt
@app.route("/api/payment/process", methods=["POST"])
def payment_process():
    """
    Process payment for solo or shared shipping.
    Creates Order, Payment record, and OrderItems in database.
    
    Accepts JSON with:
        - type: "solo" or "shared" (default: "shared")
        - method: "card", "paypal", "apple_pay" (default: "card")
        - city: Delivery city (for solo orders)
    
    Returns:
        JSON: {ok, message, order_id, payment_id, txn_ref, shipment: {...}}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        payment_type = data.get("type", "shared")
        payment_method_str = data.get("method", "card")
        city = data.get("city")

        # Get user
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        now = datetime.utcnow()

        # Map payment method string to enum
        payment_method_map = {
            "card": PaymentMethodEnum.CARD,
            "paypal": PaymentMethodEnum.PAYPAL,
            "apple_pay": PaymentMethodEnum.APPLE_PAY,
            "applepay": PaymentMethodEnum.APPLE_PAY,
        }
        payment_method_enum = payment_method_map.get(
            payment_method_str.lower(),
            PaymentMethodEnum.CARD
        )

        # -----------------------------------------------------------------
        # SOLO PAYMENT
        # -----------------------------------------------------------------
        if payment_type == "solo":
            # Get cart
            cart = get_cart()
            if not cart:
                return jsonify({"ok": False, "message": "Cart is empty"}), 400

            # Calculate costs
            cart_summary = calculate_cart_summary(cart)
            solo_share = calculate_user_share(
                cart_summary["total_qty"],
                cart_summary["subtotal"],
                members_count=1,
                is_group=False
            )

            order_city = city or user.shipping_city or "riyadh"

            # Create order
            new_order = Order(
                user_id=user_id,
                status=OrderStatusEnum.PAID,
                subtotal_sar=cart_summary["subtotal"],
                shipping_sar=solo_share["shipping_fee"],
                customs_sar=solo_share["custom_duties"],
                fsa_fee_sar=solo_share["sfda_fee"],
                handling_sar=solo_share["handling_fee"],
                merge_service_sar=0,
                total_sar=solo_share["grand_total"],
                delivery_city=order_city,
                order_type="solo",
                group_id=None,
                created_at=now
            )
            db.session.add(new_order)
            db.session.flush()

            # Create payment record
            txn_ref = f"TXN-{new_order.id}-{int(now.timestamp())}"
            payment_record = Payment(
                order_id=new_order.id,
                account_id=user_id,
                method=payment_method_enum,
                amount_sar=solo_share["grand_total"],
                status=PaymentStatusEnum.CAPTURED,
                txn_ref=txn_ref,
                processed_at=now,
                created_at=now
            )
            db.session.add(payment_record)

            # Add order items
            products = []
            for product_id, cart_item in cart.items():
                product = Product.query.filter_by(id=product_id).first()

                item_name = product.name if product else cart_item.get("name", "Product")
                item_price = (
                    float(product.price_sar or cart_item.get("price", 0))
                    if product
                    else cart_item.get("price", 0)
                )
                item_qty = cart_item.get("qty", 1)
                item_image = product.image_primary if product else None

                order_item = OrderItem(
                    order_id=new_order.id,
                    product_id=int(product_id) if str(product_id).isdigit() else None,
                    qty=item_qty,
                    unit_price_sar=item_price
                )
                db.session.add(order_item)

                products.append({
                    "id": product_id,
                    "name": item_name,
                    "price": item_price,
                    "qty": item_qty,
                    "image": item_image
                })

            db.session.commit()
            print(f"[PAYMENT] Order #{new_order.id} created with {len(products)} items")

            # Clear cart
            session["cart"] = {}
            session.modified = True
            clear_cart_in_db(user_id)

            city_info = SUPPORTED_CITIES.get(order_city, SUPPORTED_CITIES["riyadh"])

            return jsonify({
                "ok": True,
                "message": "Payment successful!",
                "order_id": new_order.id,
                "payment_id": payment_record.id,
                "txn_ref": txn_ref,
                "shipment": {
                    "type": "solo",
                    "order_id": new_order.id,
                    "payment_id": payment_record.id,
                    "txn_ref": txn_ref,
                    "products": products,
                    "product_cost": cart_summary["subtotal"],
                    "shipping_fee": solo_share["shipping_fee"],
                    "custom_duties": solo_share["custom_duties"],
                    "sfda_fee": solo_share["sfda_fee"],
                    "handling_fee": solo_share["handling_fee"],
                    "tax": solo_share["tax"],
                    "total_paid": solo_share["grand_total"],
                    "city": order_city,
                    "city_name": city_info["name_en"],
                    "delivery_days": f"{city_info['days_min']}-{city_info['days_max']}",
                    "payment_method": payment_method_str,
                    "payment_date": now.isoformat(),
                    "status": "PAID"
                }
            })

        # -----------------------------------------------------------------
        # SHARED PAYMENT (Cost Sharing)
        # -----------------------------------------------------------------
        else:
            # Validate user is in active group
            user_status = (user.shipping_status or "").upper()
            if not user.shipping_group_id or user_status not in ["WAITING", "READY"]:
                return jsonify({
                    "ok": False,
                    "message": "You're not in any active shipping group"
                }), 400

            group_id = user.shipping_group_id
            city_key = user.shipping_city or "riyadh"
            members_count = 5

            # Get user's cart snapshot
            try:
                cart_snapshot = json.loads(user.shipping_cart_snapshot or "[]")
                user_items = (
                    sum(item.get("qty", 1) for item in cart_snapshot)
                    if isinstance(cart_snapshot, list)
                    else 0
                )
            except:
                user_items = int(float(user.shipping_weight or 0) / 0.1)

            product_cost = float(user.shipping_product_cost or 0)

            # Calculate user's share
            user_share = calculate_user_share(
                user_items,
                product_cost,
                members_count=members_count,
                is_group=True
            )

            # Create order
            new_order = Order(
                user_id=user_id,
                status=OrderStatusEnum.PAID,
                subtotal_sar=product_cost,
                shipping_sar=user_share["shipping_fee"],
                customs_sar=user_share["custom_duties"],
                fsa_fee_sar=user_share["sfda_fee"],
                handling_sar=user_share["handling_fee"],
                merge_service_sar=0,
                total_sar=user_share["grand_total"],
                delivery_city=city_key,
                order_type="shared",
                group_id=group_id,
                created_at=now
            )
            db.session.add(new_order)
            db.session.flush()

            # Create payment record
            txn_ref = f"TXN-{new_order.id}-{int(now.timestamp())}"
            payment_record = Payment(
                order_id=new_order.id,
                account_id=user_id,
                method=payment_method_enum,
                amount_sar=user_share["grand_total"],
                status=PaymentStatusEnum.CAPTURED,
                txn_ref=txn_ref,
                processed_at=now,
                created_at=now
            )
            db.session.add(payment_record)

            # Add order items from snapshot
            products = []
            if isinstance(cart_snapshot, list):
                for item in cart_snapshot:
                    order_item = OrderItem(
                        order_id=new_order.id,
                        product_id=int(item.get("id")) if str(item.get("id")).isdigit() else None,
                        qty=item.get("qty", 1),
                        unit_price_sar=item.get("price", 0)
                    )
                    db.session.add(order_item)

                    products.append({
                        "id": item.get("id"),
                        "name": item.get("name", "Product"),
                        "price": item.get("price", 0),
                        "qty": item.get("qty", 1)
                    })

            # Update user status to PAID
            user.shipping_status = "PAID"

            # Clear cart
            session["cart"] = {}
            session.modified = True
            clear_cart_in_db(user_id)

            db.session.commit()
            print(f"[PAYMENT] Shared Order #{new_order.id} created")

            city_info = SUPPORTED_CITIES.get(city_key, SUPPORTED_CITIES["riyadh"])

            return jsonify({
                "ok": True,
                "message": "Payment successful!",
                "order_id": new_order.id,
                "payment_id": payment_record.id,
                "txn_ref": txn_ref,
                "shipment": {
                    "type": "shared",
                    "order_id": new_order.id,
                    "payment_id": payment_record.id,
                    "txn_ref": txn_ref,
                    "group_id": group_id,
                    "products": products,
                    "product_cost": product_cost,
                    "shipping_fee": user_share["shipping_fee"],
                    "custom_duties": user_share["custom_duties"],
                    "sfda_fee": user_share["sfda_fee"],
                    "handling_fee": user_share["handling_fee"],
                    "tax": user_share["tax"],
                    "total_paid": user_share["grand_total"],
                    "members_count": members_count,
                    "savings": user_share["savings"],
                    "city": city_key,
                    "city_name": city_info["name_en"],
                    "delivery_days": f"{city_info['days_min']}-{city_info['days_max']}",
                    "payment_method": payment_method_str,
                    "payment_date": now.isoformat(),
                    "status": "PAID"
                }
            })

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# =============================================================================
# 25. API - STATISTICS
# =============================================================================

@csrf.exempt
@app.route("/api/cost-sharing/stats", methods=["GET"])
def cost_sharing_stats():
    """
    Get platform statistics for cost sharing.
    
    Returns:
        JSON: {ok, stats: {active_groups, users_in_groups, total_savings_estimate, cities}}
    """
    try:
        # Count active groups
        active_groups = db.session.query(
            db.func.count(db.func.distinct(Account.shipping_group_id))
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY"]),
            Account.shipping_group_id.isnot(None)
        ).scalar() or 0

        # Count users in groups
        users_in_groups = Account.query.filter(
            Account.shipping_status.in_(["WAITING", "READY"]),
            Account.shipping_group_id.isnot(None)
        ).count()

        # Estimate total savings
        total_savings = users_in_groups * (SHIPPING_BASE + 50 * SHIPPING_PER_ITEM) * 0.8

        # Stats by city
        by_city = db.session.query(
            Account.shipping_city,
            db.func.count(db.func.distinct(Account.shipping_group_id)).label('groups_count'),
            db.func.count(Account.id).label('members_count')
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY"]),
            Account.shipping_group_id.isnot(None)
        ).group_by(Account.shipping_city).all()

        cities_stats = [{
            "city": city.shipping_city,
            "city_name": SUPPORTED_CITIES.get(city.shipping_city, {}).get("name_en", city.shipping_city),
            "groups_count": city.groups_count,
            "members_count": city.members_count
        } for city in by_city]

        return jsonify({
            "ok": True,
            "stats": {
                "active_groups": active_groups,
                "users_in_groups": users_in_groups,
                "total_savings_estimate": round(total_savings, 2),
                "cities": cities_stats
            }
        })

    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


# =============================================================================
# 26. API - GROUP STATUS & UTILITIES
# =============================================================================

# -----------------------------------------------------------------------------
# 26.1 Get My Status
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/my-status", methods=["GET"])
def groups_my_status():
    """
    Check current user's shipping status.
    
    Returns:
        JSON: {ok, user_id, in_group, has_paid, group_id, shipping_status, ...}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        user_status = (user.shipping_status or "").upper()

        # User is in active group only if status is WAITING or READY
        in_active_group = bool(user.shipping_group_id) and user_status in ["WAITING", "READY"]
        has_paid = user_status == "PAID"

        # Check if group still exists
        group_exists = False
        group_expired = False

        if user.shipping_group_id:
            other_members = Account.query.filter(
                Account.shipping_group_id == user.shipping_group_id,
                Account.id != user_id,
                Account.shipping_status.in_(["WAITING", "READY"])
            ).count()

            group_exists = other_members > 0

            if user.shipping_expires_at:
                group_expired = user.shipping_expires_at < datetime.utcnow()

        return jsonify({
            "ok": True,
            "user_id": user_id,
            "in_group": in_active_group,
            "has_paid": has_paid,
            "group_id": user.shipping_group_id,
            "shipping_status": user_status,
            "shipping_city": user.shipping_city,
            "group_exists": group_exists,
            "group_expired": group_expired,
            "is_creator": user.shipping_is_creator,
            "expires_at": user.shipping_expires_at.isoformat() if user.shipping_expires_at else None,
            "can_create_new_group": not in_active_group,
            "needs_cleanup": in_active_group and (not group_exists or group_expired)
        })

    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 26.2 Clear Stuck Data
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/clear-stuck", methods=["POST"])
def groups_clear_stuck():
    """
    Clear stuck shipping data for user.
    Use when user's group data is inconsistent.
    
    Returns:
        JSON: {ok, message, cleared: {old_group_id, old_status}}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # Save old values for response
        old_group = user.shipping_group_id
        old_status = user.shipping_status

        # Clear all shipping data
        clear_user_shipping_data(user)
        db.session.commit()

        return jsonify({
            "ok": True,
            "message": "Shipping data cleared successfully! You can now join a new group.",
            "cleared": {
                "old_group_id": old_group,
                "old_status": old_status
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 26.3 Force Leave Group
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/force-leave", methods=["POST"])
def groups_force_leave():
    """
    Force leave current group regardless of status.
    
    Returns:
        JSON: {ok, message, previous_group}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # Save group ID for response
        group_id = user.shipping_group_id

        # Clear all shipping data
        clear_user_shipping_data(user)
        db.session.commit()

        return jsonify({
            "ok": True,
            "message": "Successfully left the group! You can now join or create a new one.",
            "previous_group": group_id
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 26.4 Confirm Ready
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/groups/confirm-ready", methods=["POST"])
def groups_confirm_ready():
    """
    Confirm user is ready for shipping.
    Only works if group has 5 active members.
    
    Returns:
        JSON: {ok, message, confirmed_count, all_confirmed}
    """
    if "user_id" not in session:
        return jsonify({"ok": False, "message": "Not logged in"}), 401

    user_id = session["user_id"]

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        group_id = user.shipping_group_id
        if not group_id:
            return jsonify({"ok": False, "message": "You're not in any group"}), 400

        # Check group has 5 active members
        members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY"])
        ).all()

        if len(members) < 5:
            return jsonify({
                "ok": False,
                "message": "Group is not complete yet. Need 5 members."
            }), 400

        # Mark user as ready
        user.shipping_status = "READY"
        db.session.commit()

        # Check if all members are confirmed
        ready_count = sum(1 for m in members if (m.shipping_status or "").upper() == "READY")
        all_confirmed = ready_count >= 5

        return jsonify({
            "ok": True,
            "message": "Confirmed successfully",
            "confirmed_count": ready_count,
            "all_confirmed": all_confirmed
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": str(e)}), 500
    
    # =============================================================================
# 27. API - ACCOUNT PROFILE
# =============================================================================

# -----------------------------------------------------------------------------
# 27.1 Get Profile
# -----------------------------------------------------------------------------

@app.route("/api/account/profile", methods=["GET"])
def api_get_profile():
    """
    Get user profile from database.
    
    Returns:
        JSON: {ok, profile: {user_id, username, email, phone, firstName, lastName, city, avatar, created_at}}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        # Get user account
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # Get user profile
        profile = AccountProfile.query.filter_by(account_id=user_id).first()

        # Split full name into first/last
        full_name = profile.full_name if profile and profile.full_name else user.username or ""
        name_parts = full_name.strip().split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Extract phone without country code (+966, 966, 0)
        phone = user.phone_number or ""
        for prefix in ["+966", "966", "0"]:
            if phone.startswith(prefix):
                phone = phone[len(prefix):]
                break

        return jsonify({
            "ok": True,
            "profile": {
                "user_id": user_id,
                "username": user.username,
                "email": user.email,
                "phone": phone,
                "firstName": first_name,
                "lastName": last_name,
                "city": user.shipping_city or "",
                "avatar": profile.avatar_url if profile else None,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 27.2 Update Profile
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/account/profile", methods=["POST"])
def api_update_profile():
    """
    Update user profile in database.
    
    Accepts JSON with:
        - firstName: First name
        - lastName: Last name
        - phone: Phone number (9 digits starting with 5)
        - city: City key
        - avatar: Avatar URL
    
    Returns:
        JSON: {ok, message, profile}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}

        first_name = (data.get("firstName") or "").strip()
        last_name = (data.get("lastName") or "").strip()
        phone = (data.get("phone") or "").strip()
        city = (data.get("city") or "").strip()
        avatar = data.get("avatar")

        # Validate phone format (KSA: 5xxxxxxxx)
        digits = re.sub(r"\D+", "", phone)
        if digits and not re.fullmatch(r"5\d{8}", digits):
            return jsonify({
                "ok": False,
                "error": "PHONE_INVALID",
                "message": "Phone must be 9 digits and start with 5"
            }), 400

        # Get user
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # Update phone with country code
        if digits:
            user.phone_number = f"+966{digits}"

        # Update city
        if city:
            user.shipping_city = city.lower()

        # Get or create profile
        profile = AccountProfile.query.filter_by(account_id=user_id).first()
        if not profile:
            profile = AccountProfile(account_id=user_id)
            db.session.add(profile)

        # Update full name
        full_name = f"{first_name} {last_name}".strip()
        if full_name:
            profile.full_name = full_name

        # Update avatar
        if avatar:
            profile.avatar_url = avatar

        db.session.commit()

        return jsonify({
            "ok": True,
            "message": "Profile saved successfully!",
            "profile": {
                "firstName": first_name,
                "lastName": last_name,
                "phone": digits,
                "city": city,
                "avatar": avatar
            }
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# =============================================================================
# 28. API - ORDER HISTORY & DETAILS
# =============================================================================

# -----------------------------------------------------------------------------
# 28.1 Get All Orders
# -----------------------------------------------------------------------------

@app.route("/api/account/orders", methods=["GET"])
def api_get_orders():
    """
    Get all orders for current user.
    
    Returns:
        JSON: {ok, orders: [...], total_orders}
    """
    user_id = session.get("user_id")
    print(f"[ORDERS] Getting orders for user_id: {user_id}")
    
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        # Get all user orders, newest first
        orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
        print(f"[ORDERS] Found {len(orders)} orders for user {user_id}")

        orders_list = []
        for order in orders:
            # Get order items
            order_items = OrderItem.query.filter_by(order_id=order.id).all()

            # Build products list
            products = []
            for item in order_items:
                product = Product.query.filter_by(id=item.product_id).first() if item.product_id else None

                products.append({
                    "id": item.product_id,
                    "name": product.name if product else "Product",
                    "price": float(item.unit_price_sar or 0),
                    "qty": item.qty,
                    "image": product.image_primary if product else None
                })

            # Calculate simulated delivery status based on days since order
            days_since_order = (datetime.utcnow() - order.created_at).days if order.created_at else 0

            if days_since_order < 2:
                delivery_status = "Processing"
                delivery_progress = 25
            elif days_since_order < 5:
                delivery_status = "Shipped"
                delivery_progress = 50
            elif days_since_order < 8:
                delivery_status = "In Transit"
                delivery_progress = 75
            else:
                delivery_status = "Delivered"
                delivery_progress = 100

            orders_list.append({
                "id": order.id,
                "order_number": f"BF-{order.id:06d}",
                "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
                "delivery_status": delivery_status,
                "delivery_progress": delivery_progress,
                "products": products,
                "products_count": len(products),
                "subtotal": float(order.subtotal_sar or 0),
                "shipping_fee": float(order.shipping_sar or 0),
                "customs_duties": float(order.customs_sar or 0),
                "sfda_fee": float(order.fsa_fee_sar or 0),
                "handling_fee": float(order.handling_sar or 0),
                "total": float(order.total_sar or 0),
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "date_formatted": order.created_at.strftime("%B %d, %Y") if order.created_at else "N/A"
            })

        return jsonify({
            "ok": True,
            "orders": orders_list,
            "total_orders": len(orders_list)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# -----------------------------------------------------------------------------
# 28.2 Get Order Details with Tracking
# -----------------------------------------------------------------------------

@app.route("/api/orders/<int:order_id>", methods=["GET"])
def api_get_order_details(order_id):
    """
    Get order details with dynamic tracking information.
    
    Tracking is simulated based on time since order:
        - Stage 1: Confirmed (0-2 hours)
        - Stage 2: Processing (10% of delivery time)
        - Stage 3: Shipped (40% of delivery time)
        - Stage 4: Out for Delivery (30% of delivery time)
        - Stage 5: Delivered (remaining time)
    
    Args:
        order_id: Order identifier (URL parameter)
    
    Returns:
        JSON: {ok, order: {id, order_number, tracking_number, status, products, tracking, ...}}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        # Get order (must belong to user)
        order = Order.query.filter_by(id=order_id, user_id=user_id).first()
        if not order:
            return jsonify({"ok": False, "message": "Order not found"}), 404

        # Get order items/products
        order_items = OrderItem.query.filter_by(order_id=order_id).all()
        products = []
        total_qty = 0

        for item in order_items:
            product = Product.query.get(item.product_id) if item.product_id else None
            products.append({
                "id": item.product_id,
                "name": product.name if product else "Product",
                "price": float(item.unit_price_sar or 0),
                "qty": item.qty,
                "image": product.image_primary if product else None
            })
            total_qty += item.qty

        # Get city info from order
        city_key = (order.delivery_city or "riyadh").lower()
        city_info = SUPPORTED_CITIES.get(city_key, SUPPORTED_CITIES["riyadh"])

        # -----------------------------------------------------------------
        # Calculate Dynamic Tracking
        # -----------------------------------------------------------------

        now = datetime.utcnow()
        order_date = order.created_at or now

        # Time since order
        time_since_order = now - order_date
        hours_since = time_since_order.total_seconds() / 3600
        days_since = hours_since / 24

        # Delivery timeline
        days_min = city_info["days_min"]
        days_max = city_info["days_max"]
        total_days = days_max

        # Stage thresholds (as fraction of total delivery time)
        stage_1_hours = 2                    # 2 hours for confirmation
        stage_2_days = total_days * 0.10     # Processing: 10%
        stage_3_days = total_days * 0.40     # Shipping: 40%
        stage_4_days = total_days * 0.30     # In transit: 30%

        # Determine current stage
        if hours_since < stage_1_hours:
            current_stage = 1
            stage_status = "confirmed"
            stage_message = "Order Confirmed"
        elif days_since < stage_2_days:
            current_stage = 2
            stage_status = "processing"
            stage_message = "Processing Your Order"
        elif days_since < (stage_2_days + stage_3_days):
            current_stage = 3
            stage_status = "shipped"
            stage_message = "Shipped - On The Way"
        elif days_since < (stage_2_days + stage_3_days + stage_4_days):
            current_stage = 4
            stage_status = "out_for_delivery"
            stage_message = "Out for Delivery"
        else:
            current_stage = 5
            stage_status = "delivered"
            stage_message = "Delivered Successfully!"

        # Calculate dates for each stage
        stage_dates = {
            "confirmed": {
                "date": order_date.strftime("%Y-%m-%d %H:%M"),
                "formatted": order_date.strftime("%b %d, %Y %I:%M %p"),
                "status": "completed" if current_stage > 1 else "active",
                "completed": current_stage > 1
            },
            "processing": {
                "date": (order_date + timedelta(hours=stage_1_hours)).strftime("%Y-%m-%d"),
                "formatted": (order_date + timedelta(hours=stage_1_hours)).strftime("%b %d, %Y"),
                "status": "completed" if current_stage > 2 else ("active" if current_stage == 2 else "pending"),
                "completed": current_stage > 2,
                "is_current": current_stage == 2
            },
            "shipped": {
                "date": (order_date + timedelta(days=stage_2_days)).strftime("%Y-%m-%d"),
                "formatted": (order_date + timedelta(days=stage_2_days)).strftime("%b %d, %Y"),
                "status": "completed" if current_stage > 3 else ("active" if current_stage == 3 else "pending"),
                "completed": current_stage > 3,
                "is_current": current_stage == 3
            },
            "out_for_delivery": {
                "date": (order_date + timedelta(days=stage_2_days + stage_3_days)).strftime("%Y-%m-%d"),
                "formatted": (order_date + timedelta(days=stage_2_days + stage_3_days)).strftime("%b %d, %Y"),
                "status": "completed" if current_stage > 4 else ("active" if current_stage == 4 else "pending"),
                "completed": current_stage > 4,
                "is_current": current_stage == 4
            },
            "delivered": {
                "date": (order_date + timedelta(days=total_days)).strftime("%Y-%m-%d"),
                "formatted": (order_date + timedelta(days=total_days)).strftime("%b %d, %Y"),
                "status": "completed" if current_stage == 5 else "pending",
                "completed": current_stage == 5,
                "is_current": current_stage == 5
            }
        }

        # Calculate progress percentage
        total_progress = 100 if current_stage == 5 else min(100, int((days_since / total_days) * 100))

        # Days remaining
        days_remaining = max(0, round(total_days - days_since, 1))

        # Delivery estimate
        delivery_start = order_date + timedelta(days=days_min)
        delivery_end = order_date + timedelta(days=days_max)
        delivery_estimate = f"{delivery_start.strftime('%b %d')} - {delivery_end.strftime('%b %d, %Y')}"

        return jsonify({
            "ok": True,
            "order": {
                # Basic Info
                "id": order.id,
                "order_number": f"BF-{order.id:06d}",
                "tracking_number": f"BF-SHP-{order.id:06d}",
                "status": str(order.status.value) if order.status else "PAID",
                "delivery_status": stage_message,
                "created_at": order_date.isoformat(),
                "date_formatted": order_date.strftime("%B %d, %Y"),

                # Products
                "products": products,
                "products_count": len(products),
                "items_count": total_qty,

                # Costs
                "subtotal": float(order.subtotal_sar or 0),
                "shipping_fee": float(order.shipping_sar or 0),
                "custom_duties": float(order.customs_sar or 0),
                "sfda_fee": float(order.fsa_fee_sar or 0),
                "handling_fee": float(order.handling_sar or 0),
                "total": float(order.total_sar or 0),
                "total_paid": float(order.total_sar or 0),

                # Delivery Info
                "city": city_key,
                "city_name": city_info["name_en"],
                "order_type": order.order_type or "solo",
                "group_id": order.group_id,
                "members_count": 5 if order.order_type == "shared" else 1,
                "delivery_days": f"{days_min}-{days_max}",
                "delivery_estimate": delivery_estimate,
                "days_remaining": days_remaining,

                # Tracking
                "tracking": {
                    "current_stage": current_stage,
                    "stage_status": stage_status,
                    "stage_message": stage_message,
                    "total_progress": total_progress,
                    "days_remaining": days_remaining,
                    "stage_dates": stage_dates
                },

                # Legacy compatibility
                "current_stage": current_stage,
                "total_progress": total_progress,
                "stage_dates": stage_dates
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# =============================================================================
# 29. MIKA AI CHAT
# =============================================================================

# -----------------------------------------------------------------------------
# 29.1 Mika System Prompt
# -----------------------------------------------------------------------------

MIKA_SYSTEM_PROMPT = """You are Mika, BeautyFlow's smart AI assistant.

YOU CAN ANSWER ANY QUESTION ON ANY TOPIC. You are a general-purpose AI assistant.

LANGUAGE RULES:
- Default language: English
- If user writes in Arabic OR asks for Arabic, respond in Arabic
- If user says "عربي" or "بالعربي" or "Arabic please", switch to Arabic

RESPONSE STYLE:
- No emojis
- Friendly and professional
- Short and clear (2-4 sentences for simple questions)
- When listing steps, use numbers with line breaks

ABOUT YOURSELF:
- Your name is Mika
- You are BeautyFlow's AI assistant
- You are powered by advanced AI technology
- You can help with anything: questions, advice, information, creative tasks

BEAUTYFLOW KNOWLEDGE:
Platform: Saudi beauty import platform with AI packaging design, cost-sharing shipping (save 80%), and SmartPicks recommendations. Serves 20 Saudi cities. SFDA compliant.

Order Tracking: Account page > Orders tab > Click order for details

AI Design Steps:
1. Product type (Lipstick, Mascara, Blush, Foundation, Eyeliner)
2. Formula (Water, Oil, Cream, Gel, Powder, Silicone)
3. Coverage (Sheer, Medium, Full)
4. Finish (Matte, Natural, Dewy, Glowy)
5. Skin type (Normal, Oily, Dry, Combination, Sensitive)
6. Describe your packaging

SmartPicks: Choose a vibe (Cute/Luxury/Minimal) and AI generates matching products

Cost-Sharing: Groups of 5 share shipping, save up to 80%

Shipping: Solo (50-120 SAR) or Shared (10-25 SAR), delivery 5-16 days

Payment: Credit card, Apple Pay, Mada

Cities: Riyadh, Jeddah, Mecca, Medina, Dammam, Khobar, Taif, Tabuk, and more
"""


# -----------------------------------------------------------------------------
# 29.2 Mika Chat Endpoint
# -----------------------------------------------------------------------------

@csrf.exempt
@app.route("/mika/chat", methods=["POST"])
def mika_chat():
    """
    Mika AI Chat endpoint.
    General-purpose assistant that can answer any question.
    
    Accepts JSON with:
        - message: User's message (required)
    
    Returns:
        JSON: {ok, response, expression}
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        user_message = (data.get("message") or "").strip()

        # Validate message
        if not user_message:
            return jsonify({"ok": False, "message": "Empty message"}), 400

        print(f"[Mika] User {user_id}: {user_message[:100]}")

        # Call OpenAI API
        response = OpenAI_Client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": MIKA_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_tokens=400,
            temperature=0.7
        )

        mika_response = response.choices[0].message.content.strip()

        # Convert line breaks to HTML for display
        mika_response = mika_response.replace("\n\n", "<br><br>").replace("\n", "<br>")

        # Detect expression based on message content
        expression = "happy"  # Default expression
        msg_lower = user_message.lower()

        if any(word in msg_lower for word in ["angry", "mad", "frustrated", "terrible", "hate"]):
            expression = "sad"
        elif any(word in msg_lower for word in ["sad", "disappointed", "problem", "issue", "wrong"]):
            expression = "sad"
        elif any(word in msg_lower for word in ["thank", "thanks", "awesome", "great", "love", "perfect", "شكر"]):
            expression = "love"
        elif any(word in msg_lower for word in ["how", "what", "why", "where", "?", "كيف", "ايش", "وين"]):
            expression = "thinking"

        print(f"[Mika] Response: {mika_response[:100]}...")

        # Save conversation to database
        try:
            # Get or create AI session
            mika_session = AISession.query.filter_by(
                account_id=user_id,
                status="OPEN"
            ).first()

            if not mika_session:
                mika_session = AISession(account_id=user_id, status="OPEN")
                db.session.add(mika_session)
                db.session.flush()

            # Save user message
            user_msg = AIMessage(
                session_id=mika_session.id,
                role="user",
                content=user_message
            )
            db.session.add(user_msg)

            # Save bot response
            bot_msg = AIMessage(
                session_id=mika_session.id,
                role="assistant",
                content=mika_response
            )
            db.session.add(bot_msg)
            db.session.commit()

        except Exception as db_error:
            print(f"[Mika] DB save error: {db_error}")

        return jsonify({
            "ok": True,
            "response": mika_response,
            "expression": expression
        })

    except Exception as e:
        print(f"[Mika] Error: {e}")
        return jsonify({
            "ok": True,
            "response": "I apologize, I am having trouble right now. Please try again.",
            "expression": "sad"
        })


# =============================================================================
# 30. RUN SERVER
# =============================================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)