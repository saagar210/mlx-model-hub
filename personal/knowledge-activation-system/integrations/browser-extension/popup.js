// KAS Browser Extension - Popup Script

const API_URL = 'http://localhost:8000';
const WEB_URL = 'http://localhost:3000';

// Load stats on popup open
async function loadStats() {
  try {
    const response = await fetch(`${API_URL}/shortcuts/stats`);
    const data = await response.json();
    document.getElementById('doc-count').textContent = data.documents.toLocaleString();
    document.getElementById('review-count').textContent = data.review_due.toLocaleString();
  } catch (error) {
    console.error('Failed to load stats:', error);
  }
}

// Search function
let searchTimeout;
async function search(query) {
  const resultsDiv = document.getElementById('results');

  if (query.length < 3) {
    resultsDiv.innerHTML = '<div class="empty">Type at least 3 characters</div>';
    return;
  }

  try {
    const response = await fetch(`${API_URL}/api/v1/search?q=${encodeURIComponent(query)}&limit=5`);
    const data = await response.json();

    if (data.results && data.results.length > 0) {
      resultsDiv.innerHTML = data.results.map(r => `
        <div class="result-item" data-id="${r.content_id}">
          <div class="result-title">${escapeHtml(r.title)}</div>
          <div class="result-snippet">${escapeHtml(r.chunk_text.substring(0, 150))}...</div>
        </div>
      `).join('');

      // Add click handlers
      resultsDiv.querySelectorAll('.result-item').forEach(item => {
        item.addEventListener('click', () => {
          const id = item.dataset.id;
          chrome.tabs.create({ url: `${WEB_URL}/content/${id}` });
        });
      });
    } else {
      resultsDiv.innerHTML = '<div class="empty">No results found</div>';
    }
  } catch (error) {
    resultsDiv.innerHTML = `<div class="error">Search failed: ${error.message}</div>`;
  }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Capture current page
async function capturePage() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    const params = new URLSearchParams({
      text: `URL: ${tab.url}\nTitle: ${tab.title}`,
      title: tab.title,
      tags: 'bookmark,browser'
    });

    const response = await fetch(`${API_URL}/shortcuts/capture?${params}`, {
      method: 'POST'
    });

    const data = await response.json();

    if (data.success) {
      alert('Page saved to KAS!');
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    alert(`Failed to save: ${error.message}`);
  }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadStats();

  // Search input handler
  const searchInput = document.getElementById('search');
  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => search(e.target.value), 300);
  });

  // Capture button
  document.getElementById('capture').addEventListener('click', capturePage);

  // Open KAS button
  document.getElementById('open').addEventListener('click', () => {
    chrome.tabs.create({ url: WEB_URL });
  });
});
