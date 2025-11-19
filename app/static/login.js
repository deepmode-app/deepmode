// app/static/login.js

// Same backend base URL you use in popup.js
const API_BASE_URL = "https://95e81190-332d-4b5b-a875-0a3ed330e756-00-1kk0ba0t7ygdw.janeway.replit.dev";

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("loginForm");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const errorDiv = document.getElementById("loginError");
  const loginButton = document.getElementById("loginButton");

  function showError(message) {
    errorDiv.textContent = message;
    errorDiv.style.display = "block";
  }

  function clearError() {
    errorDiv.textContent = "";
    errorDiv.style.display = "none";
  }

  if (!form) {
    console.error("loginForm not found in DOM");
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
      showError("Enter your email and password.");
      return;
    }

    // Disable button while logging in
    loginButton.disabled = true;
    loginButton.textContent = "Signing in...";

    try {
      // FastAPI's OAuth2PasswordRequestForm expects:
      // grant_type=password, username=<email>, password=<password>
      const body = new URLSearchParams({
        grant_type: "password",
        username: email,
        password: password,
        scope: "",
        client_id: "",
        client_secret: "",
      });

      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Accept": "application/json",
        },
        body,
      });

      if (!response.ok) {
        // Try to read error from API, fall back to generic
        let msg = "Invalid email or password.";
        try {
          const data = await response.json();
          if (data.detail) msg = data.detail;
        } catch (_) {
          // ignore JSON parse errors
        }
        showError(msg);
        return;
      }

      const data = await response.json();
      const token = data.access_token;

      if (!token) {
        showError("Something went wrong. No token returned.");
        return;
      }

      // Store token for later use (dashboard / extension can use this later)
      localStorage.setItem("deepmode_token", token);

      // Redirect to dashboard
      window.location.href = "/dashboard";
    } catch (err) {
      console.error(err);
      showError("Couldn’t reach Deepmode servers. Try again.");
    } finally {
      loginButton.disabled = false;
      loginButton.textContent = "Sign in";
    }
  });
});
