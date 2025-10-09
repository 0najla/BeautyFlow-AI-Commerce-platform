from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from pathlib import Path
import os, random, re
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf, validate_csrf, CSRFError

# === مسارات القوالب والستايل ===
BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"

app = Flask(__name__, template_folder=str(TEMPLATES), static_folder=str(STATIC))
CORS(app)

# مفتاح سرّي مطلوب لـ CSRF و flash
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")

# === تفعيل CSRF ===
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
csrf = CSRFProtect(app)

# نعرّف csrf_token() للقوالب Jinja
@app.context_processor
def inject_csrf():
    return dict(csrf_token=generate_csrf)

# =========================
#         ROUTES
# =========================

@app.route("/", strict_slashes=False)
def home():
    # ابقيها على اللوجن كما هي
    return redirect(url_for("login_page"), code=302)

# صفحة تسجيل الدخول بالإيميل/كلمة المرور
@csrf.exempt
@app.route("/login", methods=["GET", "POST"], strict_slashes=False)
def login_page():
    if request.method == "GET":
        return render_template("login.html")
    # TODO: تحقق فعلي
    return redirect(url_for("home_index"))

# الصفحة الرئيسية (index.html)
@app.route("/index", strict_slashes=False)
def home_index():
    return render_template("index.html")

@app.route("/design-options", strict_slashes=False)
def design_options():
    return render_template("designOptions.html")

@app.route("/smartPicks", strict_slashes=False)
def smart_picks():
    return render_template("smartPicks.html")

# -------------------------
#  صفحة الحساب (Profile UI)
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
    """
    يحفظ بيانات البروفايل.
    يدعم JSON (fetch) أو form.
    CSRF:
      - fetch: مرّري التوكن في الهيدر X-CSRFToken
      - form : مرّريه في الحقل المخفي csrf_token
    """
    # ===== CSRF =====
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
        flash("CSRF token غير صالح. أعيدي المحاولة.", "error")
        return redirect(url_for("account_page"))

    # ===== DATA =====
    data = request.get_json(silent=True) or request.form.to_dict()

    first = (data.get("firstName") or "").strip()
    last  = (data.get("lastName")  or "").strip()
    addr  = (data.get("address")   or "").strip()
    raw_phone = (data.get("phone") or "").strip()

    # تنظيف رقم الجوال
    digits = re.sub(r"\D+", "", raw_phone)

    # تحقق السعودية
    if not re.fullmatch(r"5\d{8}", digits or ""):
        msg = "Phone must be 9 digits and start with 5 (KSA)."
        return (jsonify({"ok": False, "error": "PHONE_INVALID", "message": msg}), 400) if request.is_json \
               else (flash(msg, "error"), redirect(url_for("account_page")))

    if not first or not last:
        msg = "First and last name are required."
        return (jsonify({"ok": False, "error": "NAME_REQUIRED", "message": msg}), 400) if request.is_json \
               else (flash(msg, "error"), redirect(url_for("account_page")))

    # ===== SAVE (session مؤقّت) =====
    session["profile"] = {
        "firstName": first,
        "lastName":  last,
        "phone":     digits,
        "address":   addr
    }

    if request.is_json:
        return jsonify({"ok": True, "message": "Profile saved successfully ✅", "profile": session["profile"]}), 200
    else:
        flash("تم حفظ البروفايل ✅", "success")
        return redirect(url_for("account_page"))


# التسجيل
@csrf.exempt
@app.route("/signup", methods=["GET", "POST"], strict_slashes=False)
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    data = request.get_json(silent=True) or request.form
    first_name = (data.get("first_name") or "").strip()
    last_name  = (data.get("last_name") or "").strip()
    email      = (data.get("email") or "").strip()
    password   = data.get("password") or ""
    confirm    = data.get("confirm_password") or password

    if not first_name or not email:
        msg = "First name and email are required."
        return (jsonify({"message": msg}), 400) if request.is_json else (render_template("signup.html", error=msg), 400)
    if len(password) < 6:
        msg = "Password must be at least 6 characters."
        return (jsonify({"message": msg}), 400) if request.is_json else (render_template("signup.html", error=msg), 400)
    if password != confirm:
        msg = "Passwords do not match."
        return (jsonify({"message": msg}), 400) if request.is_json else (render_template("signup.html", error=msg), 400)

    # TODO: حفظ المستخدم في DB
    return (jsonify({"ok": True}), 200) if request.is_json else redirect(url_for("login_page"))

# المساعدة + نموذج التواصل
@app.route("/help", methods=["GET"], strict_slashes=False)
def help_page():
    return render_template("help.html")

@app.route("/contact", methods=["POST"], strict_slashes=False)
def submit_contact():
    first = request.form.get("first_name")
    last  = request.form.get("last_name")
    email = request.form.get("email")
    msg   = request.form.get("message")
    # TODO: إرسال بريد/حفظ DB
    flash("تم استلام رسالتك ")
    return redirect(url_for("help_page"))

# -------------------------
#  Phone Login → Verify
# -------------------------

# إدخال الجوال
@app.get("/phone_login")
def phone_login():
    return render_template("phone_login.html")

# استقبال الرقم وتوليد/إرسال OTP ثم التحويل لصفحة التحقق
@csrf.exempt
@app.route("/send_otp", methods=["POST"], strict_slashes=False)
def send_otp():
    country = request.form.get("country", "SA")
    cc = request.form.get("cc", "+966")
    phone = (request.form.get("phone") or "").strip()

    if not phone:
        flash("Enter a valid phone number.")
        return redirect(url_for("phone_login"))

    session["country"] = country
    session["cc"] = cc
    session["phone"] = phone
    session["phone_full"] = f"{cc}{phone}"

    otp = f"{random.randint(0, 999999):06d}"
    session["otp"] = otp

    # TODO: إرسال SMS فعلي (Twilio/الخ)
    print("DEBUG OTP ->", otp, "to", session["phone_full"])
    return redirect(url_for("verify_page"))

# صفحة التحقق (عرض)
@app.get("/verify")
def verify_page():
    phone_full = session.get("phone_full")
    if not phone_full:
        return redirect(url_for("phone_login"))
    masked = phone_full[:-4] + "****"
    return render_template("verify.html", phone_mask=masked)

# استلام كود التحقق → دخول
@csrf.exempt
@app.post("/verify")
def verify_submit():
    code = (request.form.get("code") or "").strip()
    # TODO: تحقق فعلي من session["otp"] == code
    flash("تم التحقق بنجاح (تخطي مؤقت)")
    # تقدرِين تغيّرينه لـ account_page لو تبين تروحين مباشرة للبروفايل
    return redirect(url_for("home_index"))

# إعادة إرسال الكود
@csrf.exempt
@app.post("/resend_otp")
def resend_otp():
    if not session.get("phone_full"):
        return redirect(url_for("phone_login"))
    otp = f"{random.randint(0, 999999):06d}"
    session["otp"] = otp
    print("DEBUG RESEND ->", otp, "to", session["phone_full"])
    flash("We sent you a new code.")
    return redirect(url_for("verify_page"))

@app.route("/logout", methods=["GET"], strict_slashes=False, endpoint="logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))



# ========================= Dev Server =========================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5005, debug=True)
