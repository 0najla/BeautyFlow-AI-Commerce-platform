from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from pathlib import Path
import os, random, re ,json
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf, validate_csrf, CSRFError
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

load_dotenv()
OpenAI_Client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please login first.", "error")
            return redirect(url_for("login_page", next=request.path))
        return view(*args, **kwargs)
    return wrapped



# === Directories ===
BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"

app = Flask(__name__, template_folder=str(TEMPLATES), static_folder=str(STATIC))
CORS(app)

app.config['SECRET_KEY'] = 'change_this_to_a_strong_secret'  # مهم


# CSRF & flash secret
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
csrf = CSRFProtect(app)
root_env_path = str(ROOT / ".env")
backend_env_path = str(BASE_DIR / ".env")

loaded1 = load_dotenv(dotenv_path=root_env_path, override=True)
loaded2 = load_dotenv(dotenv_path=backend_env_path, override=True)

# Fallback: اقرأ الملف يدويًا لو فشل التحميل
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    env_map = {}
    if os.path.exists(root_env_path):
        env_map.update(dotenv_values(root_env_path))
    if os.path.exists(backend_env_path):
        env_map.update(dotenv_values(backend_env_path))
    API_KEY = env_map.get("OPENAI_API_KEY")

# Debug مفيد
print(f"[DEBUG] .env @ ROOT exists: {os.path.exists(root_env_path)} | loaded: {loaded1}")
print(f"[DEBUG] .env @ backend exists: {os.path.exists(backend_env_path)} | loaded: {loaded2}")
print(f"[DEBUG] OPENAI_API_KEY present: {bool(API_KEY)}")

if not API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY not found. Put it in either project/.env or backend/.env as:\n"
        "OPENAI_API_KEY=sk-xxxx"
    )

OpenAI_Client = OpenAI(api_key=API_KEY)


# ========================= DB =========================
load_dotenv()  # يقرأ .env
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    from models import AccountProfile  # تأكد أنه مُصدَّر من models/__init__.py
    prof = AccountProfile.query.filter_by(account_id=account.id).first()
    created = False
    if not prof:
        prof = AccountProfile(account_id=account.id)
        created = True

    # تحديث اختياري لو فيه بيانات
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
    # ملاحظة: لا نعمل commit هنا؛ نخليه على الراؤوت يستدعي commit مرّة وحدة
    return prof, created

def _get_or_open_session(user_id):
    from all_models import AISession
    sess = AISession.query.filter_by(account_id=user_id, status="OPEN").order_by(AISession.id.desc()).first()
    if not sess:
        sess = AISession(account_id=user_id, status="OPEN", notes=json.dumps({"filled": {}, "pending": []}))
        db.session.add(sess)
        db.session.flush()
    try:
        state = json.loads(sess.notes) if sess.notes else {"filled": {}, "pending": []}
    except Exception:
        state = {"filled": {}, "pending": []}
    return sess, state

def _save_state(sess, state):
    sess.notes = json.dumps(state, ensure_ascii=False)
    db.session.flush()

def _save_msg(sess_id, who, content):
    from all_models import AIMessage
    db.session.add(AIMessage(session_id=sess_id, sender=who, content=content))
    db.session.flush()


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

    # نقرأ القيم القادمة من الصفحة
    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()

    # إذا المستخدم ما كتب شيء
    if not email or not password:
        flash("Please enter both email and password.", "error")
        return redirect(url_for("login_page"))

    # نبحث عن الإيميل في قاعدة البيانات
    user = Account.query.filter_by(email=email).first()

    # إذا المستخدم غير موجود (ما سوا Signup)
    if not user:
        flash("You don't have an account, please Sign up first.", "error")
        return redirect(url_for("login_page"))

    # إذا موجود لكن كلمة المرور خطأ
    if not check_password_hash(user.password_hash, password):
        flash("Incorrect password, please try again.", "error")
        return redirect(url_for("login_page"))

    # نجاح تسجيل الدخول
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
@login_required
def design_options():
    return render_template("designOptions.html")

@app.route("/AI", methods=["GET"])

def ai_page():
    return render_template("AI.html")

@app.route("/costSharing", methods=["GET"])
@login_required
def costSharing_page():
    return render_template("costSharing.html")

@app.route("/invoice", methods=["GET"])
@login_required
def invoice_page():
    return render_template("invoice.html")

@app.route("/invoiceShared", methods=["GET"])
@login_required
def invoiceShared_page():
    return render_template("invoiceShared.html")

@app.route("/shipment", methods=["GET"])
@login_required
def shipment_page():
    return render_template("shipment.html")

@app.route("/about")
def about_page():
    return render_template("about.html")

@app.route("/smartPicks", strict_slashes=False)
@login_required
def smartPicks_page():
    return render_template("smartPicks.html")

