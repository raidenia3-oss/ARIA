const CURRENT_SITE = (() => {
  const hostname = window.location.hostname;
  if (hostname.includes('wattpad.com')) return 'WATTPAD';
  if (hostname.includes('archiveofourown.org')) return 'AO3';
  if (hostname.includes('fanfiction.net')) return 'FANFICTION';
  return null;
})();

function getBackendUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(['auraBackendUrl'], (items) => {
      resolve(items.auraBackendUrl || 'http://127.0.0.1:8000');
    });
  });
}

async function apiCall(path, options = {}) {
  const baseUrl = await getBackendUrl();
  const url = baseUrl.replace(/\/$/, '') + path;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error ${response.status}: ${text}`);
  }
  return response.json();
}

function detectSite() {
  return CURRENT_SITE;
}

function injectFloatingButton() {
  if (document.getElementById('aura-generate-btn')) return;

  const button = document.createElement('button');
  button.id = 'aura-generate-btn';
  button.textContent = '✨ Generate Story';
  button.className = 'aura-floating-button';
  button.addEventListener('click', openGeneratorModal);

  document.body.appendChild(button);
  console.log('AURA extension injected on', CURRENT_SITE);
}

function openGeneratorModal() {
  removeModal();

  const modal = document.createElement('div');
  modal.id = 'aura-modal';
  modal.className = 'aura-modal';
  modal.innerHTML = `
    <div class="aura-modal-content">
      <div class="aura-modal-header">
        <h2>✨ Generate Fanfic with AURA</h2>
        <button class="aura-close" id="aura-close-modal">&times;</button>
      </div>

      <form id="aura-story-form" class="aura-form">
        <div class="form-group">
          <label for="aura-title">Story Title</label>
          <input type="text" id="aura-title" name="title" placeholder="Enter story title" required>
        </div>

        <div class="form-group">
          <label for="aura-premise">Premise</label>
          <textarea id="aura-premise" name="premise" placeholder="What's your story about?" rows="3"></textarea>
        </div>

        <div class="form-group">
          <label for="aura-characters">Characters (comma-separated)</label>
          <input type="text" id="aura-characters" name="characters" placeholder="Character1, Character2">
        </div>

        <div class="form-group">
          <label for="aura-tone">Tone</label>
          <select id="aura-tone" name="tone">
            <option value="dark">Dark</option>
            <option value="romantic">Romantic</option>
            <option value="noir">Noir</option>
            <option value="dramatic" selected>Dramatic</option>
            <option value="whimsical">Whimsical</option>
          </select>
        </div>

        <div class="form-group">
          <label for="aura-fandom">Fandom</label>
          <input type="text" id="aura-fandom" name="fandom" placeholder="Jujutsu Kaisen, Attack on Titan, etc.">
        </div>

        <button type="submit" class="aura-btn-primary">Generate Story</button>
        <button type="button" class="aura-btn-secondary" id="aura-cancel">Cancel</button>
      </form>

      <div id="aura-loading" class="aura-loading" style="display:none;">
        <div class="spinner"></div>
        <p>Generating story with AURA AI...</p>
      </div>

      <div id="aura-preview" class="aura-preview" style="display:none;">
        <h3>Preview</h3>
        <div id="aura-story-content" class="story-text"></div>
        <div class="preview-actions">
          <button class="aura-btn-primary" id="aura-publish">Publish to ${CURRENT_SITE || 'site'}</button>
          <button class="aura-btn-secondary" id="aura-draft">Save as Draft</button>
          <button class="aura-btn-secondary" id="aura-narrate">Narrate (TTS)</button>
          <button class="aura-btn-secondary" id="aura-copy">Copy</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  modal.querySelector('#aura-close-modal').addEventListener('click', removeModal);
  modal.querySelector('#aura-cancel').addEventListener('click', removeModal);
  modal.querySelector('#aura-story-form').addEventListener('submit', generateStory);
  modal.querySelector('#aura-publish').addEventListener('click', publishToSite);
  modal.querySelector('#aura-draft').addEventListener('click', saveDraft);
  modal.querySelector('#aura-narrate').addEventListener('click', narrateStory);
  modal.querySelector('#aura-copy').addEventListener('click', copyStory);
}

function removeModal() {
  const modal = document.getElementById('aura-modal');
  if (modal) modal.remove();
}

async function generateStory(event) {
  event.preventDefault();

  const title = document.getElementById('aura-title').value.trim();
  const premise = document.getElementById('aura-premise').value.trim();
  const charactersRaw = document.getElementById('aura-characters').value.trim();
  const tone = document.getElementById('aura-tone').value;
  const fandom = document.getElementById('aura-fandom').value.trim();

  if (!title) {
    alert('Title is required');
    return;
  }

  const characters = charactersRaw
    ? Object.fromEntries(charactersRaw.split(',').map((name) => [name.trim(), { traits: [] }]))
    : {};

  document.getElementById('aura-story-form').style.display = 'none';
  document.getElementById('aura-loading').style.display = 'block';

  try {
    const createResult = await apiCall('/api/narrative/stories/create', {
      method: 'POST',
      body: JSON.stringify({
        title,
        premise: premise || title,
        characters,
        tone,
        fandom,
      }),
    });

    const storyId = createResult.story_id || createResult.id;
    if (!storyId) {
      throw new Error('Story creation did not return an id');
    }

    const continueResult = await apiCall(`/api/narrative/stories/${storyId}/continue`, {
      method: 'POST',
      body: JSON.stringify({ prompt: 'Write the first chapter' }),
    });

    const storyText = continueResult.text || continueResult.story || '';

    document.getElementById('aura-loading').style.display = 'none';
    document.getElementById('aura-preview').style.display = 'block';
    document.getElementById('aura-story-content').textContent = storyText;

    window.__auraCurrentStoryId = storyId;
    console.log('AURA story generated:', storyId);
  } catch (error) {
    console.error('AURA generation error:', error);
    alert('Error generating story: ' + error.message);
    document.getElementById('aura-loading').style.display = 'none';
    document.getElementById('aura-story-form').style.display = 'block';
  }
}

