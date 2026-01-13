// ============================================================
// Knowledge Engine Browser Extension - Content Script
// ============================================================

// Highlight overlay for selections
let highlightOverlay = null;

// ============================================================
// Selection Highlighting
// ============================================================

function createHighlightOverlay() {
  if (highlightOverlay) return highlightOverlay;

  highlightOverlay = document.createElement('div');
  highlightOverlay.id = 'ke-highlight-overlay';
  highlightOverlay.className = 'ke-highlight-overlay';
  highlightOverlay.innerHTML = `
    <div class="ke-highlight-toolbar">
      <button class="ke-btn ke-btn-clip" title="Clip selection">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        Clip
      </button>
      <button class="ke-btn ke-btn-highlight" title="Highlight">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 11l3 3L22 4"/>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
        </svg>
      </button>
      <button class="ke-btn ke-btn-close" title="Close">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
    </div>
  `;

  document.body.appendChild(highlightOverlay);

  // Event handlers
  highlightOverlay.querySelector('.ke-btn-clip').addEventListener('click', handleClipSelection);
  highlightOverlay.querySelector('.ke-btn-highlight').addEventListener('click', handleHighlight);
  highlightOverlay.querySelector('.ke-btn-close').addEventListener('click', hideHighlightOverlay);

  return highlightOverlay;
}

function showHighlightOverlay(x, y) {
  const overlay = createHighlightOverlay();
  overlay.style.display = 'block';
  overlay.style.left = `${x}px`;
  overlay.style.top = `${y}px`;

  // Ensure it stays in viewport
  const rect = overlay.getBoundingClientRect();
  if (rect.right > window.innerWidth) {
    overlay.style.left = `${window.innerWidth - rect.width - 10}px`;
  }
  if (rect.bottom > window.innerHeight) {
    overlay.style.top = `${y - rect.height - 10}px`;
  }
}

function hideHighlightOverlay() {
  if (highlightOverlay) {
    highlightOverlay.style.display = 'none';
  }
}

// ============================================================
// Selection Handlers
// ============================================================

async function handleClipSelection() {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) return;

  const text = selection.toString().trim();
  if (!text) return;

  hideHighlightOverlay();

  try {
    await chrome.runtime.sendMessage({
      action: 'clip-selection',
    });
  } catch (error) {
    console.error('Clip selection failed:', error);
  }
}

function handleHighlight() {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) return;

  try {
    const range = selection.getRangeAt(0);
    const mark = document.createElement('mark');
    mark.className = 'ke-highlight';
    range.surroundContents(mark);
    selection.removeAllRanges();
  } catch (error) {
    console.error('Highlight failed:', error);
  }

  hideHighlightOverlay();
}

// ============================================================
// Event Listeners
// ============================================================

// Show toolbar on text selection
document.addEventListener('mouseup', (e) => {
  // Ignore if clicking on our overlay
  if (e.target.closest('.ke-highlight-overlay')) return;

  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) {
    hideHighlightOverlay();
    return;
  }

  const text = selection.toString().trim();
  if (text.length < 10) {
    hideHighlightOverlay();
    return;
  }

  // Show overlay near selection
  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  showHighlightOverlay(
    rect.left + window.scrollX,
    rect.bottom + window.scrollY + 5
  );
});

// Hide on click elsewhere
document.addEventListener('mousedown', (e) => {
  if (!e.target.closest('.ke-highlight-overlay')) {
    setTimeout(hideHighlightOverlay, 200);
  }
});

// Hide on scroll
let scrollTimeout;
document.addEventListener('scroll', () => {
  clearTimeout(scrollTimeout);
  scrollTimeout = setTimeout(hideHighlightOverlay, 100);
});

// Hide on escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    hideHighlightOverlay();
  }
});

// ============================================================
// Message Handling
// ============================================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.action) {
    case 'get-selection':
      const selection = window.getSelection();
      sendResponse({
        text: selection?.toString().trim() || '',
        url: window.location.href,
        title: document.title,
      });
      break;
    case 'highlight-text':
      // Find and highlight specific text
      highlightText(message.text);
      sendResponse({ success: true });
      break;
    case 'remove-highlights':
      removeAllHighlights();
      sendResponse({ success: true });
      break;
  }
  return true;
});

// ============================================================
// Utility Functions
// ============================================================

function highlightText(searchText) {
  if (!searchText) return;

  const treeWalker = document.createTreeWalker(
    document.body,
    NodeFilter.SHOW_TEXT,
    null
  );

  const nodesToHighlight = [];
  while (treeWalker.nextNode()) {
    const node = treeWalker.currentNode;
    if (node.textContent.includes(searchText)) {
      nodesToHighlight.push(node);
    }
  }

  nodesToHighlight.forEach((node) => {
    const text = node.textContent;
    const index = text.indexOf(searchText);
    if (index === -1) return;

    const before = text.slice(0, index);
    const match = text.slice(index, index + searchText.length);
    const after = text.slice(index + searchText.length);

    const fragment = document.createDocumentFragment();
    if (before) fragment.appendChild(document.createTextNode(before));

    const mark = document.createElement('mark');
    mark.className = 'ke-highlight ke-highlight-search';
    mark.textContent = match;
    fragment.appendChild(mark);

    if (after) fragment.appendChild(document.createTextNode(after));

    node.parentNode.replaceChild(fragment, node);
  });
}

function removeAllHighlights() {
  const highlights = document.querySelectorAll('.ke-highlight');
  highlights.forEach((mark) => {
    const parent = mark.parentNode;
    parent.replaceChild(document.createTextNode(mark.textContent), mark);
    parent.normalize();
  });
}

console.log('Knowledge Engine content script loaded');
