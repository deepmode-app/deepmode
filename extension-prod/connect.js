// connect.js
console.log("Deepmode connect script loaded on this page.");

const API_BASE_URL = "https://deepmode.app";


// Listen for messages from the *page* (dashboard / login etc.)
window.addEventListener("message", (event) => {
  if (event.source !== window) return;

  const data = event.data || {};

  // Case 1: dashboard is telling us "here is the JWT"
  if (data.type === "DEEPMODE_JWT" && typeof data.token === "string") {
    chrome.storage.local.set(
      { deepmode_access_token: data.token },
      () => {
        console.log("Deepmode: JWT stored in chrome.storage.local");
      }
    );
    return;
  }

  // Case 2: dashboard is telling us "user clicked logout"
  if (data.type === "DEEPMODE_LOGOUT") {
    console.log("Deepmode: received logout event from dashboard");

    chrome.storage.local.get(
      ["deepmode_access_token", "deepmode_active_session"],
      async (result) => {
        const token  = result.deepmode_access_token;
        const active = result.deepmode_active_session;

        // 🔹 Immediately clear extension-side auth & session
        chrome.storage.local.remove(
          ["deepmode_access_token", "deepmode_active_session"],
          () => {
            console.log(
              "Deepmode: cleared deepmode_access_token + deepmode_active_session on logout"
            );
            try {
              chrome.runtime.sendMessage({ type: "DEEPMODE_LOGOUT" });
            } catch (e) {
              console.warn("Deepmode: could not notify popup on logout", e);
            }
          }
        );

        // 🔹 Best-effort: tell backend to end the session
        if (token && active && active.id && !active.isGuest) {
          try {
            await fetch(`${API_BASE_URL}/sessions/${active.id}/end`, {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
              },
            });
            console.log("Deepmode: active session ended on logout");
          } catch (err) {
            console.warn("Deepmode: failed to end session on logout", err);
          }
        }
      }
    );
    return;
  }

  // Case 3: dashboard updates block prefs
  if (data.type === "DEEPMODE_UPDATE_BLOCK_PREFS" && data.prefs) {
    chrome.storage.sync.set(
      { deepmode_block_prefs: data.prefs },
      () => {
        console.log("Deepmode: block prefs updated from dashboard");
      }
    );
    return;
  }
});

// Listen for messages from the extension popup (logout triggered from extension)
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "EXTENSION_LOGOUT") {
    console.log("Deepmode connect: received EXTENSION_LOGOUT from popup");
    
    // Clear dashboard localStorage and redirect to homepage
    localStorage.removeItem("access_token");
    localStorage.removeItem("deepmode_token");
    
    // Redirect to homepage
    window.location.href = "/";
    
    sendResponse({ success: true });
  }
});