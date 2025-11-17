/*******************************
 * (A) AI Wizard + Image Generation
 *******************************/

document.addEventListener("DOMContentLoaded", () => {
  const chatBox = document.getElementById("chat-messages");
  const form    = document.getElementById("chat-form");
  const input   = document.getElementById("user-input");
  const intro   = document.getElementById("intro-text"); // اختياري، لو مو موجود ما فيه مشكلة

  if (!chatBox || !form || !input) {
    console.warn("AI Wizard: chat-messages / chat-form / user-input not found.");
    return;
  }

  // مسح محتوى صندوق الشات
  function clearChat() {
    chatBox.innerHTML = "";
  }

  // حالة الـ Wizard (الإجابات تنحفظ هنا)
  const wizardState = {
    step: 0,
    done: false,
    answers: {
      product_type: null,
      formula_base: null,
      coverage: null,
      finish: null,
      skin_type: null,
      packaging_desc: null
    }
  };

  // تعريف الخطوات (منطق الأسئلة)
  const steps = [
    {
      key: "product_type",
      type: "buttons",
      question: "First question: What is the product type?",
      options: [
        { label: "Lipstick",   value: "LIPSTICK" },
        { label: "Mascara",    value: "MASCARA" },
        { label: "Blush",      value: "BLUSH" },
        { label: "Foundation", value: "FOUNDATION" },
        { label: "Eyeliner",   value: "EYELINER" }
      ]
    },
    {
      key: "formula_base",
      type: "buttons",
      question: "What is the main formula base?",
      options: [
        { label: "Water-based",    value: "WATER" },
        { label: "Oil-based",      value: "OIL" },
        { label: "Cream",          value: "CREAM" },
        { label: "Gel",            value: "GEL" },
        { label: "Powder",         value: "POWDER" },
        { label: "Silicone-based", value: "SILICONE" }
      ]
    },
    {
      key: "coverage",
      type: "buttons",
      question: "What coverage level do you want?",
      options: [
        { label: "Sheer",  value: "SHEER" },
        { label: "Medium", value: "MEDIUM" },
        { label: "Full",   value: "FULL" }
      ]
    },
    {
      key: "finish",
      type: "buttons",
      question: "What finish do you want?",
      options: [
        { label: "Matte",   value: "MATTE" },
        { label: "Natural", value: "NATURAL" },
        { label: "Dewy",    value: "DEWY" },
        { label: "Glowy",   value: "GLOWY" }
      ]
    },
    {
      key: "skin_type",
      type: "buttons",
      question: "Which skin type should it suit?",
      options: [
        { label: "Normal",      value: "NORMAL" },
        { label: "Oily",        value: "OILY" },
        { label: "Dry",         value: "DRY" },
        { label: "Combination", value: "COMBINATION" },
        { label: "Sensitive",   value: "SENSITIVE" }
      ]
    },
    {
      key: "packaging_desc",
      type: "text",
      question: "Finally: How do you want the outer packaging to look? Describe the style, colors, and vibe.",
      options: null
    }
  ];

  // ====== دوال مساعدة لعرض الرسائل ======

  function addAiMessage(html) {
    const msg = document.createElement("div");
    msg.classList.add("msg", "ai");
    msg.style.direction = "ltr";
    msg.style.textAlign = "left";
    msg.innerHTML = `<p>${html}</p>`;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
    return msg;
  }

  function addUserMessage(text) {
    const msg = document.createElement("div");
    msg.classList.add("msg", "user");
    msg.textContent = text;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function clearOptions() {
    const old = chatBox.querySelectorAll(".wizard-options");
    old.forEach(el => el.remove());
  }

  function renderOptions(step) {
    clearOptions();
    const wrap = document.createElement("div");
    wrap.classList.add("wizard-options");

    step.options.forEach(opt => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.classList.add("wizard-btn");
      btn.textContent = opt.label;
      btn.addEventListener("click", () => {
        handleButtonAnswer(step, opt, wrap, btn);
      });
      wrap.appendChild(btn);
    });

    chatBox.appendChild(wrap);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // ====== منطق اختيار زر في الأسئلة ======
  function handleButtonAnswer(step, opt, wrap, btn) {
    // حفظ الإجابة
    wizardState.answers[step.key] = opt.value;

    // قفل الأزرار بعد الاختيار
    [...wrap.children].forEach(b => {
      b.disabled = true;
      b.classList.remove("selected");
    });
    btn.classList.add("selected");

    // رسالة تأكيد
    addAiMessage(`Got it! You chose: <strong>${opt.label}</strong>.`);

    // السؤال اللي بعده
    wizardState.step += 1;
    runStep();
  }

  // ====== توليد الـ prompt وإرسال الطلب لـ /ai/generate ======
  async function generatePackagingImage() {
    const a = wizardState.answers;

    const niceType     = (a.product_type   || "PRODUCT").toLowerCase();
    const niceBase     = (a.formula_base   || "").toLowerCase();
    const niceCoverage = (a.coverage       || "").toLowerCase();
    const niceFinish   = (a.finish         || "").toLowerCase();
    const niceSkin     = (a.skin_type      || "").toLowerCase();
    const desc         = a.packaging_desc  || "";

    const prompt = `
Design a high-quality beauty product packaging image for a ${niceType}.
Formula base: ${niceBase}.
Coverage: ${niceCoverage}.
Finish: ${niceFinish}.
Target skin type: ${niceSkin}.
Outer box and component style: ${desc}.
Make it professional, trendy, and suitable for a modern beauty brand.
`.trim();

    const waitMsg = addAiMessage("✨ Generating your packaging design, please wait...");

    try {
      const res = await fetch("/ai/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt })
      });

      const data = await res.json();

      if (data.ok && data.image_url) {
        waitMsg.innerHTML = "Here is your packaging idea ✨";

        const img = document.createElement("img");
        img.src = data.image_url;
        img.alt = "AI Packaging Design";
        img.style.maxWidth = "100%";
        img.style.borderRadius = "12px";
        img.style.marginTop = "8px";

        chatBox.appendChild(img);
        chatBox.scrollTop = chatBox.scrollHeight;
      } else {
        waitMsg.innerHTML = "⚠️ I couldn't generate the image. " +
          (data.message || data.error || "");
      }
    } catch (err) {
      console.error(err);
      waitMsg.innerHTML = "❌ Network error while generating image.";
    }
  }

  // ====== تشغيل الخطوة الحالية ======
  function runStep() {
    // لو خلصنا كل الأسئلة → نرسل للباك إند يولّد الصورة
    if (wizardState.step >= steps.length) {
      wizardState.done = true;
      input.disabled = true;
      input.placeholder = "Generating your packaging design...";
      console.log("Wizard finished with answers:", wizardState.answers);
      generatePackagingImage();
      return;
    }

    const step = steps[wizardState.step];

    if (step.type === "buttons") {
      // أسئلة أزرار
      input.value = "";
      input.disabled = true;
      input.placeholder = "Please choose one of the options above.";
      clearChat();
      addAiMessage(step.question);
      renderOptions(step);

    } else if (step.type === "text") {
      // آخر سؤال: يسمح بالكتابة
      clearChat();
      addAiMessage(step.question);
      input.disabled = false;
      input.value = "";
      input.placeholder = step.question;
    }
  }

  // ====== استقبال إرسال الفورم (للآخر سؤال فقط) ======
  form.addEventListener("submit", (e) => {
    e.preventDefault();

    // لو الـ wizard خلص خلاص ما نسوي شيء ثاني
    if (wizardState.done) {
      return;
    }

    const step = steps[wizardState.step];
    if (!step || step.type === "buttons") {
      // أسئلة الأزرار ما تستخدم الـ input
      return;
    }

    const value = (input.value || "").trim();
    if (!value) return;

    addUserMessage(value);
    wizardState.answers[step.key] = value;

    input.value = "";
    wizardState.step += 1;
    runStep();
  });

  // ====== البداية: رسالة ترحيب + زر Start ======
  function startWizard() {
    clearChat();

    if (intro) intro.style.display = "none";

    addAiMessage(
      "Hi! I'm here to help you.<br><br>" +
      "To create the product in the style you want, I need you to answer a few questions first."
    );

    const startBtn = document.createElement("button");
    startBtn.textContent = "Start";
    startBtn.classList.add("wizard-start-btn");

    startBtn.addEventListener("click", () => {
      clearChat();
      wizardState.step = 0;
      wizardState.done = false;
      runStep();
    });

    chatBox.appendChild(startBtn);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  startWizard();
});



/********************************
 * (C) LOGIN — safe form submit
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
 * (D) SIGNUP — matches Flask /signup payload
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
