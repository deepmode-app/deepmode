// popup.js

// Backend used ONLY when we have a JWT token (signed-in mode)
const API_BASE_URL = "http://127.0.0.1:8000";
const DASHBOARD_URL = `${API_BASE_URL}/dashboard`;

// Where we keep things in extension storage
const STORAGE_KEYS = {
  ACTIVE_SESSION: "deepmode_active_session",
  ACCESS_TOKEN: "deepmode_access_token",   // extension-side copy of JWT
};

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
  const authStateDiv = document.getElementById("authState"); // 👈 tiny line

  let timerInterval = null;
  let accessToken = null; // will be filled from chrome.storage

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
      currentCategoryDiv.textContent = `Category: ${active.category}`;

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
      statusDiv.textContent = "No active session. Name your next block and hit start.";
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
      statusDiv.textContent = `Deepmode on – ${remainingMin}m ${remainingSec}s left`;

      if (remainingMs <= 0) {
        clearInterval(timerInterval);
        autoEndSession(sessionId, isGuest);
      }
    }

    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);
  }

  // ---------- AUTO END ----------

  async function autoEndSession(sessionId, isGuest) {
    statusDiv.textContent = "Time’s up. Ending your block…";

    if (isGuest || !accessToken) {
      // Guest mode: just clear active session and let the user feel the win
      chrome.storage.local.get([STORAGE_KEYS.ACTIVE_SESSION], (result) => {
        const active = result[STORAGE_KEYS.ACTIVE_SESSION];
        if (!active || active.id !== sessionId) {
          setUIForActiveSession(null);
          return;
        }

        const start = new Date(active.start_time);
        const now = new Date();
        const mins = Math.max(
          1,
          Math.floor((now - start) / 60000)
        );

        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          setUIForActiveSession(null);
          statusDiv.style.color = "#22c55e";
          statusDiv.textContent = `Block finished. You stayed in Deepmode for ~${mins} min.`;
        });
      });
      return;
    }

    // Signed-in: hit backend
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
        statusDiv.textContent = `Session finished. Logged ~${data.actual_duration_minutes} min.`;
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

    // Decide mode
    const isGuest = !accessToken;

    statusDiv.style.color = "#e5e7eb";
    statusDiv.textContent = isGuest
      ? "Guest Deepmode starting… (this one won’t hit your dashboard yet)."
      : "Spinning up your Deepmode block…";

    if (isGuest) {
      // ---------- Guest mode: purely local ----------
      const nowIso = new Date().toISOString();
      const guestSession = {
        id: `guest-${Date.now()}`, // local-only ID
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

    // ---------- Signed-in mode: talk to backend ----------
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

        const active = {
          ...data,
          isGuest: false,
        };

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
        const mins = Math.max(
          1,
          Math.floor((now - start) / 60000)
        );

        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          setUIForActiveSession(null);
          statusDiv.style.color = "#22c55e";
          statusDiv.textContent = `Session ended. You stayed in Deepmode for ~${mins} min.`;
        });
        return;
      }

      // Signed-in → call backend
      (async () => {
        try {
          const response = await fetch(
            `${API_BASE_URL}/sessions/${active.id}/end`,
            {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json",
                Authorization: "Bearer " + accessToken,
              },
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
            statusDiv.textContent = `Session ended. Logged ~${data.actual_duration_minutes} min.`;
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
    (result) => {
      accessToken = result[STORAGE_KEYS.ACCESS_TOKEN] || null;

      // reflect current mode in tiny line
      updateAuthState();

      const active = result[STORAGE_KEYS.ACTIVE_SESSION];
      setUIForActiveSession(active);

      if (active && active.id && active.start_time && active.planned_duration_minutes) {
        const isGuest = !!active.isGuest || !accessToken;
        startCountdown(
          active.start_time,
          active.planned_duration_minutes,
          active.id,
          isGuest
        );
      }
    }
  );
});
