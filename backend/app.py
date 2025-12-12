from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from pathlib import Path
import os, random, re, json
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf, validate_csrf, CSRFError
from datetime import datetime, timedelta
from dotenv import load_dotenv, dotenv_values
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from openai import OpenAI
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from models.all_models import *
from models.all_models import db
from functools import wraps
from twilio.rest import Client
import base64
import requests
from models.all_models import AISession, AIMessage, AIGeneration
from models.all_models import AIMessage

load_dotenv()
print("DEBUG] OPENAI_API_KEY present:", bool(os.getenv("OPENAI_API_KEY")))
OpenAI_Client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === Directories ===
BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent

TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)

# مفاتيح و CORS و CSRF
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
CORS(app)
csrf = CSRFProtect(app)

print("[DEBUG] template folder:", app.template_folder)
print("[DEBUG] static folder:", app.static_folder)

# ==============================
#       تحميل .env و OpenAI
# ==============================

dotenv_path = BACKEND_ROOT / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
print("[DEBUG] OPENAI_API_KEY present:", bool(API_KEY))

if not API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY not found.\n"
        "Add it to backend/.env like:\n"
        "OPENAI_API_KEY=sk-xxxx"
    )

OpenAI_Client = OpenAI(api_key=API_KEY)

# ========================= DB =========================
load_dotenv()
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {
        "options": "-csearch_path=public"
    }
}

db.init_app(app)
migrate = Migrate(app, db)
with app.app_context():
    db.create_all()


@app.route("/dbcheck")
def dbcheck():
    try:
        with db.engine.connect() as conn:
            version = conn.execute(text("select version()")).scalar()
        return f"✅ Database Connected Successfully!<br>{version}"
    except Exception as e:
        return f"❌ Database Connection Failed:<br>{e}"


def ensure_profile_for(account, first_name=None, last_name=None, phone=None):
    """Create AccountProfile if missing; update basic fields if provided."""
    from models import AccountProfile
    prof = AccountProfile.query.filter_by(account_id=account.id).first()
    created = False
    if not prof:
        prof = AccountProfile(account_id=account.id)
        created = True

    full_name_parts = []
    if first_name:
        full_name_parts.append(first_name.strip())
    if last_name:
        full_name_parts.append(last_name.strip())
    if full_name_parts:
        prof.full_name = " ".join(full_name_parts)

    if phone and hasattr(prof, "phone"):
        prof.phone = phone
        pass

    if created:
        db.session.add(prof)
    return prof, created
# ========================================
# ✅ GENERATE PRODUCT NAME FUNCTION
# ========================================



def generate_product_name(packaging_desc=None, product_type=None, finish=None):
    """Generate smart product name based on description, type, and finish"""
    
    vibe_words = {
        'luxury': ['Royal', 'Luxe', 'Elite', 'Diamond', 'Velvet', 'Gold', 'Prestige'],
        'cute': ['Sweet', 'Dreamy', 'Bloom', 'Sugar', 'Petal', 'Berry', 'Honey'],
        'minimal': ['Pure', 'Clean', 'Soft', 'Bare', 'Fresh', 'Clear', 'Essential'],
        'natural': ['Nature', 'Organic', 'Glow', 'Herbal', 'Green', 'Zen'],
        'bold': ['Bold', 'Fierce', 'Power', 'Edge', 'Rebel', 'Storm']
    }
    
    product_words = {
        'LIPSTICK': ['Kiss', 'Lip', 'Pout', 'Velvet'],
        'MASCARA': ['Lash', 'Flutter', 'Volume', 'Drama'],
        'BLUSH': ['Flush', 'Glow', 'Cheek', 'Rose'],
        'FOUNDATION': ['Skin', 'Base', 'Flawless', 'Silk'],
        'EYELINER': ['Line', 'Edge', 'Define', 'Wing'],
        'EYESHADOW': ['Shadow', 'Shimmer', 'Sparkle'],
        'HIGHLIGHTER': ['Beam', 'Radiant', 'Glow'],
        'BRONZER': ['Sun', 'Bronze', 'Warm'],
        'PRIMER': ['Prep', 'Prime', 'Smooth'],
        'SETTING_SPRAY': ['Set', 'Lock', 'Fix']
    }
    
    # تحديد الـ vibe من الوصف
    vibe = 'minimal'
    desc = (packaging_desc or '').lower()
    
    if any(word in desc for word in ['luxury', 'gold', 'elegant', 'premium', 'black']):
        vibe = 'luxury'
    elif any(word in desc for word in ['cute', 'pink', 'heart', 'kawaii', 'pastel']):
        vibe = 'cute'
    elif any(word in desc for word in ['natural', 'organic', 'green', 'eco']):
        vibe = 'natural'
    elif any(word in desc for word in ['bold', 'dark', 'edgy', 'red', 'strong']):
        vibe = 'bold'
    
    # اختيار الكلمات
    vibe_list = vibe_words.get(vibe, vibe_words['minimal'])
    product_list = product_words.get(product_type, ['Beauty', 'Glow', 'Luxe'])
    
    v_word = random.choice(vibe_list)
    p_word = random.choice(product_list)
    
    return f"{v_word} {p_word}"

# =========================
#         ROUTES
# =========================

@app.route("/", strict_slashes=False)
def home():
    return redirect(url_for("login_page"), code=302)


@csrf.exempt
@app.route("/login", methods=["GET", "POST"], strict_slashes=False)
def login_page():
    if request.method == "GET":
        return render_template("login.html")

    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()

    if not email or not password:
        flash("Please enter both email and password.", "error")
        return redirect(url_for("login_page"))

    user = Account.query.filter_by(email=email).first()

    if not user:
        flash("You don't have an account, please Sign up first.", "error")
        return redirect(url_for("login_page"))

    if not check_password_hash(user.password_hash, password):
        flash("Incorrect password, please try again.", "error")
        return redirect(url_for("login_page"))

    session.clear()
    session["user_id"] = int(user.id)
    session["username"] = user.username

    # ✅ استرجاع السلة من Database عند تسجيل الدخول
    load_cart_from_db(user.id)

    next_page = request.args.get("next") or url_for("phone_login")
    flash("Logged in successfully ", "success")
    return redirect(url_for("phone_login"))


@app.route("/index", strict_slashes=False)
def home_index():
    return render_template("index.html")


@app.route("/design-options", strict_slashes=False)
def design_options():
    return render_template("designOptions.html")


@app.route("/AI", methods=["GET"])
def ai_page():
    return render_template("AI.html", cart_count=get_cart_count())


@app.route("/costSharing", methods=["GET"])
def costSharing_page():
    return render_template("costSharing.html")


@app.route("/invoice", methods=["GET"])
def invoice_page():
    return render_template("invoice.html")


@app.route("/invoiceShared", methods=["GET"])
def invoiceShared_page():
    return render_template("invoiceShared.html")


@app.route("/shipment", methods=["GET"])
def shipment_page():
    return render_template("shipment.html")


@app.route("/about")
def about_page():
    return render_template("about.html")


@app.route("/payment", strict_slashes=False)
def payment_page():
    return render_template("payment.html")


@app.route("/sspay", strict_slashes=False)
def sspay_page():
    return render_template("sspay.html")


# -------------------------
#  Profile routes
# -------------------------
@app.route("/account", methods=["GET"], strict_slashes=False)
def account_page():
    profile = session.get("profile", {
        "firstName": "",
        "lastName": "",
        "phone": "",
        "address": ""
    })
    return render_template("account.html", profile=profile)


@app.route("/profile/save", methods=["POST"], strict_slashes=False)
def profile_save():
    csrf_token = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
        or ((request.get_json(silent=True) or {}).get("csrf_token") if request.is_json else None)
    )
    try:
        if not csrf_token:
            raise CSRFError("Missing CSRF token.")
        validate_csrf(csrf_token)
    except Exception as e:
        if request.is_json:
            return jsonify({"ok": False, "error": "CSRF_ERROR", "message": str(e)}), 400
        flash("CSRF token invalid. Try again.", "error")
        return redirect(url_for("account_page"))

    data = request.get_json(silent=True) or request.form.to_dict()
    first = (data.get("firstName") or "").strip()
    last = (data.get("lastName") or "").strip()
    addr = (data.get("address") or "").strip()
    raw_phone = (data.get("phone") or "").strip()
    digits = re.sub(r"\D+", "", raw_phone)

    if not re.fullmatch(r"5\d{8}", digits or ""):
        msg = "Phone must be 9 digits and start with 5 (KSA)."
        return (jsonify({"ok": False, "error": "PHONE_INVALID", "message": msg}), 400) if request.is_json \
            else (flash(msg, "error"), redirect(url_for("account_page")))

    if not first or not last:
        msg = "First and last name are required."
        return (jsonify({"ok": False, "error": "NAME_REQUIRED", "message": msg}), 400) if request.is_json \
            else (flash(msg, "error"), redirect(url_for("account_page")))

    session["profile"] = {
        "firstName": first,
        "lastName": last,
        "phone": digits,
        "address": addr
    }

    if request.is_json:
        return jsonify({"ok": True, "message": "Profile saved successfully ✅", "profile": session["profile"]}), 200
    else:
        flash("Profile saved ✅", "success")
        return redirect(url_for("account_page"))


