from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from pathlib import Path
import os, random, re ,json
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf,validate_csrf, CSRFError 
from datetime import datetime
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
    items = list(cart.values())
    
    # Calculate totals
    subtotal = sum(item["price"] * item["qty"] for item in items) if items else 0
    tax = subtotal * 0.15
    total = subtotal + tax
    
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

    image = (data.get("image")
             or data.get("image_url")
             or data.get("img")
             or "").strip()

    if image.startswith("data:image"):
        print("⚠️ Skipping base64 image to avoid session explosion")
        image = ""


    if not product_id:
        print("🛑 MISSING_ID in /cart/add")
        return jsonify({"ok": False, "error": "MISSING_ID"}), 400

    cart = get_cart()
    if product_id in cart:
        cart[product_id]["qty"] += 1
    else:
        cart[product_id] = {
            "id": product_id,
            "name": name or "AI Product",
            "price": price,
            "image": image,
            "qty": 1,
        }

    save_cart(cart)
    print("✅ CART NOW:", cart)
    return jsonify({"ok": True, "cart_count": get_cart_count()})

@csrf.exempt
@app.post("/cart/remove")
def cart_remove():
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("id") or "").strip()

    if not product_id:
        return jsonify({"ok": False, "error": "MISSING_ID"}), 400

    cart = get_cart()
    if product_id in cart:
        del cart[product_id]

    save_cart(cart)
    return jsonify({
        "ok": True,
        "cart_count": get_cart_count(),
        "cart_total": sum(item["price"] * item["qty"] for item in cart.values())
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

        # 2) إنشاء Product
        product_name = "Custom AI Product"
        
        product = Product(
            supplier_id=None,
            owner_user_id=user_id,
            name=product_name,
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

        # 3) حفظ في AIGeneration
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
            prompt_json={"prompt": prompt_raw},
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
                "name": product.name,
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
# ========================================

@csrf.exempt
@app.route("/ai/favorites/add", methods=["POST"])
def ai_favorites_add():
    """Add product to user's favorites/wishlist"""
    
    # ✅ 1. التحقق من تسجيل الدخول
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "ok": False,
            "message": "Please login first"
        }), 401
    
    # ✅ 2. الحصول على product_id
    try:
        data = request.get_json()
        product_id = data.get("product_id")
        
        if not product_id:
            return jsonify({
                "ok": False,
                "message": "Product ID is required"
            }), 400
        
        print(f"💾 Adding to favorites - User: {user_id}, Product: {product_id}")
        
    except Exception as e:
        print(f"❌ Error parsing request: {e}")
        return jsonify({
            "ok": False,
            "message": "Invalid request"
        }), 400
    
    # ✅ 3. التحقق من وجود المنتج
    product = Product.query.filter_by(id=product_id).first()
    if not product:
        return jsonify({
            "ok": False,
            "message": "Product not found"
        }), 404
    
    # ✅ 4. جلب أو إنشاء Wishlist للمستخدم
    wishlist = Wishlist.query.filter_by(account_id=user_id).first()
    if not wishlist:
        wishlist = Wishlist(account_id=user_id)
        db.session.add(wishlist)
        db.session.flush()
        print(f"✅ Created new wishlist for user {user_id}")
    
    # ✅ 5. التحقق إذا المنتج موجود مسبقاً
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
    
    # ✅ 6. إضافة المنتج للمفضلة
    try:
        item = WishlistItem(
            wishlist_id=wishlist.id,
            product_id=product_id
        )
        db.session.add(item)
        db.session.commit()
        
        print(f"✅ Added product {product_id} to favorites")
        
        return jsonify({
            "ok": True,
            "message": "Added to favorites successfully"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Database error: {e}")
        return jsonify({
            "ok": False,
            "message": f"Database error: {str(e)}"
        }), 500


# ========================================
# Get Favorites Route
# ========================================

@app.route("/ai/favorites", methods=["GET"])
def ai_favorites_get():
    """Get user's favorite products"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "ok": False,
            "message": "Please login first"
        }), 401
    
    try:
        # جلب الـ wishlist
        wishlist = Wishlist.query.filter_by(account_id=user_id).first()
        
        if not wishlist:
            return jsonify({
                "ok": True,
                "favorites": []
            })
        
        # جلب المنتجات المفضلة
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
        
        return jsonify({
            "ok": True,
            "favorites": favorites
        })
        
    except Exception as e:
        print(f"❌ Error loading favorites: {e}")
        return jsonify({
            "ok": False,
            "message": str(e)
        }), 500


# ========================================
# Remove from Favorites Route
# ========================================

@csrf.exempt
@app.route("/ai/favorites/remove", methods=["POST"])
def ai_favorites_remove():
    """Remove product from favorites"""
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "ok": False,
            "message": "Please login first"
        }), 401
    
    try:
        data = request.get_json()
        product_id = data.get("product_id")
        
        if not product_id:
            return jsonify({
                "ok": False,
                "message": "Product ID is required"
            }), 400
        
        wishlist = Wishlist.query.filter_by(account_id=user_id).first()
        if not wishlist:
            return jsonify({
                "ok": False,
                "message": "Wishlist not found"
            }), 404
        
        item = WishlistItem.query.filter_by(
            wishlist_id=wishlist.id,
            product_id=product_id
        ).first()
        
        if not item:
            return jsonify({
                "ok": False,
                "message": "Item not in favorites"
            }), 404
        
        db.session.delete(item)
        db.session.commit()
        
        print(f"✅ Removed product {product_id} from favorites")
        
        return jsonify({
            "ok": True,
            "message": "Removed from favorites"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error removing favorite: {e}")
        return jsonify({
            "ok": False,
            "message": str(e)
        }), 500

# ========================= Dev Server =========================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)