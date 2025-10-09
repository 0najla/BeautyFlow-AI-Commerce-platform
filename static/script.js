// تسجيل الدخول
document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("login-form");
  const firstName = document.getElementById("firstName");
  const email = document.getElementById("email");
  const errorMessage = document.getElementById("errorMessage");

  if (loginForm) {   // ← هنا الشرط مهم
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      if (firstName.value.trim() === "" || email.value.trim() === "") {
        errorMessage.style.display = "block";
      } else {
        errorMessage.style.display = "none";
        window.location.href = "index.html";
      }
    });

  }

});

// ai custom chat
document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const messages = document.getElementById("chat-messages");
  const intro = document.getElementById("intro-text");

  if (chatForm) {   // ← هنا الشرط مهم
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;

      const p = document.createElement("p");
      p.className = "msg user";
      p.textContent = text;
      messages.appendChild(p);

      input.value = "";

      if (text.toLowerCase() === "start") {
        intro.style.display = "none";
        const botMsg = document.createElement("p");
        botMsg.className = "msg bot";
        botMsg.textContent = "مرحباً! صفّي شكل الباكيجنق ✨";
        messages.appendChild(botMsg);
        return;
      }

      const botMsg = document.createElement("p");
      botMsg.className = "msg bot";
      botMsg.textContent = "👌 استلمت وصفك، جاري تجهيز المعاينة…";
      messages.appendChild(botMsg);

    });
  }
});
document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("signupForm");

  const fname = document.getElementById("fname");
  const lname = document.getElementById("lname");
  const email = document.getElementById("email");
  const password = document.getElementById("password");
  const confirmPassword = document.getElementById("confirm-password");

  const errorMessage = document.getElementById("error-message");
  const passwordError = document.getElementById("password-error");

  // إظهار رسالة طول كلمة المرور أثناء الكتابة
  password.addEventListener("input", () => {
    if (password.value && password.value.length < 6) {
      passwordError.style.display = "block";
    } else {
      passwordError.style.display = "none";
    }
  });

  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    let valid = true;
    errorMessage.style.display = "none";
    errorMessage.textContent = "Please fix the errors above.";

    // تحقق الحقول الأساسية
    if (!fname.value.trim() || !email.value.trim()) {
      errorMessage.textContent = "Please fill all required fields.";
      errorMessage.style.display = "block";
      valid = false;
    }

    // طول كلمة المرور
    if (password.value.length < 6) {
      passwordError.style.display = "block";
      valid = false;
    } else {
      passwordError.style.display = "none";
    }

    // تطابق كلمة المرور
    if (password.value !== confirmPassword.value) {
      errorMessage.textContent = "Passwords do not match!";
      errorMessage.style.display = "block";
      valid = false;
    }

    if (!valid) return;

    // إرسال لـ Flask عبر fetch (يتوقع راوت اسمه signup يرجع 200 عند النجاح)
    try {
      const resp = await fetch("{{ url_for('signup') }}", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: fname.value.trim(),
          last_name: lname.value.trim(),
          email: email.value.trim(),
          password: password.value,
        }),
      });

      if (resp.ok) {
        // نجاح: ودي المستخدم لصفحة تسجيل الدخول
        window.location.href = "{{ url_for('login_page') }}";
      } else {
        const data = await resp.json().catch(() => ({}));
        errorMessage.textContent = data.message || "Signup failed. Try again.";
        errorMessage.style.display = "block";
      }
    } catch (err) {
      errorMessage.textContent = "Network error. Please try again.";
      errorMessage.style.display = "block";
    }
  });
});


