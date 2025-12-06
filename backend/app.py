from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from pathlib import Path
import os, random, re ,json
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf,validate_csrf, CSRFError 
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
from models.all_models import AISession, AIMessage ,AIGeneration
from models.all_models import AIMessage

load_dotenv()
print("DEBUG] OPENAI_API_KEY present:",bool(os.getenv("OPENAI_API_KEY")))
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
migrate= Migrate(app, db)
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

# =========================
#         ROUTES
# =========================

@app.route("/",strict_slashes=False)
def home():
    return redirect(url_for("login_page"),code=302)

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

def cart_page():
    return render_template("cart.html")

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
    last  = (data.get("lastName") or "").strip()
    addr  = (data.get("address") or "").strip()
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
    
# ========= cart helpers =========

def get_cart():
    return session.get("cart", {})

def save_cart(cart: dict):
    session["cart"] = cart
    session.modified = True

def get_cart_count():
    cart = get_cart()
    return sum(item["qty"] for item in cart.values())

# ========= SmartPicks + Cart =========

@app.route("/smartPicks", strict_slashes=False)
def smartPicks_page():
    return render_template("smartPicks.html", cart_count=get_cart_count())

@app.route("/cart", strict_slashes=False)
def cart_page():
    """Display cart page with products loaded from session"""
    
    cart = get_cart()
    items = []
    
    print(f"📦 Loading cart: {len(cart)} items")
    
    # ✅ لكل منتج في السلة، نجيب صورته من Database
    for product_id, cart_item in cart.items():
        # جلب المنتج من Database
        try:
            product = Product.query.filter_by(id=product_id).first()
            
            if product:
                # ✅ تحقق من وجود صورة
                image_url = None
                if product.image_primary:
                    # لو الصورة Base64، ناخذها كاملة
                    if product.image_primary.startswith("data:image"):
                        image_url = product.image_primary
                        print(f"✅ Loaded Base64 image for {product.name}: {len(image_url)} chars")
                    else:
                        # لو URL عادي
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
                # لو المنتج محذوف من DB
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
            
            # حتى لو في خطأ، نضيف المنتج بدون صورة
            items.append({
                "id": product_id,
                "name": cart_item.get("name", "Product"),
                "price": cart_item.get("price", 0),
                "qty": cart_item.get("qty", 1),
                "image": None,
            })
    
    # Calculate totals
    subtotal = sum(item["price"] * item["qty"] for item in items) if items else 0
    tax = subtotal * 0.15
    total = subtotal + tax
    
    print(f"📊 Cart: {len(items)} items, Subtotal: {subtotal} SAR")
    
    return render_template("cart.html", 
                         items=items, 
                         subtotal=round(subtotal, 1),
                         tax=round(tax, 1),
                         total=round(total, 1))

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

    # ✅ بدل ما نحفظ الصورة في Session، نحفظ فقط علامة
    # الصورة بنجيبها لاحقاً من Database في /cart
    image_marker = f"DB:{product_id}"  # علامة تقول "اجلب من DB"

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
            "image": image_marker,  # ✅ علامة بدل Base64
            "qty": 1,
        }
        print(f"✅ Added new item: {product_id}")

    save_cart(cart)
    print(f"✅ CART NOW: {len(cart)} items")
    return jsonify({"ok": True, "cart_count": get_cart_count()})




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
    
    # حساب المجموع الجديد
    cart_subtotal = sum(item["price"] * item["qty"] for item in cart.values())
    
    return jsonify({
        "ok": True,
        "cart_count": get_cart_count(),
        "cart_subtotal": cart_subtotal,
        "cart_total": cart_subtotal
    })

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
    if action == "inc":
        item["qty"] += 1
    elif action == "dec":
        item["qty"] -= 1
        if item["qty"] <= 0:
            del cart[product_id]
            save_cart(cart)
            return jsonify({
                "ok": True,
                "removed": True,
                "cart_count": get_cart_count(),
                "cart_total": sum(i["price"] * i["qty"] for i in cart.values())
            })

    save_cart(cart)
    cart_total = sum(i["price"] * i["qty"] for i in cart.values())

    return jsonify({
        "ok": True,
        "removed": False,
        "item_qty": item["qty"],
        "cart_count": get_cart_count(),
        "cart_total": cart_total
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
    email    = (data.get("email") or "").strip().lower()
    phone    = (data.get("phone") or "").strip() or None
    password = data.get("password") or ""
    confirm  = data.get("confirm_password") or password

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
    last  = request.form.get("last_name")
    email = request.form.get("email")
    msg   = request.form.get("message")
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

@app.route("/logout", methods=["GET"], strict_slashes=False, endpoint="logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# =========================
#      OpenAI Chat API
# =========================


def generate_product_name(packaging_desc, product_type, finish):
    """توليد اسم ذكي من وصف المستخدم"""
    try:
        desc = (packaging_desc or "").lower()
        
        # نوع المنتج
        if "lipstick" in desc or "LIPSTICK" in (product_type or ""):
            type_word = "Lipstick"
        elif "blush" in desc or "BLUSH" in (product_type or ""):
            type_word = "Blush"
        elif "mascara" in desc or "MASCARA" in (product_type or ""):
            type_word = "Mascara"
        elif "foundation" in desc or "FOUNDATION" in (product_type or ""):
            type_word = "Foundation"
        elif "eyeliner" in desc or "EYELINER" in (product_type or ""):
            type_word = "Eyeliner"
        else:
            type_word = "Product"
        
        # لون
        color = None
        if "pink" in desc:
            color = "Pink"
        elif "red" in desc:
            color = "Red"
        elif "gold" in desc:
            color = "Gold"
        elif "nude" in desc:
            color = "Nude"
        elif "coral" in desc:
            color = "Coral"
        
        # شكل
        theme = None
        if "sunflower" in desc:
            theme = "Sunflower"
        elif "heart" in desc:
            theme = "Heart"
        elif "star" in desc:
            theme = "Star"
        elif "rose" in desc:
            theme = "Rose"
        elif "cloud" in desc:
            theme = "Cloud"
        elif "butterfly" in desc:
            theme = "Butterfly"
        elif "flower" in desc:
            theme = "Flower"
        
        # بناء الاسم
        parts = []
        if color:
            parts.append(color)
        if theme:
            parts.append(theme)
        parts.append(type_word)
        
        result = " ".join(parts) if len(parts) > 1 else f"Custom {type_word}"
        print(f"✅ Generated name: {result}")
        return result
        
    except Exception as e:
        print(f"❌ Error in generate_product_name: {e}")
        return "Custom Product"

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

        # 1) توليد الصورة من OpenAI
        result = OpenAI_Client.images.generate(
            model="dall-e-2",
            prompt=prompt_raw,
            size="1024x1024",
            response_format="b64_json",
        )
        b64_data = result.data[0].b64_json
        image_url = f"data:image/png;base64,{b64_data}"

        # ✅ 2) استخراج معلومات من الـ prompt للتسمية الذكية
        # الـ prompt عادة يكون على شكل:
        # "Professional product photo of a LIPSTICK... Packaging: [وصف المستخدم]"
        
        # نستخرج نوع المنتج
        product_type = None
        if "LIPSTICK" in prompt_raw.upper():
            product_type = "LIPSTICK"
        elif "MASCARA" in prompt_raw.upper():
            product_type = "MASCARA"
        elif "BLUSH" in prompt_raw.upper():
            product_type = "BLUSH"
        elif "FOUNDATION" in prompt_raw.upper():
            product_type = "FOUNDATION"
        elif "EYELINER" in prompt_raw.upper():
            product_type = "EYELINER"
        
        # نستخرج الـ finish
        finish = None
        if "matte" in prompt_raw.lower():
            finish = "matte"
        elif "dewy" in prompt_raw.lower():
            finish = "dewy"
        
        # نستخرج وصف الـ packaging (الجزء المهم)
        packaging_desc = ""
        if "Packaging:" in prompt_raw:
            packaging_desc = prompt_raw.split("Packaging:")[-1].split(".")[0].strip()
        
        print(f"📝 Extracted packaging description: {packaging_desc}")
        
        # ✅ توليد اسم ذكي
        product_name = generate_product_name(packaging_desc, product_type, finish)
        
        print(f"✅ Generated product name: {product_name}")
        
        # 3) إنشاء Product
        product = Product(
            supplier_id=None,
            owner_user_id=user_id,
            name=product_name,  # ✅ الاسم الذكي من وصف المستخدم
            sku=f"AI-{user_id}-{int(datetime.utcnow().timestamp())}-{random.randint(1000,9999)}",
            description=prompt_raw,
            image_primary=image_url,
            origin=ProductOriginEnum.AI,
            visibility=ProductVisibilityEnum.PRIVATE,
            status=ProductStatusEnum.DRAFT,
            price_sar=120.0,
            base_price_sar=120.0,
            complexity_factor=1,
            category_multiplier=1,
            discount_percent=0,
            final_price_sar=120.0,
            category="AI-CUSTOM",
            brand="BeautyFlow AI",
        )
        product.recalc_price()
        
        db.session.add(product)
        db.session.flush()

        # 4) حفظ في AIGeneration
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
                "vibe": data.get("vibe")
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
                "name": product.name,  # ✅ الاسم الذكي
                "price_sar": float(product.final_price_sar or 0),
                "size": "10g"
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
        
        # جلب آخر 20 منتج AI
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

# FIXED: Add to Favorites Route
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
#       COST SHARING APIs - UPDATED!
# ========================================
# ========================================

# المدن المدعومة مع معاملات الأسعار وأيام التوصيل
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
    "sakaka": {"name": "سكاكا", "name_en": "Sakaka", "multiplier": 1.22, "days_min": 12, "days_max": 16},
}


def calculate_shipping_cost(weight_kg, product_cost, city_key, members_count=1):
    """
    حساب تكلفة الشحن الكاملة
    
    المعادلة:
    - الشحن الأساسي = (الوزن × 16 × معامل المدينة) + 200
    - الجمارك = الشحن × 5%
    - رسوم SFDA = 20 ريال
    - المناولة = 80 ريال
    - رسوم الدمج = 40 ريال (إذا أكثر من شخص)
    """
    city = SUPPORTED_CITIES.get(city_key, SUPPORTED_CITIES["riyadh"])
    multiplier = city["multiplier"]
    
    # الشحن الأساسي
    base_shipping = (weight_kg * 16 * multiplier) + 200
    
    # الجمارك (5% من الشحن)
    customs = base_shipping * 0.05
    
    # رسوم SFDA
    sfda_fee = 20
    
    # المناولة
    handling = 80
    
    # رسوم الدمج (فقط إذا أكثر من شخص)
    merge_fee = 40 if members_count > 1 else 0
    
    # المجموع قبل التقسيم
    total_before_split = base_shipping + customs + sfda_fee + handling + merge_fee
    
    # التقسيم على عدد الأعضاء
    per_person = total_before_split / members_count
    
    return {
        "base_shipping": round(base_shipping, 2),
        "customs": round(customs, 2),
        "sfda_fee": sfda_fee,
        "handling": handling,
        "merge_fee": merge_fee,
        "total_before_split": round(total_before_split, 2),
        "members_count": members_count,
        "per_person": round(per_person, 2),
        "city": city,
        "savings": round(total_before_split - per_person, 2) if members_count > 1 else 0
    }


def generate_group_id(city_key):
    """توليد معرف فريد للمجموعة"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
    random_suffix = random.randint(100, 999)
    return f"{city_key}-{timestamp}-{random_suffix}"


# ========================================
# API 1: Load Cart Data for Cost Sharing (UPDATED)
# ========================================

@csrf.exempt
@app.route("/api/cost-sharing/load", methods=["GET"])
def cost_sharing_load():
    """تحميل بيانات السلة مع حساب التكاليف الأولية - محدث"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        cart = get_cart()
        
        if not cart:
            return jsonify({
                "ok": False,
                "cart_empty": True,
                "message": "Your cart is empty"
            })
        
        # حساب تفاصيل السلة
        items = []
        total_weight = 0
        total_cost = 0
        
        for product_id, cart_item in cart.items():
            product = Product.query.filter_by(id=product_id).first()
            
            if product:
                # افتراض وزن 0.1 كجم لكل منتج تجميل
                weight = 0.1 * cart_item.get("qty", 1)
                price = float(product.price_sar or cart_item.get("price", 0))
                qty = cart_item.get("qty", 1)
                
                items.append({
                    "id": product_id,
                    "name": product.name,
                    "price": price,
                    "qty": qty,
                    "weight": weight,
                    "subtotal": price * qty
                })
                
                total_weight += weight
                total_cost += price * qty
        
        # حساب الشحن للرياض كمثال افتراضي
        shipping_solo = calculate_shipping_cost(total_weight, total_cost, "riyadh", 1)
        shipping_shared = calculate_shipping_cost(total_weight, total_cost, "riyadh", 5)
        
        # التحقق إذا المستخدم في مجموعة
        user = Account.query.get(user_id)
        in_group = user.is_in_shipping_group() if user else False
        
        return jsonify({
            "ok": True,
            "cart_empty": False,
            "items": items,
            "summary": {
                "items_count": sum(i["qty"] for i in items),  # ✅ NEW
                "total_items": len(items),
                "total_qty": sum(i["qty"] for i in items),
                "total_weight": round(total_weight, 2),
                "total_cost": round(total_cost, 2),
                "tax": round(total_cost * 0.15, 2),
                "grand_total": round(total_cost * 1.15, 2)
            },
            "shipping_solo": shipping_solo,
            "shipping_shared": shipping_shared,
            "potential_savings": round(shipping_solo["per_person"] - shipping_shared["per_person"], 2),
            "in_group": in_group,
            "group_id": user.shipping_group_id if in_group else None,
            "user_status": user.shipping_status if user else None,  # ✅ NEW
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
# API 2: Calculate Shipping for Specific City
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
        members_count = data.get("members", 1)
        
        if city_key not in SUPPORTED_CITIES:
            return jsonify({"ok": False, "message": "City not supported"}), 400
        
        cart = get_cart()
        if not cart:
            return jsonify({"ok": False, "message": "Cart is empty"}), 400
        
        # حساب الوزن والتكلفة
        total_weight = 0
        total_cost = 0
        
        for product_id, cart_item in cart.items():
            product = Product.query.filter_by(id=product_id).first()
            if product:
                weight = 0.1 * cart_item.get("qty", 1)
                price = float(product.price_sar or cart_item.get("price", 0))
                qty = cart_item.get("qty", 1)
                total_weight += weight
                total_cost += price * qty
        
        # حساب الشحن
        shipping = calculate_shipping_cost(total_weight, total_cost, city_key, members_count)
        shipping_solo = calculate_shipping_cost(total_weight, total_cost, city_key, 1)
        
        city_info = SUPPORTED_CITIES[city_key]
        
        return jsonify({
            "ok": True,
            "city": {
                "key": city_key,
                "name": city_info["name"],
                "name_en": city_info["name_en"],
                "delivery_days": f"{city_info['days_min']}-{city_info['days_max']}"
            },
            "shipping": shipping,
            "shipping_solo": shipping_solo,
            "savings": round(shipping_solo["per_person"] - shipping["per_person"], 2),
            "savings_percent": round((1 - shipping["per_person"] / shipping_solo["per_person"]) * 100, 1) if shipping_solo["per_person"] > 0 else 0
        })
        
    except Exception as e:
        print(f"❌ Error in cost_sharing_calculate: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API 3: Get Available Groups to Join (UPDATED)
# ========================================

@csrf.exempt
@app.route("/api/groups/available", methods=["GET"])
def groups_available():
    """جلب المجموعات المتاحة للانضمام في مدينة معينة - محدث"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        city_key = (request.args.get("city") or "riyadh").lower()
        
        if city_key not in SUPPORTED_CITIES:
            return jsonify({"ok": False, "message": "City not supported"}), 400
        
        # جلب المجموعات النشطة في هذه المدينة
        # ✅ دعم الحالات بالحروف الكبيرة والصغيرة
        groups_query = db.session.query(
            Account.shipping_group_id,
            Account.shipping_city,
            Account.shipping_expires_at,
            db.func.count(Account.id).label('members_count'),
            db.func.sum(Account.shipping_weight).label('total_weight'),
            db.func.min(Account.shipping_joined_at).label('created_at')
        ).filter(
            Account.shipping_city == city_key,
            Account.shipping_status.in_(["WAITING", "waiting"]),  # ✅ دعم الحالتين
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
            # حساب الوقت المتبقي
            if g.shipping_expires_at:
                time_left = g.shipping_expires_at - datetime.utcnow()
                days_left = time_left.days
                hours_left = time_left.seconds // 3600
                time_left_str = f"{days_left}d {hours_left}h" if days_left > 0 else f"{hours_left}h"
            else:
                time_left_str = "N/A"
            
            # حساب تكلفة الشحن المتوقعة لـ 5 أشخاص
            shipping_5 = calculate_shipping_cost(
                float(g.total_weight or 0.5),
                500,
                city_key,
                5
            )
            
            groups.append({
                "group_id": g.shipping_group_id,
                "city": city_key,
                "members_count": g.members_count,
                "spots_left": 5 - g.members_count,
                "created_at": g.created_at.isoformat() if g.created_at else None,
                "expires_at": g.shipping_expires_at.isoformat() if g.shipping_expires_at else None,
                "time_left": time_left_str,
                "estimated_cost_per_person": shipping_5["per_person"],
                "potential_savings": round(shipping_5["total_before_split"] - shipping_5["per_person"], 2)
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
# API 4: Create New Group (UPDATED)
# ========================================

@csrf.exempt
@app.route("/api/groups/create", methods=["POST"])
def groups_create():
    """إنشاء مجموعة جديدة - محدث"""
    
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
        
        # التحقق إذا المستخدم في مجموعة
        if user.is_in_shipping_group():
            return jsonify({
                "ok": False, 
                "message": "You are already in a group. Leave it first.",
                "current_group": user.shipping_group_id
            }), 400
        
        # التحقق من وجود منتجات في السلة
        cart = get_cart()
        if not cart:
            return jsonify({"ok": False, "message": "Your cart is empty"}), 400
        
        # حساب الوزن والتكلفة
        total_weight = 0
        total_cost = 0
        cart_items = []
        
        for product_id, cart_item in cart.items():
            product = Product.query.filter_by(id=product_id).first()
            if product:
                weight = 0.1 * cart_item.get("qty", 1)
                price = float(product.price_sar or cart_item.get("price", 0))
                qty = cart_item.get("qty", 1)
                total_weight += weight
                total_cost += price * qty
                cart_items.append({
                    "id": product_id,
                    "name": product.name,
                    "price": price,
                    "qty": qty
                })
        
        # توليد group_id
        group_id = generate_group_id(city_key)
        
        # تحديث بيانات المستخدم
        user.shipping_group_id = group_id
        user.shipping_city = city_key
        user.shipping_joined_at = datetime.utcnow()
        user.shipping_cart_snapshot = json.dumps(cart_items)
        user.shipping_weight = total_weight
        user.shipping_product_cost = total_cost
        user.shipping_is_creator = True
        user.shipping_expires_at = datetime.utcnow() + timedelta(days=7)
        user.shipping_status = "WAITING"  # ✅ Uppercase
        user.shipping_extended_count = 0
        
        # حساب تكلفة الشحن (شخص واحد حالياً)
        shipping = calculate_shipping_cost(total_weight, total_cost, city_key, 1)
        user.shipping_cost = shipping["per_person"]
        
        db.session.commit()
        
        city_info = SUPPORTED_CITIES[city_key]
        
        return jsonify({
            "ok": True,
            "message": "Group created successfully! 🎉",
            "group": {
                "group_id": group_id,
                "city": city_key,
                "city_name": city_info["name_en"],  # ✅ English name
                "members_count": 1,
                "your_weight": total_weight,
                "your_product_cost": total_cost,
                "shipping_cost": shipping["per_person"],
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
# API 5: Join Existing Group (UPDATED)
# ========================================

@csrf.exempt
@app.route("/api/groups/join", methods=["POST"])
def groups_join():
    """الانضمام لمجموعة موجودة - محدث"""
    
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
        
        # التحقق إذا المستخدم في مجموعة
        if user.is_in_shipping_group():
            return jsonify({"ok": False, "message": "You are already in a group"}), 400
        
        # التحقق من السلة
        cart = get_cart()
        if not cart:
            return jsonify({"ok": False, "message": "Your cart is empty"}), 400
        
        # جلب معلومات المجموعة - ✅ دعم الحالتين
        group_members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "waiting"])
        ).all()
        
        if not group_members:
            return jsonify({"ok": False, "message": "Group not found or expired"}), 404
        
        if len(group_members) >= 5:
            return jsonify({"ok": False, "message": "Group is full"}), 400
        
        # التحقق من انتهاء الصلاحية
        first_member = group_members[0]
        if first_member.shipping_expires_at and first_member.shipping_expires_at < datetime.utcnow():
            return jsonify({"ok": False, "message": "Group has expired"}), 400
        
        city_key = first_member.shipping_city
        
        # حساب الوزن والتكلفة
        total_weight = 0
        total_cost = 0
        cart_items = []
        
        for product_id, cart_item in cart.items():
            product = Product.query.filter_by(id=product_id).first()
            if product:
                weight = 0.1 * cart_item.get("qty", 1)
                price = float(product.price_sar or cart_item.get("price", 0))
                qty = cart_item.get("qty", 1)
                total_weight += weight
                total_cost += price * qty
                cart_items.append({
                    "id": product_id,
                    "name": product.name,
                    "price": price,
                    "qty": qty
                })
        
        # إضافة المستخدم للمجموعة
        user.shipping_group_id = group_id
        user.shipping_city = city_key
        user.shipping_joined_at = datetime.utcnow()
        user.shipping_cart_snapshot = json.dumps(cart_items)
        user.shipping_weight = total_weight
        user.shipping_product_cost = total_cost
        user.shipping_is_creator = False
        user.shipping_expires_at = first_member.shipping_expires_at
        user.shipping_status = "WAITING"  # ✅ Uppercase
        user.shipping_extended_count = 0
        
        db.session.flush()
        
        # إعادة حساب التكلفة لكل الأعضاء
        new_members_count = len(group_members) + 1
        group_total_weight = sum(float(m.shipping_weight or 0) for m in group_members) + total_weight
        
        new_shipping = calculate_shipping_cost(group_total_weight, 0, city_key, new_members_count)
        
        # تحديث تكلفة الشحن لكل الأعضاء
        for member in group_members:
            member_weight = float(member.shipping_weight or 0)
            member_share = (member_weight / group_total_weight) * new_shipping["total_before_split"] if group_total_weight > 0 else new_shipping["per_person"]
            member.shipping_cost = round(member_share, 2)
        
        # تكلفة المستخدم الجديد
        user_share = (total_weight / group_total_weight) * new_shipping["total_before_split"] if group_total_weight > 0 else new_shipping["per_person"]
        user.shipping_cost = round(user_share, 2)
        
        # ✅ التحقق إذا اكتملت المجموعة (5 أعضاء)
        if new_members_count >= 5:
            for member in group_members:
                member.shipping_status = "READY"  # ✅ Uppercase
            user.shipping_status = "READY"
        
        db.session.commit()
        
        city_info = SUPPORTED_CITIES[city_key]
        
        return jsonify({
            "ok": True,
            "message": "Joined group successfully! 🎉",
            "group": {
                "group_id": group_id,
                "city": city_key,
                "city_name": city_info["name_en"],  # ✅ English name
                "members_count": new_members_count,
                "your_weight": total_weight,
                "your_shipping_cost": user.shipping_cost,
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
# API 6: Leave Group
# ========================================

@csrf.exempt
@app.route("/api/groups/leave", methods=["POST"])
def groups_leave():
    """مغادرة المجموعة"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        if not user.is_in_shipping_group():
            return jsonify({"ok": False, "message": "You are not in any group"}), 400
        
        group_id = user.shipping_group_id
        city_key = user.shipping_city
        was_creator = user.shipping_is_creator
        
        # مسح بيانات الشحن للمستخدم
        user.clear_shipping_data()
        
        db.session.flush()
        
        # جلب الأعضاء الباقين - ✅ دعم الحالتين
        remaining_members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY", "waiting", "ready"])
        ).all()
        
        if remaining_members:
            # إعادة حساب التكلفة
            total_weight = sum(float(m.shipping_weight or 0) for m in remaining_members)
            new_shipping = calculate_shipping_cost(total_weight, 0, city_key, len(remaining_members))
            
            for member in remaining_members:
                member_weight = float(member.shipping_weight or 0)
                member_share = (member_weight / total_weight) * new_shipping["total_before_split"] if total_weight > 0 else new_shipping["per_person"]
                member.shipping_cost = round(member_share, 2)
                
                # لو الشخص كان Creator، نعين أقدم عضو كـ creator جديد
                if was_creator and member == remaining_members[0]:
                    member.shipping_is_creator = True
                
                # لو أقل من 5، نرجع الحالة WAITING
                if len(remaining_members) < 5:
                    member.shipping_status = "WAITING"
        
        db.session.commit()
        
        return jsonify({
            "ok": True,
            "message": "You have left the group",
            "remaining_members": len(remaining_members) if remaining_members else 0
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in groups_leave: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API 7: Get My Group Info (UPDATED)
# ========================================

@csrf.exempt
@app.route("/api/groups/my-group", methods=["GET"])
def groups_my_group():
    """جلب معلومات مجموعتي - محدث لدعم الحالات الأربع"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        # إذا المستخدم ليس في مجموعة
        if not user.shipping_group_id:
            return jsonify({
                "ok": True,
                "in_group": False,
                "status": None,
                "message": "You are not in any group"
            })
        
        group_id = user.shipping_group_id
        
        # جلب كل الأعضاء - ✅ دعم الحالات المختلفة
        members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY", "PAID", "waiting", "ready", "paid"])
        ).order_by(Account.shipping_joined_at).all()
        
        members_list = []
        total_weight = 0
        total_product_cost = 0
        paid_count = 0
        
        for m in members:
            # ✅ تحديد حالة الدفع
            is_paid = (m.shipping_status or "").upper() == "PAID"
            if is_paid:
                paid_count += 1
                
            members_list.append({
                "id": m.id,
                "username": m.username or f"User{m.id}",
                "is_creator": m.shipping_is_creator,
                "is_you": m.id == user_id,
                "weight": float(m.shipping_weight or 0),
                "product_cost": float(m.shipping_product_cost or 0),
                "shipping_cost": float(m.shipping_cost or 0),
                "joined_at": m.shipping_joined_at.isoformat() if m.shipping_joined_at else None,
                "avatar": m.get_avatar_url() if hasattr(m, 'get_avatar_url') else f"https://i.pravatar.cc/60?img={m.id % 70}",
                "status": (m.shipping_status or "").upper(),
                "is_paid": is_paid  # ✅ NEW
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
        
        # حساب الشحن الحالي
        current_shipping = calculate_shipping_cost(total_weight, total_product_cost, city_key, len(members))
        shipping_solo = calculate_shipping_cost(float(user.shipping_weight or 0), float(user.shipping_product_cost or 0), city_key, 1)
        
        # ✅ تحديد الحالة الفعلية للمجموعة (بالحروف الكبيرة)
        user_status = (user.shipping_status or "").upper()
        
        return jsonify({
            "ok": True,
            "in_group": True,
            "group": {
                "group_id": group_id,
                "city": city_key,
                "city_name": city_info["name_en"],  # ✅ English name
                "city_name_ar": city_info["name"],
                "status": user_status,  # ✅ Normalized status
                "is_complete": len(members) >= 5,
                "members_count": len(members),
                "spots_left": max(0, 5 - len(members)),
                "total_weight": round(total_weight, 2),
                "total_product_cost": round(total_product_cost, 2),
                "expires_at": user.shipping_expires_at.isoformat() if user.shipping_expires_at else None,
                "time_left": time_left,
                "can_extend": (user.shipping_extended_count or 0) < 2,
                "extended_count": user.shipping_extended_count or 0,
                "delivery_days": f"{city_info['days_min']}-{city_info['days_max']}",
                "paid_count": paid_count,  # ✅ NEW
                "all_paid": paid_count == len(members) and len(members) > 0  # ✅ NEW
            },
            "members": members_list,
            "your_info": {
                "is_creator": user.shipping_is_creator,
                "weight": float(user.shipping_weight or 0),
                "product_cost": float(user.shipping_product_cost or 0),
                "shipping_cost": float(user.shipping_cost or 0),
                "shipping_solo": shipping_solo["per_person"],
                "savings": round(shipping_solo["per_person"] - float(user.shipping_cost or 0), 2),
                "status": user_status,
                "is_paid": user_status == "PAID"
            },
            "shipping_breakdown": current_shipping
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
        
        if not user.is_in_shipping_group():
            return jsonify({"ok": False, "message": "You are not in any group"}), 400
        
        # فقط Creator يقدر يمدد
        if not user.shipping_is_creator:
            return jsonify({"ok": False, "message": "Only group creator can extend"}), 403
        
        # التحقق من عدد مرات التمديد
        if (user.shipping_extended_count or 0) >= 2:
            return jsonify({"ok": False, "message": "Maximum extensions reached (2)"}), 400
        
        group_id = user.shipping_group_id
        
        # تمديد لكل الأعضاء
        members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY", "waiting", "ready"])
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
# API 9: Ship Now (UPDATED)
# ========================================

@csrf.exempt
@app.route("/api/groups/ship-now", methods=["POST"])
def groups_ship_now():
    """الشحن بالعدد الحالي (حتى لو أقل من 5) - محدث"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        if not user.is_in_shipping_group():
            return jsonify({"ok": False, "message": "You are not in any group"}), 400
        
        # فقط Creator يقدر يشحن
        if not user.shipping_is_creator:
            return jsonify({"ok": False, "message": "Only group creator can initiate shipping"}), 403
        
        group_id = user.shipping_group_id
        
        # تغيير حالة كل الأعضاء إلى READY
        members = Account.query.filter_by(
            shipping_group_id=group_id
        ).filter(
            Account.shipping_status.in_(["WAITING", "waiting"])
        ).all()
        
        for member in members:
            member.shipping_status = "READY"  # ✅ Uppercase
        
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
# API 10: Process Payment (UPDATED)
# ========================================

@csrf.exempt
@app.route("/api/payment/process", methods=["POST"])
def payment_process():
    """معالجة الدفع - محدث لدعم Solo و Shared"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "Please login first"}), 401
    
    try:
        data = request.get_json() or {}
        payment_type = data.get("type", "shared")  # solo or shared
        payment_method = data.get("method", "card")
        city = data.get("city")
        
        user = Account.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "message": "User not found"}), 404
        
        # ✅ Handle Solo Payment
        if payment_type == "solo":
            cart = get_cart()
            if not cart:
                return jsonify({"ok": False, "message": "Cart is empty"}), 400
            
            # حساب التكلفة
            total_weight = 0
            total_cost = 0
            
            for product_id, cart_item in cart.items():
                product = Product.query.filter_by(id=product_id).first()
                if product:
                    weight = 0.1 * cart_item.get("qty", 1)
                    price = float(product.price_sar or cart_item.get("price", 0))
                    qty = cart_item.get("qty", 1)
                    total_weight += weight
                    total_cost += price * qty
            
            shipping = calculate_shipping_cost(total_weight, total_cost, city or "riyadh", 1)
            
            # TODO: تكامل مع بوابة الدفع
            # هنا فقط نفرغ السلة
            
            session["cart"] = {}
            session.modified = True
            
            return jsonify({
                "ok": True,
                "message": "Payment successful! ✅",
                "type": "solo",
                "amount_paid": round(total_cost + shipping["per_person"], 2),
                "redirect_to": "/shipment"
            })
        
        # ✅ Handle Shared Payment
        else:
            # التحقق من حالة المجموعة
            if not user.shipping_group_id:
                return jsonify({"ok": False, "message": "You are not in any group"}), 400
            
            user_status = (user.shipping_status or "").upper()
            
            if user_status == "PAID":
                return jsonify({"ok": False, "message": "You have already paid"}), 400
            
            if user_status != "READY":
                return jsonify({"ok": False, "message": "Group is not ready for payment yet"}), 400
            
            # TODO: تكامل مع بوابة الدفع
            # هنا فقط نغير الحالة
            
            user.shipping_status = "PAID"
            
            # تفريغ السلة
            session["cart"] = {}
            session.modified = True
            
            db.session.commit()
            
            # التحقق إذا كل الأعضاء دفعوا
            group_id = user.shipping_group_id
            unpaid = Account.query.filter_by(
                shipping_group_id=group_id
            ).filter(
                Account.shipping_status.in_(["READY", "ready"])
            ).count()
            
            all_paid = unpaid == 0
            
            return jsonify({
                "ok": True,
                "message": "Payment successful! ✅",
                "type": "shared",
                "all_members_paid": all_paid,
                "amount_paid": float(user.shipping_product_cost or 0) + float(user.shipping_cost or 0),
                "redirect_to": "/shipment" if all_paid else None
            })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in payment_process: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================================
# API 11: Get Statistics for Dashboard
# ========================================

@csrf.exempt
@app.route("/api/cost-sharing/stats", methods=["GET"])
def cost_sharing_stats():
    """إحصائيات للداشبورد"""
    
    try:
        # إجمالي المجموعات النشطة
        active_groups = db.session.query(
            db.func.count(db.func.distinct(Account.shipping_group_id))
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY", "waiting", "ready"]),
            Account.shipping_group_id.isnot(None)
        ).scalar() or 0
        
        # إجمالي المستخدمين في مجموعات
        users_in_groups = Account.query.filter(
            Account.shipping_status.in_(["WAITING", "READY", "waiting", "ready"]),
            Account.shipping_group_id.isnot(None)
        ).count()
        
        # إجمالي التوفير (تقديري)
        total_savings = users_in_groups * 80  # تقدير متوسط التوفير
        
        # المجموعات حسب المدينة
        by_city = db.session.query(
            Account.shipping_city,
            db.func.count(db.func.distinct(Account.shipping_group_id)).label('groups_count'),
            db.func.count(Account.id).label('members_count')
        ).filter(
            Account.shipping_status.in_(["WAITING", "READY", "waiting", "ready"]),
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
                "total_savings_estimate": total_savings,
                "cities": cities_stats
            }
        })
        
    except Exception as e:
        print(f"❌ Error in cost_sharing_stats: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500


# ========================= Dev Server =========================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)