# ========================================
# ✅✅✅ CART & SHIPPING CONSTANTS - UNIFIED!
# ✅ بدون Merge Fee!
# ========================================
SHIPPING_BASE = 50          # سعر أساسي للشحن
SHIPPING_PER_ITEM = 5       # + 5 ريال لكل منتج
CUSTOMS_RATE = 0.05         # 5% جمارك على المنتجات
SFDA_FEE = 20               # رسوم SFDA ثابتة
HANDLING_PER_ITEM = 8       # 8 ريال مناولة لكل منتج
TAX_RATE = 0.15             # 15% ضريبة


# ========================================
# ✅ Cart Database Functions
# ========================================

def save_cart_to_db(user_id, cart):
    """حفظ السلة في Database للمستخدم"""
    try:
        user = Account.query.get(user_id)
        if user:
            user.cart_data = json.dumps(cart) if cart else None
            db.session.commit()
            print(f"✅ Cart saved to DB for user {user_id}: {len(cart)} items")
    except Exception as e:
        print(f"❌ Error saving cart to DB: {e}")
        db.session.rollback()


def load_cart_from_db(user_id):
    """تحميل السلة من Database للمستخدم"""
    try:
        user = Account.query.get(user_id)
        if user and user.cart_data:
            cart = json.loads(user.cart_data)
            session["cart"] = cart
            session.modified = True
            print(f"✅ Cart loaded from DB for user {user_id}: {len(cart)} items")
            return cart
    except Exception as e:
        print(f"❌ Error loading cart from DB: {e}")
    return {}


def clear_cart_in_db(user_id):
    """مسح السلة من Database"""
    try:
        user = Account.query.get(user_id)
        if user:
            user.cart_data = None
            db.session.commit()
            print(f"✅ Cart cleared in DB for user {user_id}")
    except Exception as e:
        print(f"❌ Error clearing cart in DB: {e}")
        db.session.rollback()


# ========================================
# Cart Helper Functions
# ========================================

def get_cart():
    return session.get("cart", {})


def save_cart(cart: dict):
    """حفظ السلة في Session و Database"""
    session["cart"] = cart
    session.modified = True

    user_id = session.get("user_id")
    if user_id:
        save_cart_to_db(user_id, cart)


def get_cart_count():
    cart = get_cart()
    return sum(item["qty"] for item in cart.values())


