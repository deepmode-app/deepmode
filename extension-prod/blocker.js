// blocker.js – runs in the context of pages that Deepmode decided to block
console.log("Deepmode blocker loaded on this page.");

// Keep track of page media state so we can restore it
let deepmodeMediaState = [];

// ---------- MOTIVATIONAL LINES POOL ----------

const DM_MOTIVATION_LINES = [
  (task) => `Keep building momentum — go back to "${task}".`,
  (task) => `Real progress is on "${task}", not here.`,
  (task) => `Don't let this tab win — finish "${task}" first.`,
  (task) => `Your future self cares about "${task}" more than this page.`,
  (task) => `Stay with "${task}" — this is where the real dopamine comes from.`,
  (task) => `Deep focus now, everything else later. Back to "${task}".`,
  (task) => `You started this block for "${task}". Honor that decision.`,
  (task) => `One more stretch on "${task}" beats ten minutes of scrolling.`,
  (task) => `Protect your focus — return to "${task}".`,
  (task) => `You're building discipline rep by rep. Stick with "${task}".`,
  (task) => `Distractions are cheap. "${task}" is not.`,
  (task) => `Stay in Deepmode — finish the hard part of "${task}".`,
  (task) => `This site will still be here. Your block for "${task}" won't.`,
  (task) => `Momentum is fragile. Guard it — go back to "${task}".`,
  (task) => `You're closer than you think on "${task}". Keep going.`,
  (task) => `Train your brain: choose "${task}" over this tab.`,
  (task) => `Scroll less. Ship more. Back to "${task}".`,
  (task) => `Your best work happens in blocks like this — stay on "${task}".`,
  (task) => `Tiny choice: distraction or "${task}". Choose the one that compounds.`,
  (task) => `One finished block on "${task}" beats a day of half-focus.`,
  (task) => `This is the test. Stay with "${task}" until the timer ends.`,
  (task) => `Deep workers say no to this tab and yes to "${task}".`,
  (task) => `Refocus now — even 5 more minutes on "${task}" matters.`,
  (task) => `You locked in for a reason. Return to "${task}".`,
];

function getMotivationLine(taskName) {
  const task = taskName && taskName.trim() ? taskName.trim() : "your task";
  const idx = Math.floor(Math.random() * DM_MOTIVATION_LINES.length);
  return DM_MOTIVATION_LINES[idx](task);
}

// ---------- MEDIA MUTE/RESTORE ----------

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

// ---------- OVERLAY ----------

function showOverlay(activeSession) {
  if (document.getElementById("deepwork-overlay")) return;

  // Determine if user is Pro - check session first, then storage
  let isPro = false;
  if (activeSession && activeSession.is_pro !== undefined) {
    isPro = activeSession.is_pro;
  } else {
    // Check storage for user info
    chrome.storage.local.get(["deepmode_user"], (result) => {
      if (result.deepmode_user && result.deepmode_user.is_pro) {
        isPro = true;
      }
      renderOverlay(activeSession, isPro);
    });
    return; // Will render in callback
  }
  
  renderOverlay(activeSession, isPro);
}

