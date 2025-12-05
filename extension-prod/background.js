// background.js – Deepmode service worker
// Responsibilities:
// 1) Auto-ending Deepmode sessions at the planned end time (via chrome.alarms)
// 2) Blocking distraction sites by injecting blocker.js while a Deepmode session is active
// 3) Handling timer notifications and extend/end actions

// ---------- CONSTANTS ----------

const STORAGE_KEYS = {
  ACTIVE_SESSION: "deepmode_active_session",
  ACCESS_TOKEN: "deepmode_access_token",
};

const BLOCK_PREFS_KEY = "deepmode_block_prefs";

const SESSION_ALARM_PREFIX = "deepmode_session_";
const BADGE_UPDATE_ALARM_PREFIX = "deepmode_badge_";
const WARNING_5MIN_ALARM_PREFIX = "deepmode_warn5min_";

// Keep in sync with backend URL and popup.js
const API_BASE_URL = "https://deepmode.app";


// Must stay in sync with DEFAULT_SITES from popup.js
const DEFAULT_SITES = [
  { id: "youtube",   host: "youtube.com"   },
  { id: "twitter",   host: "twitter.com"   },
  { id: "instagram", host: "instagram.com" },
  { id: "facebook",  host: "facebook.com"  },
  { id: "reddit",    host: "reddit.com"    },
  { id: "tiktok",    host: "tiktok.com"    },
];

// ---------- IN-MEMORY STATE ----------

let activeSession = null;
let blockPrefs = {
  defaultSiteFlags: {},
  customSites: [],
};

// ---------- ALARM HELPERS ----------

function sessionAlarmName(sessionId) {
  return `${SESSION_ALARM_PREFIX}${sessionId}`;
}

function scheduleSessionAlarm(session) {
  if (
    !session ||
    !session.id ||
    !session.start_time ||
    !session.planned_duration_minutes
  ) {
    return;
  }

  const name = sessionAlarmName(session.id);

  const startMs = new Date(session.start_time).getTime();
  const durationMs = session.planned_duration_minutes * 60 * 1000;
  const targetTime = startMs + durationMs;

  let delayMs = targetTime - Date.now();

  if (delayMs < 5_000) {
    delayMs = 5_000;
  }

  // Main alarm for auto-end
  chrome.alarms.create(name, { when: Date.now() + delayMs });

  // 5-minute warning alarm (only for blocks > 5 minutes)
  if (session.planned_duration_minutes > 5) {
    const warningTime = targetTime - (5 * 60 * 1000); // 5 minutes before end
    const warningDelayMs = warningTime - Date.now();
    if (warningDelayMs > 1000) { // Only schedule if more than 1 second away
      const warningName = `${WARNING_5MIN_ALARM_PREFIX}${session.id}`;
      chrome.alarms.create(warningName, { when: Date.now() + warningDelayMs });
      console.log("[Deepmode BG] 5-minute warning alarm created, fires in", Math.round(warningDelayMs / 1000), "seconds");
    }
  }

  // Badge update alarm (every 60 seconds)
  const badgeName = `${BADGE_UPDATE_ALARM_PREFIX}${session.id}`;
  chrome.alarms.create(badgeName, { periodInMinutes: 1 });
  
  // Initial badge update
  updateBadgeFromSession(session);

  console.log(
    "[Deepmode BG] Alarm created:",
    name,
    "fires in",
    Math.round(delayMs / 1000),
    "seconds"
  );
}

function clearSessionAlarm(sessionId) {
  if (!sessionId) return;
  const name = sessionAlarmName(sessionId);
  const warningName = `${WARNING_5MIN_ALARM_PREFIX}${sessionId}`;
  const badgeName = `${BADGE_UPDATE_ALARM_PREFIX}${sessionId}`;
  
  chrome.alarms.clear(name);
  chrome.alarms.clear(warningName);
  chrome.alarms.clear(badgeName);
  
  console.log("[Deepmode BG] All alarms cleared for session:", sessionId);
}

