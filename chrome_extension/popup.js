const AURA_ENDPOINTS = {
  local: 'http://127.0.0.1:8000',
  cloud: 'https://aura-prod.railway.app',
};
let currentEndpoint = 'local';

async function detectEndpoint() {
  try {
    const res = await fetch(`${AURA_ENDPOINTS.local}/api/health`, { method: 'GET', signal: AbortSignal.timeout(2000) });
    if (res.ok) { currentEndpoint = 'local'; return; }
  } catch(e) {}
  try {
    const res = await fetch(`${AURA_ENDPOINTS.cloud}/api/health`, { method: 'GET', signal: AbortSignal.timeout(3000) });
    if (res.ok) { currentEndpoint = 'cloud'; return; }
  } catch(e) {}
  currentEndpoint = 'local';
}

function getEndpoint() {
  return AURA_ENDPOINTS[currentEndpoint];
}

async function sendToAURA(message) {
  if (!message.trim()) return null;
  try {
    const res = await fetch(`${getEndpoint()}/api/aura/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    return data;
  } catch(e) {
    return { error: e.message };
  }
}

async function sendCommand(command, args = {}) {
  try {
    const res = await fetch(`${getEndpoint()}/api/aura/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, args }),
    });
    const data = await res.json();
    return data;
  } catch(e) {
    return { error: e.message };
  }
}

function addMsg(text, cls = 'msg-aura') {
  const chat = document.getElementById('chat');
  const div = document.createElement('div');
  div.className = `msg ${cls}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function addSystem(text) { addMsg(text, 'msg-system'); }

async function sendMessage() {
  const input = document.getElementById('input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  addMsg(text, 'msg-user');

  if (text.startsWith('/')) {
    await handleCommand(text);
    return;
  }

  const data = await sendToAURA(text);
  if (data && data.response) {
    addMsg(data.response, 'msg-aura');
  } else if (data && data.error) {
    addMsg(`Error: ${data.error}`, 'msg-system');
  } else {
    addMsg('No response from AURA', 'msg-system');
  }
}

async function handleCommand(text) {
  const parts = text.split(' ');
  const cmd = parts[0].toLowerCase();
  const arg = parts.slice(1).join(' ');

  addSystem(`> ${text}`);

  switch(cmd) {
    case '/fanfic': {
      const res = await sendCommand('write_fanfic', { prompt: arg || 'an adventure in cyberpunk Tokyo' });
      addMsg(res.result || res.response || 'Generating fanfic...', 'msg-aura');
      break;
    }
    case '/search': {
      const res = await sendToAURA(`search: ${arg}`);
      addMsg(res?.response || 'Searching...', 'msg-aura');
      break;
    }
    case '/marketplace': {
      try {
        const res = await fetch(`${getEndpoint()}/api/v1/marketplace/list`);
        const data = await res.json();
        addMsg(`Marketplace: ${data.total || 0} items available`, 'msg-aura');
      } catch(e) {
        addMsg('Marketplace: check AURA desktop', 'msg-system');
      }
      break;
    }
    case '/netrunner': {
      addSystem('Opening Netrunner v2 in new tab...');
      window.open(`${getEndpoint()}/netrunner`, '_blank');
      break;
    }
    case '/status': {
      try {
        const res = await fetch(`${getEndpoint()}/api/status`);
        const data = await res.json();
        const daq = data.daemon || {};
        addMsg(`Status: ${daq.current_tasks || 0} tasks, $${data.revenue || 0} revenue`, 'msg-aura');
      } catch(e) {
        addMsg('Run AURA desktop first', 'msg-system');
      }
      break;
    }
    case '/ask': {
      const res = await sendToAURA(arg);
      addMsg(res?.response || 'Ask AURA something', 'msg-aura');
      break;
    }
    case '/help': {
      addSystem('Commands: /fanfic, /search, /marketplace, /netrunner, /status, /ask, /help');
      break;
    }
    default:
      addMsg(`Unknown: ${cmd}`, 'msg-system');
  }
}

async function init() {
  await detectEndpoint();
  addSystem(`Connected via ${currentEndpoint}`);

  try {
    const stored = await chrome.storage.local.get('history');
    if (stored.history && Array.isArray(stored.history)) {
      const chat = document.getElementById('chat');
      chat.innerHTML = '';
      for (const msg of stored.history.slice(-20)) {
        addMsg(msg.text, msg.cls);
      }
    }
  } catch(e) {}
}

const origSend = sendMessage;
sendMessage = async function() {
  await origSend();
  try {
    const chat = document.getElementById('chat');
    const msgs = Array.from(chat.querySelectorAll('.msg')).map(d => ({
      text: d.textContent,
      cls: d.className.replace('msg ', ''),
    }));
    await chrome.storage.local.set({ history: msgs });
  } catch(e) {}
};

init();
