// ============================================================
// Knowledge Engine Browser Extension - Background Service Worker
// ============================================================

// Default settings
const DEFAULT_SETTINGS = {
  apiUrl: 'http://localhost:8000',
  apiKey: '',
  namespace: 'browser',
  autoExtract: true,
  showNotifications: true,
  extractImages: false,
  extractLinks: true,
};

// ============================================================
// Storage & Settings
// ============================================================

async function getSettings() {
  const result = await chrome.storage.sync.get('settings');
  return { ...DEFAULT_SETTINGS, ...result.settings };
}

async function saveSettings(settings) {
  await chrome.storage.sync.set({ settings });
}

// ============================================================
// API Client
// ============================================================

class KnowledgeEngineAPI {
  constructor(settings) {
    this.settings = settings;
  }

  async fetch(endpoint, options = {}) {
    const url = `${this.settings.apiUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
    };

    if (this.settings.apiKey) {
      headers['X-API-Key'] = this.settings.apiKey;
    }

    const response = await fetch(url, {
      ...options,
      headers: { ...headers, ...options.headers },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API error: ${response.status} - ${error}`);
    }

    return response.json();
  }

  async ingestUrl(url, options = {}) {
    return this.fetch('/v1/ingest/url', {
      method: 'POST',
      body: JSON.stringify({
        url,
        namespace: this.settings.namespace,
        ...options,
      }),
    });
  }

  async ingestText(title, content, metadata = {}) {
    return this.fetch('/v1/ingest/text', {
      method: 'POST',
      body: JSON.stringify({
        title,
        content,
        namespace: this.settings.namespace,
        metadata: {
          source: 'browser_extension',
          ...metadata,
        },
      }),
    });
  }

  async checkHealth() {
    try {
      const response = await this.fetch('/health');
      return response.status === 'healthy';
    } catch {
      return false;
    }
  }
}

// ============================================================
// Content Extraction
// ============================================================

async function extractPageContent(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        // Extract main content using Readability-like heuristics
        const article = document.querySelector('article') ||
                       document.querySelector('[role="main"]') ||
                       document.querySelector('main') ||
                       document.body;

        // Get meta information
        const title = document.title ||
                     document.querySelector('meta[property="og:title"]')?.content ||
                     document.querySelector('h1')?.textContent ||
                     'Untitled';

        const description = document.querySelector('meta[name="description"]')?.content ||
                           document.querySelector('meta[property="og:description"]')?.content ||
                           '';

        const author = document.querySelector('meta[name="author"]')?.content ||
                      document.querySelector('[rel="author"]')?.textContent ||
                      '';

        const publishedDate = document.querySelector('meta[property="article:published_time"]')?.content ||
                             document.querySelector('time[datetime]')?.getAttribute('datetime') ||
                             '';

        // Extract text content
        const clone = article.cloneNode(true);

        // Remove unwanted elements
        const unwanted = clone.querySelectorAll(
          'script, style, nav, header, footer, aside, [role="navigation"], ' +
          '[role="banner"], [role="contentinfo"], .advertisement, .ad, .sidebar, ' +
          '.comments, .comment, .related, .recommended, .social-share'
        );
        unwanted.forEach(el => el.remove());

        // Get clean text
        const content = clone.textContent
          .replace(/\s+/g, ' ')
          .trim();

        // Extract links
        const links = Array.from(document.querySelectorAll('a[href]'))
          .map(a => ({ text: a.textContent.trim(), href: a.href }))
          .filter(l => l.text && l.href.startsWith('http'))
          .slice(0, 50);

        // Extract images
        const images = Array.from(document.querySelectorAll('img[src]'))
          .map(img => ({
            src: img.src,
            alt: img.alt,
            width: img.naturalWidth,
            height: img.naturalHeight,
          }))
          .filter(img => img.width > 100 && img.height > 100)
          .slice(0, 20);

        return {
          title,
          description,
          author,
          publishedDate,
          content,
          links,
          images,
          url: window.location.href,
          extractedAt: new Date().toISOString(),
        };
      },
    });

    return results[0]?.result;
  } catch (error) {
    console.error('Content extraction failed:', error);
    throw error;
  }
}