def calculate_cart_summary(cart):
    """
    ✅✅✅ حساب ملخص السلة - الدالة الموحدة!
    ✅ بدون Merge Fee!
    """
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

    items_count = len(cart)
    total_qty = sum(item.get("qty", 1) for item in cart.values())
    subtotal = sum(item.get("price", 0) * item.get("qty", 1) for item in cart.values())

    # ✅ 1. Shipping Fee = Base + (items × per item) - هذا فقط يتقسم!
    shipping_fee = SHIPPING_BASE + (total_qty * SHIPPING_PER_ITEM) if total_qty > 0 else 0

    # ✅ 2. Custom Duties = 5% من سعر المنتجات - ثابت لكل مستخدم
    custom_duties = round(subtotal * CUSTOMS_RATE, 2)

    # ✅ 3. SFDA Fee = 20 SAR - ثابت
    sfda_fee = SFDA_FEE if total_qty > 0 else 0

    # ✅ 4. Handling = 8 × عدد المنتجات - ثابت لكل مستخدم
    handling_fee = total_qty * HANDLING_PER_ITEM

    # ✅ 5. Total Shipping = مجموع كل رسوم الشحن (بدون Merge Fee!)
    shipping = shipping_fee + custom_duties + sfda_fee + handling_fee

    # ✅ 6. Tax = 15% من (المنتجات + الشحن)
    tax = round((subtotal + shipping) * TAX_RATE, 2)

    # ✅ 7. المجموع الكلي
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
    ✅✅✅ حساب حصة المستخدم - للـ Cost Sharing!
    ✅ بدون Merge Fee!
    
    القاعدة الذهبية: فقط Shipping Fee يتقسم على عدد الأعضاء!
    """
    # ✅ 1. Shipping Fee = Base + (items × per_item) - هذا فقط يتقسم!
    shipping_fee_solo = SHIPPING_BASE + (total_items * SHIPPING_PER_ITEM)
    shipping_fee_shared = round(shipping_fee_solo / members_count, 2) if members_count > 1 else shipping_fee_solo

    # ✅ 2. Custom Duties = 5% من المنتجات - ثابت لكل مستخدم
    custom_duties = round(product_cost * CUSTOMS_RATE, 2)

    # ✅ 3. SFDA Fee - ثابت
    sfda_fee = SFDA_FEE

    # ✅ 4. Handling = 8 × items - ثابت لكل مستخدم
    handling_fee = total_items * HANDLING_PER_ITEM

    # ✅ 5. Total Shipping حسب النوع (بدون Merge Fee!)
    shipping_fee_used = shipping_fee_shared if is_group else shipping_fee_solo
    total_shipping = shipping_fee_used + custom_duties + sfda_fee + handling_fee

    # ✅ 6. Tax = 15% من (المنتجات + الشحن)
    tax = round((product_cost + total_shipping) * TAX_RATE, 2)

    # ✅ 7. Grand Total
    grand_total = round(product_cost + total_shipping + tax, 2)

    # ✅ 8. Savings = الفرق في Shipping Fee فقط!
    savings = round(shipping_fee_solo - shipping_fee_shared, 2) if members_count > 1 else 0

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
        "savings_percent": round((savings / shipping_fee_solo) * 100, 1) if shipping_fee_solo > 0 else 0,
        "members_count": members_count
    }


# ========================================
# ✅ Helper Function: Clear User Shipping Data
# ========================================
def clear_user_shipping_data(user):
    """مسح بيانات الشحن للمستخدم"""
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


# ========= SmartPicks + Cart =========

@app.route("/smartPicks", strict_slashes=False)
def smartPicks_page():
    return render_template("smartPicks.html", cart_count=get_cart_count())


# ========================================
# Cart Page Route
# ========================================
@app.route("/cart", strict_slashes=False)
def cart_page():
    """Display cart page with products loaded from session"""

    cart = get_cart()
    items = []

    print(f"📦 Loading cart: {len(cart)} items")

    for product_id, cart_item in cart.items():
        try:
            product = Product.query.filter_by(id=product_id).first()

            if product:
                image_url = None
                if product.image_primary:
                    if product.image_primary.startswith("data:image"):
                        image_url = product.image_primary
                        print(f"✅ Loaded Base64 image for {product.name}: {len(image_url)} chars")
                    else:
                        image_url = product.image_primary
                        print(f"✅ Loaded URL image for {product.name}: {image_url[:50]}")
                else:
                    print(f"⚠️ No image for {product.name}")

                item_data = {
                    "id": product_id,
                    "name": cart_item.get("name") or product.name,
                    "price": cart_item.get("price") or float(product.price_sar or 0),
                    "qty": cart_item.get("qty", 1),
                    "image": image_url,
                }
                print(f"✅ Added {product.name} to cart items")
            else:
                item_data = {
                    "id": product_id,
                    "name": cart_item.get("name", "Product"),
                    "price": cart_item.get("price", 0),
                    "qty": cart_item.get("qty", 1),
                    "image": None,
                }
                print(f"⚠️ Product {product_id} not found in DB")

            items.append(item_data)

        except Exception as e:
            print(f"❌ Error loading product {product_id}: {e}")
            import traceback
            traceback.print_exc()

            items.append({
                "id": product_id,
                "name": cart_item.get("name", "Product"),
                "price": cart_item.get("price", 0),
                "qty": cart_item.get("qty", 1),
                "image": None,
            })

    summary = calculate_cart_summary(cart)

    print(f"📊 Cart: {len(items)} items, Subtotal: {summary['subtotal']} SAR, Shipping: {summary['shipping']} SAR")

    return render_template("cart.html",
                           items=items,
                           subtotal=summary["subtotal"],
                           total_qty=summary["total_qty"],
                           shipping=summary["shipping"],
                           tax=summary["tax"],
                           total=summary["subtotal"],
                           grand_total=summary["total"])


# ========================================
# Cart Add
# ========================================
@csrf.exempt
@app.post("/cart/add")
def cart_add():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    print("🛒 /cart/add DATA:", data)

    product_id = str(
        data.get("id")
        or data.get("product_id")
        or data.get("productId")
        or data.get("sku")
        or ""
    ).strip()

    name = (data.get("name")
            or data.get("title")
            or data.get("product_name")
            or "").strip()

    raw_price = data.get("price") or data.get("amount") or data.get("sar") or 0
    try:
        price = float(raw_price)
    except (TypeError, ValueError):
        price = 0.0

    image_marker = f"DB:{product_id}"

    if not product_id:
        print("🛑 MISSING_ID in /cart/add")
        return jsonify({"ok": False, "error": "MISSING_ID"}), 400

    cart = get_cart()
    if product_id in cart:
        cart[product_id]["qty"] += 1
        print(f"✅ Increased qty for {product_id}")
    else:
        cart[product_id] = {
            "id": product_id,
            "name": name or "AI Product",
            "price": price,
            "image": image_marker,
            "qty": 1,
        }
        print(f"✅ Added new item: {product_id}")

    save_cart(cart)

    summary = calculate_cart_summary(cart)

    print(f"✅ CART NOW: {len(cart)} items, Total: {summary['total']} SAR")

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


# ========================================
# Cart Remove
# ========================================
@csrf.exempt
@app.post("/cart/remove")
def cart_remove():
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("id") or "").strip()

    print(f"🗑️ Removing product: {product_id}")

    if not product_id:
        return jsonify({"ok": False, "error": "MISSING_ID"}), 400

    cart = get_cart()
    if product_id in cart:
        del cart[product_id]
        print(f"✅ Removed {product_id}")
    else:
        print(f"⚠️ Product {product_id} not in cart")

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


# ========================================
# Cart Update Quantity
# ========================================
@csrf.exempt
@app.post("/cart/update_qty")
def cart_update_qty():
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("id") or "").strip()
    action = (data.get("action") or "").strip()

    if not product_id or action not in {"inc", "dec"}:
        return jsonify({"ok": False, "error": "BAD_REQUEST"}), 400

    cart = get_cart()
    if product_id not in cart:
        return jsonify({"ok": False, "error": "NOT_FOUND"}), 404

    item = cart[product_id]
    removed = False

    if action == "inc":
        item["qty"] += 1
    elif action == "dec":
        item["qty"] -= 1
        if item["qty"] <= 0:
            del cart[product_id]
            removed = True

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


# -------------------------
# Signup / Help / Phone login routes
# -------------------------
@csrf.exempt
@app.route("/signup", methods=["GET", "POST"], strict_slashes=False)
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip() or None
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or password

    if not username or not email or not password:
        flash("Please fill username, email, and password.", "error")
        return redirect(url_for("signup"))
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("signup"))
    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("signup"))

    pwd_hash = generate_password_hash(password)
    user = Account(username=username, email=email, phone_number=phone, password_hash=pwd_hash)

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
    except Exception as e:
        db.session.rollback()
        flash("Unexpected error.", "error")
        return redirect(url_for("signup"))


@app.route("/help", methods=["GET"], strict_slashes=False)
def help_page():
    return render_template("help.html")


@app.route("/contact", methods=["POST"], strict_slashes=False)
def submit_contact():
    first = request.form.get("first_name")
    last = request.form.get("last_name")
    email = request.form.get("email")
    msg = request.form.get("message")
    flash("Message received ✅")
    return redirect(url_for("help_page"))


# -------------------------
# Phone login / OTP routes
# -------------------------
@app.get("/phone_login")
def phone_login():
    return render_template("phone_login.html")


@app.get("/verify")
def verify_page():
    phone_full = session.get("phone_full")
    if not phone_full:
        return redirect(url_for("phone_login"))
    masked = phone_full[:-4] + "****"
    return render_template("verify.html", phone_mask=masked)


client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
VERIFY_SID = os.getenv("TWILIO_VERIFY_SID")
USE_TWILIO = os.getenv("USE_TWILIO", "0") == "1"


@csrf.exempt
@app.post("/send_otp")
def send_otp():
    print("[DEBUG] USE_TWILIO:", USE_TWILIO, "VERIFY_SID:", VERIFY_SID)
    raw_phone = (request.form.get("phone") or "").strip()
    print("[DEBUG] raw_phone:", raw_phone)

    digits = re.sub(r"\D+", "", raw_phone)
    if digits.startswith("966"): digits = digits[3:]
    if digits.startswith("05") and len(digits) == 10: digits = digits[1:]
    if digits.startswith("5") and len(digits) == 9:
        phone_full = f"+966{digits}"
    else:
        flash("Phone number format is invalid. Use 05xxxxxxxx.", "error")
        return redirect(url_for("phone_login"))

    print("[DEBUG] phone_full:", phone_full)

    session["phone_full"] = phone_full

    if not USE_TWILIO:
        print("[DEV MODE] Would send OTP to:", phone_full)
        flash("DEV mode: set USE_TWILIO=1 to send real SMS.", "success")
        return redirect(url_for("verify_page"))

    try:
        v = client.verify.v2.services(VERIFY_SID).verifications.create(
            to=phone_full,
            channel="sms"
        )
        print("[DEBUG] Twilio status:", v.status)
        flash("OTP sent via SMS ", "success")
        return redirect(url_for("verify_page"))
    except Exception as e:
        print("[Twilio ERROR]", repr(e))
        flash("Failed to send SMS. Check console/logs.", "error")
        return redirect(url_for("phone_login"))


@csrf.exempt
@app.post("/verify")
def verify_submit():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    code = (request.form.get("code") or "").strip()
    phone_full = session.get("phone_full")

    if not phone_full:
        flash("Session expired. Send OTP again.", "error")
        return redirect(url_for("phone_login"))

    try:
        if USE_TWILIO:
            check = client.verify.v2.services(VERIFY_SID).verification_checks.create(
                to=phone_full, code=code
            )
            print("[DEBUG] verify status:", check.status)
            if check.status != "approved":
                flash("Incorrect OTP code", "error")
                return redirect(url_for("verify_page"))
        else:
            expected = session.get("otp")
            if not expected or code != expected:
                flash("Incorrect OTP code", "error")
                return redirect(url_for("verify_page"))
    except Exception as e:
        print("[Verify ERROR]", repr(e))
        flash("Verification failed. Try again.", "error")
        return redirect(url_for("verify_page"))

    user = Account.query.get(session["user_id"])
    if user:
        if user.phone_number != phone_full:
            user.phone_number = phone_full
        sec = AccountSecurity.query.filter_by(account_id=user.id).first()
        if not sec:
            sec = AccountSecurity(account_id=user.id)
            db.session.add(sec)
        sec.is_2fa_enabled = True
        sec.two_factor_method = "sms"
        db.session.commit()

    session.pop("phone_full", None)
    session.pop("otp", None)

    flash("Phone verified ✅", "success")
    return redirect(url_for("home_index"))


@csrf.exempt
@app.post("/resend_otp")
def resend_otp():
    phone_full = session.get("phone_full")
    if not phone_full:
        return redirect(url_for("phone_login"))

    try:
        if USE_TWILIO:
            client.verify.v2.services(VERIFY_SID).verifications.create(
                to=phone_full, channel="sms"
            )
            flash("A new OTP has been sent.", "success")
        else:
            otp = f"{random.randint(0, 999999):06d}"
            session["otp"] = otp
            print("[DEV RESEND] OTP ->", otp, "to", phone_full)
            flash("DEV mode: new code printed in console.", "success")
    except Exception as e:
        print("[Resend ERROR]", repr(e))
        flash("Failed to resend code. Try again.", "error")

    return redirect(url_for("verify_page"))


# ========================================
# ✅ LOGOUT
# ========================================
@app.route("/logout", methods=["GET"], strict_slashes=False, endpoint="logout")
def logout():
    user_id = session.get("user_id")
    if user_id:
        print(f"✅ User {user_id} logging out, cart is preserved in database")

    session.clear()
    return redirect(url_for("login_page"))


@csrf.exempt
@app.route("/ai/generate", methods=["POST"])
def ai_generate_packaging():
    try:
        data = request.get_json(silent=True) or {}
        prompt_raw = (data.get("prompt") or "").strip()

        if not prompt_raw:
            return jsonify({"ok": False, "message": "Empty prompt"}), 400

        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "message": "Please login"}), 401

        print("🔥 PROMPT RECEIVED:", prompt_raw)

        result = OpenAI_Client.images.generate(
            model="dall-e-2",
            prompt=prompt_raw,
            size="1024x1024",
            response_format="b64_json",
        )
        b64_data = result.data[0].b64_json
        image_url = f"data:image/png;base64,{b64_data}"

        # ========== استخراج نوع المنتج ==========
        product_type = "LIPSTICK"  # default
        prompt_upper = prompt_raw.upper()
        
        if "LIPSTICK" in prompt_upper:
            product_type = "LIPSTICK"
        elif "MASCARA" in prompt_upper:
            product_type = "MASCARA"
        elif "BLUSH" in prompt_upper:
            product_type = "BLUSH"
        elif "FOUNDATION" in prompt_upper:
            product_type = "FOUNDATION"
        elif "EYELINER" in prompt_upper:
            product_type = "EYELINER"
        elif "EYESHADOW" in prompt_upper:
            product_type = "EYESHADOW"
        elif "HIGHLIGHTER" in prompt_upper:
            product_type = "HIGHLIGHTER"
        elif "BRONZER" in prompt_upper:
            product_type = "BRONZER"
        elif "PRIMER" in prompt_upper:
            product_type = "PRIMER"
        elif "SETTING" in prompt_upper:
            product_type = "SETTING_SPRAY"

        # ========== استخراج باقي المواصفات ==========
        prompt_lower = prompt_raw.lower()
        
        # Formula
        formula = "CREAM"
        if "water" in prompt_lower:
            formula = "WATER"
        elif "oil" in prompt_lower:
            formula = "OIL"
        elif "gel" in prompt_lower:
            formula = "GEL"
        elif "powder" in prompt_lower:
            formula = "POWDER"
        elif "silicone" in prompt_lower:
            formula = "SILICONE"
        
        # Coverage
        coverage = "MEDIUM"
        if "sheer" in prompt_lower:
            coverage = "SHEER"
        elif "full" in prompt_lower:
            coverage = "FULL"
        
        # Finish
        finish = "NATURAL"
        if "matte" in prompt_lower:
            finish = "MATTE"
        elif "dewy" in prompt_lower:
            finish = "DEWY"
        elif "glowy" in prompt_lower:
            finish = "GLOWY"
        elif "satin" in prompt_lower:
            finish = "SATIN"
        
        # Skin Type
        skin_type = "NORMAL"
        if "oily" in prompt_lower:
            skin_type = "OILY"
        elif "dry" in prompt_lower:
            skin_type = "DRY"
        elif "combination" in prompt_lower:
            skin_type = "COMBINATION"
        elif "sensitive" in prompt_lower:
            skin_type = "SENSITIVE"

        # ========== حساب السعر الديناميكي ==========
        BASE_PRICES = {
            'LIPSTICK': 45, 'MASCARA': 50, 'BLUSH': 55, 'FOUNDATION': 65,
            'EYELINER': 40, 'EYESHADOW': 60, 'HIGHLIGHTER': 55,
            'BRONZER': 55, 'PRIMER': 60, 'SETTING_SPRAY': 50
        }
        FORMULA_MULT = {'WATER': 1.0, 'OIL': 1.05, 'CREAM': 1.03, 'GEL': 1.02, 'POWDER': 0.98, 'SILICONE': 1.08}
        COVERAGE_MULT = {'SHEER': 0.95, 'MEDIUM': 1.0, 'FULL': 1.05}
        FINISH_MULT = {'MATTE': 1.02, 'NATURAL': 1.0, 'DEWY': 1.03, 'GLOWY': 1.04, 'SATIN': 1.02}
        SKIN_MULT = {'NORMAL': 1.0, 'OILY': 1.02, 'DRY': 1.03, 'COMBINATION': 1.03, 'SENSITIVE': 1.05}
        MAX_PRICE = 150

        base_price = BASE_PRICES.get(product_type, 50)
        calculated_price = base_price \
            * FORMULA_MULT.get(formula, 1) \
            * COVERAGE_MULT.get(coverage, 1) \
            * FINISH_MULT.get(finish, 1) \
            * SKIN_MULT.get(skin_type, 1)
        
        # تقريب لأقرب 5 مع حد أقصى 150
        final_price = min(round(calculated_price / 5) * 5, MAX_PRICE)

        print(f"💰 Price: base={base_price}, calculated={calculated_price:.2f}, final={final_price}")

        # ========== حساب الحجم ==========
        PRODUCT_SIZES = {
            'LIPSTICK': '3.5g', 'MASCARA': '8ml', 'BLUSH': '5g',
            'FOUNDATION': '30ml', 'EYELINER': '0.5ml', 'EYESHADOW': '1.5g',
            'HIGHLIGHTER': '8g', 'BRONZER': '8g', 'PRIMER': '30ml',
            'SETTING_SPRAY': '60ml'
        }
        product_size = PRODUCT_SIZES.get(product_type, '10g')

        print(f"📦 Product: {product_type}, Size: {product_size}, Price: {final_price} SAR")

        # ========== استخراج الوصف ==========
        packaging_desc = ""
        if "Packaging:" in prompt_raw:
            packaging_desc = prompt_raw.split("Packaging:")[-1].split(".")[0].strip()

        product_name = generate_product_name(packaging_desc, product_type, finish)
        print(f"✅ Generated product name: {product_name}")

        # ========== إنشاء المنتج ==========
        product = Product(
            supplier_id=None,
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

        session_obj = AISession.query.filter_by(
            account_id=user_id,
            status="OPEN"
        ).order_by(AISession.id.desc()).first()

        if not session_obj:
            session_obj = AISession(account_id=user_id, status="OPEN")
            db.session.add(session_obj)
            db.session.flush()

        gen = AIGeneration(
            session_id=session_obj.id,
            product_id=product.id,
            image_url=image_url,
            prompt_json={"prompt": prompt_raw, "packaging_desc": packaging_desc},
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

        print("💾 IMAGE + PRODUCT SAVED IN DATABASE!")

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
        print("\n🔥🔥 ERROR 🔥🔥")
        traceback.print_exc()
        return jsonify({"ok": False, "error": "OPENAI_ERROR", "message": str(e)}), 500


# ========== AI History ==========
@app.route("/ai/history", methods=["GET"])
def ai_history():
    """جلب آخر 20 منتج AI للمستخدم"""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "message": "Not logged in"}), 401

        products = Product.query.filter_by(
            owner_user_id=user_id,
            origin=ProductOriginEnum.AI
        ).order_by(Product.created_at.desc()).limit(20).all()

        history = []
        for product in products:
            history.append({
                "id": product.id,
                "name": product.name,
                "image_url": product.image_primary,
                "created_at": product.created_at.isoformat(),
                "price_sar": float(product.price_sar or 0),
                "size": "10g"
            })

        return jsonify({"ok": True, "history": history})

    except Exception as e:
        print(f"❌ Error in ai_history: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


@csrf.exempt
@app.route("/ai/favorites/add", methods=["POST"])
def ai_favorites_add():
    """Add product to user's favorites/wishlist"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json()
        product_id = data.get("product_id")

        if not product_id:
            return jsonify({"ok": False, "message": "Product ID is required"}), 400

        print(f"💾 Adding to favorites - User: {user_id}, Product: {product_id}")

    except Exception as e:
        print(f"❌ Error parsing request: {e}")
        return jsonify({"ok": False, "message": "Invalid request"}), 400

    product = Product.query.filter_by(id=product_id).first()
    if not product:
        return jsonify({"ok": False, "message": "Product not found"}), 404

    wishlist = Wishlist.query.filter_by(account_id=user_id).first()
    if not wishlist:
        wishlist = Wishlist(account_id=user_id)
        db.session.add(wishlist)
        db.session.flush()
        print(f"✅ Created new wishlist for user {user_id}")

    existing = WishlistItem.query.filter_by(
        wishlist_id=wishlist.id,
        product_id=product_id
    ).first()

    if existing:
        return jsonify({"ok": True, "message": "Already in favorites", "already_exists": True})

    try:
        item = WishlistItem(wishlist_id=wishlist.id, product_id=product_id)
        db.session.add(item)
        db.session.commit()
        print(f"✅ Added product {product_id} to favorites")
        return jsonify({"ok": True, "message": "Added to favorites successfully"})

    except Exception as e:
        db.session.rollback()
        print(f"❌ Database error: {e}")
        return jsonify({"ok": False, "message": f"Database error: {str(e)}"}), 500


