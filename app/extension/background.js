// background.js – Deepmode tab control, blocking, muting, and blocklist toggles

const STORAGE_KEYS = {
    ACTIVE_SESSION: "deepmode_active_session",
  };
  
  const SYNC_KEYS = {
    BLOCK_PREFS: "deepmode_block_prefs",
  };
  
  // Default platforms we offer as checkboxes in the popup
  const DEFAULT_SITES = {
    youtube: {
      id: "youtube",
      hosts: ["www.youtube.com", "youtube.com"],
    },
    twitter: {
      id: "twitter",
      hosts: ["twitter.com", "x.com"],
    },
    facebook: {
      id: "facebook",
      hosts: ["facebook.com", "www.facebook.com"],
    },
    instagram: {
      id: "instagram",
      hosts: ["instagram.com", "www.instagram.com"],
    },
    reddit: {
      id: "reddit",
      hosts: ["reddit.com", "www.reddit.com"],
    },
    tiktok: {
      id: "tiktok",
      hosts: ["tiktok.com", "www.tiktok.com"],
    },
  };
  
  // Single source of truth for “is there an active session?”
  let currentSessionActive = false;
  
  // ---------- Pref helpers ----------
  
  function getDefaultBlockPrefs() {
    return {
      defaultSiteFlags: {
        youtube: true,
        twitter: true,
        facebook: true,
        instagram: true,
        reddit: true,
        tiktok: true,
      },
      customSites: [],
    };
  }
  
  function getBlockPrefs(callback) {
    chrome.storage.sync.get(SYNC_KEYS.BLOCK_PREFS, (result) => {
      const prefs =
        result[SYNC_KEYS.BLOCK_PREFS] || getDefaultBlockPrefs();
      callback(prefs);
    });
  }
  
  function shouldBlockHost(hostname, prefs) {
    const { defaultSiteFlags, customSites } = prefs;
  
    // Check defaults
    for (const [key, def] of Object.entries(DEFAULT_SITES)) {
      if (!defaultSiteFlags[key]) continue;
      if (def.hosts.includes(hostname)) return true;
    }
  
    // Check custom host substrings
    if (Array.isArray(customSites)) {
      for (const pattern of customSites) {
        if (!pattern) continue;
        if (hostname.includes(pattern)) return true;
      }
    }
  
    return false;
  }
  
  // ---------- Core blocking logic ----------
  
  function applyBlockingToTab(tab, sessionActive, prefs) {
    if (!tab || !tab.id || !tab.url) return;
  
    let hostname = "";
    try {
      const u = new URL(tab.url);
      hostname = u.hostname;
    } catch {
      return;
    }
  
    const blockThis = sessionActive && shouldBlockHost(hostname, prefs);
  
    if (blockThis) {
      // Mute tab
      chrome.tabs.update(
        tab.id,
        { muted: true },
        () => {
          if (chrome.runtime.lastError) {
            // swallow, no noise
          }
        }
      );
  
      // Inject blocker overlay script (if not already)
      chrome.scripting.executeScript(
        {
          target: { tabId: tab.id },
          files: ["blocker.js"],
        },
        () => {
          if (chrome.runtime.lastError) {
            // swallow, no noise
          }
        }
      );
  
      // Ask the content script (if present) to force-show overlay
      chrome.tabs.sendMessage(
        tab.id,
        { type: "DEEPMODE_FORCE_BLOCK" },
        () => {
          if (chrome.runtime.lastError) {
            // No receiver -> no blocker.js on that tab yet. Fine.
          }
        }
      );
    } else {
      // Unmute tab
      chrome.tabs.update(
        tab.id,
        { muted: false },
        () => {
          if (chrome.runtime.lastError) {
            // swallow
          }
        }
      );
  
      // Ask the content script (if present) to remove overlay
      chrome.tabs.sendMessage(
        tab.id,
        { type: "DEEPMODE_UNBLOCK" },
        () => {
          if (chrome.runtime.lastError) {
            // no script there, ignore
          }
        }
      );
    }
  }
  
  function applyBlockingToAllTabs(sessionActive) {
    getBlockPrefs((prefs) => {
      chrome.tabs.query({ url: ["<all_urls>"] }, (tabs) => {
        if (chrome.runtime.lastError) {
          console.warn(
            "Deepmode background: tabs.query error",
            chrome.runtime.lastError.message
          );
          return;
        }
  
        if (!tabs || !tabs.length) return;
  
        for (const tab of tabs) {
          applyBlockingToTab(tab, sessionActive, prefs);
        }
      });
    });
  }
  
  // ---------- Helpers ----------
  
  function isSessionActiveFromChange(change) {
    const newVal = change && change.newValue;
    return !!(newVal && newVal.id);
  }
  
  function refreshSessionActiveFromStorage() {
    chrome.storage.local.get(STORAGE_KEYS.ACTIVE_SESSION, (result) => {
      const active = result[STORAGE_KEYS.ACTIVE_SESSION];
      currentSessionActive = !!(active && active.id);
      console.log("Deepmode background: restored sessionActive =", currentSessionActive);
      if (currentSessionActive) {
        applyBlockingToAllTabs(true);
      } else {
        applyBlockingToAllTabs(false);
      }
    });
  }
  
  // ---------- Storage change listeners ----------
  
  chrome.storage.onChanged.addListener((changes, area) => {
    // 1) Session start / end
    if (area === "local" && changes[STORAGE_KEYS.ACTIVE_SESSION]) {
      currentSessionActive = isSessionActiveFromChange(
        changes[STORAGE_KEYS.ACTIVE_SESSION]
      );
      console.log(
        "Deepmode background: ACTIVE_SESSION changed – sessionActive =",
        currentSessionActive
      );
      applyBlockingToAllTabs(currentSessionActive);
    }
  
    // 2) Block prefs change
    if (area === "sync" && changes[SYNC_KEYS.BLOCK_PREFS]) {
      console.log("Deepmode background: block prefs changed in sync");
  
      // Just re-apply rules using currentSessionActive
      applyBlockingToAllTabs(currentSessionActive);
    }
  });
  
  // ---------- Tab event listeners (fix: block new tabs) ----------
  
  // When a tab finishes loading, if a session is active, apply rules to that tab only
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (!currentSessionActive) return;
    if (changeInfo.status !== "complete") return;
    if (!tab || !tab.url) return;
  
    getBlockPrefs((prefs) => {
      applyBlockingToTab(tab, currentSessionActive, prefs);
    });
  });
  
  // When a new tab is created, try to apply rules once it has a URL.
  // (onUpdated will also catch it when it navigates)
  chrome.tabs.onCreated.addListener((tab) => {
    if (!currentSessionActive) return;
    if (!tab || !tab.url) return;
  
    getBlockPrefs((prefs) => {
      applyBlockingToTab(tab, currentSessionActive, prefs);
    });
  });
  
  // ---------- Extension lifecycle ----------
  
  // When extension is installed or browser starts, restore sessionActive from storage
  chrome.runtime.onStartup.addListener(() => {
    console.log("Deepmode background: onStartup – restoring session state");
    refreshSessionActiveFromStorage();
  });
  
  chrome.runtime.onInstalled.addListener(() => {
    console.log("Deepmode background: onInstalled – restoring session state");
    refreshSessionActiveFromStorage();
  });
  