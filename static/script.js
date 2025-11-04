/*******************************
 * (A) AI custom chat  (optional)
 *******************************/


  




/********************************
 * (B) LOGIN — safe form submit
 ********************************/
document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("loginForm"); // يطابق login.html
  if (!loginForm) return;

  const email        = document.getElementById("email");
  const password     = document.getElementById("password");
  const errorMessage = document.getElementById("errorMessage"); // في login.html

  loginForm.addEventListener("submit", (e) => {
    const emailVal = email && email.value ? email.value.trim() : "";
    const passVal  = password && password.value ? password.value.trim() : "";

    // نمنع فقط لو الحقول ناقصة — غير كذا نخلي POST /login يتم طبيعي
    if (!emailVal || !passVal) {
      e.preventDefault();
      if (errorMessage) {
        errorMessage.style.display = "block";
        errorMessage.textContent = "Please enter both email and password.";
      }
    }
  });
});


/*********************************************
 * (C) SIGNUP — matches Flask /signup payload
 *********************************************/
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("signupForm");
  if (!form) return;

  const username        = document.getElementById("username");
  const email           = document.getElementById("email");
  const phone           = document.getElementById("phone");             // اختياري
  const password        = document.getElementById("password");
  const confirmPassword = document.getElementById("confirm-password");

  const errorMessage = document.getElementById("error-message");        // في signup.html
  const passwordError = document.getElementById("password-error");

  if (password) {
    password.addEventListener("input", () => {
      if (password.value && password.value.length < 6) {
        if (passwordError) passwordError.style.display = "block";
      } else {
        if (passwordError) passwordError.style.display = "none";
      }
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    let valid = true;
    if (errorMessage) {
      errorMessage.style.display = "none";
      errorMessage.textContent = "Please fix the errors above.";
    }

    const unameVal = username && username.value ? username.value.trim() : "";
    const emailVal = email && email.value ? email.value.trim().toLowerCase() : "";
    const passVal  = password && password.value ? password.value : "";
    const cpassVal = confirmPassword && confirmPassword.value ? confirmPassword.value : "";
    const phoneVal = phone && phone.value ? phone.value.trim() : "";

    if (!unameVal || !emailVal || !passVal) {
      if (errorMessage) {
        errorMessage.textContent = "Please fill all required fields.";
        errorMessage.style.display = "block";
      }
      valid = false;
    }

    if (passVal.length < 6) {
      if (passwordError) passwordError.style.display = "block";
      valid = false;
    } else {
      if (passwordError) passwordError.style.display = "none";
    }

    if (passVal !== cpassVal) {
      if (errorMessage) {
        errorMessage.textContent = "Passwords do not match!";
        errorMessage.style.display = "block";
      }
      valid = false;
    }

    if (!valid) return;

    try {
      const resp = await fetch("/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: unameVal,
          email: emailVal,
          phone: phoneVal,
          password: passVal,
          confirm_password: cpassVal
        }),
      });

      if (resp.ok) {
        window.location.href = "/login";
      } else {
        const data = await resp.json().catch(() => ({}));
        if (errorMessage) {
          errorMessage.textContent = data.message || "Signup failed. Try again.";
          errorMessage.style.display = "block";
        }
      }
    } catch (err) {
      if (errorMessage) {
        errorMessage.textContent = "Network error. Please try again.";
        errorMessage.style.display = "block";
      }
    }
  });
});