@app.route("/ai/favorites", methods=["GET"])
def ai_favorites_get():
    """Get user's favorite products"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        wishlist = Wishlist.query.filter_by(account_id=user_id).first()

        if not wishlist:
            return jsonify({"ok": True, "favorites": []})

        items = WishlistItem.query.filter_by(wishlist_id=wishlist.id).all()

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

        print(f"✅ Retrieved {len(favorites)} favorites for user {user_id}")
        return jsonify({"ok": True, "favorites": favorites})

    except Exception as e:
        print(f"❌ Error loading favorites: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


@csrf.exempt
@app.route("/ai/favorites/remove", methods=["POST"])
def ai_favorites_remove():
    """Remove product from favorites"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json()
        product_id = data.get("product_id")

        if not product_id:
            return jsonify({"ok": False, "message": "Product ID is required"}), 400

        wishlist = Wishlist.query.filter_by(account_id=user_id).first()
        if not wishlist:
            return jsonify({"ok": False, "message": "Wishlist not found"}), 404

        item = WishlistItem.query.filter_by(
            wishlist_id=wishlist.id,
            product_id=product_id
        ).first()

        if not item:
            return jsonify({"ok": False, "message": "Item not in favorites"}), 404

        db.session.delete(item)
        db.session.commit()

        print(f"✅ Removed product {product_id} from favorites")
        return jsonify({"ok": True, "message": "Removed from favorites"})

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error removing favorite: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# ========================================
#       ✅✅✅ COST SHARING APIs - FIXED!
#       فقط Shipping Fee يتقسم! بدون Merge Fee!
# ========================================
# ========================================

