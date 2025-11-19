console.log("Deepwork blocker loaded on this page.");

function showOverlay() {
  if (document.getElementById("deepwork-overlay")) return;

  const overlay = document.createElement("div");
  overlay.id = "deepwork-overlay";
  overlay.style.position = "fixed";
  overlay.style.top = "0";
  overlay.style.left = "0";
  overlay.style.width = "100%";
  overlay.style.height = "100%";
  overlay.style.background = "rgba(0, 0, 0, 0.92)";
  overlay.style.display = "flex";
  overlay.style.alignItems = "center";
  overlay.style.justifyContent = "center";
  overlay.style.zIndex = "999999";

  overlay.innerHTML = `
    <div style="
      background:#111118;
      padding:24px 28px;
      border-radius:18px;
      box-shadow:0 22px 60px rgba(0,0,0,0.85);
      max-width:420px;
      text-align:center;
      color:#f5f5f5;
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
    ">
      <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.15em; color:#9ca3af; margin-bottom:6px;">
        Deepwork AI
      </div>
      <h2 style="margin:0 0 8px; font-size:22px;">You're in a Deepwork Session</h2>
      <p style="margin:0 0 4px; font-size:14px; color:#e5e7eb;">
        Focus mode is active. Close this tab or end your session in the Deepwork popup.
      </p>
    </div>
  `;

  document.body.appendChild(overlay);
}


function removeOverlay() {
  const overlay = document.getElementById("deepwork-overlay");
  if (overlay) overlay.remove();
}

// Initial check when the content script loads
chrome.storage.local.get(["deepwork_active_session"], (result) => {
  const active = result.deepwork_active_session;
  if (active && active.id) {
    console.log("Deepwork active on load — blocking.");
    showOverlay();
  } else {
    console.log("No active session on load.");
  }
});

// React to session start/end while this tab is open
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if (!changes.deepwork_active_session) return;

  const newVal = changes.deepwork_active_session.newValue;

  if (newVal && newVal.id) {
    console.log("Deepwork started — showing overlay.");
    showOverlay();
  } else {
    console.log("Deepwork ended — removing overlay.");
    removeOverlay();
  }
});
