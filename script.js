// تسجيل الدخول
document.addEventListener("DOMContentLoaded", () => {
  const loginForm   = document.getElementById("login-form");
  const firstName   = document.getElementById("firstName");
  const email       = document.getElementById("email");
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
  const chatForm  = document.getElementById("chat-form");
  const input     = document.getElementById("user-input");
  const messages  = document.getElementById("chat-messages");
  const intro     = document.getElementById("intro-text");

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