# المدن المدعومة
SUPPORTED_CITIES = {
    "riyadh": {"name": "الرياض", "name_en": "Riyadh", "multiplier": 1.0, "days_min": 7, "days_max": 10},
    "jeddah": {"name": "جدة", "name_en": "Jeddah", "multiplier": 0.95, "days_min": 5, "days_max": 7},
    "makkah": {"name": "مكة", "name_en": "Makkah", "multiplier": 0.98, "days_min": 5, "days_max": 7},
    "madinah": {"name": "المدينة", "name_en": "Madinah", "multiplier": 1.02, "days_min": 6, "days_max": 8},
    "dammam": {"name": "الدمام", "name_en": "Dammam", "multiplier": 1.05, "days_min": 7, "days_max": 10},
    "khobar": {"name": "الخبر", "name_en": "Khobar", "multiplier": 1.05, "days_min": 7, "days_max": 10},
    "dhahran": {"name": "الظهران", "name_en": "Dhahran", "multiplier": 1.05, "days_min": 7, "days_max": 10},
    "tabuk": {"name": "تبوك", "name_en": "Tabuk", "multiplier": 1.15, "days_min": 10, "days_max": 14},
    "abha": {"name": "أبها", "name_en": "Abha", "multiplier": 1.20, "days_min": 10, "days_max": 14},
    "khamis": {"name": "خميس مشيط", "name_en": "Khamis Mushait", "multiplier": 1.20, "days_min": 10, "days_max": 14},
    "taif": {"name": "الطائف", "name_en": "Taif", "multiplier": 1.08, "days_min": 8, "days_max": 12},
    "buraidah": {"name": "بريدة", "name_en": "Buraidah", "multiplier": 1.08, "days_min": 8, "days_max": 12},
    "najran": {"name": "نجران", "name_en": "Najran", "multiplier": 1.25, "days_min": 12, "days_max": 16},
    "jubail": {"name": "الجبيل", "name_en": "Jubail", "multiplier": 1.08, "days_min": 8, "days_max": 11},
    "hofuf": {"name": "الهفوف", "name_en": "Hofuf", "multiplier": 1.08, "days_min": 8, "days_max": 11},
    "yanbu": {"name": "ينبع", "name_en": "Yanbu", "multiplier": 1.02, "days_min": 7, "days_max": 10},
    "hail": {"name": "حائل", "name_en": "Hail", "multiplier": 1.12, "days_min": 9, "days_max": 12},
    "jazan": {"name": "جازان", "name_en": "Jazan", "multiplier": 1.18, "days_min": 11, "days_max": 15},
    "arar": {"name": "عرعر", "name_en": "Arar", "multiplier": 1.22, "days_min": 12, "days_max": 16},
    "albaha": {"name": "الباحة", "name_en": "Al baha", "multiplier": 1.22, "days_min": 12, "days_max": 16},
}


