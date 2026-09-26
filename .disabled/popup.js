document.addEventListener('DOMContentLoaded', async () => {
  const statusEl = document.getElementById('status');
  const backendUrlEl = document.getElementById('backend-url');
  const savedEl = document.getElementById('saved');
  const draftsEl = document.getElementById('drafts');

  const items = await chrome.storage.sync.get(['auraBackendUrl']);
  const backendUrl = (items.auraBackendUrl || 'http://127.0.0.1:8000').replace(/\/$/, '');
  backendUrlEl.textContent = backendUrl.replace(/^https?:\/\//, '');

  try {
    const response = await fetch(backendUrl + '/api/selflearn/status');
    if (response.ok) {
      statusEl.textContent = 'Online';
      statusEl.style.color = '#22c55e';
    } else {
      statusEl.textContent = 'Error';
      statusEl.style.color = '#ef4444';
    }
  } catch (e) {
    statusEl.textContent = 'Offline';
    statusEl.style.color = '#ef4444';
  }

  try {
    const draftsResponse = await fetch(backendUrl + '/api/fanfic/drafts?limit=10');
    if (draftsResponse.ok) {
      const data = await draftsResponse.json();
      const drafts = data.drafts || [];
      savedEl.textContent = String(drafts.length);

      if (drafts.length === 0) {
        draftsEl.innerHTML = '<p style="color: #999; font-size: 12px;">No drafts yet</p>';
      } else {
        draftsEl.innerHTML = drafts
          .map((draft) => `<div class="draft-item"><strong>${escapeHtml(draft.title || 'Untitled')}</strong><br><span style="color:#666;font-size:11px;">${escapeHtml(draft.platform || 'draft')} - ${new Date(draft.updated_at || Date.now()).toLocaleString()}</span></div>`)
          .join('');
      }
    } else {
      throw new Error('Failed to load drafts');
    }
  } catch (e) {
    savedEl.textContent = '?';
    draftsEl.innerHTML = '<p style="color: #999; font-size: 12px;">Could not load drafts</p>';
  }

  document.getElementById('open-settings').addEventListener('click', () => {
    const url = prompt('AURA Backend URL', backendUrl);
    if (url !== null) {
      chrome.storage.sync.set({ auraBackendUrl: url.trim() });
      backendUrlEl.textContent = url.trim().replace(/^https?:\/\//, '');
    }
  });

  document.getElementById('open-help').addEventListener('click', () => {
    alert('AURA Fanfic Generator\n\n1. Open Wattpad, AO3, or FanFiction.net\n2. Click the AURA button\n3. Fill the form and generate\n4. Publish, save draft, narrate, or copy');
  });
});

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
