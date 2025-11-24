// popup.js

// Backend used ONLY when we have a JWT token (signed-in mode)
const API_BASE_URL = "http://127.0.0.1:8000";
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

  const defaultSitesRow = document.getElementById("defaultSitesRow");
  const customSitesTextarea = document.getElementById("customSites");

  let timerInterval = null;
  let accessToken = null;
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
        "👤 Signed in – your focus goes to your dashboard.";
    } else {
      authStateDiv.textContent =
        "🕶 Guest mode – this block lives only on this device.";
    }
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
        ? "Deepmode guest session running. This one stays on this device."
        : "Deepmode session running. Stats will land in your dashboard.";
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
      statusDiv.textContent =
        "No active session. Name your next block and hit start.";
      if (timerInterval) clearInterval(timerInterval);
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
      statusDiv.textContent =
        `Deepmode on – ${remainingMin}m ${remainingSec}s left`;

      if (remainingMs <= 0) {
        clearInterval(timerInterval);
        autoEndSession(sessionId, isGuest);
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

        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          setUIForActiveSession(null);
          statusDiv.style.color = "#22c55e";
          statusDiv.textContent =
            `Block finished. You stayed in Deepmode for ~${mins} min.`;
        });
      });
      return;
    }

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
          "Couldn’t auto-end session on the server, but your block is done.";
      } else {
        const data = await response.json();
        statusDiv.style.color = "#22c55e";
        statusDiv.textContent =
          `Session finished. Logged ~${data.actual_duration_minutes} min.`;
      }
    } catch (err) {
      console.error(err);
      statusDiv.style.color = "#e50914";
      statusDiv.textContent = "Network issue while ending session.";
    } finally {
      chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
        setUIForActiveSession(null);
      });
    }
  }

  // ---------- START BUTTON ----------

  startBtn.addEventListener("click", () => {
    const task = taskInput.value.trim();
    const category = categorySelect.value;
    const duration = parseInt(durationSelect.value, 10);

    if (!task) {
      statusDiv.style.color = "#e5e7eb";
      statusDiv.textContent =
        "Name your block. If you can’t name it, you’re not really doing it.";
      return;
    }

    const isGuest = !accessToken;

    statusDiv.style.color = "#e5e7eb";
    statusDiv.textContent = isGuest
      ? "Guest Deepmode starting… (this one won’t hit your dashboard yet)."
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
          const data = await response.json().catch(() => ({}));
          statusDiv.style.color = "#e50914";
          statusDiv.textContent =
            data.detail ||
            "Today’s free limit is done. Deepmode Pro unlocks unlimited sessions.";
          return;
        }

        if (!response.ok) {
          console.error("Failed to start session", response.status);
          statusDiv.style.color = "#e50914";
          statusDiv.textContent =
            "Couldn’t start your session on the server. Try again.";
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
          "Backend unreachable. The good news? Distractions still count as distractions.";
      }
    })();
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
            `Session ended. You stayed in Deepmode for ~${mins} min.`;
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
              "Server error while ending session, but your block is finished.";
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
            "Network error; we’ll treat the block as done locally.";
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

  // ---------- Init on popup open ----------

  chrome.storage.local.get(
    [STORAGE_KEYS.ACTIVE_SESSION, STORAGE_KEYS.ACCESS_TOKEN],
    async (result) => {
      accessToken = result[STORAGE_KEYS.ACCESS_TOKEN] || null;
      updateAuthState();

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

		// 1) Kill timer immediately
		if (timerInterval) {
		  clearInterval(timerInterval);
		  timerInterval = null;
		}

		// 2) Wipe BOTH token + active session from extension storage
		chrome.storage.local.remove(
		  [STORAGE_KEYS.ACTIVE_SESSION, STORAGE_KEYS.ACCESS_TOKEN],
		  () => {
			accessToken = null;
			updateAuthState();
			setUIForActiveSession(null);

			statusDiv.style.color = "#9ca3af";
			statusDiv.textContent =
			  "Logged out — start a new Deepmode block anytime.";
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
        if (timerInterval) clearInterval(timerInterval);
        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          setUIForActiveSession(null);
        });
        return;
      }

      // If we just got a token and we have a local active session,
      // double-check with backend now.
      chrome.storage.local.get(
        STORAGE_KEYS.ACTIVE_SESSION,
        async (res) => {
          const localActive = res[STORAGE_KEYS.ACTIVE_SESSION];
          if (localActive && localActive.id && !localActive.isGuest) {
            await reconcileActiveWithBackend(localActive);
          }
        }
      );
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