def generate_group_id(city_key):
    """توليد معرف فريد للمجموعة"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
    random_suffix = random.randint(100, 999)
    return f"{city_key}-{timestamp}-{random_suffix}"


# ========================================
# ✅ API 1: Load Cart Data for Cost Sharing
# ========================================

@csrf.exempt
@app.route("/api/cost-sharing/load", methods=["GET"])
def cost_sharing_load():
    """تحميل بيانات السلة لصفحة Cost Sharing"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        cart = get_cart()
        cart_summary = calculate_cart_summary(cart)
        cart_empty = cart_summary["total_qty"] == 0
        total_weight = round(cart_summary["total_qty"] * 0.1, 2)

        solo_share = calculate_user_share(
            cart_summary["total_qty"],
            cart_summary["subtotal"],
            members_count=1,
            is_group=False
        )

        shared_share = calculate_user_share(
            cart_summary["total_qty"],
            cart_summary["subtotal"],
            members_count=5,
            is_group=True
        )

        user = Account.query.get(user_id)
        
        # ✅ المستخدم في مجموعة إذا عنده group_id وحالته ليست فارغة
        # ✅ لكن إذا دفع (PAID) يمكنه إنشاء/الانضمام لمجموعة جديدة
        user_status = (user.shipping_status or "").upper() if user else ""
        in_group = bool(user and user.shipping_group_id and user_status and user_status != "PAID")

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
        print(f"❌ Error in cost_sharing_load: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# ✅ API 2: Calculate Shipping for Specific City
# ========================================

@csrf.exempt
@app.route("/api/cost-sharing/calculate", methods=["POST"])
def cost_sharing_calculate():
    """حساب تكلفة الشحن لمدينة معينة"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        city_key = (data.get("city") or "riyadh").lower()
        members_count = data.get("members", 5)

        if city_key not in SUPPORTED_CITIES:
            return jsonify({"ok": False, "message": "City not supported"}), 400

        cart = get_cart()
        city_info = SUPPORTED_CITIES[city_key]
        cart_summary = calculate_cart_summary(cart)

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
        print(f"❌ Error in cost_sharing_calculate: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API 3: Get Available Groups to Join
# ========================================

@csrf.exempt
@app.route("/api/groups/available", methods=["GET"])
def groups_available():
    """جلب المجموعات المتاحة للانضمام في مدينة معينة"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        city_key = (request.args.get("city") or "riyadh").lower()

        if city_key not in SUPPORTED_CITIES:
            return jsonify({"ok": False, "message": "City not supported"}), 400

        # ✅ جلب المجموعات التي حالتها WAITING فقط (ليست PAID أو READY)
        groups_query = db.session.query(
            Account.shipping_group_id,
            Account.shipping_city,
            Account.shipping_expires_at,
            db.func.count(Account.id).label('members_count'),
            db.func.sum(Account.shipping_weight).label('total_weight'),
            db.func.min(Account.shipping_joined_at).label('created_at')
        ).filter(
            Account.shipping_city == city_key,
            Account.shipping_status == "WAITING",  # ✅ فقط WAITING
            Account.shipping_group_id.isnot(None),
            Account.shipping_expires_at > datetime.utcnow()
        ).group_by(
            Account.shipping_group_id,
            Account.shipping_city,
            Account.shipping_expires_at
        ).having(
            db.func.count(Account.id) < 5
        ).all()

        groups = []
        for g in groups_query:
            if g.shipping_expires_at:
                time_left = g.shipping_expires_at - datetime.utcnow()
                days_left = time_left.days
                hours_left = time_left.seconds // 3600
                time_left_str = f"{days_left}d {hours_left}h" if days_left > 0 else f"{hours_left}h"
            else:
                time_left_str = "N/A"

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
        print(f"❌ Error in groups_available: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# ✅ API 4: Create New Group
# ========================================

@csrf.exempt
@app.route("/api/groups/create", methods=["POST"])
def groups_create():
    """إنشاء مجموعة جديدة"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        city_key = (data.get("city") or "").lower()

        if not city_key or city_key not in SUPPORTED_CITIES:
            return jsonify({"ok": False, "message": "Please select a valid city"}), 400

        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # ✅✅✅ تحقق محسّن: المستخدم في مجموعة فقط إذا كانت حالته WAITING أو READY
        # إذا كانت حالته PAID أو فارغة، يمكنه إنشاء مجموعة جديدة
        user_status = (user.shipping_status or "").upper()
        if user.shipping_group_id and user_status in ["WAITING", "READY"]:
            return jsonify({
                "ok": False,
                "message": "You are already in a group. Leave it first.",
                "current_group": user.shipping_group_id
            }), 400

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

        group_id = generate_group_id(city_key)

        user_share = calculate_user_share(
            cart_summary["total_qty"],
            total_cost,
            members_count=1,
            is_group=True
        )

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
            "message": "Group created successfully! 🎉",
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
        print(f"❌ Error in groups_create: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# ✅ API 5: Join Existing Group
# ========================================

@csrf.exempt
@app.route("/api/groups/join", methods=["POST"])
def groups_join():
    """الانضمام لمجموعة موجودة"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        group_id = data.get("group_id")

        if not group_id:
            return jsonify({"ok": False, "message": "Group ID is required"}), 400

        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # ✅✅✅ تحقق محسّن
        user_status = (user.shipping_status or "").upper()
        if user.shipping_group_id and user_status in ["WAITING", "READY"]:
            return jsonify({"ok": False, "message": "You are already in a group"}), 400

        # ✅ جلب أعضاء المجموعة الذين حالتهم WAITING فقط
        group_members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status == "WAITING"
        ).all()

        if not group_members:
            return jsonify({"ok": False, "message": "Group not found or expired"}), 404

        if len(group_members) >= 5:
            return jsonify({"ok": False, "message": "Group is full"}), 400

        first_member = group_members[0]
        if first_member.shipping_expires_at and first_member.shipping_expires_at < datetime.utcnow():
            return jsonify({"ok": False, "message": "Group has expired"}), 400

        city_key = first_member.shipping_city

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

        user_share = calculate_user_share(
            cart_summary["total_qty"],
            total_cost,
            members_count=new_members_count,
            is_group=True
        )

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

        # تحديث تكلفة الشحن لجميع الأعضاء
        for member in group_members:
            try:
                member_cart = json.loads(member.shipping_cart_snapshot or "[]")
                member_items = sum(item.get("qty", 1) for item in member_cart) if isinstance(member_cart, list) else 0
            except:
                member_items = int(float(member.shipping_weight or 0) / 0.1)

            member_share = calculate_user_share(
                member_items,
                float(member.shipping_product_cost or 0),
                members_count=new_members_count,
                is_group=True
            )
            member.shipping_cost = member_share["shipping_fee"]

        # ✅ إذا اكتملت المجموعة، غير حالة الجميع إلى READY
        if new_members_count >= 5:
            for member in group_members:
                member.shipping_status = "READY"
            user.shipping_status = "READY"

        db.session.commit()

        city_info = SUPPORTED_CITIES[city_key]

        return jsonify({
            "ok": True,
            "message": "Joined group successfully! 🎉",
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
        print(f"❌ Error in groups_join: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# ✅ API 6: Leave Group - FIXED!
# ========================================
@csrf.exempt
@app.route("/api/groups/leave", methods=["POST"])
def groups_leave():
    """مغادرة المجموعة - فقط إذا لم تكتمل"""
    if "user_id" not in session:
        return jsonify({"ok": False, "message": "Not logged in"}), 401
    
    user_id = session["user_id"]
    
    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        if not user.shipping_group_id:
            return jsonify({"ok": False, "message": "You're not in any group"}), 400
        
        group_id = user.shipping_group_id
        user_status = (user.shipping_status or "").upper()
        
        print(f"🚪 User {user_id} trying to leave group {group_id}, status: {user_status}")
        
        # ✅ إذا المستخدم دفع، لا يمكنه المغادرة
        if user_status == "PAID":
            return jsonify({
                "ok": False, 
                "message": "You have already paid. Cannot leave after payment."
            }), 400
        
        # ✅ Check how many ACTIVE members (WAITING + READY, not PAID)
        active_members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY"])
        ).count()
        
        print(f"📊 Active members in group: {active_members}")
        
        # ✅ Prevent leaving if group is complete (5 active members)
        if active_members >= 5:
            return jsonify({
                "ok": False, 
                "message": "Cannot leave a complete group. All 5 members must proceed together."
            }), 400
        
        # Clear all shipping fields
        clear_user_shipping_data(user)
        
        db.session.commit()
        
        print(f"✅ User {user_id} left group {group_id} successfully")
        
        return jsonify({
            "ok": True,
            "message": "Left group successfully"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error leaving group: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# ✅ API 7: Get My Group Info
# ========================================
@csrf.exempt
@app.route("/api/groups/my-group", methods=["GET"])
def groups_my_group():
    """جلب معلومات مجموعتي مع حالة الدفع لكل عضو"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        # ✅ المستخدم ليس في مجموعة إذا حالته PAID أو فارغة
        user_status = (user.shipping_status or "").upper()
        if not user.shipping_group_id or user_status not in ["WAITING", "READY"]:
            return jsonify({
                "ok": True,
                "in_group": False,
                "status": user_status or None,
                "message": "You are not in any active group"
            })

        group_id = user.shipping_group_id
        
        print(f"📦 Loading group {group_id} for user {user_id}, status: {user_status}")

        # ✅ جلب جميع أعضاء المجموعة (WAITING, READY, PAID)
        members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY", "PAID"])
        ).order_by(Account.shipping_joined_at).all()

        members_list = []
        total_weight = 0
        total_product_cost = 0
        paid_count = 0
        waiting_count = 0
        ready_count = 0

        for m in members:
            member_status = (m.shipping_status or "WAITING").upper()
            is_paid = member_status == "PAID"
            is_ready = member_status == "READY"
            is_waiting = member_status == "WAITING"
            
            if is_paid:
                paid_count += 1
            elif is_ready:
                ready_count += 1
            elif is_waiting:
                waiting_count += 1

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
                "is_paid": is_paid,
                "is_ready": is_ready,
                "is_waiting": is_waiting
            })
            total_weight += float(m.shipping_weight or 0)
            total_product_cost += float(m.shipping_product_cost or 0)

        city_key = user.shipping_city or "riyadh"
        city_info = SUPPORTED_CITIES.get(city_key, SUPPORTED_CITIES["riyadh"])

        # حساب الوقت المتبقي
        time_left = None
        if user.shipping_expires_at:
            delta = user.shipping_expires_at - datetime.utcnow()
            if delta.total_seconds() > 0:
                days = delta.days
                hours = delta.seconds // 3600
                time_left = f"{days}d {hours}h" if days > 0 else f"{hours}h"
            else:
                time_left = "Expired"

        # حساب التكلفة
        try:
            cart_snapshot = json.loads(user.shipping_cart_snapshot or "[]")
            user_items = sum(item.get("qty", 1) for item in cart_snapshot) if isinstance(cart_snapshot, list) else 0
        except:
            user_items = int(float(user.shipping_weight or 0) / 0.1)

        # ✅ عدد الأعضاء النشطين (WAITING + READY فقط، بدون PAID)
        active_members_count = waiting_count + ready_count

        current_share = calculate_user_share(
            user_items,
            float(user.shipping_product_cost or 0),
            members_count=max(active_members_count, 1),
            is_group=True
        )

        solo_share = calculate_user_share(
            user_items,
            float(user.shipping_product_cost or 0),
            members_count=1,
            is_group=False
        )

        # ✅ تحديد حالة المجموعة
        group_status = "WAITING"
        if active_members_count >= 5:
            group_status = "READY"
        
        print(f"📊 Group stats: {len(members)} total, {waiting_count} waiting, {ready_count} ready, {paid_count} paid")

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
                "members_count": active_members_count,  # ✅ فقط الأعضاء النشطين
                "total_members": len(members),  # ✅ إجمالي الأعضاء (بما فيهم PAID)
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
        print(f"❌ Error in groups_my_group: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API 8: Extend Group Time
# ========================================

@csrf.exempt
@app.route("/api/groups/extend", methods=["POST"])
def groups_extend():
    """تمديد مهلة المجموعة أسبوع إضافي"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        if not user.shipping_group_id or not user.shipping_status:
            return jsonify({"ok": False, "message": "You are not in any group"}), 400

        if not user.shipping_is_creator:
            return jsonify({"ok": False, "message": "Only group creator can extend"}), 403

        if (user.shipping_extended_count or 0) >= 2:
            return jsonify({"ok": False, "message": "Maximum extensions reached (2)"}), 400

        group_id = user.shipping_group_id

        members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY"])
        ).all()

        new_expires = datetime.utcnow() + timedelta(days=7)

        for member in members:
            member.shipping_expires_at = new_expires
            member.shipping_extended_count = (member.shipping_extended_count or 0) + 1

        db.session.commit()

        return jsonify({
            "ok": True,
            "message": "Group extended by 1 week! ✅",
            "new_expires_at": new_expires.isoformat(),
            "extensions_remaining": 2 - (user.shipping_extended_count or 0)
        })

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in groups_extend: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API 9: Ship Now
# ========================================

@csrf.exempt
@app.route("/api/groups/ship-now", methods=["POST"])
def groups_ship_now():
    """الشحن بالعدد الحالي"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        if not user.shipping_group_id or not user.shipping_status:
            return jsonify({"ok": False, "message": "You are not in any group"}), 400

        if not user.shipping_is_creator:
            return jsonify({"ok": False, "message": "Only group creator can initiate shipping"}), 403

        group_id = user.shipping_group_id

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
            "message": "Group is now ready for payment! 💳",
            "members_count": len(members),
            "status": "READY"
        })

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in groups_ship_now: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# ✅✅✅ API 10: Process Payment - FIXED!

@csrf.exempt
@app.route("/api/payment/process", methods=["POST"])
def payment_process():
    """معالجة الدفع - حفظ الطلب في قاعدة البيانات مع المدينة"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        data = request.get_json() or {}
        payment_type = data.get("type", "shared")
        payment_method = data.get("method", "card")
        city = data.get("city")  # المدينة من الطلب

        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404

        now = datetime.utcnow()

        # ========================================
        # ✅ SOLO PAYMENT
        # ========================================
        if payment_type == "solo":
            cart = get_cart()
            if not cart:
                return jsonify({"ok": False, "message": "Cart is empty"}), 400

            cart_summary = calculate_cart_summary(cart)

            solo_share = calculate_user_share(
                cart_summary["total_qty"],
                cart_summary["subtotal"],
                members_count=1,
                is_group=False
            )

            # ✅ تحديد المدينة: من الطلب أو من بروفايل المستخدم
            order_city = city or user.shipping_city or "riyadh"

            # ✅✅✅ إنشاء الطلب في قاعدة البيانات
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
                created_at=now
            )
            
            # ✅ حفظ المدينة مع الطلب
            new_order.delivery_city = order_city
            new_order.order_type = "solo"
            new_order.group_id = None

            db.session.add(new_order)
            db.session.flush()

            print(f"✅ Created Order #{new_order.id} for user {user_id} - City: {order_city}")

            # ✅✅✅ إضافة المنتجات إلى order_items
            products = []
            for product_id, cart_item in cart.items():
                product = Product.query.filter_by(id=product_id).first()
                
                item_name = cart_item.get("name", "Product")
                item_price = cart_item.get("price", 0)
                item_qty = cart_item.get("qty", 1)
                item_image = None
                
                if product:
                    item_name = product.name
                    item_price = float(product.price_sar or cart_item.get("price", 0))
                    item_image = product.image_primary
                
                # ✅ إنشاء OrderItem
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
            print(f"✅ Order #{new_order.id} saved with {len(products)} items")

            # مسح السلة
            session["cart"] = {}
            session.modified = True
            clear_cart_in_db(user_id)

            city_key = order_city
            city_info = SUPPORTED_CITIES.get(city_key, SUPPORTED_CITIES["riyadh"])

            return jsonify({
                "ok": True,
                "message": "Payment successful! ✅",
                "order_id": new_order.id,
                "shipment": {
                    "type": "solo",
                    "order_id": new_order.id,
                    "products": products,
                    "product_cost": cart_summary["subtotal"],
                    "shipping_fee": solo_share["shipping_fee"],
                    "custom_duties": solo_share["custom_duties"],
                    "sfda_fee": solo_share["sfda_fee"],
                    "handling_fee": solo_share["handling_fee"],
                    "tax": solo_share["tax"],
                    "total_paid": solo_share["grand_total"],
                    "city": city_key,
                    "city_name": city_info["name_en"],
                    "delivery_days": f"{city_info['days_min']}-{city_info['days_max']}",
                    "payment_method": payment_method,
                    "payment_date": now.isoformat(),
                    "status": "PAID"
                }
            })

        # ========================================
        # ✅ SHARED PAYMENT (Cost Sharing)
        # ========================================
        else:
            user_status = (user.shipping_status or "").upper()
            if not user.shipping_group_id or user_status not in ["WAITING", "READY"]:
                return jsonify({
                    "ok": False,
                    "message": "You're not in any active shipping group"
                }), 400

            group_id = user.shipping_group_id
            city_key = user.shipping_city or "riyadh"

            active_members = Account.query.filter_by(
                shipping_group_id=group_id
            ).filter(
                Account.shipping_status.in_(["WAITING", "READY"])
            ).all()

            members_count = 5

            try:
                cart_snapshot = json.loads(user.shipping_cart_snapshot or "[]")
                user_items = sum(item.get("qty", 1) for item in cart_snapshot) if isinstance(cart_snapshot, list) else 0
            except:
                user_items = int(float(user.shipping_weight or 0) / 0.1)

            product_cost = float(user.shipping_product_cost or 0)

            user_share = calculate_user_share(
                user_items,
                product_cost,
                members_count=members_count,
                is_group=True
            )

            # ✅✅✅ إنشاء الطلب في قاعدة البيانات
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
                created_at=now
            )
            
            # ✅ حفظ المدينة مع الطلب (من Cost Sharing)
            new_order.delivery_city = city_key
            new_order.order_type = "shared"
            new_order.group_id = group_id
            
            db.session.add(new_order)
            db.session.flush()

            print(f"✅ Created Shared Order #{new_order.id} for user {user_id} - City: {city_key}")

            # ✅✅✅ إضافة المنتجات من cart_snapshot
            products = []
            if isinstance(cart_snapshot, list):
                for item in cart_snapshot:
                    product_id = item.get("id")
                    item_qty = item.get("qty", 1)
                    item_price = item.get("price", 0)
                    item_name = item.get("name", "Product")
                    
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
                        "qty": item_qty
                    })

            user.shipping_status = "PAID"
            user.shipping_confirmed = True
            user.shipping_confirmed_at = now
            session["cart"] = {}
            session.modified = True
            clear_cart_in_db(user_id)

            db.session.commit()
            print(f"✅ Shared Order #{new_order.id} saved with {len(products)} items")

            city_info = SUPPORTED_CITIES.get(city_key, SUPPORTED_CITIES["riyadh"])

            return jsonify({
                "ok": True,
                "message": "Payment successful! ✅",
                "order_id": new_order.id,
                "shipment": {
                    "type": "shared",
                    "order_id": new_order.id,
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
                    "payment_method": payment_method,
                    "payment_date": now.isoformat(),
                    "status": "PAID"
                }
            })

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in payment_process: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API 11: Get Statistics
# ========================================

