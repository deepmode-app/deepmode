// deepmode-extension/popup.js

// 1) CONFIG – set this to your backend base URL
const API_BASE = "https://95e81190-332d-4b5b-a875-0a3ed330e756-00-1kk0ba0t7ygdw.janeway.replit.dev"; // NO trailing slash

// 2) Helpers for chrome.storage
function getStoredAuth() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(["deepmode_token", "deepmode_email", "deepmode_active_session"], (data) => {
      resolve({
        token: data.deepmode_token || null,
        email: data.deepmode_email || null,
        activeSessionId: data.deepmode_active_session || null,
      });
    });
  });
}

function storeAuth(token, email) {
  return new Promise((resolve) => {
    chrome.storage.sync.set(
      {
        deepmode_token: token,
        deepmode_email: email,
      },
      resolve
    );
  });
}

function clearAuth() {
  return new Promise((resolve) => {
    chrome.storage.sync.remove(
      ["deepmode_token", "deepmode_email", "deepmode_active_session"],
      resolve
    );
  });
}

function storeActiveSession(id) {
  return new Promise((resolve) => {
    chrome.storage.sync.set({ deepmode_active_session: id }, resolve);
  });
}

// 3) UI refs
const loggedInSection = document.getElementById("loggedInSection");
const loginSection = document.getElementById("loginSection");

const loggedInMeta = document.getElementById("loggedInMeta");
const taskInput = document.getElementById("taskInput");
const categorySelect = document.getElementById("categorySelect");
const durationSelect = document.getElementById("durationSelect");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const statusMsg = document.getElementById("statusMsg");
const sessionStatusText = document.getElementById("sessionStatusText");
const logoutBtn = document.getElementById("logoutBtn");

const emailInput = document.getElementById("emailInput");
const passwordInput = document.getElementById("passwordInput");
const loginBtn = document.getElementById("loginBtn");
const loginError = document.getElementById("loginError");

// 4) State
let currentToken = null;
let currentEmail = null;
let activeSessionId = null;

// 5) Init
document.addEventListener("DOMContentLoaded", async () => {
  const auth = await getStoredAuth();
  currentToken = auth.token;
  currentEmail = auth.email;
  activeSessionId = auth.activeSessionId;

  if (!currentToken) {
    showLogin();
  } else {
    showLoggedIn();
  }
});

// ----- UI MODE SWITCHES -----

function showLogin() {
  loggedInSection.style.display = "none";
  loginSection.style.display = "block";
  loginError.textContent = "";
}

function showLoggedIn() {
  loginSection.style.display = "none";
  loggedInSection.style.display = "block";

  loggedInMeta.textContent = currentEmail
    ? `Signed in as ${currentEmail}.`
    : ``;

  if (activeSessionId) {
    startBtn.disabled = true;
    stopBtn.disabled = false;
    sessionStatusText.textContent = "Active block running…";
  } else {
    startBtn.disabled = false;
    stopBtn.disabled = true;
    sessionStatusText.textContent = "No active block.";
  }

  statusMsg.textContent = "";
}

// ----- LOGIN FLOW -----

loginBtn.addEventListener("click", async () => {
  loginError.textContent = "";

  const email = emailInput.value.trim();
  const password = passwordInput.value;

  if (!email || !password) {
    loginError.textContent = "Email and password are required.";
    return;
  }

  loginBtn.disabled = true;
  loginBtn.textContent = "Logging in…";

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      loginError.textContent = data.detail || "Login failed. Check your details.";
      loginBtn.disabled = false;
      loginBtn.textContent = "Log in";
      return;
    }

    const data = await res.json();
    if (!data.access_token) {
      loginError.textContent = "No token returned from server.";
      loginBtn.disabled = false;
      loginBtn.textContent = "Log in";
      return;
    }

    currentToken = data.access_token;
    currentEmail = email;
    activeSessionId = null;

    await storeAuth(currentToken, currentEmail);
    await storeActiveSession(null);

    showLoggedIn();
  } catch (err) {
    console.error(err);
    loginError.textContent = "Network error. Try again.";
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = "Log in";
  }
});

// ----- LOGOUT -----

logoutBtn.addEventListener("click", async () => {
  await clearAuth();
  currentToken = null;
  currentEmail = null;
  activeSessionId = null;
  showLogin();
});

// ----- SESSION START / STOP -----

startBtn.addEventListener("click", async () => {
  if (!currentToken) {
    showLogin();
    return;
  }

  const task = taskInput.value.trim() || "Deep work";
  const category = categorySelect.value || "deepwork";
  const duration = parseInt(durationSelect.value, 10) || 25;

  startBtn.disabled = true;
  stopBtn.disabled = true;
  statusMsg.textContent = "Starting block…";

  try {
    const res = await fetch(`${API_BASE}/sessions/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + currentToken,
        "Accept": "application/json",
      },
      body: JSON.stringify({
        task: task,
        category: category,
        planned_duration_minutes: duration,
      }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      statusMsg.textContent = data.detail || "Couldn’t start block.";
      startBtn.disabled = false;
      stopBtn.disabled = true;
      return;
    }

    const sess = await res.json();
    activeSessionId = sess.id;
    await storeActiveSession(activeSessionId);

    statusMsg.textContent = "Block started. Stay on task.";
    startBtn.disabled = true;
    stopBtn.disabled = false;
    sessionStatusText.textContent = "Active block running…";
  } catch (err) {
    console.error(err);
    statusMsg.textContent = "Network error while starting block.";
    startBtn.disabled = false;
    stopBtn.disabled = true;
  }
});

stopBtn.addEventListener("click", async () => {
  if (!currentToken || !activeSessionId) {
    return;
  }

  stopBtn.disabled = true;
  statusMsg.textContent = "Ending block…";

  try {
    const res = await fetch(`${API_BASE}/sessions/${activeSessionId}/end`, {
      method: "PATCH",
      headers: {
        "Authorization": "Bearer " + currentToken,
        "Accept": "application/json",
      },
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      statusMsg.textContent = data.detail || "Couldn’t end block.";
      stopBtn.disabled = false;
      return;
    }

    const updated = await res.json();
    statusMsg.textContent = `Block completed: ${updated.actual_duration_minutes || 0} min.`;
    activeSessionId = null;
    await storeActiveSession(null);

    startBtn.disabled = false;
    stopBtn.disabled = true;
    sessionStatusText.textContent = "No active block.";
  } catch (err) {
    console.error(err);
    statusMsg.textContent = "Network error while ending block.";
    stopBtn.disabled = false;
  }
});
