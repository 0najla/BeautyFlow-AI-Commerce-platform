
/**
 * ============================================================================
 * BeautyFlow - Main JavaScript File
 * ============================================================================
 * Frontend scripts for BeautyFlow beauty import platform.
 * Handles login, signup, and SmartPicks AI generation.
 * 
 * Author: BeautyFlow Team
 * Version: 2.0.0
 * ============================================================================
 */

// =============================================================================
// 1. LOGIN FORM HANDLER
// =============================================================================

/**
 * Initialize login form validation.
 * Validates email and password fields before form submission.
 */
document.addEventListener("DOMContentLoaded", () => {
    // Get login form element
    const loginForm = document.getElementById("loginForm");
    
    // Exit if not on login page
    if (!loginForm) return;

    // Get form elements
    const email = document.getElementById("email");
    const password = document.getElementById("password");
    const errorMessage = document.getElementById("errorMessage");

    // Handle form submission
    loginForm.addEventListener("submit", (e) => {
        // Get trimmed values
        const emailVal = email && email.value ? email.value.trim() : "";
        const passVal = password && password.value ? password.value.trim() : "";

        // Validate required fields
        if (!emailVal || !passVal) {
            e.preventDefault();
            
            if (errorMessage) {
                errorMessage.style.display = "block";
                errorMessage.textContent = "Please enter both email and password.";
            }
        }
    });
});


// =============================================================================
// 2. SIGNUP FORM HANDLER
// =============================================================================

/**
 * Initialize signup form with validation and API submission.
 * Validates username, email, phone, password, and confirmation.
 */
document.addEventListener("DOMContentLoaded", () => {
    // Get signup form element
    const form = document.getElementById("signupForm");
    
    // Exit if not on signup page
    if (!form) return;

    // -------------------------------------------------------------------------
    // 2.1 Get Form Elements
    // -------------------------------------------------------------------------
    
    const username = document.getElementById("username");
    const email = document.getElementById("email");
    const phone = document.getElementById("phone");
    const password = document.getElementById("password");
    const confirmPassword = document.getElementById("confirm-password");
    const errorMessage = document.getElementById("error-message");
    const passwordError = document.getElementById("password-error");

    // -------------------------------------------------------------------------
    // 2.2 Real-time Password Validation
    // -------------------------------------------------------------------------
    
    if (password) {
        password.addEventListener("input", () => {
            // Show error if password is less than 6 characters
            if (password.value && password.value.length < 6) {
                if (passwordError) passwordError.style.display = "block";
            } else {
                if (passwordError) passwordError.style.display = "none";
            }
        });
    }

    // -------------------------------------------------------------------------
    // 2.3 Form Submission Handler
    // -------------------------------------------------------------------------
    
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        let valid = true;
        
        // Hide previous error messages
        if (errorMessage) errorMessage.style.display = "none";

        // Get form values
        const unameVal = username && username.value ? username.value.trim() : "";
        const emailVal = email && email.value ? email.value.trim().toLowerCase() : "";
        const passVal = password && password.value ? password.value : "";
        const cpassVal = confirmPassword && confirmPassword.value ? confirmPassword.value : "";
        const phoneVal = phone && phone.value ? phone.value.trim() : "";

        // ---------------------------------------------------------------------
        // Validation: Required Fields
        // ---------------------------------------------------------------------
        
        if (!unameVal || !emailVal || !passVal) {
            if (errorMessage) {
                errorMessage.textContent = "Please fill all required fields.";
                errorMessage.style.display = "block";
            }
            valid = false;
        }

        // ---------------------------------------------------------------------
        // Validation: Password Length (minimum 6 characters)
        // ---------------------------------------------------------------------
        
        if (passVal.length < 6) {
            if (passwordError) passwordError.style.display = "block";
            valid = false;
        }

        // ---------------------------------------------------------------------
        // Validation: Password Match
        // ---------------------------------------------------------------------
        
        if (passVal !== cpassVal) {
            if (errorMessage) {
                errorMessage.textContent = "Passwords do not match!";
                errorMessage.style.display = "block";
            }
            valid = false;
        }

        // Stop if validation failed
        if (!valid) return;

        // ---------------------------------------------------------------------
        // API Request: Create Account
        // ---------------------------------------------------------------------
        
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

            // Handle response
            if (resp.ok) {
                // Redirect to login on success
                window.location.href = "/login";
            } else {
                // Show error message
                const data = await resp.json().catch(() => ({}));
                if (errorMessage) {
                    errorMessage.textContent = data.message || "Signup failed.";
                    errorMessage.style.display = "block";
                }
            }
        } catch (err) {
            // Handle network errors
            if (errorMessage) {
                errorMessage.textContent = "Network error.";
                errorMessage.style.display = "block";
            }
        }
    });
});


 // =============================================================================