@csrf.exempt
@app.route("/api/cost-sharing/stats", methods=["GET"])
def cost_sharing_stats():
    """إحصائيات"""

    try:
        active_groups = db.session.query(
            db.func.count(db.func.distinct(Account.shipping_group_id))
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY"]),
            Account.shipping_group_id.isnot(None)
        ).scalar() or 0

        users_in_groups = Account.query.filter(
            Account.shipping_status.in_(["WAITING", "READY"]),
            Account.shipping_group_id.isnot(None)
        ).count()

        total_savings = users_in_groups * (SHIPPING_BASE + 50 * SHIPPING_PER_ITEM) * 0.8

        by_city = db.session.query(
            Account.shipping_city,
            db.func.count(db.func.distinct(Account.shipping_group_id)).label('groups_count'),
            db.func.count(Account.id).label('members_count')
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY"]),
            Account.shipping_group_id.isnot(None)
        ).group_by(Account.shipping_city).all()

        cities_stats = []
        for city in by_city:
            city_info = SUPPORTED_CITIES.get(city.shipping_city, {})
            cities_stats.append({
                "city": city.shipping_city,
                "city_name": city_info.get("name_en", city.shipping_city),
                "groups_count": city.groups_count,
                "members_count": city.members_count
            })

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
        print(f"❌ Error in cost_sharing_stats: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# ✅ API: Get Product Image
# ========================================

@csrf.exempt
@app.route("/api/products/<int:product_id>/image", methods=["GET"])
def get_product_image(product_id):
    """جلب صورة المنتج من قاعدة البيانات"""
    try:
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({
                "ok": False, 
                "message": "Product not found",
                "image_url": None
            }), 404
        
        image_url = None
        if product.image_primary:
            image_url = product.image_primary
        
        return jsonify({
            "ok": True,
            "product_id": product_id,
            "name": product.name,
            "image_url": image_url,
            "price_sar": float(product.price_sar or 0)
        })
        
    except Exception as e:
        print(f"❌ Error getting product image: {e}")
        return jsonify({
            "ok": False, 
            "message": str(e),
            "image_url": None
        }), 500


@csrf.exempt
@app.route("/api/cart/products", methods=["GET"])
def get_cart_products_with_images():
    """جلب منتجات السلة مع الصور من قاعدة البيانات"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        cart = get_cart()
        products = []
        
        for product_id, cart_item in cart.items():
            product = Product.query.filter_by(id=product_id).first()
            
            if product:
                products.append({
                    "id": product_id,
                    "name": product.name or cart_item.get("name", "Product"),
                    "price": float(product.price_sar or cart_item.get("price", 0)),
                    "qty": cart_item.get("qty", 1),
                    "image_url": product.image_primary
                })
            else:
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
        print(f"❌ Error getting cart products: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API: Check User Shipping Status
# ========================================
@csrf.exempt
@app.route("/api/groups/my-status", methods=["GET"])
def groups_my_status():
    """فحص حالة الشحن للمستخدم الحالي"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        user_status = (user.shipping_status or "").upper()
        
        # ✅ المستخدم في مجموعة نشطة فقط إذا حالته WAITING أو READY
        in_active_group = bool(user.shipping_group_id) and user_status in ["WAITING", "READY"]
        
        # ✅ المستخدم دفع إذا حالته PAID
        has_paid = user_status == "PAID"
        
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
            "can_create_new_group": not in_active_group,  # ✅ يمكنه إنشاء مجموعة جديدة إذا ليس في مجموعة نشطة
            "needs_cleanup": in_active_group and (not group_exists or group_expired)
        })
        
    except Exception as e:
        print(f"❌ Error in my-status: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API: Clear Stuck Shipping Data
# ========================================
@csrf.exempt
@app.route("/api/groups/clear-stuck", methods=["POST"])
def groups_clear_stuck():
    """مسح بيانات الشحن العالقة للمستخدم"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        old_group = user.shipping_group_id
        old_status = user.shipping_status
        
        clear_user_shipping_data(user)
        
        db.session.commit()
        
        print(f"✅ Cleared stuck shipping data for user {user_id}")
        print(f"   Old group: {old_group}, Old status: {old_status}")
        
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
        print(f"❌ Error clearing stuck data: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API: Force Leave Group
# ========================================
@csrf.exempt
@app.route("/api/groups/force-leave", methods=["POST"])
def groups_force_leave():
    """مغادرة إجبارية للمجموعة"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        group_id = user.shipping_group_id
        
        clear_user_shipping_data(user)
        
        db.session.commit()
        
        print(f"✅ Force left group for user {user_id}, was in group: {group_id}")
        
        return jsonify({
            "ok": True,
            "message": "Successfully left the group! You can now join or create a new one.",
            "previous_group": group_id
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in force-leave: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API: Group Confirmation
# ========================================
@csrf.exempt
@app.route("/api/groups/confirm-ready", methods=["POST"])
def groups_confirm_ready():
    """تأكيد الموافقة على الشحن"""
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
        
        # ✅ جلب الأعضاء النشطين فقط
        members = Account.query.filter_by(shipping_group_id=group_id).filter(
            Account.shipping_status.in_(["WAITING", "READY"])
        ).all()
        
        if len(members) < 5:
            return jsonify({"ok": False, "message": "Group is not complete yet. Need 5 members."}), 400
        
        # Mark this user as READY
        user.shipping_status = "READY"
        db.session.commit()
        
        # Check if all members are READY
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
        print(f"Error confirming: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/cart/count", methods=["GET"])
def cart_count(): 
    cart = get_cart()
    count = sum(item.get("qty", 1) for item in cart.values())
    return jsonify({"count": count})


# ========================================
# ✅✅✅ ACCOUNT PROFILE APIs
# ========================================

@app.route("/api/account/profile", methods=["GET"])
def api_get_profile():
    """جلب بيانات المستخدم من قاعدة البيانات"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        # جلب الـ Profile إذا موجود
        profile = AccountProfile.query.filter_by(account_id=user_id).first()
        
        # تقسيم الاسم الكامل إلى first/last
        full_name = profile.full_name if profile and profile.full_name else user.username or ""
        name_parts = full_name.strip().split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # استخراج رقم الهاتف بدون +966
        phone = user.phone_number or ""
        if phone.startswith("+966"):
            phone = phone[4:]
        elif phone.startswith("966"):
            phone = phone[3:]
        elif phone.startswith("0"):
            phone = phone[1:]
        
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
        print(f"❌ Error getting profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


@csrf.exempt
@app.route("/api/account/profile", methods=["POST"])
def api_update_profile():
    """تحديث بيانات المستخدم في قاعدة البيانات"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        data = request.get_json() or {}
        
        first_name = (data.get("firstName") or "").strip()
        last_name = (data.get("lastName") or "").strip()
        phone = (data.get("phone") or "").strip()
        city = (data.get("city") or "").strip()
        avatar = data.get("avatar")  # emoji or image URL/base64
        
        # تحقق من رقم الهاتف
        digits = re.sub(r"\D+", "", phone)
        if digits and not re.fullmatch(r"5\d{8}", digits):
            return jsonify({
                "ok": False, 
                "error": "PHONE_INVALID",
                "message": "Phone must be 9 digits and start with 5"
            }), 400
        
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        # تحديث رقم الهاتف مع +966
        if digits:
            user.phone_number = f"+966{digits}"
        
        # تحديث المدينة
        if city:
            user.shipping_city = city.lower()
        
        # تحديث/إنشاء Profile
        profile = AccountProfile.query.filter_by(account_id=user_id).first()
        if not profile:
            profile = AccountProfile(account_id=user_id)
            db.session.add(profile)
        
        # تحديث الاسم الكامل
        full_name = f"{first_name} {last_name}".strip()
        if full_name:
            profile.full_name = full_name
        
        # تحديث الأفاتار
        if avatar:
            profile.avatar_url = avatar
        
        db.session.commit()
        
        print(f"✅ Profile updated for user {user_id}")
        
        return jsonify({
            "ok": True,
            "message": "Profile saved successfully! ✨",
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
        print(f"❌ Error updating profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# ✅✅✅ ORDER HISTORY API
# ========================================
@app.route("/api/account/orders", methods=["GET"])
def api_get_orders():
    """جلب جميع طلبات المستخدم من قاعدة البيانات"""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401

    try:
        orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()

        orders_list = []
        for order in orders:
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            
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

        print(f"✅ Retrieved {len(orders_list)} orders for user {user_id}")

        return jsonify({
            "ok": True,
            "orders": orders_list,
            "total_orders": len(orders_list)
        })

    except Exception as e:
        print(f"❌ Error in api_get_orders: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


def calculate_simulated_status(order_date, current_status):
    """
    حساب الحالة المحاكية بناءً على الوقت منذ الطلب
    
    | Time Since Order | Status |
    |-----------------|--------|
    | 0-3 days        | 🔵 Processing |
    | 3-7 days        | 🟡 Shipped |
    | 7+ days         | 🟢 Delivered |
    """
    
    if not order_date:
        return {"status": "Processing", "icon": "🔵", "color": "blue"}
    
    # إذا الحالة محددة مسبقاً (DELIVERED, CANCELLED)
    if current_status in ["DELIVERED", "CANCELLED"]:
        if current_status == "DELIVERED":
            return {"status": "Delivered", "icon": "🟢", "color": "green"}
        else:
            return {"status": "Cancelled", "icon": "🔴", "color": "red"}
    
    now = datetime.utcnow()
    days_since = (now - order_date).days
    
    if days_since < 3:
        return {"status": "Processing", "icon": "🔵", "color": "blue"}
    elif days_since < 7:
        return {"status": "Shipped", "icon": "🟡", "color": "yellow"}
    else:
        return {"status": "Delivered", "icon": "🟢", "color": "green"}
    
# ========================================
# ✅✅✅ API: Get Order Details with Dynamic Tracking
# ========================================
@app.route("/api/orders/<int:order_id>", methods=["GET"])
def api_get_order_details(order_id):
    """الحصول على تفاصيل الطلب مع التتبع الديناميكي"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        # جلب الطلب
        order = Order.query.filter_by(id=order_id, user_id=user_id).first()
        if not order:
            return jsonify({"ok": False, "message": "Order not found"}), 404
        
        # جلب المنتجات
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
        
        # ✅✅✅ المدينة من الطلب (وليس من البروفايل) - هذا المهم!
        city_key = (order.delivery_city or "riyadh").lower()
        city_info = SUPPORTED_CITIES.get(city_key, SUPPORTED_CITIES["riyadh"])
        
        # ✅ حساب التتبع الديناميكي
        now = datetime.utcnow()
        order_date = order.created_at or now
        
        # الوقت المنقضي منذ الطلب
        time_since_order = now - order_date
        hours_since = time_since_order.total_seconds() / 3600
        days_since = hours_since / 24
        
        # إجمالي أيام التوصيل للمدينة
        days_min = city_info["days_min"]
        days_max = city_info["days_max"]
        total_days = days_max
        
        # ✅ حساب المراحل بناءً على الوقت المنقضي
        stage_1_hours = 2  # ساعتين للتأكيد
        stage_2_days = total_days * 0.10  # معالجة
        stage_3_days = total_days * 0.40  # شحن
        stage_4_days = total_days * 0.30  # في الطريق
        
        # تحديد المرحلة الحالية
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
            stage_message = "Delivered Successfully! 🎉"
        
        # ✅ حساب التواريخ لكل مرحلة
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
        
        # ✅ حساب نسبة التقدم
        if current_stage == 5:
            total_progress = 100
        else:
            total_progress = min(100, int((days_since / total_days) * 100))
        
        # ✅ حساب الأيام المتبقية
        days_remaining = max(0, round(total_days - days_since, 1))
        
        # حساب تاريخ التوصيل المتوقع
        delivery_start = order_date + timedelta(days=days_min)
        delivery_end = order_date + timedelta(days=days_max)
        delivery_estimate = f"{delivery_start.strftime('%b %d')} - {delivery_end.strftime('%b %d, %Y')}"
        
        return jsonify({
            "ok": True,
            "order": {
                "id": order.id,
                "order_number": f"BF-{order.id:06d}",
                "tracking_number": f"BF-SHP-{order.id:06d}",
                "status": str(order.status.value) if order.status else "PAID",
                "delivery_status": stage_message,
                "created_at": order_date.isoformat(),
                "date_formatted": order_date.strftime("%B %d, %Y"),
                
                # المنتجات
                "products": products,
                "products_count": len(products),
                "items_count": total_qty,
                
                # التكاليف
                "subtotal": float(order.subtotal_sar or 0),
                "shipping_fee": float(order.shipping_sar or 0),
                "custom_duties": float(order.customs_sar or 0),
                "sfda_fee": float(order.fsa_fee_sar or 0),
                "handling_fee": float(order.handling_sar or 0),
                "total": float(order.total_sar or 0),
                "total_paid": float(order.total_sar or 0),
                
                # ✅ المدينة من الطلب!
                "city": city_key,
                "city_name": city_info["name_en"],
                "order_type": order.order_type or "solo",
                "group_id": order.group_id,
                "members_count": 5 if order.order_type == "shared" else 1,
                "delivery_days": f"{days_min}-{days_max}",
                "delivery_estimate": delivery_estimate,
                "days_remaining": days_remaining,
                
                # ✅ التتبع الديناميكي
                "tracking": {
                    "current_stage": current_stage,
                    "stage_status": stage_status,
                    "stage_message": stage_message,
                    "total_progress": total_progress,
                    "days_remaining": days_remaining,
                    "stage_dates": stage_dates
                },
                
                # للتوافق مع الـ Frontend القديم
                "current_stage": current_stage,
                "total_progress": total_progress,
                "stage_dates": stage_dates
            }
        })
        
    except Exception as e:
        print(f"❌ Error getting order details: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500
    
# ✅ API: Update Product Name - للـ AI و SmartPicks
# ========================================
@csrf.exempt
@app.route("/ai/product/update-name", methods=["POST"])
def ai_update_product_name():
    """تحديث اسم المنتج في قاعدة البيانات"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        data = request.get_json() or {}
        product_id = data.get("product_id")
        new_name = (data.get("name") or "").strip()
        
        if not product_id or not new_name:
            return jsonify({"ok": False, "message": "Product ID and name required"}), 400
        
        # البحث عن المنتج (يجب أن يكون ملك المستخدم)
        product = Product.query.filter_by(id=product_id, owner_user_id=user_id).first()
        
        if not product:
            # ممكن يكون المنتج بدون owner (من SmartPicks)
            product = Product.query.filter_by(id=product_id).first()
            if not product:
                return jsonify({"ok": False, "message": "Product not found"}), 404
        
        old_name = product.name
        product.name = new_name
        db.session.commit()
        
        print(f"✅ Product {product_id} name: '{old_name}' → '{new_name}'")
        
        return jsonify({
            "ok": True,
            "message": "Name updated",
            "product_id": product_id,
            "old_name": old_name,
            "new_name": new_name
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating name: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500
    
# ========================= Dev Server =========================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)