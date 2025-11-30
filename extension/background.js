// background.js – Deepmode service worker
// Responsibilities:
// 1) Auto-ending Deepmode sessions at the planned end time (via chrome.alarms)
// 2) Blocking distraction sites by injecting blocker.js while a Deepmode session is active
// NOTE: Chrome desktop notifications have been removed. No OS notifications.

// ---------- CONSTANTS ----------

const STORAGE_KEYS = {
    ACTIVE_SESSION: "deepmode_active_session",
    ACCESS_TOKEN: "deepmode_access_token",
  };
  
  const BLOCK_PREFS_KEY = "deepmode_block_prefs";
  
  const SESSION_ALARM_PREFIX = "deepmode_session_";
  
  // Keep in sync with backend URL and popup.js
  const API_BASE_URL = "https://deepmode.onrender.com";
  
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
  
  // ---------- ALARM HELPERS (NO NOTIFICATIONS) ----------
  
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
  
    chrome.alarms.create(name, { when: Date.now() + delayMs });
  
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
    chrome.alarms.clear(name, (wasCleared) => {
      if (wasCleared) {
        console.log("[Deepmode BG] Alarm cleared:", name);
      }
    });
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
        } else {
          activeSession = null;
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
      } else {
        console.log("[Deepmode BG] No active session after change.");
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
  
  // ---------- ALARM HANDLER: AUTO END SESSION (NO DESKTOP NOTIFICATION) ----------
  
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (!alarm || !alarm.name || !alarm.name.startsWith(SESSION_ALARM_PREFIX)) {
      return;
    }
  
    const sessionIdPart = alarm.name.substring(SESSION_ALARM_PREFIX.length);
    console.log("[Deepmode BG] Alarm fired for session:", sessionIdPart);
  
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
  
        console.log(
          "[Deepmode BG] Auto-ending session from background. guest=",
          isGuest
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
  
  console.log("[Deepmode BG] Service worker loaded (alarms enabled, notifications disabled).");
  