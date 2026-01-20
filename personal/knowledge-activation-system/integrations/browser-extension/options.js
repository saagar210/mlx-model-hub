// KAS Browser Extension - Options

const defaults = {
  apiUrl: 'http://localhost:8000',
  webUrl: 'http://localhost:3000'
};

// Load saved settings
document.addEventListener('DOMContentLoaded', async () => {
  const result = await chrome.storage.sync.get(defaults);
  document.getElementById('apiUrl').value = result.apiUrl;
  document.getElementById('webUrl').value = result.webUrl;
});

// Save settings
document.getElementById('save').addEventListener('click', async () => {
  const apiUrl = document.getElementById('apiUrl').value;
  const webUrl = document.getElementById('webUrl').value;

  await chrome.storage.sync.set({ apiUrl, webUrl });

  const status = document.getElementById('status');
  status.textContent = 'Settings saved!';
  status.className = 'status success';

  setTimeout(() => {
    status.textContent = '';
    status.className = '';
  }, 2000);
});
