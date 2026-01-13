// ============================================================
// Knowledge Engine Browser Extension - Popup Script
// ============================================================

// ============================================================
// DOM Elements
// ============================================================

const statusEl = document.getElementById('status');
const pageTitleEl = document.getElementById('page-title');
const pageUrlEl = document.getElementById('page-url');
const pageStatsEl = document.getElementById('page-stats');
const clipPageBtn = document.getElementById('clip-page-btn');
const clipSelectionBtn = document.getElementById('clip-selection-btn');
const urlInput = document.getElementById('url-input');
const clipUrlBtn = document.getElementById('clip-url-btn');
const recentList = document.getElementById('recent-list');

// ============================================================
// State
// ============================================================

let isConnected = false;
let currentPageInfo = null;

// ============================================================
// Initialization
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {
  await checkConnection();
  await loadPageInfo();
  await loadRecentClips();
  setupEventListeners();
});

// ============================================================
// Connection Check
// ============================================================

async function checkConnection() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'check-health' });
    isConnected = response.success && response.healthy;
    updateConnectionStatus(isConnected);
  } catch (error) {
    console.error('Health check failed:', error);
    updateConnectionStatus(false);
  }
}

function updateConnectionStatus(connected) {
  const dot = statusEl.querySelector('.status-dot');
  const text = statusEl.querySelector('.status-text');

  if (connected) {
    dot.classList.add('connected');
    dot.classList.remove('disconnected');
    text.textContent = 'Connected';
  } else {
    dot.classList.remove('connected');
    dot.classList.add('disconnected');
    text.textContent = 'Disconnected';
  }
}

// ============================================================
// Page Info
// ============================================================

async function loadPageInfo() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'get-page-info' });
    if (response.success && response.content) {
      currentPageInfo = response.content;
      displayPageInfo(response.content);
    }
  } catch (error) {
    console.error('Failed to load page info:', error);
    pageTitleEl.textContent = 'Unable to load page info';
  }
}

function displayPageInfo(info) {
  pageTitleEl.textContent = info.title || 'Untitled';
  pageTitleEl.title = info.title || 'Untitled';

  pageUrlEl.textContent = truncateUrl(info.url);
  pageUrlEl.title = info.url;

  const wordCount = info.content ? info.content.split(/\s+/).length : 0;
  const readTime = Math.ceil(wordCount / 200);
  pageStatsEl.textContent = `${wordCount.toLocaleString()} words · ${readTime} min read`;
}

function truncateUrl(url) {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname.length > 30
      ? parsed.pathname.slice(0, 30) + '...'
      : parsed.pathname;
    return parsed.hostname + path;
  } catch {
    return url.slice(0, 50) + '...';
  }
}

// ============================================================
// Event Listeners
// ============================================================

function setupEventListeners() {
  clipPageBtn.addEventListener('click', handleClipPage);
  clipSelectionBtn.addEventListener('click', handleClipSelection);
  clipUrlBtn.addEventListener('click', handleClipUrl);

  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      handleClipUrl();
    }
  });
}

async function handleClipPage() {
  if (!isConnected) {
    showError('Not connected to Knowledge Engine');
    return;
  }

  setButtonLoading(clipPageBtn, true);

  try {
    const response = await chrome.runtime.sendMessage({ action: 'clip-page' });
    if (response.success) {
      showSuccess('Page clipped successfully!');
      addToRecentClips({
        title: currentPageInfo?.title || 'Untitled',
        url: currentPageInfo?.url,
        timestamp: new Date().toISOString(),
        chunks: response.result.chunk_count,
      });
    } else {
      showError(response.error || 'Failed to clip page');
    }
  } catch (error) {
    showError(error.message);
  } finally {
    setButtonLoading(clipPageBtn, false);
  }
}

async function handleClipSelection() {
  if (!isConnected) {
    showError('Not connected to Knowledge Engine');
    return;
  }

  setButtonLoading(clipSelectionBtn, true);

  try {
    const response = await chrome.runtime.sendMessage({ action: 'clip-selection' });
    if (response.success) {
      showSuccess('Selection clipped!');
    } else {
      showError(response.error || 'Failed to clip selection');
    }
  } catch (error) {
    showError(error.message);
  } finally {
    setButtonLoading(clipSelectionBtn, false);
  }
}

async function handleClipUrl() {
  const url = urlInput.value.trim();
  if (!url) {
    showError('Please enter a URL');
    return;
  }

  if (!isConnected) {
    showError('Not connected to Knowledge Engine');
    return;
  }

  // Validate URL
  try {
    new URL(url);
  } catch {
    showError('Invalid URL format');
    return;
  }

  setButtonLoading(clipUrlBtn, true);

  try {
    const response = await chrome.runtime.sendMessage({
      action: 'clip-url',
      url,
    });

    if (response.success) {
      showSuccess('URL clipped successfully!');
      urlInput.value = '';
      addToRecentClips({
        title: response.result.title,
        url,
        timestamp: new Date().toISOString(),
        chunks: response.result.chunk_count,
      });
    } else {
      showError(response.error || 'Failed to clip URL');
    }
  } catch (error) {
    showError(error.message);
  } finally {
    setButtonLoading(clipUrlBtn, false);
  }
}

// ============================================================
// Recent Clips
// ============================================================

async function loadRecentClips() {
  try {
    const result = await chrome.storage.local.get('recentClips');
    const clips = result.recentClips || [];
    displayRecentClips(clips);
  } catch (error) {
    console.error('Failed to load recent clips:', error);
  }
}

function displayRecentClips(clips) {
  if (clips.length === 0) {
    recentList.innerHTML = '<div class="empty-state">No recent clips</div>';
    return;
  }

  recentList.innerHTML = clips.slice(0, 5).map(clip => `
    <div class="recent-item" title="${clip.url}">
      <div class="recent-title">${escapeHtml(clip.title)}</div>
      <div class="recent-meta">
        <span>${formatRelativeTime(clip.timestamp)}</span>
        ${clip.chunks ? `<span>· ${clip.chunks} chunks</span>` : ''}
      </div>
    </div>
  `).join('');
}

async function addToRecentClips(clip) {
  try {
    const result = await chrome.storage.local.get('recentClips');
    const clips = result.recentClips || [];

    // Add new clip at the beginning
    clips.unshift(clip);

    // Keep only last 20 clips
    const trimmedClips = clips.slice(0, 20);

    await chrome.storage.local.set({ recentClips: trimmedClips });
    displayRecentClips(trimmedClips);
  } catch (error) {
    console.error('Failed to save recent clip:', error);
  }
}

// ============================================================
// UI Helpers
// ============================================================

function setButtonLoading(button, loading) {
  if (loading) {
    button.disabled = true;
    button.classList.add('loading');
  } else {
    button.disabled = false;
    button.classList.remove('loading');
  }
}

function showSuccess(message) {
  showToast(message, 'success');
}

function showError(message) {
  showToast(message, 'error');
}

function showToast(message, type = 'info') {
  // Remove existing toast
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  // Animate in
  setTimeout(() => toast.classList.add('show'), 10);

  // Remove after delay
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatRelativeTime(timestamp) {
  const now = new Date();
  const then = new Date(timestamp);
  const diff = now - then;

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return then.toLocaleDateString();
}
