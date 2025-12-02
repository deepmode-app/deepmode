// blocker.js – runs in the context of pages that Deepmode decided to block
console.log("Deepmode blocker loaded on this page.");

// Keep track of page media state so we can restore it
let deepmodeMediaState = [];

/**
 * Mute + pause all audio/video elements on the page,
 * while remembering their previous state so we can restore later.
 */
function mutePageMedia() {
  deepmodeMediaState = [];

  try {
    const mediaEls = document.querySelectorAll("video, audio");
    mediaEls.forEach((el) => {
      try {
        deepmodeMediaState.push({
          el,
          wasMuted: el.muted,
          wasPaused: el.paused,
        });

        el.muted = true;
        if (!el.paused) {
          el.pause();
        }
      } catch (e) {
        console.warn("Deepmode blocker: error muting media element", e);
      }
    });
  } catch (e) {
    console.warn("Deepmode blocker: error querying media elements", e);
  }
}

/**
 * Restore audio/video elements to their previous mute/play state
 * where possible (elements may have been removed / changed meanwhile).
 *
 * Includes a fallback using an inline <script> so playback resumes
 * in page context (bypassing autoplay restrictions on YouTube, etc.).
 */
function restorePageMedia() {
  if (!deepmodeMediaState || deepmodeMediaState.length === 0) return;

  deepmodeMediaState.forEach((state) => {
    const el = state.el;
    if (!el || !el.isConnected) return;

    try {
      // Restore mute flag
      el.muted = state.wasMuted;

      // If it was playing before, try to resume
      if (!state.wasPaused) {
        const playPromise = el.play();
        if (playPromise && typeof playPromise.catch === "function") {
          playPromise.catch(() => {
            // Fallback: run in page context where autoplay is allowed
            forcePlayInPage();
          });
        }
      }
    } catch (e) {
      console.warn("Deepmode blocker: error restoring media element", e);
    }
  });

  deepmodeMediaState = [];
}

/**
 * Fallback: injects a tiny inline <script> that calls play()
 * from the page's own JS context. This is needed to bypass
 * autoplay restrictions on some sites (YouTube, etc.).
 */
function forcePlayInPage() {
  try {
    const s = document.createElement("script");
    s.textContent = `
      try {
        const mediaEls = document.querySelectorAll("video, audio");
        mediaEls.forEach((el) => {
          el.muted = false;
          const p = el.play();
          if (p && typeof p.catch === "function") {
            p.catch(() => {});
          }
        });
      } catch (e) {}
    `;
    document.documentElement.appendChild(s);
    s.remove();
  } catch (e) {
    console.warn("Deepmode blocker: forcePlayInPage failed", e);
  }
}

