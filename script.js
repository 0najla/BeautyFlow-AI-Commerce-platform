form.addEventListener("submit", function (e) {
    e.preventDefault(); // يمنع الانتقال التلقائي
    if (firstName.value.trim() === "" || email.value.trim() === "") {
      errorMessage.style.display = "block"; // إظهار الخطأ
    } else {
      errorMessage.style.display = "none"; // إخفاء الخطأ
      window.location.href = "index.html"; // ✅ الانتقال للرئيسية
    }
    
  });