async function getSelectedText(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const selection = window.getSelection();
        if (!selection || selection.isCollapsed) {
          return null;
        }

        const range = selection.getRangeAt(0);
        const container = range.commonAncestorContainer;

        // Get surrounding context
        const parent = container.nodeType === Node.TEXT_NODE
          ? container.parentElement
          : container;

        return {
          text: selection.toString().trim(),
          context: parent?.textContent?.trim().slice(0, 500),
          url: window.location.href,
          title: document.title,
        };
      },
    });

    return results[0]?.result;
  } catch (error) {
    console.error('Selection extraction failed:', error);
    throw error;
  }
}

// ============================================================
// Clipping Functions
// ============================================================

async function clipPage(tab) {
  const settings = await getSettings();
  const api = new KnowledgeEngineAPI(settings);

  try {
    // Send start notification
    await sendNotification('Clipping page...', tab.title);

    // Extract content
    const content = await extractPageContent(tab.id);

    if (!content || !content.content || content.content.length < 50) {
      throw new Error('Could not extract meaningful content from page');
    }

    // Build metadata
    const metadata = {
      source_url: content.url,
      author: content.author,
      published_date: content.publishedDate,
      description: content.description,
      extracted_at: content.extractedAt,
    };

    if (settings.extractLinks && content.links.length > 0) {
      metadata.links = content.links;
    }

    if (settings.extractImages && content.images.length > 0) {
      metadata.images = content.images;
    }

    // Ingest to Knowledge Engine
    const result = await api.ingestText(content.title, content.content, metadata);

    // Success notification
    await sendNotification(
      'Page clipped!',
      `${content.title} (${result.chunk_count} chunks)`
    );

    // Update badge
    chrome.action.setBadgeText({ text: '✓', tabId: tab.id });
    chrome.action.setBadgeBackgroundColor({ color: '#22c55e', tabId: tab.id });
    setTimeout(() => {
      chrome.action.setBadgeText({ text: '', tabId: tab.id });
    }, 3000);

    return result;
  } catch (error) {
    console.error('Clip page failed:', error);
    await sendNotification('Clip failed', error.message);

    chrome.action.setBadgeText({ text: '!', tabId: tab.id });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444', tabId: tab.id });
    setTimeout(() => {
      chrome.action.setBadgeText({ text: '', tabId: tab.id });
    }, 3000);

    throw error;
  }
}

async function clipSelection(tab) {
  const settings = await getSettings();
  const api = new KnowledgeEngineAPI(settings);

  try {
    const selection = await getSelectedText(tab.id);

    if (!selection || !selection.text) {
      throw new Error('No text selected');
    }

    // Send start notification
    await sendNotification('Clipping selection...', selection.text.slice(0, 50) + '...');

    // Create title from selection
    const title = `Selection from: ${selection.title}`;

    // Build content with context
    const content = selection.context
      ? `${selection.text}\n\n---\nContext: ${selection.context}`
      : selection.text;

    // Ingest to Knowledge Engine
    const result = await api.ingestText(title, content, {
      source_url: selection.url,
      selection_type: 'text',
      original_title: selection.title,
    });

    // Success notification
    await sendNotification(
      'Selection clipped!',
      `${result.chunk_count} chunks saved`
    );

    return result;
  } catch (error) {
    console.error('Clip selection failed:', error);
    await sendNotification('Clip failed', error.message);
    throw error;
  }
}

