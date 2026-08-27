/*
 * content.js
 * ──────────
 * YouTube RAG Chrome Extension — Content Script
 *
 * Injected on YouTube watch pages. Responsibilities:
 *  1. Inject the sidebar UI into the YouTube DOM
 *  2. Auto-detect the current video ID from the URL
 *  3. Handle YouTube SPA navigation (yt-navigate-finish)
 *  4. Communicate with the FastAPI backend (localhost:8000)
 *  5. Render chat messages with timestamped source links
 *  6. Clicking a timestamp seeks the YouTube <video> player
 */

(function () {
  "use strict";

  // Prevent double-injection
  if (document.getElementById("ytrag-sidebar")) return;

  // ── Constants ────────────────────────────────────────────────────────────
  const DEFAULT_API = "http://127.0.0.1:8000";
  let API_BASE = DEFAULT_API;
  let currentVideoId = null;
  let isIndexed = false;
  let chatHistory = [];

  // ── Load backend URL from storage ────────────────────────────────────────
  function loadBackendUrl() {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ action: "get-backend-url" }, (resp) => {
          if (resp && resp.url) {
            API_BASE = resp.url;
          }
          resolve();
        });
      } catch {
        resolve();
      }
    });
  }

  // ── Inject sidebar HTML ──────────────────────────────────────────────────
  async function injectSidebar() {
    await loadBackendUrl();

    // Fetch the sidebar HTML fragment
    const htmlUrl = chrome.runtime.getURL("sidebar.html");
    const resp = await fetch(htmlUrl);
    const html = await resp.text();

    // Create a wrapper div and inject
    const wrapper = document.createElement("div");
    wrapper.id = "ytrag-extension-root";
    wrapper.innerHTML = html;
    document.body.appendChild(wrapper);

    // Bind event listeners
    bindEvents();

    // Detect current video
    detectVideo();
  }

  // ── Event bindings ───────────────────────────────────────────────────────
  function bindEvents() {
    // Toggle button
    const toggleBtn = document.getElementById("ytrag-toggle-btn");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", toggleSidebar);
    }

    // Close button
    const closeBtn = document.getElementById("ytrag-close-btn");
    if (closeBtn) {
      closeBtn.addEventListener("click", closeSidebar);
    }

    // Index button
    const indexBtn = document.getElementById("ytrag-index-btn");
    if (indexBtn) {
      indexBtn.addEventListener("click", indexVideo);
    }

    // Send button
    const sendBtn = document.getElementById("ytrag-send-btn");
    if (sendBtn) {
      sendBtn.addEventListener("click", sendMessage);
    }

    // Enter key in chat input
    const chatInput = document.getElementById("ytrag-chat-input");
    if (chatInput) {
      chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });
    }

    // Listen for messages from background (icon click toggle)
    chrome.runtime.onMessage.addListener((msg) => {
      if (msg.action === "toggle-sidebar") {
        toggleSidebar();
      }
    });

    // YouTube SPA navigation — re-detect video on page change
    document.addEventListener("yt-navigate-finish", () => {
      setTimeout(detectVideo, 500);
    });

    // Also watch for popstate (back/forward)
    window.addEventListener("popstate", () => {
      setTimeout(detectVideo, 500);
    });
  }

  // ── Sidebar toggle ──────────────────────────────────────────────────────
  function toggleSidebar() {
    const sidebar = document.getElementById("ytrag-sidebar");
    if (sidebar) {
      sidebar.classList.toggle("ytrag-open");
    }
  }

  function closeSidebar() {
    const sidebar = document.getElementById("ytrag-sidebar");
    if (sidebar) {
      sidebar.classList.remove("ytrag-open");
    }
  }

  function openSidebar() {
    const sidebar = document.getElementById("ytrag-sidebar");
    if (sidebar) {
      sidebar.classList.add("ytrag-open");
    }
  }

  // ── Video detection ──────────────────────────────────────────────────────
  function extractVideoIdFromUrl(url) {
    const urlObj = new URL(url);
    return urlObj.searchParams.get("v") || null;
  }

  async function detectVideo() {
    const url = window.location.href;
    if (!url.includes("youtube.com/watch")) {
      return;
    }

    const videoId = extractVideoIdFromUrl(url);
    if (!videoId || videoId === currentVideoId) {
      return; // Same video, no change
    }

    currentVideoId = videoId;
    isIndexed = false;
    chatHistory = [];

    // Update UI
    updateVideoTitle();
    updateStatus("idle", "○ Not indexed");
    clearMessages();
    showWelcome(true);

    // Check if already indexed
    await checkIndexStatus();
  }

  function updateVideoTitle() {
    const titleEl = document.getElementById("ytrag-title-text");
    if (!titleEl) return;

    // Try to get the title from the YouTube page
    const ytTitle =
      document.querySelector(
        "h1.ytd-watch-metadata yt-formatted-string"
      )?.textContent ||
      document.querySelector("#title h1 yt-formatted-string")?.textContent ||
      document.title.replace(" - YouTube", "").trim() ||
      `Video: ${currentVideoId}`;

    titleEl.textContent = ytTitle;
  }

  // ── Index status check ───────────────────────────────────────────────────
  async function checkIndexStatus() {
    if (!currentVideoId) return;

    try {
      const resp = await new Promise((resolve) => {
        chrome.runtime.sendMessage(
          { action: "fetch-api", url: `${API_BASE}/api/status/${currentVideoId}`, options: { method: "GET" } },
          resolve
        );
      });

      if (!resp || !resp.ok) throw new Error(resp ? resp.error || `Status ${resp.status}` : "Network error");

      const data = resp.data;
      isIndexed = data.is_indexed;

      if (isIndexed) {
        updateStatus("success", "● Indexed ✓");
        updateIndexButton(false, "✅ Already Indexed");
      } else {
        updateStatus("idle", "○ Not indexed");
        updateIndexButton(false, "🚀 Index This Video");
      }
    } catch (err) {
      console.error("Failed to check index status:", err);
      updateStatus("error", "⚠ Server offline");
      updateIndexButton(false, "🚀 Index This Video");
    }
  }

  // ── Index video ──────────────────────────────────────────────────────────
  async function indexVideo() {
    if (!currentVideoId) return;

    const indexBtn = document.getElementById("ytrag-index-btn");
    const progressEl = document.getElementById("ytrag-progress");
    const progressBar = document.getElementById("ytrag-progress-bar");

    // Show loading state
    updateIndexButton(true, "⏳ Indexing…");
    updateStatus("loading", "⟳ Indexing…");
    if (progressEl) progressEl.style.display = "block";

    // Animate progress bar
    let progress = 0;
    const progressInterval = setInterval(() => {
      progress = Math.min(progress + Math.random() * 12, 90);
      if (progressBar) progressBar.style.width = `${progress}%`;
    }, 400);

    try {
      const videoUrl = `https://www.youtube.com/watch?v=${currentVideoId}`;
      const resp = await new Promise((resolve) => {
        chrome.runtime.sendMessage(
          {
            action: "fetch-api",
            url: `${API_BASE}/api/index`,
            options: {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ video_url: videoUrl }),
            },
          },
          resolve
        );
      });

      clearInterval(progressInterval);

      if (!resp || !resp.ok) {
        const err = resp ? resp.data || {} : {};
        throw new Error(err.detail || (resp ? `HTTP ${resp.status}` : "Network error"));
      }

      const data = resp.data;

      if (progressBar) progressBar.style.width = "100%";

      if (data.success) {
        isIndexed = true;
        updateStatus("success", "● Indexed ✓");

        const msg = data.already_indexed
          ? "✅ Already Indexed"
          : `✅ Indexed ${data.chunks_indexed} chunks`;
        updateIndexButton(false, msg);

        // Update title if we got a better one from the API
        if (data.video_title && data.video_title !== "Unknown Title") {
          const titleEl = document.getElementById("ytrag-title-text");
          if (titleEl) titleEl.textContent = data.video_title;
        }
      } else {
        updateStatus("error", "✗ Failed");
        updateIndexButton(false, "🚀 Retry Index");
        addSystemMessage(`❌ ${data.message || "Failed to index video."}`);
      }
    } catch (err) {
      clearInterval(progressInterval);
      console.error("Index error:", err);
      updateStatus("error", "✗ Error");
      updateIndexButton(false, "🚀 Retry Index");
      addSystemMessage(`❌ Error: ${err.message}`);
    }

    // Hide progress after a moment
    setTimeout(() => {
      if (progressEl) progressEl.style.display = "none";
      if (progressBar) progressBar.style.width = "0%";
    }, 1200);
  }

  // ── Send chat message ────────────────────────────────────────────────────
  async function sendMessage() {
    const input = document.getElementById("ytrag-chat-input");
    if (!input) return;

    const question = input.value.trim();
    if (!question) return;

    if (!currentVideoId) {
      addSystemMessage("⚠ No video detected. Please navigate to a YouTube video.");
      return;
    }

    if (!isIndexed) {
      addSystemMessage("⚠ Please index the video first before asking questions.");
      return;
    }

    // Clear input
    input.value = "";

    // Hide welcome
    showWelcome(false);

    // Add user message to chat
    addMessage("user", question);

    // Show typing indicator
    showTyping(true);

    // Disable send
    const sendBtn = document.getElementById("ytrag-send-btn");
    if (sendBtn) sendBtn.disabled = true;

    try {
      const resp = await new Promise((resolve) => {
        chrome.runtime.sendMessage(
          {
            action: "fetch-api",
            url: `${API_BASE}/api/chat`,
            options: {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                video_id: currentVideoId,
                question: question,
                chat_history: chatHistory.slice(-6).map(msg => ({
                  role: msg.role,
                  content: msg.content
                })),
              }),
            },
          },
          resolve
        );
      });

      showTyping(false);

      if (!resp || !resp.ok) {
        const err = resp ? resp.data || {} : {};
        throw new Error(err.detail || (resp ? `HTTP ${resp.status}` : "Network error"));
      }

      const data = resp.data;
      addAssistantMessage(data.answer, data.sources || []);
    } catch (err) {
      showTyping(false);
      console.error("Chat error:", err);
      addSystemMessage(`❌ Error: ${err.message}`);
    }

    if (sendBtn) sendBtn.disabled = false;
    input.focus();
  }

  // ── Message rendering ────────────────────────────────────────────────────
  function addMessage(role, content) {
    const container = document.getElementById("ytrag-messages");
    if (!container) return;

    const bubble = document.createElement("div");
    bubble.className = `ytrag-message ytrag-message-${role}`;
    bubble.textContent = content;

    container.appendChild(bubble);
    scrollToBottom();

    chatHistory.push({ role, content });
  }

  function addAssistantMessage(answer, sources) {
    const container = document.getElementById("ytrag-messages");
    if (!container) return;

    const bubble = document.createElement("div");
    bubble.className = "ytrag-message ytrag-message-assistant";

    // Render answer with basic markdown support
    bubble.innerHTML = renderMarkdown(answer);

    // Add sources if available
    if (sources && sources.length > 0) {
      const sourcesDiv = document.createElement("div");
      sourcesDiv.className = "ytrag-sources";

      const title = document.createElement("div");
      title.className = "ytrag-sources-title";
      title.innerHTML = "📌 Sources in this video:";
      sourcesDiv.appendChild(title);

      sources.forEach((src, i) => {
        const link = document.createElement("a");
        link.className = "ytrag-source-link";
        link.innerHTML = `<span class="ytrag-play-icon">▶</span> ${src.timestamp}`;
        link.title = src.text_snippet || `Jump to ${src.timestamp}`;
        link.href = "#";
        link.addEventListener("click", (e) => {
          e.preventDefault();
          seekVideo(src.start_seconds);
        });
        sourcesDiv.appendChild(link);
      });

      bubble.appendChild(sourcesDiv);
    }

    container.appendChild(bubble);
    scrollToBottom();

    chatHistory.push({ role: "assistant", content: answer, sources });
  }

  function addSystemMessage(text) {
    const container = document.getElementById("ytrag-messages");
    if (!container) return;

    showWelcome(false);

    const msg = document.createElement("div");
    msg.className = "ytrag-error-msg";
    msg.textContent = text;
    container.appendChild(msg);
    scrollToBottom();
  }

  function clearMessages() {
    const container = document.getElementById("ytrag-messages");
    if (!container) return;

    // Remove all children except the welcome div
    const welcome = document.getElementById("ytrag-welcome");
    container.innerHTML = "";
    if (welcome) container.appendChild(welcome);
  }

  // ── Basic Markdown renderer ──────────────────────────────────────────────
  function renderMarkdown(text) {
    if (!text) return "";

    // Escape HTML first
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Bold **text**
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    // Italic *text*
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

    // Inline code `text`
    html = html.replace(/`(.+?)`/g, "<code>$1</code>");

    // Line breaks
    html = html.replace(/\n/g, "<br>");

    // Bullet points (- item or * item at start of line)
    html = html.replace(
      /(?:^|<br>)\s*[-*]\s+(.+?)(?=<br>|$)/g,
      "<br>• $1"
    );

    // Numbered lists (1. item)
    html = html.replace(
      /(?:^|<br>)\s*(\d+)\.\s+(.+?)(?=<br>|$)/g,
      "<br>$1. $2"
    );

    return html;
  }

  // ── Typing indicator ─────────────────────────────────────────────────────
  function showTyping(show) {
    const container = document.getElementById("ytrag-messages");
    if (!container) return;

    // Remove existing typing indicator
    const existing = container.querySelector(".ytrag-typing");
    if (existing) existing.remove();

    if (show) {
      const typing = document.createElement("div");
      typing.className = "ytrag-typing";
      typing.innerHTML = `
        <div class="ytrag-typing-dot"></div>
        <div class="ytrag-typing-dot"></div>
        <div class="ytrag-typing-dot"></div>
      `;
      container.appendChild(typing);
      scrollToBottom();
    }
  }

  // ── Seek YouTube video ───────────────────────────────────────────────────
  function seekVideo(seconds) {
    const video = document.querySelector("video.html5-main-video") ||
                  document.querySelector("video");
    if (video) {
      video.currentTime = seconds;
      video.play().catch(() => {}); // Autoplay might be blocked
    }
  }

  // ── UI helpers ───────────────────────────────────────────────────────────
  function updateStatus(type, text) {
    const badge = document.getElementById("ytrag-status-badge");
    if (!badge) return;

    badge.className = `ytrag-badge ytrag-badge-${type}`;
    badge.textContent = text;
  }

  function updateIndexButton(disabled, text) {
    const btn = document.getElementById("ytrag-index-btn");
    if (!btn) return;

    btn.disabled = disabled;
    btn.textContent = text;
  }

  function showWelcome(show) {
    const welcome = document.getElementById("ytrag-welcome");
    if (welcome) {
      welcome.style.display = show ? "flex" : "none";
    }
  }

  function scrollToBottom() {
    const container = document.getElementById("ytrag-messages");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }

  // ── Initialise ───────────────────────────────────────────────────────────
  injectSidebar();
})();