// 3. SMARTPICKS - AI IMAGE GENERATION
// =============================================================================

/**
 * Initialize SmartPicks page with AI-powered product generation.
 * Generates product images based on selected vibe (cute/luxury/minimal).
 */
document.addEventListener("DOMContentLoaded", () => {
    // Exit if not on SmartPicks page
    if (!document.body.classList.contains("smartPicks-page")) return;

    // Get page elements
    const vibeButtons = document.querySelectorAll(".vibe-btn");
    const cardImages = document.querySelectorAll(".brand-card-image");

    // Exit if elements not found
    if (!vibeButtons.length || !cardImages.length) return;

    // -------------------------------------------------------------------------
    // 3.1 Build AI Prompt Based on Vibe
    // -------------------------------------------------------------------------
    
    /**
     * Generate AI prompt for product image based on vibe.
     * 
     * @param {string} vibe - Selected vibe (cute/luxury/minimal)
     * @param {number} index - Card index for variation
     * @returns {string} - Complete prompt for AI generation
     */
    function buildPrompt(vibe, index) {
        const base = "High-quality product photo of 3 makeup products, studio lighting, no text, white background. ";
        
        if (vibe === "cute") {
            return base + "Cute pastel kawaii style, soft pink colors. Variation #" + (index + 1);
        }
        
        if (vibe === "luxury") {
            return base + "Luxury black and gold packaging. Variation #" + (index + 1);
        }
        
        // Default: minimal
        return base + "Ultra minimal white and beige packaging. Variation #" + (index + 1);
    }

    // -------------------------------------------------------------------------
    // 3.2 Generate Images for Selected Vibe
    // -------------------------------------------------------------------------
    
    /**
     * Generate AI images for all cards based on selected vibe.
     * Shows loading state, makes API calls, and updates card images.
     * 
     * @param {string} vibe - Selected vibe (cute/luxury/minimal)
     */
    async function generateImagesForVibe(vibe) {
        // Show loading state for all cards
        cardImages.forEach((box) => {
            box.style.backgroundImage = "none";
            box.style.backgroundColor = "#f3f3f3";
            box.innerHTML = "Loading...";
            box.style.display = "flex";
            box.style.alignItems = "center";
            box.style.justifyContent = "center";
        });

        // Disable all vibe buttons during generation
        vibeButtons.forEach((btn) => (btn.disabled = true));

        try {
            // Generate image for each card
            for (let i = 0; i < cardImages.length; i++) {
                const prompt = buildPrompt(vibe, i);
                
                // Make API request
                const res = await fetch("/ai/generate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        prompt: prompt,
                        context: "smartpicks",
                        vibe: vibe
                    })
                });

                const data = await res.json().catch(() => ({}));

                // Update card with generated image
                if (res.ok && data.ok && data.image_url) {
                    const box = cardImages[i];
                    box.innerHTML = "";
                    box.style.backgroundColor = "transparent";
                    box.style.backgroundImage = "url(" + data.image_url + ")";
                    box.style.backgroundSize = "cover";
                    box.style.backgroundPosition = "center";
                } else {
                    // Show error on failed generation
                    cardImages[i].innerHTML = "⚠️ Error";
                }
            }
        } catch (err) {
            // Handle network errors
            cardImages.forEach((box) => {
                box.innerHTML = "❌ Network error";
            });
        } finally {
            // Re-enable vibe buttons
            vibeButtons.forEach((btn) => (btn.disabled = false));
        }
    }

    // -------------------------------------------------------------------------
    // 3.3 Attach Click Handlers to Vibe Buttons
    // -------------------------------------------------------------------------
    
    vibeButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            // Get vibe from button data attribute or text content
            const vibe = (btn.dataset.vibe || btn.textContent || "").toLowerCase().trim();
            
            // Generate images if vibe is valid
            if (vibe) {
                generateImagesForVibe(vibe);
            }
        });
    });
});