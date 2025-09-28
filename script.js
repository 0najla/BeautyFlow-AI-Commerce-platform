
form.addEventListener("submit", function (e) {
    if (password.value !== confirmPassword.value) {
        e.preventDefault();
        errorMessage.style.display = "block";
    } else {
        errorMessage.style.display = "none";
        alert("Account created successfully!");
    }
})
