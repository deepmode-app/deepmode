const API_BASE_URL = "https://95e81190-332d-4b5b-a875-0a3ed330e756-00-1kk0ba0t7ygdw.janeway.replit.dev";
const DASHBOARD_URL = `${API_BASE_URL}/dashboard`;

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

  let timerInterval = null;

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
    } else {
      startBtn.disabled = false;
      endBtn.disabled = true;
      taskInput.disabled = false;
      categorySelect.disabled = false;
      durationSelect.disabled = false;

      currentSessionBox.style.display = "none";
      currentTaskDiv.textContent = "";
      currentCategoryDiv.textContent = "";

      statusDiv.textContent = "No active session.";
      if (timerInterval) clearInterval(timerInterval);
    }
  }

  function startCountdown(startTime, plannedDuration, sessionId) {
    if (timerInterval) clearInterval(timerInterval);

    function updateTimer() {
      const elapsedMs = Date.now() - new Date(startTime).getTime();
      const remainingMs = plannedDuration * 60 * 1000 - elapsedMs;
      const remainingMin = Math.max(Math.floor(remainingMs / 60000), 0);
      const remainingSec = Math.max(Math.floor((remainingMs % 60000) / 1000), 0);

      statusDiv.textContent = `Deepwork active – time left: ${remainingMin}m ${remainingSec}s`;

      if (remainingMs <= 0) {
        clearInterval(timerInterval);
        autoEndSession(sessionId);
      }
    }

    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);
  }

  async function autoEndSession(sessionId) {
    statusDiv.textContent = "Session complete! Ending automatically...";
    try {
      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/end`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" }
      });
      const data = await response.json();
      console.log("Auto-ended:", data);
      chrome.storage.local.remove("deepwork_active_session", () => {
        setUIForActiveSession(null);
        statusDiv.textContent = `Session finished! Duration: ${data.actual_duration_minutes} min`;
      });
    } catch (err) {
      console.error(err);
      statusDiv.textContent = "Error auto-ending session.";
    }
  }


  // ---------- START ----------
  startBtn.addEventListener("click", async () => {
    const task = taskInput.value.trim();
    const category = categorySelect.value;
    const duration = parseInt(durationSelect.value, 10);

    if (!task) {
      statusDiv.textContent = "Please enter a task.";
      statusDiv.style.color = "#e5e7eb";
      return;
    }

    statusDiv.textContent = "Starting session...";
    statusDiv.style.color = "#e5e7eb";

    try {
      const response = await fetch(`${API_BASE_URL}/sessions/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: task,
          category: category,
          planned_duration_minutes: duration
        })
      });

      // --- FREE TIER LIMIT HANDLING ---
      if (response.status === 429) {
        const data = await response.json();
        statusDiv.textContent = data.detail || "Daily free limit reached.";
        statusDiv.style.color = "#e50914"; // red accent
        return;
      }

      if (!response.ok) {
        statusDiv.textContent = "Error starting session.";
        statusDiv.style.color = "#e50914";
        return;
      }

      const data = await response.json();
      console.log("Deepwork response:", data);

      const active = {
        id: data.id,
        task: data.task,
        category: data.category,
        start_time: data.start_time,
        planned_duration_minutes: data.planned_duration_minutes
      };

      chrome.storage.local.set({ deepwork_active_session: active }, () => {
        setUIForActiveSession(active);
        startCountdown(
          active.start_time,
          active.planned_duration_minutes,
          active.id
        );
        taskInput.value = "";
      });
    } catch (err) {
      console.error(err);
      statusDiv.textContent = "Failed to reach backend.";
      statusDiv.style.color = "#e50914";
    }
  });


  // ---------- END ----------
  endBtn.addEventListener("click", async () => {
    chrome.storage.local.get(["deepwork_active_session"], async (result) => {
      const active = result.deepwork_active_session;
      if (!active || !active.id) {
        statusDiv.textContent = "No active session found.";
        return;
      }

      statusDiv.textContent = "Ending session...";
      if (timerInterval) clearInterval(timerInterval);

      try {
        const response = await fetch(`${API_BASE_URL}/sessions/${active.id}/end`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" }
        });
        const data = await response.json();
        console.log("Session ended:", data);
        chrome.storage.local.remove("deepwork_active_session", () => {
          setUIForActiveSession(null);
          statusDiv.textContent = `Session ended. Duration: ${data.actual_duration_minutes} min`;
        });
      } catch (err) {
        console.error(err);
        statusDiv.textContent = "Failed to end session.";
      }
    });
  });

  // ---------- OPEN DASHBOARD ----------
  if (dashboardLink) {
    dashboardLink.addEventListener("click", () => {
      chrome.tabs.create({ url: DASHBOARD_URL });
    });
  } else {
    console.warn("dashboardLink element not found in popup.");
  }

  // ---------- INIT ON POPUP OPEN ----------
  chrome.storage.local.get(["deepwork_active_session"], (result) => {
    const active = result.deepwork_active_session;
    setUIForActiveSession(active);
    if (active && active.id) {
      startCountdown(active.start_time, active.planned_duration_minutes, active.id);
    }
  });
});