function updateBadgeFromSession(session) {
  if (!session || !session.start_time || !session.planned_duration_minutes) {
    chrome.action.setBadgeText({ text: "" });
    return;
  }

  const startMs = new Date(session.start_time).getTime();
  const durationMs = session.planned_duration_minutes * 60 * 1000;
  const targetTime = startMs + durationMs;
  const remainingMs = targetTime - Date.now();
  const remainingSeconds = Math.max(0, Math.floor(remainingMs / 1000));
  
  // Show "1" when there's less than a minute but more than 0 seconds
  // Use Math.ceil to round up (59 seconds = 1 minute, 1 second = 1 minute)
  const minutesLeft = remainingSeconds > 0 ? Math.ceil(remainingSeconds / 60) : 0;

  if (minutesLeft > 0) {
    chrome.action.setBadgeText({ text: minutesLeft.toString() });
    
    // Color code: green >10min, orange 3-10min, red <3min
    let badgeColor = "#22c55e"; // green
    if (minutesLeft <= 10) {
      badgeColor = "#ffb84d"; // orange
    }
    if (minutesLeft <= 3) {
      badgeColor = "#e50914"; // red
    }
    chrome.action.setBadgeBackgroundColor({ color: badgeColor });
  } else {
    chrome.action.setBadgeText({ text: "0" });
    chrome.action.setBadgeBackgroundColor({ color: "#e50914" }); // red
  }
}

// ---------- STARTUP RESYNC ----------

function resyncOnStartup() {
  chrome.storage.local.get(
    [STORAGE_KEYS.ACTIVE_SESSION],
    (res) => {
      const active = res[STORAGE_KEYS.ACTIVE_SESSION];
      if (active && active.id) {
        activeSession = active;
        console.log(
          "[Deepmode BG] Resync: found active session on startup:",
          active.id
        );
        scheduleSessionAlarm(active);
        updateBadgeFromSession(active);
        updateBadgeFromSession(active);
      } else {
        activeSession = null;
        chrome.action.setBadgeText({ text: "" });
        console.log("[Deepmode BG] Resync: no active session on startup.");
      }
    }
  );

  chrome.storage.sync.get(BLOCK_PREFS_KEY, (res) => {
    const prefs = res[BLOCK_PREFS_KEY];
    if (prefs && typeof prefs === "object") {
      blockPrefs.defaultSiteFlags = prefs.defaultSiteFlags || {};
      blockPrefs.customSites = Array.isArray(prefs.customSites)
        ? prefs.customSites
        : [];
      console.log("[Deepmode BG] Resync: block prefs loaded.");
    }
  });
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("[Deepmode BG] onInstalled");
  resyncOnStartup();
});

chrome.runtime.onStartup.addListener(() => {
  console.log("[Deepmode BG] onStartup");
  resyncOnStartup();
});

// ---------- NOTIFICATION HANDLERS ----------

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // Note: 5-minute warning and BLOCK_FINISHED notifications are now handled by alarms, not messages
  // Note: Badge updates are now handled by alarms (updateBadgeFromSession), not messages

  // Handle DEEPMODE_LOGOUT (from connect.js when user logs out from dashboard)
  if (msg.type === "DEEPMODE_LOGOUT") {
    console.log("[Deepmode BG] DEEPMODE_LOGOUT received - clearing session and badge");
    // Clear any active session alarms
    if (activeSession && activeSession.id) {
      clearSessionAlarm(activeSession.id);
    }
    activeSession = null;
    // Immediately clear badge
    chrome.action.setBadgeText({ text: "" });
    console.log("[Deepmode BG] Badge cleared on logout");
    return;
  }

  // Handle END_SESSION_AT_TIMER_ZERO (from blocker.js when timer hits 0 - backup to alarm)
  if (msg.type === "END_SESSION_AT_TIMER_ZERO") {
    console.log("[Deepmode BG] END_SESSION_AT_TIMER_ZERO received (backup trigger)");
    // Use same handler as END_SESSION
    msg.type = "END_SESSION";
  }

  // Handle END_SESSION (from notification button, blocker.js, or manual end)
  if (msg.type === "END_SESSION") {
    console.log("[Deepmode BG] END_SESSION received - ending session via backend");
    chrome.storage.local.get(
      [STORAGE_KEYS.ACTIVE_SESSION, STORAGE_KEYS.ACCESS_TOKEN],
      async (res) => {
        const active = res[STORAGE_KEYS.ACTIVE_SESSION];
        const accessToken = res[STORAGE_KEYS.ACCESS_TOKEN] || null;

        if (!active || !active.id) {
          console.log("[Deepmode BG] No active session to end");
          return;
        }

        const isGuest = !!active.isGuest || !accessToken;

        if (isGuest) {
          console.log("[Deepmode BG] Ending guest session (local only)");
          chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
            activeSession = null;
            // Clear badge
            chrome.action.setBadgeText({ text: "" });
          });
          return;
        }

        // Send end notification for manual end
        chrome.notifications.create(
          {
            type: "basic",
            iconUrl: "icon.png",
            title: "Deepwork block complete",
            message: "Great work. Take a short break and come back. You're building your future one session at a time.",
            priority: 2
          },
          (notificationId) => {
            if (chrome.runtime.lastError) {
              console.error("[Deepmode BG] ❌ ERROR creating end notification:", chrome.runtime.lastError.message);
            } else {
              console.log("[Deepmode BG] ✅ End notification created:", notificationId);
            }
          }
        );

        try {
          console.log(`[Deepmode BG] Calling backend /sessions/${active.id}/end`);
          const response = await fetch(
            `${API_BASE_URL}/sessions/${active.id}/end`,
            {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + accessToken,
              },
            }
          );
          
          if (response.ok) {
            console.log("[Deepmode BG] ✅ Session ended successfully on backend");
          } else {
            console.error(`[Deepmode BG] Backend returned error: ${response.status}`);
          }
        } catch (err) {
          console.error("[Deepmode BG] Error ending session", err);
        } finally {
          // Always clear local session and badge, even if backend call failed
          chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
            activeSession = null;
            // Clear badge
            chrome.action.setBadgeText({ text: "" });
            console.log("[Deepmode BG] Local session cleared, badge cleared");
          });
        }
      }
    );
    return;
  }

  // Handle end session from blocker (legacy)
  if (msg.type === "END_SESSION_FROM_BLOCKER") {
    // Forward to END_SESSION handler
    chrome.runtime.sendMessage({ type: "END_SESSION" });
    return;
  }
});