async function publishToSite() {
  const content = document.getElementById('aura-story-content').textContent;
  const title = document.getElementById('aura-title').value.trim();

  if (!content) {
    alert('No story content to publish');
    return;
  }

  try {
    if (CURRENT_SITE === 'WATTPAD') {
      await publishToWattpad(title, content);
    } else if (CURRENT_SITE === 'AO3') {
      await publishToAO3(title, content);
    } else if (CURRENT_SITE === 'FANFICTION') {
      await publishToFanfiction(title, content);
    } else {
      await copyStory();
      alert('Published site not detected. Content copied to clipboard.');
    }
  } catch (error) {
    alert('Publish failed: ' + error.message);
  }
}

async function publishToWattpad(title, content) {
  const titleInput = document.querySelector('input[name="title"]') || document.querySelector('#story-title');
  const bodyInput = document.querySelector('textarea[name="content"]') || document.querySelector('#story-text') || document.querySelector('textarea');

  if (titleInput) titleInput.value = title || 'Generated Story';
  if (bodyInput) {
    bodyInput.value = content;
    bodyInput.dispatchEvent(new Event('input', { bubbles: true }));
    bodyInput.dispatchEvent(new Event('change', { bubbles: true }));
  }

  const submitBtn = document.querySelector('button[type="submit"]') || document.querySelector('.submit-btn') || document.querySelector('[data-testid="submit-button"]');
  if (submitBtn) {
    submitBtn.click();
    alert('Story sent to Wattpad. Please review and publish manually if needed.');
  } else {
    alert('Wattpad publish form not found. Content copied to clipboard.');
    await copyStory();
  }
}

async function publishToAO3(title, content) {
  const titleInput = document.querySelector('input[name="title"]') || document.querySelector('#title');
  const bodyInput = document.querySelector('#story_text') || document.querySelector('textarea#body') || document.querySelector('textarea');

  if (titleInput) titleInput.value = title || 'Generated Story';
  if (bodyInput) {
    bodyInput.value = content;
    bodyInput.dispatchEvent(new Event('input', { bubbles: true }));
  }

  const submitBtn = document.querySelector('input[type="submit"]') || document.querySelector('button[type="submit"]');
  if (submitBtn) {
    submitBtn.click();
    alert('Story sent to AO3. Please review and publish manually if needed.');
  } else {
    alert('AO3 publish form not found. Content copied to clipboard.');
    await copyStory();
  }
}

async function publishToFanfiction(title, content) {
  const titleInput = document.querySelector('input[name="storytitle"]') || document.querySelector('#storytitle');
  const bodyInput = document.querySelector('textarea[name="storytext1"]') || document.querySelector('#storytext1');

  if (titleInput) titleInput.value = title || 'Generated Story';
  if (bodyInput) {
    bodyInput.value = content;
    bodyInput.dispatchEvent(new Event('input', { bubbles: true }));
  }

  const submitBtn = document.querySelector('input[value="Post"]') || document.querySelector('input[value="Post Review"]');
  if (submitBtn) {
    submitBtn.click();
    alert('Story sent to FanFiction.net. Please review and publish manually if needed.');
  } else {
    alert('FanFiction.net publish form not found. Content copied to clipboard.');
    await copyStory();
  }
}

async function saveDraft() {
  const storyId = window.__auraCurrentStoryId;
  if (!storyId) {
    alert('No active story to save');
    return;
  }

  try {
    const result = await apiCall(`/api/fanfic/stories/${storyId}/save-draft`, {
      method: 'POST',
    });
    if (result.status === 'draft_saved') {
      alert('Draft saved to AURA cloud!');
      removeModal();
    } else {
      throw new Error('Unexpected response');
    }
  } catch (error) {
    alert('Failed to save draft: ' + error.message);
  }
}

function narrateStory() {
  const content = document.getElementById('aura-story-content').textContent;
  if (!content) {
    alert('No story content to narrate');
    return;
  }

  if (!window.speechSynthesis) {
    alert('Text-to-speech is not supported in this browser');
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(content);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
  alert('Narrating story...');
}

async function copyStory() {
  const content = document.getElementById('aura-story-content').textContent;
  if (!content) {
    alert('No story content to copy');
    return;
  }
  try {
    await navigator.clipboard.writeText(content);
    alert('Copied to clipboard!');
  } catch (error) {
    alert('Failed to copy: ' + error.message);
  }
}

function monitorPageChanges() {
  const observer = new MutationObserver(() => {
    if (!document.getElementById('aura-generate-btn')) {
      injectFloatingButton();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

if (CURRENT_SITE) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      injectFloatingButton();
      monitorPageChanges();
    });
  } else {
    injectFloatingButton();
    monitorPageChanges();
  }
}
