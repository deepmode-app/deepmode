// popup.js

// Backend used ONLY when we have a JWT token (signed-in mode)
const API_BASE_URL = "https://deepmode.onrender.com";
const DASHBOARD_URL = `${API_BASE_URL}/dashboard`;

// Storage keys
const STORAGE_KEYS = {
  ACTIVE_SESSION: "deepmode_active_session",
  ACCESS_TOKEN: "deepmode_access_token",
};

// Block preferences (sync)
const BLOCK_PREFS_KEY = "deepmode_block_prefs";

const DEFAULT_SITES = [
  { id: "youtube",   label: "YouTube",    host: "youtube.com",   icon: "▶" },
  { id: "twitter",   label: "Twitter/X",  host: "twitter.com",   icon: "✕" },
  { id: "instagram", label: "Instagram",  host: "instagram.com", icon: "◎" },
  { id: "facebook",  label: "Facebook",   host: "facebook.com",  icon: "f" },
  { id: "reddit",    label: "Reddit",     host: "reddit.com",    icon: "r" },
  { id: "tiktok",    label: "TikTok",     host: "tiktok.com",    icon: "♬" }
];

document.addEventListener("DOMContentLoaded", () => {
  const taskInput = document.getElementById("task");
  const categorySelect = document.getElementById("category");
  const durationSelect = document.getElementById("duration");
  const startBtn = document.getElementById("startBtn");
  const endBtn = document.getElementById("endBtn");
  const statusDiv = document.getElementById("status");
  const currentSessionBox = document.getElementById("currentSession");
  const currentTaskDiv = document.getElementById("currentTask");
  const currentCategoryDiv = document.getElementById("currentCategory");
  const dashboardLink = document.getElementById("dashboardLink");

  const authStateDiv = document.getElementById("authState");
  const planLabel = document.getElementById("planLabel");
  const durationHint = document.getElementById("durationHint");
  const upgradeRow = document.getElementById("upgradeRow");
  const upgradeCopy = document.getElementById("upgradeCopy");
  const upgradeBtn = document.getElementById("upgradeBtn");

  const defaultSitesRow = document.getElementById("defaultSitesRow");
  const customSitesTextarea = document.getElementById("customSites");

  // Priming overlay elements
  const primingOverlay = document.getElementById("primingOverlay");
  const primingCountdownEl = document.getElementById("primingCountdown");

  let timerInterval = null;
  let primingTimerId = null;
  let pendingSessionConfig = null;

  let accessToken = null;
  let isProUser = false;

  // ---------- NOTIFICATION PERMISSION CHECK ----------

  function checkNotificationPermission() {
    if (!chrome.notifications) {
      return;
    }

    if (chrome.notifications.getPermissionLevel) {
      chrome.notifications.getPermissionLevel((level) => {
        if (level === "denied") {
          // Show helpful message in status area
          if (statusDiv) {
            const hasActiveSession = currentSessionBox && currentSessionBox.style.display !== "none";
            
            if (!hasActiveSession) {
              // Only show if no active session (don't interfere with timer display)
              const originalText = statusDiv.textContent;
              statusDiv.style.color = "#ffb84d";
              statusDiv.style.fontSize = "11px";
              statusDiv.style.lineHeight = "1.4";
              statusDiv.textContent = "🔔 Enable notifications for timer alerts: Windows Settings > System > Notifications > Chrome";
              statusDiv.title = "Notifications help you know when your block finishes. Enable in Windows Settings.";
              
              // Restore after 10 seconds
              setTimeout(() => {
                chrome.storage.local.get([STORAGE_KEYS.ACTIVE_SESSION], (result) => {
                  if (!result[STORAGE_KEYS.ACTIVE_SESSION] && statusDiv.textContent.includes("Enable notifications")) {
                    statusDiv.textContent = originalText || "";
                    statusDiv.style.color = "";
                    statusDiv.style.fontSize = "";
                    statusDiv.style.lineHeight = "";
                    statusDiv.title = "";
                  }
                });
              }, 10000);
            }
          }
        } else if (level === "granted") {
          // Notifications enabled - all good
          console.log("[Deepmode Popup] Notifications enabled ✓");
        }
      });
    }
  }

  // Check notification permission on popup open
  checkNotificationPermission();
  
  // Re-check when popup is opened again (user might have enabled notifications)
  let lastPermissionCheck = 0;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      const now = Date.now();
      if (now - lastPermissionCheck > 5000) { // Check max once per 5 seconds
        checkNotificationPermission();
        lastPermissionCheck = now;
      }
    }
  });

  let blockPrefs = {
    defaultSiteFlags: {},
    customSites: [],
  };

  // ---------- Small helpers ----------

  function formatCategoryLabel(cat) {
    if (!cat) return "";
    const c = String(cat).toLowerCase().trim();
    if (c === "coding") return "Coding";
    if (c === "writing") return "Writing";
    if (c === "study") return "Study";
    if (c === "other") return "Other";
    return cat.charAt(0).toUpperCase() + cat.slice(1);
  }

  // ---------- UI helpers ----------

  function updateAuthState() {
    if (!authStateDiv) return;

    if (accessToken) {
      authStateDiv.textContent =
        "👤 Signed in — synced to dashboard.";
    } else {
      authStateDiv.textContent =
        "🕶 Guest mode — local only.";
    }
  }

  function applyPlanUI() {
    // Plan & hint text (short, no repetition)
    if (!accessToken) {
      if (planLabel) {
        planLabel.textContent = "Guest — 5m & 25m blocks.";
      }
      if (durationHint) {
        durationHint.textContent = "";
      }
      if (upgradeRow && upgradeCopy && upgradeBtn) {
        upgradeRow.style.display = "flex";
        upgradeCopy.textContent = "Try Deepmode Pro?";
        upgradeBtn.textContent = "See Pro plans";
      }
    } else if (!isProUser) {
      if (planLabel) {
        planLabel.textContent = "Free plan — 5m & 25m.";
      }
      if (durationHint) {
        durationHint.textContent = "";
      }
      if (upgradeRow && upgradeCopy && upgradeBtn) {
        upgradeRow.style.display = "flex";
        upgradeCopy.textContent = "Need longer blocks?";
        upgradeBtn.textContent = "Unlock Pro blocks";
      }
    } else {
      if (planLabel) {
        planLabel.textContent = "Pro — FOCUS unlocked.";
      }
      if (durationHint) {
        durationHint.textContent = "";
      }
      if (upgradeRow) {
        upgradeRow.style.display = "none";
      }
    }

    // Lock/unlock 50m & 90m based on plan
    if (!durationSelect) return;

    const opt50 = durationSelect.querySelector('option[value="50"]');
    const opt90 = durationSelect.querySelector('option[value="90"]');

    const canUseLongBlocks = !!(accessToken && isProUser);

    if (!canUseLongBlocks) {
      if (opt50) {
        opt50.disabled = true;
        if (!opt50.textContent.includes("🔒")) {
          opt50.textContent += " 🔒";
        }
      }
      if (opt90) {
        opt90.disabled = true;
        if (!opt90.textContent.includes("🔒")) {
          opt90.textContent += " 🔒";
        }
      }

      if (durationSelect.value === "50" || durationSelect.value === "90") {
        durationSelect.value = "25";
      }
    } else {
      if (opt50) {
        opt50.disabled = false;
        opt50.textContent = "Deep (50m) – Serious Focus";
      }
      if (opt90) {
        opt90.disabled = false;
        opt90.textContent = "Immersive (90m) – Full Flow Reset";
      }
    }
  }

  async function fetchMeAndApplyPlan() {
    if (!accessToken) {
      isProUser = false;
    } else {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/me`, {
          headers: {
            "Accept": "application/json",
            "Authorization": "Bearer " + accessToken,
          },
        });

        if (!res.ok) {
          console.warn("Deepmode popup: /auth/me not OK", res.status);
          isProUser = false;
        } else {
          const me = await res.json();
          isProUser = !!me.is_pro;
        }
      } catch (err) {
        console.error("Deepmode popup: error hitting /auth/me", err);
        isProUser = false;
      }
    }

    applyPlanUI();
  }

  function setUIForActiveSession(active) {
    if (active && active.id) {
      startBtn.disabled = true;
      endBtn.disabled = false;
      taskInput.disabled = true;
      categorySelect.disabled = true;
      durationSelect.disabled = true;

      currentSessionBox.style.display = "block";
      currentTaskDiv.textContent = `Task: ${active.task}`;
      currentCategoryDiv.textContent =
        `Category: ${formatCategoryLabel(active.category)}`;

      statusDiv.style.color = "#e5e7eb";
      statusDiv.textContent = active.isGuest
        ? "Deepmode guest session running."
        : "Deepmode session running.";
    } else {
      startBtn.disabled = false;
      endBtn.disabled = true;
      taskInput.disabled = false;
      categorySelect.disabled = false;
      durationSelect.disabled = false;

      currentSessionBox.style.display = "none";
      currentTaskDiv.textContent = "";
      currentCategoryDiv.textContent = "";

      statusDiv.style.color = "#9ca3af";
      statusDiv.textContent = "No active session.";

      if (timerInterval) clearInterval(timerInterval);
      applyPlanUI();
    }
  }

  function startCountdown(startTime, plannedDuration, sessionId, isGuest) {
    if (timerInterval) clearInterval(timerInterval);

    function updateTimer() {
      const elapsedMs = Date.now() - new Date(startTime).getTime();
      const remainingMs = plannedDuration * 60 * 1000 - elapsedMs;
      const remainingMin = Math.max(Math.floor(remainingMs / 60000), 0);
      const remainingSec = Math.max(
        Math.floor((remainingMs % 60000) / 1000),
        0
      );

      statusDiv.style.color = "#e5e7eb";
      
      if (remainingMs <= 0) {
        // Timer reached 0 - don't auto-end here
        // The blocker.js timer will send BLOCK_FINISHED notification
        // and user can choose to end or extend
        statusDiv.textContent = "Deepmode on – Time's up! Check notifications.";
        clearInterval(timerInterval);
        // DISABLED: autoEndSession(sessionId, isGuest);
        // Blocker.js handles notifications and user choice now
      } else {
        statusDiv.textContent =
          `Deepmode on – ${remainingMin}m ${remainingSec}s left`;
      }
    }

    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);
  }

  // ---------- Blocklist UI helpers ----------

  function renderDefaultSitePills() {
    if (!defaultSitesRow) return;
    defaultSitesRow.innerHTML = "";

    const flags = blockPrefs.defaultSiteFlags || {};
    const noFlags = !flags || Object.keys(flags).length === 0;

    DEFAULT_SITES.forEach((site) => {
      const enabled = noFlags ? true : !!flags[site.id];

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "site-pill" + (enabled ? " active" : "");
      btn.dataset.siteId = site.id;

      btn.innerHTML = `
        <span class="icon">${site.icon}</span>
        <span>${site.label}</span>
      `;

      btn.addEventListener("click", () => {
        const current = blockPrefs.defaultSiteFlags[site.id];
        const next = !(current === true); // toggle; default true on first click

        blockPrefs.defaultSiteFlags[site.id] = next;

        chrome.storage.sync.set(
          { [BLOCK_PREFS_KEY]: blockPrefs },
          () => {
            renderDefaultSitePills();
          }
        );
      });

      defaultSitesRow.appendChild(btn);
    });
  }

  function renderCustomSitesTextarea() {
    if (!customSitesTextarea) return;
    customSitesTextarea.value = (blockPrefs.customSites || []).join("\n");
  }

  function setupCustomSitesEvents() {
    if (!customSitesTextarea) return;

    const saveCustomSites = () => {
      const lines = customSitesTextarea.value
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);

      blockPrefs.customSites = lines;
      chrome.storage.sync.set({ [BLOCK_PREFS_KEY]: blockPrefs });
    };

    customSitesTextarea.addEventListener("blur", saveCustomSites);
    customSitesTextarea.addEventListener("change", saveCustomSites);
  }

  // ---------- Reconcile local active session with backend ----------

  async function reconcileActiveWithBackend(localActive) {
    // If no token or guest session → trust local, nothing to check
    if (!accessToken || !localActive || localActive.isGuest) {
      if (localActive && localActive.id) {
        setUIForActiveSession(localActive);
        startCountdown(
          localActive.start_time,
          localActive.planned_duration_minutes,
          localActive.id,
          true
        );
      } else {
        setUIForActiveSession(null);
      }
      return;
    }

    // Signed-in + local session → ask backend what it thinks
    try {
      const res = await fetch(`${API_BASE_URL}/sessions/active`, {
        headers: {
          "Accept": "application/json",
          "Authorization": "Bearer " + accessToken,
        },
      });

      // If token is dead or user not authorised, just drop local session
      if (res.status === 401) {
        console.warn("Deepmode popup: 401 on /sessions/active, clearing local session");
        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          setUIForActiveSession(null);
        });
        return;
      }

      if (!res.ok) {
        console.warn("Deepmode popup: /sessions/active not OK", res.status);
        // Fallback: if backend is down, keep using local state
        setUIForActiveSession(localActive);
        startCountdown(
          localActive.start_time,
          localActive.planned_duration_minutes,
          localActive.id,
          false
        );
        return;
      }

      const serverActive = await res.json();

      // If server says "no active session" → our local one is stale → clear it
      if (!serverActive || !serverActive.id || serverActive.end_time) {
        console.log("Deepmode popup: server has no active session, clearing local");
        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          setUIForActiveSession(null);
        });
        return;
      }

      // If IDs differ → local belongs to an older / abandoned session → clear local
      if (serverActive.id !== localActive.id) {
        console.log(
          "Deepmode popup: local session stale (id mismatch), clearing local"
        );
        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          setUIForActiveSession(null);
        });
        return;
      }

      // At this point serverActive is THE truth: still running
      const merged = { ...serverActive, isGuest: false };

      chrome.storage.local.set(
        { [STORAGE_KEYS.ACTIVE_SESSION]: merged },
        () => {
          setUIForActiveSession(merged);
          startCountdown(
            merged.start_time,
            merged.planned_duration_minutes,
            merged.id,
            false
          );
        }
      );
    } catch (err) {
      console.error("Deepmode popup: error hitting /sessions/active", err);
      // Network error → fall back to trusting local
      setUIForActiveSession(localActive);
      startCountdown(
        localActive.start_time,
        localActive.planned_duration_minutes,
        localActive.id,
        false
      );
    }
  }

	// ---------- AUTO END ----------

	async function autoEndSession(sessionId, isGuest) {
	  statusDiv.textContent = "Time’s up. Ending your block…";

	  // GUEST MODE / NO TOKEN
	  if (isGuest || !accessToken) {
		chrome.storage.local.get([STORAGE_KEYS.ACTIVE_SESSION], (result) => {
		  const active = result[STORAGE_KEYS.ACTIVE_SESSION];
		  if (!active || active.id !== sessionId) {
			setUIForActiveSession(null);
			return;
		  }

		  const start = new Date(active.start_time);
		  const now = new Date();
		  const mins = Math.max(1, Math.floor((now - start) / 60000));

		  const taskLabel = active.task
			? `“${active.task}”`
			: "this Deepmode block";

		  // Make popup clearly show "block complete"
		  statusDiv.style.color = "#22c55e";
		  statusDiv.textContent =
			`Block complete — you stayed in Deepmode for ~${mins} min on ${taskLabel}.`;

		  // Clear local session state
		  chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
			setUIForActiveSession(null);
		  });
		});
		return;
	  }

	  // SIGNED-IN MODE
	  try {
		const response = await fetch(
		  `${API_BASE_URL}/sessions/${sessionId}/end`,
		  {
			method: "PATCH",
			headers: {
			  "Content-Type": "application/json",
			  Authorization: "Bearer " + accessToken,
			},
		  }
		);

		if (!response.ok) {
		  console.error("Auto end failed", response.status);
		  statusDiv.style.color = "#e50914";
		  statusDiv.textContent =
			"Couldn’t auto-end your session on the server, but your block is finished.";
		} else {
		  const data = await response.json();

		  const mins = data.actual_duration_minutes ?? 0;
		  const label = data.task
			? `“${data.task}”`
			: "your Deepmode block";

		  statusDiv.style.color = "#22c55e";
		  statusDiv.textContent =
			`Block complete — logged ~${mins} min on ${label}.`;
		}
	  } catch (err) {
		console.error(err);
		statusDiv.style.color = "#e50914";
		statusDiv.textContent =
		  "Network issue while ending session — your block is done locally.";
	  } finally {
		// Clear local active session for both success/error cases
		chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
		  setUIForActiveSession(null);
		});
	  }
	}


  // ---------- PLAN / LIMIT ERROR HANDLER ----------

  async function handleSessionStartLimitError(response) {
    let payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      payload = {};
    }

    let detail = payload.detail;
    let message = null;

    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object") {
      message = detail.message || detail.detail || null;
    }

    if (!message) {
      message =
        "Free limit reached. Pro unlocks longer and unlimited blocks.";
    }

    statusDiv.style.color = "#e50914";
    statusDiv.textContent = message;

    applyPlanUI();
  }

  // ---------- SIGNED-IN START (backend first, then priming) ----------

  async function startSignedInBlock(task, category, duration) {
    statusDiv.style.color = "#e5e7eb";
    statusDiv.textContent = "Checking your plan…";

    try {
      const response = await fetch(`${API_BASE_URL}/sessions/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + accessToken,
        },
        body: JSON.stringify({
          task,
          category,
          planned_duration_minutes: duration,
        }),
      });

      if (response.status === 403 || response.status === 429) {
        await handleSessionStartLimitError(response);
        return; // no countdown if blocked
      }

      if (!response.ok) {
        console.error("Failed to start session", response.status);
        statusDiv.style.color = "#e50914";
        statusDiv.textContent =
          "Couldn’t start your session on the server.";
        return; // no countdown
      }

      const data = await response.json();
      const active = { ...data, isGuest: false };

      // Save as active session so background + blocker can see it
      chrome.storage.local.set(
        { [STORAGE_KEYS.ACTIVE_SESSION]: active },
        () => {
          // Only now do we show the priming,
          // using the already-created server session.
          beginPrimingCountdown({ serverSession: active });
        }
      );
    } catch (err) {
      console.error(err);
      statusDiv.style.color = "#e50914";
      statusDiv.textContent =
        "Backend unreachable.";
    }
  }

  // ---------- PRIMING COUNTDOWN ----------

  function beginPrimingCountdown(config) {
    // config can be:
    // - { task, category, duration } for guest mode
    // - { serverSession } for signed-in mode
    pendingSessionConfig = config || {};

    if (!primingOverlay || !primingCountdownEl) {
      // Failsafe: if overlay missing
      if (pendingSessionConfig && pendingSessionConfig.serverSession) {
        const s = pendingSessionConfig.serverSession;
        pendingSessionConfig = null;
        setUIForActiveSession({ ...s, isGuest: false });
        startCountdown(
          s.start_time,
          s.planned_duration_minutes,
          s.id,
          false
        );
      } else {
        actuallyStartSession();
      }
      return;
    }

    // Reset classes/state
    primingOverlay.classList.remove("fade-out");
    primingOverlay.classList.add("visible");
    primingOverlay.style.display = "flex";

    let remaining = 5;
    primingCountdownEl.textContent = remaining.toString();

    if (primingTimerId) {
      clearInterval(primingTimerId);
      primingTimerId = null;
    }

    primingTimerId = setInterval(() => {
      remaining -= 1;

      if (remaining <= 0) {
        clearInterval(primingTimerId);
        primingTimerId = null;

        // Fade out, then either attach to serverSession (signed-in) or start guest
        primingOverlay.classList.remove("visible");
        primingOverlay.classList.add("fade-out");

        setTimeout(() => {
          primingOverlay.style.display = "none";
          primingOverlay.classList.remove("fade-out");

          if (pendingSessionConfig && pendingSessionConfig.serverSession) {
            const s = pendingSessionConfig.serverSession;
            pendingSessionConfig = null;

            setUIForActiveSession({ ...s, isGuest: false });
            startCountdown(
              s.start_time,
              s.planned_duration_minutes,
              s.id,
              false
            );
          } else {
            actuallyStartSession();
          }
        }, 320); // match primingFadeOut duration
      } else {
        primingCountdownEl.textContent = remaining.toString();
      }
    }, 1000);
  }

  // ---------- ACTUAL START SESSION LOGIC (mainly guest) ----------

  function actuallyStartSession() {
    const cfg = pendingSessionConfig || {};

    const task = (cfg.task ?? taskInput.value).trim();
    const category = cfg.category ?? categorySelect.value;
    const duration = cfg.duration ?? parseInt(durationSelect.value, 10);

    pendingSessionConfig = null;

    if (!task) {
      statusDiv.style.color = "#e5e7eb";
      statusDiv.textContent = "Name your block.";
      return;
    }

    const isGuest = !accessToken;

    statusDiv.style.color = "#e5e7eb";
    statusDiv.textContent = isGuest
      ? "Guest Deepmode starting…"
      : "Spinning up your Deepmode block…";

    if (isGuest) {
      const nowIso = new Date().toISOString();
      const guestSession = {
        id: `guest-${Date.now()}`,
        user_id: null,
        task,
        category,
        planned_duration_minutes: duration,
        start_time: nowIso,
        end_time: null,
        actual_duration_minutes: null,
        discipline_score: null,
        isGuest: true,
      };

      chrome.storage.local.set(
        { [STORAGE_KEYS.ACTIVE_SESSION]: guestSession },
        () => {
          setUIForActiveSession(guestSession);
          startCountdown(
            guestSession.start_time,
            guestSession.planned_duration_minutes,
            guestSession.id,
            true
          );
          taskInput.value = "";
        }
      );
      return;
    }

    // Defensive fallback: if we somehow land here signed-in,
    // we do the old behaviour (backend POST), but normal path uses startSignedInBlock.
    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/sessions/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer " + accessToken,
          },
          body: JSON.stringify({
            task,
            category,
            planned_duration_minutes: duration,
          }),
        });

        if (response.status === 403 || response.status === 429) {
          await handleSessionStartLimitError(response);
          return;
        }

        if (!response.ok) {
          console.error("Failed to start session", response.status);
          statusDiv.style.color = "#e50914";
          statusDiv.textContent =
            "Couldn’t start your session on the server.";
          return;
        }

        const data = await response.json();
        const active = { ...data, isGuest: false };

        chrome.storage.local.set(
          { [STORAGE_KEYS.ACTIVE_SESSION]: active },
          () => {
            setUIForActiveSession(active);
            startCountdown(
              active.start_time,
              active.planned_duration_minutes,
              active.id,
              false
            );
            taskInput.value = "";
          }
        );
      } catch (err) {
        console.error(err);
        statusDiv.style.color = "#e50914";
        statusDiv.textContent =
          "Backend unreachable.";
      }
    })();
  }

  // ---------- START BUTTON ----------

  startBtn.addEventListener("click", () => {
    // If UI already in "active" state, ignore start clicks
    if (endBtn.disabled === false) {
      return;
    }

    const task = taskInput.value.trim();
    const category = categorySelect.value;
    const duration = parseInt(durationSelect.value, 10);

    if (!task) {
      statusDiv.style.color = "#e5e7eb";
      statusDiv.textContent = "Name your block.";
      return;
    }

    // Guest mode: keep behaviour (priming → local session)
    if (!accessToken) {
      const config = { task, category, duration };
      beginPrimingCountdown(config);
      return;
    }

    // Signed-in: check backend first (limits / Pro),
    // only show priming if server created the session.
    startSignedInBlock(task, category, duration);
  });

  // ---------- END BUTTON ----------

  endBtn.addEventListener("click", () => {
    chrome.storage.local.get([STORAGE_KEYS.ACTIVE_SESSION], (result) => {
      const active = result[STORAGE_KEYS.ACTIVE_SESSION];

      if (!active || !active.id) {
        statusDiv.style.color = "#e5e7eb";
        statusDiv.textContent = "No active session to end.";
        return;
      }

      if (timerInterval) clearInterval(timerInterval);
      statusDiv.style.color = "#e5e7eb";
      statusDiv.textContent = "Ending your block…";

      const isGuest = !!active.isGuest || !accessToken;

      if (isGuest) {
        const start = new Date(active.start_time);
        const now = new Date();
        const mins = Math.max(1, Math.floor((now - start) / 60000));

        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          setUIForActiveSession(null);
          statusDiv.style.color = "#22c55e";
          statusDiv.textContent =
            `Session ended. ~${mins} min focused.`;
        });
        return;
      }

      (async () => {
        try {
          const response = await fetch(
            `${API_BASE_URL}/sessions/${active.id}/end`,
            {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json",
                Authorization: "Bearer " + accessToken,
              }
            }
          );

          if (!response.ok) {
            console.error("Failed to end session", response.status);
            statusDiv.style.color = "#e50914";
            statusDiv.textContent =
              "Server error while ending session.";
          } else {
            const data = await response.json();
            statusDiv.style.color = "#22c55e";
            statusDiv.textContent =
              `Session ended. Logged ~${data.actual_duration_minutes} min.`;
          }
        } catch (err) {
          console.error(err);
          statusDiv.style.color = "#e50914";
          statusDiv.textContent =
            "Network error; block treated as done.";
        } finally {
          chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
            setUIForActiveSession(null);
          });
        }
      })();
    });
  });

  // ---------- Open dashboard from popup ----------

  if (dashboardLink) {
    dashboardLink.addEventListener("click", () => {
      chrome.tabs.create({ url: DASHBOARD_URL });
    });
  }

  // ---------- Upgrade button click → pricing ----------

  if (upgradeBtn) {
    upgradeBtn.addEventListener("click", () => {
      try {
        chrome.tabs.create({ url: `${API_BASE_URL}/pricing` });
      } catch (e) {
        console.warn("Deepmode: failed to open pricing tab", e);
      }
    });
  }

  // ---------- Init on popup open ----------

  chrome.storage.local.get(
    [STORAGE_KEYS.ACTIVE_SESSION, STORAGE_KEYS.ACCESS_TOKEN],
    async (result) => {
      accessToken = result[STORAGE_KEYS.ACCESS_TOKEN] || null;
      updateAuthState();
      await fetchMeAndApplyPlan();

      const active = result[STORAGE_KEYS.ACTIVE_SESSION];

      // Always reconcile with backend if we are signed in
      await reconcileActiveWithBackend(active);
    }
  );

  // Load block prefs from sync
  chrome.storage.sync.get(BLOCK_PREFS_KEY, (res) => {
    const prefs = res[BLOCK_PREFS_KEY];
    if (prefs && typeof prefs === "object") {
      blockPrefs.defaultSiteFlags = prefs.defaultSiteFlags || {};
      blockPrefs.customSites = Array.isArray(prefs.customSites)
        ? prefs.customSites
        : [];
    }
    renderDefaultSitePills();
    renderCustomSitesTextarea();
    setupCustomSitesEvents();
  });

  // ---------- React immediately to logout (from connect.js) ----------

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg && msg.type === "DEEPMODE_LOGOUT") {
      console.log("Deepmode popup: received DEEPMODE_LOGOUT");

      // 1) Kill timers immediately
      if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
      }
      if (primingTimerId) {
        clearInterval(primingTimerId);
        primingTimerId = null;
      }
      if (primingOverlay) {
        primingOverlay.style.display = "none";
        primingOverlay.classList.remove("visible", "fade-out");
      }

      // 2) Wipe BOTH token + active session from extension storage
      chrome.storage.local.remove(
        [STORAGE_KEYS.ACTIVE_SESSION, STORAGE_KEYS.ACCESS_TOKEN],
        () => {
          accessToken = null;
          isProUser = false;
          updateAuthState();
          applyPlanUI();
          setUIForActiveSession(null);

          statusDiv.style.color = "#9ca3af";
          statusDiv.textContent =
            "Logged out.";
        }
      );
    }
  });

  // ---------- React to storage changes as backup ----------

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;

    if (changes[STORAGE_KEYS.ACCESS_TOKEN]) {
      const newToken = changes[STORAGE_KEYS.ACCESS_TOKEN].newValue || null;
      accessToken = newToken;
      updateAuthState();

      // If token was removed → force-clear session + timer
      if (!newToken) {
        isProUser = false;
        if (timerInterval) clearInterval(timerInterval);
        if (primingTimerId) clearInterval(primingTimerId);
        if (primingOverlay) {
          primingOverlay.style.display = "none";
          primingOverlay.classList.remove("visible", "fade-out");
        }

        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          setUIForActiveSession(null);
        });
        applyPlanUI();
        return;
      }

      // If we just got a token, fetch plan + reconcile sessions
      (async () => {
        await fetchMeAndApplyPlan();

        chrome.storage.local.get(
          STORAGE_KEYS.ACTIVE_SESSION,
          async (res) => {
            const localActive = res[STORAGE_KEYS.ACTIVE_SESSION];
            if (localActive && localActive.id && !localActive.isGuest) {
              await reconcileActiveWithBackend(localActive);
            }
          }
        );
      })();
    }

    if (changes[STORAGE_KEYS.ACTIVE_SESSION]) {
      const newActive = changes[STORAGE_KEYS.ACTIVE_SESSION].newValue || null;

      if (!newActive && timerInterval) {
        clearInterval(timerInterval);
      }

      setUIForActiveSession(newActive);
    }
  });
});
