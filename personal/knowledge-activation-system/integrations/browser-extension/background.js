// KAS Browser Extension - Background Service Worker

const API_URL = 'http://localhost:8000';

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'kas-save-selection',
    title: 'Save to KAS',
    contexts: ['selection']
  });

  chrome.contextMenus.create({
    id: 'kas-save-link',
    title: 'Save Link to KAS',
    contexts: ['link']
  });

  chrome.contextMenus.create({
    id: 'kas-save-page',
    title: 'Save Page to KAS',
    contexts: ['page']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  let text = '';
  let title = '';
  let tags = 'browser';

  switch (info.menuItemId) {
    case 'kas-save-selection':
      text = info.selectionText;
      title = `Selection from ${tab.title}`;
      tags = 'selection,browser';
      break;

    case 'kas-save-link':
      text = `URL: ${info.linkUrl}`;
      title = info.linkUrl;
      tags = 'link,browser';
      break;

    case 'kas-save-page':
      text = `URL: ${tab.url}\nTitle: ${tab.title}`;
      title = tab.title;
      tags = 'page,browser';
      break;
  }

  try {
    const params = new URLSearchParams({ text, title, tags });
    const response = await fetch(`${API_URL}/shortcuts/capture?${params}`, {
      method: 'POST'
    });

    const data = await response.json();

    if (data.success) {
      // Show notification
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: 'Saved to KAS',
        message: data.message
      });
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon48.png',
      title: 'KAS Error',
      message: `Failed to save: ${error.message}`
    });
  }
});
