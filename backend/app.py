from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from pathlib import Path
import os, random, re
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf, validate_csrf, CSRFError
from datetime import datetime
from dotenv import load_dotenv, dotenv_values


# OpenAI (SDK الجديد)
from openai import OpenAI

# === Directories ===
BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"

app = Flask(__name__, template_folder=str(TEMPLATES), static_folder=str(STATIC))
CORS(app)

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

client = OpenAI(api_key=API_KEY)

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
    return redirect(url_for("home_index"))

@app.route("/index", strict_slashes=False)
def home_index():
    return render_template("index.html")

@app.route("/design-options", strict_slashes=False)
def design_options():
    return render_template("designOptions.html")

@app.route("/AI", methods=["GET"])
def ai_page():
    return render_template("AI.html")

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

@app.route("/smartPicks", strict_slashes=False)
def smartPicks_page():
    return render_template("smartPicks.html")

@app.route("/cart", strict_slashes=False)
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

# -------------------------
# Signup / Help / Phone login routes
# -------------------------
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
    confirm    = (data.get("confirm_password") or password)

    if not first_name or not email:
        msg = "First name and email are required."
        return (jsonify({"message": msg}), 400) if request.is_json else (render_template("signup.html", error=msg), 400)
    if len(password) < 6:
        msg = "Password must be at least 6 characters."
        return (jsonify({"message": msg}), 400) if request.is_json else (render_template("signup.html", error=msg), 400)
    if password != confirm:
        msg = "Passwords do not match."
        return (jsonify({"message": msg}), 400) if request.is_json else (render_template("signup.html", error=msg), 400)

    return (jsonify({"ok": True}), 200) if request.is_json else redirect(url_for("login_page"))

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
    print("DEBUG OTP ->", otp, "to", session["phone_full"])
    return redirect(url_for("verify_page"))

@app.get("/verify")
def verify_page():
    phone_full = session.get("phone_full")
    if not phone_full:
        return redirect(url_for("phone_login"))
    masked = phone_full[:-4] + "****"
    return render_template("verify.html", phone_mask=masked)

@csrf.exempt
@app.post("/verify")
def verify_submit():
    code = (request.form.get("code") or "").strip()
    flash("Verified successfully ✅")
    return redirect(url_for("home_index"))

@csrf.exempt
@app.post("/resend_otp")
def resend_otp():
    if not session.get("phone_full"):
        return redirect(url_for("phone_login"))
    otp = f"{random.randint(0, 999999):06d}"
    session["otp"] = otp
    print("DEBUG RESEND ->", otp, "to", session["phone_full"])
    flash("A new OTP has been sent.")
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
def chat_api_openai():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"ok": False, "reply": "Message is empty"}), 400

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for packaging ideas."},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=200
        )
        reply = completion.choices[0].message.content
        return jsonify({"ok": True, "reply": reply}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "reply": f"OpenAI error: {e}"}), 500

# ========================= Dev Server =========================
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5005)