// ---------- URL / BLOCKING HELPERS ----------

function getHostnameFromUrl(url) {
  try {
    const u = new URL(url);
    return u.hostname || "";
  } catch {
    return "";
  }
}

function isDefaultSiteBlocked(hostname) {
  if (!hostname) return false;

  const flags = blockPrefs.defaultSiteFlags || {};
  const noFlagsConfigured = !flags || Object.keys(flags).length === 0;

  for (const site of DEFAULT_SITES) {
    const enabled = noFlagsConfigured ? true : !!flags[site.id];
    if (!enabled) continue;

    if (hostname.includes(site.host)) {
      return true;
    }
  }
  return false;
}

function isCustomSiteBlocked(hostname) {
  if (!hostname) return false;
  const custom = blockPrefs.customSites || [];

  for (const entry of custom) {
    const needle = (entry || "").trim().toLowerCase();
    if (!needle) continue;

    if (hostname.toLowerCase().includes(needle)) {
      return true;
    }
  }
  return false;
}

function shouldBlockUrl(url) {
  if (!activeSession || !activeSession.id) return false;

  const hostname = getHostnameFromUrl(url);
  if (!hostname) return false;

  return isDefaultSiteBlocked(hostname) || isCustomSiteBlocked(hostname);
}

function injectBlockerIntoTab(tabId) {
  if (!tabId || tabId < 0) return;

  chrome.scripting.executeScript(
    {
      target: { tabId },
      files: ["blocker.js"],
    },
    () => {
      if (chrome.runtime.lastError) {
        console.warn(
          "[Deepmode BG] Failed to inject blocker.js:",
          chrome.runtime.lastError.message
        );
      } else {
        console.log("[Deepmode BG] blocker.js injected into tab", tabId);
      }
    }
  );
}

function ensureTabBlocked(tab) {
  if (!tab || !tab.id || !tab.url) return;
  if (!shouldBlockUrl(tab.url)) return;

  chrome.tabs.sendMessage(
    tab.id,
    { type: "DEEPMODE_BLOCK" },
    () => {
      const err = chrome.runtime.lastError;
      if (err) {
        injectBlockerIntoTab(tab.id);
      }
    }
  );
}

/**
 * maybeBlockTab – robust version:
 * - If in-memory activeSession is missing (service worker restart),
 *   it reloads from chrome.storage.local and then decides.
 */
function maybeBlockTab(tab) {
  if (!tab || !tab.id || !tab.url) return;

  if (activeSession && activeSession.id) {
    if (shouldBlockUrl(tab.url)) {
      ensureTabBlocked(tab);
    }
    return;
  }

  // Fallback: pull from storage if memory is empty
  chrome.storage.local.get([STORAGE_KEYS.ACTIVE_SESSION], (res) => {
    const stored = res[STORAGE_KEYS.ACTIVE_SESSION];
    if (stored && stored.id) {
      activeSession = stored;
      if (shouldBlockUrl(tab.url)) {
        ensureTabBlocked(tab);
      }
    }
  });
}

