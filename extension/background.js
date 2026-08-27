/*
 * background.js
 * ─────────────
 * Chrome Extension Service Worker.
 *
 * Handles:
 *  - Extension icon click → toggle sidebar on the active YouTube tab
 *  - Storing/retrieving the backend URL preference
 */

// Default backend URL
const DEFAULT_BACKEND_URL = "http://localhost:8000";

// ── Icon click → toggle sidebar ──────────────────────────────────────────────
chrome.action.onClicked.addListener(async (tab) => {
  // Only act on YouTube watch pages
  if (!tab.url || !tab.url.includes("youtube.com/watch")) {
    return;
  }

  try {
    await chrome.tabs.sendMessage(tab.id, { action: "toggle-sidebar" });
  } catch (err) {
    // Content script might not be injected yet — inject it manually
    console.warn("Content script not ready, injecting now…", err);
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"],
    });
    await chrome.scripting.insertCSS({
      target: { tabId: tab.id },
      files: ["sidebar.css"],
    });
    // Retry toggle after injection
    setTimeout(async () => {
      try {
        await chrome.tabs.sendMessage(tab.id, { action: "toggle-sidebar" });
      } catch (retryErr) {
        console.error("Failed to toggle sidebar after injection:", retryErr);
      }
    }, 500);
  }
});

// ── Backend URL management ───────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "get-backend-url") {
    chrome.storage.local.get(["backendUrl"], (result) => {
      sendResponse({ url: result.backendUrl || DEFAULT_BACKEND_URL });
    });
    return true; // async response
  }

  if (message.action === "set-backend-url") {
    chrome.storage.local.set({ backendUrl: message.url }, () => {
      sendResponse({ success: true });
    });
    return true;
  }

  if (message.action === "fetch-api") {
    fetch(message.url, message.options)
      .then(async (resp) => {
        const text = await resp.text();
        let data;
        try {
          data = JSON.parse(text);
        } catch {
          data = text;
        }
        sendResponse({ ok: resp.ok, status: resp.status, data: data });
      })
      .catch((err) => {
        sendResponse({ ok: false, error: err.message });
      });
    return true;
  }
});