@app.route("/cart", strict_slashes=False)
@login_required
def cart_page():
    return render_template("cart.html")

@app.route("/payment", strict_slashes=False)
@login_required
def payment_page():
    return render_template("payment.html")

@app.route("/sspay", strict_slashes=False)
@login_required
def sspay_page():
    return render_template("sspay.html")

# -------------------------
#  Profile routes
# -------------------------
@app.route("/account", methods=["GET"], strict_slashes=False)
@login_required
def account_page():
    profile = session.get("profile", {
        "firstName": "",
        "lastName": "",
        "phone": "",
        "address": ""
    })
    return render_template("account.html", profile=profile)

@app.route("/profile/save", methods=["POST"], strict_slashes=False)
@login_required
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
        db.session.flush()                # يعطي user.id بدون إنهاء المعاملة
        ensure_profile_for(user, first_name=username)  # ينشئ صف في account_profiles
        db.session.commit()               # هنا الحفظ الفعلي للجدولين
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

    # طَبّعي رقم السعودية إلى +9665xxxxxxxx
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
        print("[DEBUG] Twilio status:", v.status)  # should be 'pending'
        flash("OTP sent via SMS ", "success")
        return redirect(url_for("verify_page"))
    except Exception as e:
        print("[Twilio ERROR]", repr(e))
        flash("Failed to send SMS. Check console/logs.", "error")
        return redirect(url_for("phone_login"))
    


@csrf.exempt
@app.post("/verify")
def verify_submit():
    # لازم يكون المستخدم مسجّل دخول
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

    # ✅ نجاح التحقق
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
            # وضع التطوير: ولّدي كود جديد وخزّنيه
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
@app.route("/chat", methods=["POST"])
@login_required
def chat_api_openai():
    from all_models import AISession, AIMessage, AIGeneration
    data = request.get_json(silent=True) or {}
    user_text = (data.get("message") or "").strip()
    reset = bool(data.get("reset"))

    if not user_text:
        return jsonify({"ok": False, "reply": "Message is empty"}), 400

    user_id = int(session["user_id"])

    # reset optional
    if reset:
        for s in AISession.query.filter_by(account_id=user_id, status="OPEN").all():
            s.status = "CLOSED"
        db.session.flush()

    sess, state = _get_or_open_session(user_id)
    filled, pending = state.get("filled", {}), state.get("pending", [])
    REQUIRED = ["appearance", "formula_base", "skin_type", "finish", "coverage"]

    # First message: greet and list needed fields
    if not filled and not pending:
        pending = REQUIRED.copy()
        state["pending"] = pending
        greeting = (
            "Hi! Tell me the product *appearance* (colors, style, logo/print, packaging details).\n"
            "We will also need:\n"
            "• Formula base: POWDER / GEL / CREAM / OIL / WATER\n"
            "• Skin type: OILY / DRY / NORMAL / COMBINATION / SENSITIVE\n"
            "• Finish: MATTE / NATURAL / DEWY / GLOWY\n"
            "• Coverage: SHEER / MEDIUM / FULL\n\n"
            "Start with the overall appearance ✨"
        )
        _save_state(sess, state)
        _save_msg(sess.id, "USER", user_text)
        _save_msg(sess.id, "AI", greeting)
        db.session.commit()
        return jsonify({"ok": True, "reply": greeting, "session_id": int(sess.id)}), 200

    # Save user message
    _save_msg(sess.id, "USER", user_text)
    low = user_text.lower()

    # Fill slots
    if "appearance" in pending and len(user_text.split()) >= 2:
        filled["appearance"] = user_text; pending.remove("appearance")
    if "formula_base" in pending:
        if   "powder" in low: filled["formula_base"] = "POWDER";  pending.remove("formula_base")
        elif "gel"    in low: filled["formula_base"] = "GEL";     pending.remove("formula_base")
        elif "cream"  in low: filled["formula_base"] = "CREAM";   pending.remove("formula_base")
        elif "oil"    in low: filled["formula_base"] = "OIL";     pending.remove("formula_base")
        elif "water"  in low: filled["formula_base"] = "WATER";   pending.remove("formula_base")
    if "skin_type" in pending:
        if   "oily"        in low: filled["skin_type"] = "OILY";        pending.remove("skin_type")
        elif "dry"         in low: filled["skin_type"] = "DRY";         pending.remove("skin_type")
        elif "normal"      in low: filled["skin_type"] = "NORMAL";      pending.remove("skin_type")
        elif "combination" in low: filled["skin_type"] = "COMBINATION"; pending.remove("skin_type")
        elif "sensitive"   in low: filled["skin_type"] = "SENSITIVE";   pending.remove("skin_type")
    if "finish" in pending:
        if   "matte"   in low: filled["finish"] = "MATTE";   pending.remove("finish")
        elif "natural" in low: filled["finish"] = "NATURAL"; pending.remove("finish")
        elif "dewy"    in low: filled["finish"] = "DEWY";    pending.remove("finish")
        elif "glowy"   in low or "glow" in low: filled["finish"] = "GLOWY"; pending.remove("finish")
    if "coverage" in pending:
        if   "sheer" in low or "light" in low: filled["coverage"] = "SHEER";  pending.remove("coverage")
        elif "medium" in low:               filled["coverage"] = "MEDIUM"; pending.remove("coverage")
        elif "full" in low or "high" in low:filled["coverage"] = "FULL";   pending.remove("coverage")

    state["filled"], state["pending"] = filled, pending
    _save_state(sess, state)

    # Ask next required field
    if pending:
        nxt = pending[0]
        questions = {
            "appearance":  "Please describe the outer look (colors, style, logo/print, bottle/jar details).",
            "formula_base":"Pick one formula base: POWDER / GEL / CREAM / OIL / WATER.",
            "skin_type":   "Pick skin type: OILY / DRY / NORMAL / COMBINATION / SENSITIVE.",
            "finish":      "Pick finish: MATTE / NATURAL / DEWY / GLOWY.",
            "coverage":    "Pick coverage: SHEER / MEDIUM / FULL."
        }
        follow_up = f"Got it so far ✅: { {k:v for k,v in filled.items()} }\n\n{questions[nxt]}"
        _save_msg(sess.id, "AI", follow_up)
        db.session.commit()
        return jsonify({"ok": True, "reply": follow_up, "session_id": int(sess.id)}), 200

    # All slots filled → build prompt, generate image, save
    appearance   = filled["appearance"]
    formula_base = filled["formula_base"]
    skin_type    = filled["skin_type"]
    finish       = filled["finish"]
    coverage     = filled["coverage"]

    final_desc = (
        f"Cosmetics product packaging, photorealistic render.\n"
        f"Appearance: {appearance}\n"
        f"Formula base: {formula_base}\n"
        f"Skin type: {skin_type} | Finish: {finish} | Coverage: {coverage}\n"
        f"Studio product shot, centered, high detail, soft lighting."
    )

    image_url = None
    try:
        result = openai_client.images.generate(model="gpt-image-1", prompt=final_desc, size="1024x1024")
        image_url = result.data[0].url

        gen = AIGeneration(
            session_id=sess.id,
            image_url=image_url,
            prompt_json={"prompt": final_desc},
            meta_json={"model": "gpt-image-1"}
        )
        db.session.add(gen)
        db.session.commit()

    except Exception:
        db.session.rollback()
        err_reply = "All specs captured ✅ but image generation failed. Please try again."
        _save_msg(sess.id, "AI", err_reply)
        return jsonify({"ok": True, "reply": err_reply, "session_id": int(sess.id)}), 200

    success = (
        "Here is a first preview based on your specs 👇\n\n"
        f"- Formula: **{formula_base}**  |  Skin: **{skin_type}**\n"
        f"- Finish: **{finish}**  |  Coverage: **{coverage}**\n\n"
        "Want to tweak anything (formula/skin/finish/coverage/appearance)?"
    )
    _save_msg(sess.id, "AI", success)

    return jsonify({"ok": True, "reply": success, "image_url": image_url, "session_id": int(sess.id)}), 200


    # =========================