// ---------- STORAGE CHANGE HANDLER ----------

chrome.storage.onChanged.addListener((changes, area) => {
  // Local: active session → update in-memory state + alarms + re-evaluate tabs
  if (area === "local" && changes[STORAGE_KEYS.ACTIVE_SESSION]) {
    const { oldValue, newValue } = changes[STORAGE_KEYS.ACTIVE_SESSION];

    if (oldValue && oldValue.id) {
      clearSessionAlarm(oldValue.id);
    }

    activeSession = newValue || null;

    if (newValue && newValue.id) {
      console.log("[Deepmode BG] New active session:", newValue.id);
      scheduleSessionAlarm(newValue);
      // Badge will be updated by blocker.js timer
      
      // Send start notification
      chrome.notifications.create(
        {
          type: "basic",
          iconUrl: "icon.png",
          title: "Deepmode",
          message: "Deepwork session started. Lock in.",
          priority: 1
        },
        (notificationId) => {
          if (chrome.runtime.lastError) {
            console.error("[Deepmode BG] Error creating start notification:", chrome.runtime.lastError.message);
          }
        }
      );
    } else {
      console.log("[Deepmode BG] No active session after change.");
      // Clear badge when session ends
      chrome.action.setBadgeText({ text: "" });
    }

    // 🔁 Immediately re-evaluate ALL open tabs when a session starts/ends
    chrome.tabs.query({}, (tabs) => {
      if (chrome.runtime.lastError || !tabs) return;

      tabs.forEach((tab) => {
        if (!tab || !tab.id || !tab.url) return;

        if (activeSession && activeSession.id) {
          // Session started or switched → block where needed
          if (shouldBlockUrl(tab.url)) {
            ensureTabBlocked(tab);
          } else {
            chrome.tabs.sendMessage(
              tab.id,
              { type: "DEEPMODE_UNBLOCK" },
              () => {
                // ignore missing receiver
              }
            );
          }
        } else {
          // Session ended → unblock everywhere
          chrome.tabs.sendMessage(
            tab.id,
            { type: "DEEPMODE_UNBLOCK" },
            () => {
              // ignore missing receiver
            }
          );
        }
      });
    });
  }

  // Sync: block prefs updated from popup or dashboard
  if (area === "sync" && changes[BLOCK_PREFS_KEY]) {
    const prefs = changes[BLOCK_PREFS_KEY].newValue;
    if (prefs && typeof prefs === "object") {
      blockPrefs.defaultSiteFlags = prefs.defaultSiteFlags || {};
      blockPrefs.customSites = Array.isArray(prefs.customSites)
        ? prefs.customSites
        : [];
      console.log("[Deepmode BG] Block prefs updated from sync.");

      if (activeSession && activeSession.id) {
        chrome.tabs.query({}, (tabs) => {
          if (chrome.runtime.lastError || !tabs) return;

          tabs.forEach((tab) => {
            if (!tab || !tab.id || !tab.url) return;

            const shouldBlock = shouldBlockUrl(tab.url);

            if (shouldBlock) {
              ensureTabBlocked(tab);
            } else {
              chrome.tabs.sendMessage(
                tab.id,
                { type: "DEEPMODE_UNBLOCK" },
                () => {
                  const err = chrome.runtime.lastError;
                  if (err) {
                    // ignore tabs without content script
                  }
                }
              );
            }
          });
        });
      }
    }
  }
});

// ---------- ALARM HANDLER: AUTO END SESSION ----------

