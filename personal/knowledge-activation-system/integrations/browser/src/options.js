// ============================================================
// Knowledge Engine Browser Extension - Options Script
// ============================================================

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
// DOM Elements
// ============================================================

const apiUrlInput = document.getElementById('api-url');
const apiKeyInput = document.getElementById('api-key');
const namespaceInput = document.getElementById('namespace');
const autoExtractCheckbox = document.getElementById('auto-extract');
const showNotificationsCheckbox = document.getElementById('show-notifications');
const extractImagesCheckbox = document.getElementById('extract-images');
const extractLinksCheckbox = document.getElementById('extract-links');
const testConnectionBtn = document.getElementById('test-connection');
const connectionStatus = document.getElementById('connection-status');
const clearRecentBtn = document.getElementById('clear-recent');
const exportSettingsBtn = document.getElementById('export-settings');
const importSettingsBtn = document.getElementById('import-settings');
const importFileInput = document.getElementById('import-file');
const saveSettingsBtn = document.getElementById('save-settings');
const resetSettingsBtn = document.getElementById('reset-settings');

// ============================================================
// Initialization
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  setupEventListeners();
});

// ============================================================
// Settings Management
// ============================================================

async function loadSettings() {
  try {
    const result = await chrome.storage.sync.get('settings');
    const settings = { ...DEFAULT_SETTINGS, ...result.settings };
    populateForm(settings);
  } catch (error) {
    console.error('Failed to load settings:', error);
    populateForm(DEFAULT_SETTINGS);
  }
}

function populateForm(settings) {
  apiUrlInput.value = settings.apiUrl;
  apiKeyInput.value = settings.apiKey;
  namespaceInput.value = settings.namespace;
  autoExtractCheckbox.checked = settings.autoExtract;
  showNotificationsCheckbox.checked = settings.showNotifications;
  extractImagesCheckbox.checked = settings.extractImages;
  extractLinksCheckbox.checked = settings.extractLinks;
}

function getFormSettings() {
  return {
    apiUrl: apiUrlInput.value.trim() || DEFAULT_SETTINGS.apiUrl,
    apiKey: apiKeyInput.value.trim(),
    namespace: namespaceInput.value.trim() || DEFAULT_SETTINGS.namespace,
    autoExtract: autoExtractCheckbox.checked,
    showNotifications: showNotificationsCheckbox.checked,
    extractImages: extractImagesCheckbox.checked,
    extractLinks: extractLinksCheckbox.checked,
  };
}

async function saveSettings() {
  const settings = getFormSettings();

  try {
    await chrome.storage.sync.set({ settings });
    showMessage('Settings saved successfully!', 'success');
  } catch (error) {
    console.error('Failed to save settings:', error);
    showMessage('Failed to save settings', 'error');
  }
}

async function resetSettings() {
  if (!confirm('Are you sure you want to reset all settings to defaults?')) {
    return;
  }

  try {
    await chrome.storage.sync.set({ settings: DEFAULT_SETTINGS });
    populateForm(DEFAULT_SETTINGS);
    showMessage('Settings reset to defaults', 'success');
  } catch (error) {
    console.error('Failed to reset settings:', error);
    showMessage('Failed to reset settings', 'error');
  }
}

// ============================================================
// Connection Test
// ============================================================

async function testConnection() {
  const settings = getFormSettings();

  testConnectionBtn.disabled = true;
  testConnectionBtn.textContent = 'Testing...';
  connectionStatus.textContent = '';
  connectionStatus.className = 'connection-status';

  try {
    const response = await fetch(`${settings.apiUrl}/health`, {
      headers: settings.apiKey ? { 'X-API-Key': settings.apiKey } : {},
    });

    if (response.ok) {
      const data = await response.json();
      if (data.status === 'healthy') {
        connectionStatus.textContent = '✓ Connected';
        connectionStatus.classList.add('success');
      } else {
        connectionStatus.textContent = '⚠ Unhealthy';
        connectionStatus.classList.add('warning');
      }
    } else {
      connectionStatus.textContent = `✗ Error: ${response.status}`;
      connectionStatus.classList.add('error');
    }
  } catch (error) {
    connectionStatus.textContent = '✗ Connection failed';
    connectionStatus.classList.add('error');
  } finally {
    testConnectionBtn.disabled = false;
    testConnectionBtn.textContent = 'Test Connection';
  }
}

// ============================================================
// Data Management
// ============================================================

async function clearRecentClips() {
  if (!confirm('Are you sure you want to clear all recent clips?')) {
    return;
  }

  try {
    await chrome.storage.local.remove('recentClips');
    showMessage('Recent clips cleared', 'success');
  } catch (error) {
    console.error('Failed to clear recent clips:', error);
    showMessage('Failed to clear recent clips', 'error');
  }
}

function exportSettings() {
  const settings = getFormSettings();
  const blob = new Blob([JSON.stringify(settings, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'knowledge-engine-settings.json';
  a.click();
  URL.revokeObjectURL(url);
  showMessage('Settings exported', 'success');
}

function importSettings() {
  importFileInput.click();
}

async function handleImportFile(event) {
  const file = event.target.files[0];
  if (!file) return;

  try {
    const text = await file.text();
    const settings = JSON.parse(text);

    // Validate settings
    const validSettings = { ...DEFAULT_SETTINGS };
    for (const key of Object.keys(DEFAULT_SETTINGS)) {
      if (key in settings) {
        validSettings[key] = settings[key];
      }
    }

    await chrome.storage.sync.set({ settings: validSettings });
    populateForm(validSettings);
    showMessage('Settings imported successfully!', 'success');
  } catch (error) {
    console.error('Failed to import settings:', error);
    showMessage('Failed to import settings: Invalid file format', 'error');
  }

  // Reset file input
  event.target.value = '';
}

// ============================================================
// Event Listeners
// ============================================================

function setupEventListeners() {
  testConnectionBtn.addEventListener('click', testConnection);
  clearRecentBtn.addEventListener('click', clearRecentClips);
  exportSettingsBtn.addEventListener('click', exportSettings);
  importSettingsBtn.addEventListener('click', importSettings);
  importFileInput.addEventListener('change', handleImportFile);
  saveSettingsBtn.addEventListener('click', saveSettings);
  resetSettingsBtn.addEventListener('click', resetSettings);

  // Auto-save on change (optional)
  // const inputs = document.querySelectorAll('input');
  // inputs.forEach(input => {
  //   input.addEventListener('change', saveSettings);
  // });
}

// ============================================================
// UI Helpers
// ============================================================

function showMessage(message, type = 'info') {
  // Remove existing message
  const existing = document.querySelector('.toast-message');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = `toast-message toast-${type}`;
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