#  AI Image Generation (Packaging)
# =========================
@csrf.exempt
@app.route("/ai/generate", methods=["POST"])
@login_required
def ai_generate_packaging():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"ok": False, "error": "EMPTY_PROMPT", "message": "Please describe the packaging."}), 400

    user_id = session.get("user_id")
    try:
        # 1. توليد الصورة
        result = OpenAI_Client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )
        image_url = result.data[0].url

        # 2. إنشاء جلسة لو ما فيه وحدة مفتوحة
        session_obj = AISession.query.filter_by(account_id=user_id, status="OPEN").first()
        if not session_obj:
            session_obj = AISession(account_id=user_id)
            db.session.add(session_obj)
            db.session.flush()

        # 3. حفظ الصورة في قاعدة البيانات
        gen = AIGeneration(
            session_id=session_obj.id,
            image_url=image_url,
            prompt_json={"prompt": prompt},
            meta_json={"model": "gpt-image-1"}
        )
        db.session.add(gen)
        db.session.commit()

        return jsonify({"ok": True, "image_url": image_url}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": "OPENAI_ERROR", "message": str(e)}), 500

    
@app.route("/debug-profiles")
def debug_profiles():
    rows = AccountProfile.query.order_by(AccountProfile.id.desc()).all()
    return jsonify([{"id": int(r.id), "account_id": int(r.account_id), "full_name": r.full_name} for r in rows])





# ========================= Dev Server =========================
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5005)




