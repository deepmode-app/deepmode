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
let fallbackAutoEndTimeout = null;

// Session config variables
let baseMinutes = 0;
let isShortBlock = false;
const MAX_SESSION_SECONDS = 2 * 60 * 60; // 2 hours
let plannedSeconds = 0;
let remainingSeconds = 0;
let fiveMinuteWarningSent = false;
let sessionFinishedNotified = false;
let taskLabel = "";

function updateTimerUI(seconds) {
  // Update any timer display if needed (currently no UI in blocker.js)
  // This is a placeholder for future UI updates
}

function initializeTimer(activeSession) {
  if (!activeSession || !activeSession.id) {
    if (timerHandle) {
      clearTimeout(timerHandle);
      timerHandle = null;
    }
    if (fallbackAutoEndTimeout) {
      clearTimeout(fallbackAutoEndTimeout);
      fallbackAutoEndTimeout = null;
    }
    isRunning = false;
    return;
  }

  const durationMinutes = activeSession.planned_duration_minutes || 0;
  taskLabel = activeSession.task || "Deepmode block";

  // Base session config
  baseMinutes = durationMinutes;
  isShortBlock = baseMinutes <= 5;

  // Hard cap: 2 hours max planned time for a single deep block
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
  
  fiveMinuteWarningSent = false;
  sessionFinishedNotified = false;

  // Start the timer
  if (!isRunning) {
    isRunning = true;
    tickTimer();
  }
}

function tickTimer() {
  if (!isRunning) return;

  remainingSeconds--;

  // ----- 5-MINUTE WARNING (only for non-short blocks) -----
  if (
    !isShortBlock &&
    !fiveMinuteWarningSent &&
    remainingSeconds === 5 * 60
  ) {
    fiveMinuteWarningSent = true;

    chrome.runtime.sendMessage({
      type: "BLOCK_5MIN_LEFT",
      task: taskLabel,
      remaining: remainingSeconds
    });
  }

  // ----- HIT ZERO (do NOT auto-end; ask user what to do) -----
  if (remainingSeconds <= 0 && !sessionFinishedNotified) {
    sessionFinishedNotified = true;
    remainingSeconds = 0;

    updateTimerUI(remainingSeconds);

    chrome.runtime.sendMessage({
      type: "BLOCK_FINISHED",
      task: taskLabel
    });

    // Set a fallback auto-end after 10 minutes if user doesn't respond
    if (fallbackAutoEndTimeout) {
      clearTimeout(fallbackAutoEndTimeout);
    }
    fallbackAutoEndTimeout = setTimeout(() => {
      // Check if session is still active and still at 0 (user didn't extend or end)
      chrome.storage.local.get(["deepmode_active_session"], (result) => {
        const active = result.deepmode_active_session;
        if (active && active.id && remainingSeconds <= 0) {
          // User didn't respond - auto-end the session
          console.log("[Deepmode Blocker] Auto-ending session after 10min grace period (no user response)");
          chrome.runtime.sendMessage({ type: "END_SESSION" });
        }
      });
      fallbackAutoEndTimeout = null;
    }, 10 * 60 * 1000); // 10 minutes grace period

    // Freeze at 0 until user chooses End or Extend
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
    if (timerHandle) {
      clearTimeout(timerHandle);
      timerHandle = null;
    }
    isRunning = false;
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
    // User chose to end from notification
    isRunning = false;
    if (timerHandle) {
      clearTimeout(timerHandle);
      timerHandle = null;
    }
    // Clear fallback auto-end since user responded
    if (fallbackAutoEndTimeout) {
      clearTimeout(fallbackAutoEndTimeout);
      fallbackAutoEndTimeout = null;
    }
    if (typeof endSessionHandler === "function") {
      endSessionHandler();
    } else {
      // Fallback: send message to background to end session
      chrome.runtime.sendMessage({ type: "END_SESSION_FROM_BLOCKER" });
    }
    return;
  }

  if (msg.type === "EXTEND_SESSION") {
    const extraSeconds = (msg.minutes || 0) * 60;
    if (extraSeconds <= 0) return;

    const newPlanned = plannedSeconds + extraSeconds;

    // Enforce hard cap at 2 hours
    if (newPlanned > MAX_SESSION_SECONDS) {
      chrome.runtime.sendMessage({
        type: "BLOCK_MAX_REACHED",
        task: taskLabel
      });
      return;
    }

    // Clear fallback auto-end since user responded
    if (fallbackAutoEndTimeout) {
      clearTimeout(fallbackAutoEndTimeout);
      fallbackAutoEndTimeout = null;
    }

    plannedSeconds = newPlanned;
    remainingSeconds += extraSeconds;

    // Allow a new 5-minute warning near the *new* end
    fiveMinuteWarningSent = false;
    sessionFinishedNotified = false;

    updateTimerUI(remainingSeconds);
    if (!isRunning) {
      isRunning = true;
      tickTimer();
    }
    return;
  }
});