function renderOverlay(activeSession, isPro) {
  if (document.getElementById("deepwork-overlay")) return;

  // Get the task name for personalized motivation
  const taskName = activeSession && activeSession.task ? activeSession.task : null;
  
  // Get a random motivational line
  const motivationLine = getMotivationLine(taskName);

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
    <div class="deepmode-overlay-bg-logo"></div>
    <div style="
      background:#111118;
      padding:28px 32px;
      border-radius:18px;
      box-shadow:0 22px 60px rgba(0,0,0,0.85);
      max-width:520px;
      text-align:center;
      color:#f5f5f5;
      font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
      position:relative;
      z-index:1;
    ">
      <div style="font-size:10px; text-transform:uppercase; letter-spacing:0.18em; color:#6b7280; margin-bottom:10px; font-weight:500;">
        DEEPMODE FOCUS LOCK
      </div>
      <h2 style="margin:0 0 14px; font-size:24px; font-weight:600;">Deepwork in progress.</h2>
      <p id="dm-motivation-line" style="margin:0 0 16px; font-size:15px; color:#e5e7eb; line-height:1.6;">
        ${motivationLine}
      </p>
      <p style="margin:0; font-size:11px; color:#6b7280; line-height:1.5;">
        Distractions are blocked to protect this focus block.<br/>
        If this site is essential for your task, you can allow it from the Deepmode extension.
      </p>
    </div>
  `;

  // Add CSS for background logo and Inter font
  if (!document.getElementById("deepmode-overlay-styles")) {
    const style = document.createElement("style");
    style.id = "deepmode-overlay-styles";
    const fontLink = document.createElement("link");
    fontLink.rel = "preconnect";
    fontLink.href = "https://fonts.googleapis.com";
    document.head.appendChild(fontLink);
    const fontLink2 = document.createElement("link");
    fontLink2.rel = "preconnect";
    fontLink2.href = "https://fonts.gstatic.com";
    fontLink2.crossOrigin = "anonymous";
    document.head.appendChild(fontLink2);
    const fontLink3 = document.createElement("link");
    fontLink3.rel = "stylesheet";
    fontLink3.href = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap";
    document.head.appendChild(fontLink3);
    style.textContent = `
      #deepwork-overlay {
        position: relative;
      }
      .deepmode-overlay-bg-logo {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 480px;
        height: 480px;
        background-image: url("https://deepmode.app/static/logos/Logo%20-%20Red%20BG.png");
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
        opacity: 0.05;
        pointer-events: none;
        filter: blur(1.5px) drop-shadow(0 0 60px rgba(229, 9, 20, 0.3));
        z-index: 0;
      }
    `;
    document.head.appendChild(style);
  }

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
  if (remainingSeconds > 0) {
      isRunning = true;
      console.log(`[Deepmode Blocker] ✅ Timer started! Will auto-end in ${remainingSeconds} seconds`);
      tickTimer();
  } else {
    console.log(`[Deepmode Blocker] ⚠️ Timer already expired (${remainingSeconds}s), triggering immediate auto-end`);
    // Timer already expired, trigger auto-end immediately
    if (!sessionFinishedNotified) {
      sessionFinishedNotified = true;
      chrome.runtime.sendMessage(
        { type: "END_SESSION_AT_TIMER_ZERO" },
        (response) => {
          if (chrome.runtime.lastError) {
            console.error("[Deepmode Blocker] Error sending END_SESSION_AT_TIMER_ZERO:", chrome.runtime.lastError.message);
          } else {
            console.log("[Deepmode Blocker] ✅ END_SESSION_AT_TIMER_ZERO sent successfully");
          }
        }
      );
    }
  }
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

  // ----- HIT ZERO - Send END_SESSION_AT_TIMER_ZERO (alarm is primary, this is backup) -----
  if (remainingSeconds <= 0 && !sessionFinishedNotified) {
    sessionFinishedNotified = true;
    remainingSeconds = 0;
    console.log("[Deepmode Blocker] Timer reached 0 - sending END_SESSION_AT_TIMER_ZERO (backup trigger)");

    // Update badge to 0
    updateTimerUI(remainingSeconds);

    // Send END_SESSION_AT_TIMER_ZERO message to background.js
    // Background.js alarm is the primary trigger, but this ensures we end even if alarm fails
    chrome.runtime.sendMessage(
      { type: "END_SESSION_AT_TIMER_ZERO" },
      (response) => {
        if (chrome.runtime.lastError) {
          console.error("[Deepmode Blocker] Error sending END_SESSION_AT_TIMER_ZERO:", chrome.runtime.lastError.message);
        } else {
          console.log("[Deepmode Blocker] ✅ END_SESSION_AT_TIMER_ZERO sent successfully");
        }
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