async function clipUrl(url) {
  const settings = await getSettings();
  const api = new KnowledgeEngineAPI(settings);

  try {
    await sendNotification('Fetching URL...', url);
    const result = await api.ingestUrl(url);
    await sendNotification('URL clipped!', `${result.title} (${result.chunk_count} chunks)`);
    return result;
  } catch (error) {
    console.error('Clip URL failed:', error);
    await sendNotification('Clip failed', error.message);
    throw error;
  }
}

// ============================================================
// Notifications
// ============================================================

async function sendNotification(title, message) {
  const settings = await getSettings();
  if (!settings.showNotifications) return;

  // Use badge for quick feedback
  chrome.action.setTitle({ title: `${title}: ${message}` });
}

// ============================================================
// Context Menu
// ============================================================

chrome.runtime.onInstalled.addListener(() => {
  // Create context menu items
  chrome.contextMenus.create({
    id: 'clip-page',
    title: 'Clip entire page to Knowledge Engine',
    contexts: ['page'],
  });

  chrome.contextMenus.create({
    id: 'clip-selection',
    title: 'Clip selection to Knowledge Engine',
    contexts: ['selection'],
  });

  chrome.contextMenus.create({
    id: 'clip-link',
    title: 'Clip linked page to Knowledge Engine',
    contexts: ['link'],
  });

  chrome.contextMenus.create({
    id: 'clip-image',
    title: 'Clip image to Knowledge Engine',
    contexts: ['image'],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  try {
    switch (info.menuItemId) {
      case 'clip-page':
        await clipPage(tab);
        break;
      case 'clip-selection':
        await clipSelection(tab);
        break;
      case 'clip-link':
        if (info.linkUrl) {
          await clipUrl(info.linkUrl);
        }
        break;
      case 'clip-image':
        if (info.srcUrl) {
          const settings = await getSettings();
          const api = new KnowledgeEngineAPI(settings);
          await api.ingestText(`Image from ${tab.title}`, `Image URL: ${info.srcUrl}`, {
            source_url: tab.url,
            image_url: info.srcUrl,
            content_type: 'image',
          });
          await sendNotification('Image clipped!', info.srcUrl);
        }
        break;
    }
  } catch (error) {
    console.error('Context menu action failed:', error);
  }
});

// ============================================================
// Keyboard Shortcuts
// ============================================================

chrome.commands.onCommand.addListener(async (command) => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;

  try {
    switch (command) {
      case 'clip-page':
        await clipPage(tab);
        break;
      case 'clip-selection':
        await clipSelection(tab);
        break;
    }
  } catch (error) {
    console.error('Command failed:', error);
  }
});

// ============================================================
// Message Handling
// ============================================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      switch (message.action) {
        case 'clip-page': {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tab) {
            const result = await clipPage(tab);
            sendResponse({ success: true, result });
          }
          break;
        }
        case 'clip-selection': {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tab) {
            const result = await clipSelection(tab);
            sendResponse({ success: true, result });
          }
          break;
        }
        case 'clip-url': {
          const result = await clipUrl(message.url);
          sendResponse({ success: true, result });
          break;
        }
        case 'get-settings': {
          const settings = await getSettings();
          sendResponse({ success: true, settings });
          break;
        }
        case 'save-settings': {
          await saveSettings(message.settings);
          sendResponse({ success: true });
          break;
        }
        case 'check-health': {
          const settings = await getSettings();
          const api = new KnowledgeEngineAPI(settings);
          const healthy = await api.checkHealth();
          sendResponse({ success: true, healthy });
          break;
        }
        case 'get-page-info': {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tab) {
            const content = await extractPageContent(tab.id);
            sendResponse({ success: true, content });
          }
          break;
        }
        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    } catch (error) {
      sendResponse({ success: false, error: error.message });
    }
  })();
  return true; // Keep channel open for async response
});

// ============================================================
// Badge Status
// ============================================================

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  // Reset badge when switching tabs
  chrome.action.setBadgeText({ text: '', tabId });
});

console.log('Knowledge Engine background service worker loaded');