function showOverlay(activeSession) {
  if (document.getElementById("deepwork-overlay")) return;

  // Try to personalize with the current task
  const taskLabel = (activeSession && activeSession.task)
    ? `“${activeSession.task}”`
    : "your current Deepmode block";

  // Pool of random one-liners
  const messages = [
    `This tab is bait. Get back to ${taskLabel}.`,
    `Scroll later. Finish ${taskLabel} first.`,
    `Your future self doesn’t care about this page. It cares that you finish ${taskLabel}.`,
    `You opened this out of habit, not intention. Return to ${taskLabel}.`,
    `Tiny distraction. Huge cost. Close this and push ${taskLabel} forward.`,
    `Every tab like this steals time from ${taskLabel}. Don’t donate your focus.`,
    `This doesn’t move your life. ${taskLabel} does. Go back.`,
    `You already know what’s here. You *don’t* know how far ${taskLabel} can go.`,
    `Distraction is free. Progress isn’t. Choose ${taskLabel}.`,
    `One more click here = one less rep on ${taskLabel}.`,
    `You said you wanted deep work. Prove it. Back to ${taskLabel}.`,
    `This tab is how you stay the same. ${taskLabel} is how you change.`,
    `Your best work isn’t on this site. It’s inside ${taskLabel}.`,
    `Close this. Breathe. Do 5 more focused minutes on ${taskLabel}.`,
    `Attention is a currency. Don’t tip this site with it. Invest in ${taskLabel}.`,
    `You’re not missing anything here. You *are* missing progress on ${taskLabel}.`,
    `You came here on autopilot. Go back to ${taskLabel} on purpose.`,
    `This is the old loop. ${taskLabel} is the new path. Pick the new path.`,
    `Be the person who finishes ${taskLabel}, not the person who refreshes this site.`,
    `You’re in Deepmode. This tab isn’t. Go where your focus is supposed to be.`,
    `Close this and make 10 intentional minutes on ${taskLabel}.`,
    `This page gives you a hit. ${taskLabel} gives you momentum.`,
    `If it’s not helping ${taskLabel}, it’s stealing from it.`,
    `The work that matters is waiting. Hint: it’s ${taskLabel}.`,
    `You can doomscroll or you can finish ${taskLabel}. Not both.`,
    `You’re already in power mode. Don’t leak it here. Back to ${taskLabel}.`,
    `Momentum dies here. Momentum grows in ${taskLabel}.`,
    `You don’t need this. You *do* need progress on ${taskLabel}.`,
    `Close this tab. Resume ${taskLabel}. That’s the move.`
  ];

  const randomMessage =
    messages[Math.floor(Math.random() * messages.length)];

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
      max-width:480px;
      text-align:center;
      color:#f5f5f5;
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
    ">
      <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.15em; color:#9ca3af; margin-bottom:6px;">
        Deepmode AI
      </div>
      <h2 style="margin:0 0 10px; font-size:22px;">You're in a Deepwork Session</h2>
      <p style="margin:0; font-size:14px; color:#e5e7eb; line-height:1.5;">
        ${randomMessage}
      </p>
      <p style="margin:10px 0 0; font-size:12px; color:#9ca3af;">
        Close this tab or end your session from the Deepmode extension popup.
      </p>
    </div>
  `;

  document.body.appendChild(overlay);

  // 🔇 Mute + pause any active media on the page
  mutePageMedia();
}

function removeOverlay() {
  const overlay = document.getElementById("deepwork-overlay");
  if (overlay) overlay.remove();

  // 🔊 Restore page media to previous state
  restorePageMedia();
}

// ---------- TIMER LOGIC ----------

let isRunning = false;
let timerHandle = null;
let endSessionHandler = null;
// Session config variables
let baseMinutes = 0;
let isShortBlock = false;
let plannedSeconds = 0;
let remainingSeconds = 0;
let fiveMinuteWarningSent = false;
let sessionFinishedNotified = false;
let taskLabel = "";

function updateTimerUI(seconds) {
  // Update extension badge with remaining time
  const minutes = Math.ceil(seconds / 60);
  const badgeText = seconds > 0 ? minutes.toString() : "0";
  
  chrome.runtime.sendMessage({
    type: "UPDATE_BADGE",
    text: badgeText,
    seconds: seconds
  }, () => {
    // Ignore errors (background might not be ready)
    if (chrome.runtime.lastError) {
      // Background not ready, that's okay
    }
  });
}

function initializeTimer(activeSession) {
  if (!activeSession || !activeSession.id) {
    if (timerHandle) {
      clearTimeout(timerHandle);
      timerHandle = null;
    }
    isRunning = false;
    return;
  }

  const durationMinutes = activeSession.planned_duration_minutes || 0;
  taskLabel = activeSession.task || "Deepmode block";

  // Base session config
  baseMinutes = durationMinutes;
  isShortBlock = baseMinutes <= 5; // <=5 means no 5-minute warning

  plannedSeconds = durationMinutes * 60;
  
  // Calculate remaining time based on elapsed time from start_time
  if (activeSession.start_time) {
    const startTime = new Date(activeSession.start_time).getTime();
    const now = Date.now();
    const elapsedSeconds = Math.floor((now - startTime) / 1000);
    remainingSeconds = Math.max(0, plannedSeconds - elapsedSeconds);
  } else {
    remainingSeconds = plannedSeconds;
  }
  
  console.log(`[Deepmode Blocker] Timer initialized: ${durationMinutes}min planned, ${remainingSeconds}s remaining, isShortBlock=${isShortBlock}`);
  
  fiveMinuteWarningSent = false;
  sessionFinishedNotified = false;

  // Stop any existing timer
  if (timerHandle) {
    clearTimeout(timerHandle);
    timerHandle = null;
  }
  isRunning = false;

  // Update badge immediately
  updateTimerUI(remainingSeconds);

  // Start the timer
  isRunning = true;
  tickTimer();
}

function tickTimer() {
  if (!isRunning) {
    console.log("[Deepmode Blocker] Timer tick skipped - not running");
    return;
  }

  remainingSeconds--;

  // Debug log every 60 seconds OR when close to 0
  if ((remainingSeconds % 60 === 0 && remainingSeconds > 0) || (remainingSeconds <= 10 && remainingSeconds > 0)) {
    console.log(`[Deepmode Blocker] Timer: ${Math.floor(remainingSeconds / 60)}m ${remainingSeconds % 60}s remaining`);
  }
  
  // ----- 5-MINUTE WARNING (only for blocks > 5 minutes) -----
  if (
    !isShortBlock &&
    !fiveMinuteWarningSent &&
    remainingSeconds === 5 * 60
  ) {
    fiveMinuteWarningSent = true;
    console.log("[Deepmode Blocker] 5 minutes left - sending notification");

    chrome.runtime.sendMessage({
      type: "BLOCK_5MIN_LEFT",
      task: taskLabel
    }, (response) => {
      if (chrome.runtime.lastError) {
        console.error("[Deepmode Blocker] Error sending BLOCK_5MIN_LEFT:", chrome.runtime.lastError.message);
      } else {
        console.log("[Deepmode Blocker] BLOCK_5MIN_LEFT sent successfully");
      }
    });
  }

  // ----- HIT ZERO - Auto-end session -----
  if (remainingSeconds <= 0 && !sessionFinishedNotified) {
    sessionFinishedNotified = true;
    remainingSeconds = 0;
    console.log("[Deepmode Blocker] Timer reached 0 - sending BLOCK_FINISHED and auto-ending session");

    // Update badge to 0
    updateTimerUI(remainingSeconds);

    // 1) Notify background so it can show a passive notification
    chrome.runtime.sendMessage(
      {
        type: "BLOCK_FINISHED",
        task: taskLabel || "your block"
      },
      () => {
        // Optional: ignore errors (e.g., background unavailable)
      }
    );

    // 2) Auto-end the session via background (single source of truth)
    chrome.runtime.sendMessage(
      { type: "END_SESSION" },
      () => {
        // No-op; background will handle API call and storage cleanup
      }
    );

    // Stop the local timer loop
    isRunning = false;
    if (timerHandle) {
      clearTimeout(timerHandle);
      timerHandle = null;
    }
    return;
  }

  // Normal ticking
  updateTimerUI(remainingSeconds);
  timerHandle = setTimeout(tickTimer, 1000);
}

// Initial check when script loads
chrome.storage.local.get(["deepmode_active_session"], (result) => {
  const active = result.deepmode_active_session;
  if (active && active.id) {
    console.log("Deepmode active on load — showing overlay.");
    showOverlay(active);   // pass session so we can personalize
    initializeTimer(active);
  } else {
    console.log("No active session on load (blocker).");
  }
});

// React to session start/end (storage-based)
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if (!changes.deepmode_active_session) return;

  const newVal = changes.deepmode_active_session.newValue;

  if (newVal && newVal.id) {
    console.log("Deepmode started — showing overlay.");
    showOverlay(newVal);   // personalized message
    initializeTimer(newVal);
  } else {
    console.log("Deepmode ended — removing overlay.");
    removeOverlay();
    if (timerHandle) {
      clearTimeout(timerHandle);
      timerHandle = null;
    }
    isRunning = false;
  }
});

// React to explicit block/unblock messages from background.js
chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || !msg.type) return;

  if (msg.type === "DEEPMODE_UNBLOCK") {
    console.log("Deepmode blocker: received DEEPMODE_UNBLOCK – removing overlay");
    removeOverlay();
    // Check if session is still active before stopping timer
    chrome.storage.local.get(["deepmode_active_session"], (result) => {
      const active = result.deepmode_active_session;
      if (!active || !active.id) {
        // Session actually ended - stop timer and clear badge
        console.log("[Deepmode Blocker] Session ended - stopping timer");
        if (timerHandle) {
          clearTimeout(timerHandle);
          timerHandle = null;
        }
        isRunning = false;
        // Clear badge
        chrome.runtime.sendMessage({ type: "CLEAR_BADGE" }, () => {});
      } else {
        // Session still active, just unblocking this tab - keep timer running
        console.log("[Deepmode Blocker] Session still active - keeping timer running");
      }
    });
    return;
  }

  if (msg.type === "DEEPMODE_BLOCK") {
    console.log("Deepmode blocker: received DEEPMODE_BLOCK – showing overlay again");
    chrome.storage.local.get(["deepmode_active_session"], (result) => {
      const active = result.deepmode_active_session;
      if (active && active.id) {
        showOverlay(active);
        initializeTimer(active);
      }
    });
    return;
  }

  if (msg.type === "END_SESSION") {
    // Manual end from popup/dashboard - stop timer cleanly
    console.log("[Deepmode Blocker] END_SESSION received - stopping timer");
    isRunning = false;
    if (timerHandle) {
      clearTimeout(timerHandle);
      timerHandle = null;
    }
    // Forward to background.js to handle backend call
    chrome.runtime.sendMessage({ type: "END_SESSION" }, () => {
      if (chrome.runtime.lastError) {
        // Fallback if background not ready
        chrome.runtime.sendMessage({ type: "END_SESSION_FROM_BLOCKER" });
      }
    });
    return;
  }
});