chrome.alarms.onAlarm.addListener((alarm) => {
  if (!alarm || !alarm.name) {
    return;
  }

  // Handle 5-minute warning
  if (alarm.name.startsWith(WARNING_5MIN_ALARM_PREFIX)) {
    const sessionIdPart = alarm.name.substring(WARNING_5MIN_ALARM_PREFIX.length);
    chrome.storage.local.get([STORAGE_KEYS.ACTIVE_SESSION], (res) => {
      const active = res[STORAGE_KEYS.ACTIVE_SESSION];
      if (active && String(active.id) === String(sessionIdPart)) {
        const taskLabel = active.task || "Your deep block";
        console.log("[Deepmode BG] 5-minute warning alarm fired for:", taskLabel);
        chrome.notifications.create(
          {
            type: "basic",
            iconUrl: "icon.png",
            title: "5 minutes left",
            message: "Stay with it. Finish this block strong.",
            priority: 1
          },
          (notificationId) => {
            if (chrome.runtime.lastError) {
              console.error("[Deepmode BG] ❌ ERROR creating notification:", chrome.runtime.lastError.message);
            } else {
              console.log("[Deepmode BG] ✅ 5-minute warning notification created");
            }
          }
        );
      }
    });
    return;
  }

  // Handle badge updates
  if (alarm.name.startsWith(BADGE_UPDATE_ALARM_PREFIX)) {
    const sessionIdPart = alarm.name.substring(BADGE_UPDATE_ALARM_PREFIX.length);
    chrome.storage.local.get([STORAGE_KEYS.ACTIVE_SESSION], (res) => {
      const active = res[STORAGE_KEYS.ACTIVE_SESSION];
      if (active && String(active.id) === String(sessionIdPart)) {
        updateBadgeFromSession(active);
      } else {
        // Session ended, clear badge and stop alarm
        chrome.alarms.clear(alarm.name);
        chrome.action.setBadgeText({ text: "" });
      }
    });
    return;
  }

  // Handle session end alarm
  if (!alarm.name.startsWith(SESSION_ALARM_PREFIX)) {
    return;
  }

  const sessionIdPart = alarm.name.substring(SESSION_ALARM_PREFIX.length);
  console.log("[Deepmode BG] ✅ Alarm fired for session:", sessionIdPart, "- Auto-ending session");

  chrome.storage.local.get(
    [STORAGE_KEYS.ACTIVE_SESSION, STORAGE_KEYS.ACCESS_TOKEN],
    async (res) => {
      const active = res[STORAGE_KEYS.ACTIVE_SESSION];
      const accessToken = res[STORAGE_KEYS.ACCESS_TOKEN] || null;

      if (!active || !active.id) {
        console.log(
          "[Deepmode BG] No active session found on alarm, skipping auto-end."
        );
        return;
      }

      if (String(active.id) !== String(sessionIdPart)) {
        console.log(
          "[Deepmode BG] Active session id mismatch on alarm, skipping auto-end."
        );
        return;
      }

      const isGuest = !!active.isGuest || !accessToken;
      const taskLabel = active.task || "your block";

      console.log("[Deepmode BG] ✅ Auto-ending session from alarm. guest=", isGuest);

      // Send notification BEFORE ending
      chrome.notifications.create(
        {
          type: "basic",
          iconUrl: "icon.png",
          title: "Deepwork block complete",
          message: "Great work. Take a short break and come back. You're building your future one session at a time.",
          priority: 2
        },
        (notificationId) => {
          if (chrome.runtime.lastError) {
            console.error("[Deepmode BG] ❌ ERROR creating notification:", chrome.runtime.lastError.message);
          } else {
            console.log("[Deepmode BG] ✅ End notification created:", notificationId);
          }
        }
      );

      if (isGuest) {
        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          activeSession = null;
          console.log(
            "[Deepmode BG] Guest session auto-ended and cleared from storage."
          );
        });
        return;
      }

      try {
        const resp = await fetch(
          `${API_BASE_URL}/sessions/${active.id}/end`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
              "Authorization": "Bearer " + accessToken,
            },
          }
        );

        if (!resp.ok) {
          console.error(
            "[Deepmode BG] Auto-end PATCH failed",
            resp.status
          );
        } else {
          console.log("[Deepmode BG] Auto-end PATCH succeeded.");
        }
      } catch (err) {
        console.error(
          "[Deepmode BG] Error calling backend on auto-end",
          err
        );
      } finally {
        chrome.storage.local.remove(STORAGE_KEYS.ACTIVE_SESSION, () => {
          activeSession = null;
          console.log(
            "[Deepmode BG] Session cleared from storage after auto-end."
          );
        });
      }
    }
  );
});

// ---------- TAB EVENTS: APPLY BLOCKER ON NAVIGATION / FOCUS ----------

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete") {
    maybeBlockTab(tab);
  }
});

chrome.tabs.onActivated.addListener((activeInfo) => {
  chrome.tabs.get(activeInfo.tabId, (tab) => {
    if (chrome.runtime.lastError || !tab) return;
    maybeBlockTab(tab);
  });
});

console.log("[Deepmode BG] Service worker loaded (alarms and notifications enabled).");

