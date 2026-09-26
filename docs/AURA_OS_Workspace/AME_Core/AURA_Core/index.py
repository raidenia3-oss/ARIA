import os
import requests
import personality
import httpx
import threading
from search import smart_search
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from upstash_vector import Index
from monitor import get_world_news, get_market_summary
from models import call_llm, get_status
from coder import execute_code, format_result, detect_language
from hacker import start_rollercoin_farmer, get_farmer_status

# --- INICIO DEL BOT DE DISCORD (Versión Robusta) ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if DISCORD_TOKEN and len(DISCORD_TOKEN) > 10:
    try:
        import discord
        from discord.ext import commands

        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix="!", intents=intents)

        @bot.event
        async def on_ready():
            print(f"✅ Discord Bot conectado como {bot.user}")

        @bot.command()
        async def hablar(ctx, *, pregunta: str):
            """Pregunta a AURA a través de Discord."""
            try:
                response = requests.post(
                    f"{os.getenv('HERMES_NGROK_URL')}/ask",
                    json={"prompt": pregunta},
                    timeout=120
                )
                if response.status_code == 200:
                    respuesta = response.json().get("response", "Sin respuesta.")
                    await ctx.send(f"💬 **AURA:** {respuesta}")
                else:
                    await ctx.send("❌ Error: No pude contactar a mi cerebro local.")
            except Exception as e:
                await ctx.send(f"❌ Error: {str(e)}")

        def run_bot():
            bot.run(DISCORD_TOKEN)

        threading.Thread(target=run_bot, daemon=True).start()
        print("✅ Hilo de Discord iniciado.")

    except ImportError as e:
        print(f"❌ No se pudo importar discord.py: {e}")
    except Exception as e:
        print(f"❌ Error al iniciar el bot de Discord: {e}")
else:
    print("⚠️ DISCORD_TOKEN no configurado. Bot de Discord no iniciado.")

# --- Configuración de ngrok para Hermes ---
HERMES_NGROK_URL = os.environ.get("HERMES_NGROK_URL", "https://scabbed-uneven-habitant.ngrok-free.dev")

app = FastAPI()

try:
    vector_index = Index(
        url=os.environ.get("UPSTASH_VECTOR_REST_URL"),
        token=os.environ.get("UPSTASH_VECTOR_REST_TOKEN")
    )
except Exception:
    vector_index = None

try:
    from upstash_redis import Redis
    redis_client = Redis(
        url=os.environ.get("UPSTASH_REDIS_REST_URL"),
        token=os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    )
except Exception:
    redis_client = None

GITHUB_OWNER = "raidenia3-oss"
GITHUB_REPO = "AURA-server.01"
GITHUB_BRANCH = "main"
GITHUB_MEMORY_PATH = "AURA-Brain/AURA-Brain/Memorias"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}"
MAX_MEMORY_CHARS = 7000


def github_api_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AURA-Agent"
    }
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    return headers


def list_github_memory_files():
    try:
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees/{GITHUB_BRANCH}?recursive=1"
        response = requests.get(url, headers=github_api_headers(), timeout=20)
        response.raise_for_status()
        data = response.json()
        tree = data.get("tree", [])
        paths = [item["path"] for item in tree
                 if item.get("type") == "blob"
                 and item.get("path", "").startswith(GITHUB_MEMORY_PATH + "/")
                 and item.get("path", "").lower().endswith(".md")]
        return sorted(paths)
    except Exception:
        return []


def fetch_github_raw_file(path):
    try:
        raw_url = f"{GITHUB_RAW_BASE}/{GITHUB_BRANCH}/{path}"
        response = requests.get(raw_url, headers=github_api_headers(), timeout=20)
        if response.status_code == 200:
            return response.text
    except Exception:
        pass
    return None


def load_obsidian_memory():
    memory_files = []
    for path in list_github_memory_files():
        content = fetch_github_raw_file(path)
        if not content:
            continue
        relname = path[len(GITHUB_MEMORY_PATH) + 1:]
        memory_files.append({"file_name": relname, "content": content.strip()})

    context_parts = []
    total_chars = 0
    for entry in memory_files:
        prefix = f"[Memoria Obsidian: {entry['file_name']}]:\n"
        snippet = entry["content"][:2000]
        block = prefix + snippet
        if total_chars + len(block) > MAX_MEMORY_CHARS:
            remaining = MAX_MEMORY_CHARS - total_chars - len(prefix)
            if remaining > 0:
                block = prefix + snippet[:remaining]
            else:
                break
        context_parts.append(block)
        total_chars += len(block)

    return {"memory_files": memory_files, "context": "\n\n".join(context_parts)}


@app.get("/memory")
async def memory():
    memory_data = load_obsidian_memory()
    return {
        "memory_source": f"{GITHUB_RAW_BASE}/{GITHUB_BRANCH}/{GITHUB_MEMORY_PATH}",
        "memory": memory_data["context"],
        "files": [
            {"file_name": item["file_name"], "content": item["content"]}
            for item in memory_data["memory_files"]
        ]
    }

@app.get("/news")
async def get_news():
    try:
        from search import search_bbc, search_tech_news
        news = search_bbc() + search_tech_news()
        if not news:
            return {"news": []}
        lines = [l.strip() for l in news.strip().split("\n") if l.strip()]
        return {"news": lines[:6]}
    except Exception as e:
        return {"news": [], "error": str(e)}

@app.get("/markets")
async def get_markets():
    try:
        return {"data": get_market_summary()}
    except Exception as e:
        return {"data": f"Error: {str(e)}"}

@app.get("/worldnews")
async def get_world_news_endpoint():
    try:
        news = get_world_news()
        return {"news": news}
    except Exception as e:
        return {"news": [], "error": str(e)}

@app.post("/rollercoin/start")
async def rollercoin_start():
    return start_rollercoin_farmer()

@app.get("/rollercoin/status")
async def rollercoin_status():
    return get_farmer_status()

@app.get("/debug")
async def debug():
    ngrok_url = os.environ.get("NGROK_URL", "")
    ngrok_status = None
    ngrok_response = None
    ngrok_error = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                ngrok_url,
                json={
                    "model": "dolphin-llama3:8b",
                    "messages": [{"role": "user", "content": "di hola en español"}],
                    "stream": False
                },
                headers={
                    "User-Agent": "curl/7.68.0",
                    "ngrok-skip-browser-warning": "true"
                }
            )
            ngrok_status = r.status_code
            ngrok_response = r.text[:200]
    except Exception as e:
        ngrok_error = str(e)
    return {
        "ngrok_url": ngrok_url,
        "ngrok_status": ngrok_status,
        "ngrok_response": ngrok_response,
        "ngrok_error": ngrok_error
    }

@app.get("/test-hermes")
async def test_hermes_endpoint():
    """
    Endpoint de prueba simple para verificar la conexión con tu cerebro local.
    """
    import requests
    
    url = os.environ.get("HERMES_NGROK_URL", "")
    if not url:
        return {"status": "error", "message": "HERMES_NGROK_URL no configurado."}
    
    try:
        # Envía una pregunta simple
        response = requests.post(f"{url}/ask", json={"prompt": "Di 'Hola desde AURA' y explica brevemente tu función."}, timeout=120)
        response.raise_for_status()
        data = response.json()
        return {"status": "success", "respuesta_local": data.get("response", "Sin respuesta de Hermes")}
    except Exception as e:
        return {"status": "error", "message": f"Error al conectar con Hermes local: {str(e)}"}

HTML_CHAT = r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AURA CORE</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
            --green: #00ff41;
            --green-dim: #00aa2a;
            --green-dark: #002200;
            --bg: #0a0a0a;
            --bg2: #0f0f0f;
            --border: #1a1a1a;
            --text-dim: #444;
        }
        body { background: var(--bg); color: var(--green); font-family: 'Courier New', monospace; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        #header { background: var(--bg2); border-bottom: 1px solid var(--border); padding: 8px 20px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
        #header .title { font-size: 13px; letter-spacing: 4px; color: var(--green); }
        #status { font-size: 10px; color: var(--text-dim); letter-spacing: 2px; }
        #status.active { color: var(--green); }
        #status.speaking { color: #00aaff; }
        .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--text-dim); margin-right: 5px; }
        #status.active .dot { background: var(--green); box-shadow: 0 0 6px var(--green); }
        #status.speaking .dot { background: #00aaff; box-shadow: 0 0 6px #00aaff; }
        #news-ticker { background: #050505; border-bottom: 1px solid var(--border); padding: 5px 20px; font-size: 10px; color: var(--text-dim); overflow: hidden; white-space: nowrap; flex-shrink: 0; display: flex; align-items: center; gap: 10px; }
        #news-ticker .label { color: var(--green-dim); flex-shrink: 0; letter-spacing: 2px; }
        #ticker-content { display: inline-block; animation: ticker 40s linear infinite; }
        @keyframes ticker { 0% { transform: translateX(100vw); } 100% { transform: translateX(-100%); } }
        #main { display: flex; flex: 1; overflow: hidden; }
        #sidebar { width: 200px; background: var(--bg2); border-right: 1px solid var(--border); padding: 15px 10px; display: flex; flex-direction: column; gap: 5px; flex-shrink: 0; overflow-y: auto; }
        .sidebar-title { font-size: 9px; color: var(--text-dim); letter-spacing: 2px; padding: 5px 8px; margin-top: 10px; }
        .sidebar-btn { background: none; border: 1px solid var(--border); color: var(--text-dim); padding: 8px 10px; text-align: left; cursor: pointer; font-family: monospace; font-size: 11px; transition: all 0.2s; border-radius: 2px; width: 100%; }
        .sidebar-btn:hover { border-color: var(--green-dim); color: var(--green); background: var(--green-dark); }
        .sidebar-btn.active { border-color: var(--green); color: var(--green); background: var(--green-dark); }
        #chat-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
        #chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
        #chat::-webkit-scrollbar { width: 4px; }
        #chat::-webkit-scrollbar-thumb { background: var(--border); }
        .msg { max-width: 80%; padding: 12px 15px; border-radius: 2px; font-size: 12px; line-height: 1.6; border: 1px solid var(--border); animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; } }
        .msg.user { align-self: flex-end; background: var(--green-dark); border-color: var(--green-dim); }
        .msg.aura { align-self: flex-start; background: var(--bg2); }
        .msg.aura:hover { border-color: var(--green-dim); }
        .msg.system { align-self: center; background: none; font-size: 10px; color: var(--text-dim); max-width: 100%; text-align: center; padding: 5px 15px; }
        .msg-header { font-size: 10px; color: var(--green-dim); margin-bottom: 6px; letter-spacing: 1px; display: flex; align-items: center; gap: 6px; }
        .tag { font-size: 9px; padding: 1px 5px; border-radius: 2px; }
        .tag.web  { background: #001133; color: #4488ff; border: 1px solid #003366; }
        .tag.file { background: #1a0a00; color: #ff8844; border: 1px solid #663300; }
        .tag.mem  { background: #0a0a1a; color: #8844ff; border: 1px solid #330066; }
        .tag.game { background: #001a00; color: #00ff88; border: 1px solid #006633; }
        .msg-body { white-space: pre-wrap; }
        #typing-indicator { padding: 8px 20px; font-size: 10px; color: var(--text-dim); display: none; flex-shrink: 0; }
        #typing-indicator.show { display: block; }
        .blink { animation: blink 1s infinite; }
        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
        #input-area { background: var(--bg2); border-top: 1px solid var(--border); padding: 12px 20px; display: flex; flex-direction: column; gap: 8px; flex-shrink: 0; position: relative; z-index: 10; }
        #toolbar { display: flex; gap: 8px; align-items: center; }
        #file-name { font-size: 10px; color: var(--text-dim); flex: 1; }
        .tool-btn { background: none; border: 1px solid var(--border); color: var(--text-dim); padding: 5px 10px; cursor: pointer; font-family: monospace; font-size: 10px; transition: all 0.2s; }
        .tool-btn:hover { border-color: var(--green-dim); color: var(--green); }
        .tool-btn.active { border-color: #ff4444; color: #ff4444; background: #110000; }
        #input-row { display: flex; gap: 8px; }
        #msgInput { flex: 1; background: var(--bg); border: 1px solid var(--border); color: var(--green); padding: 10px 15px; outline: none; font-family: monospace; font-size: 12px; }
        #msgInput:focus { border-color: var(--green-dim); }
        #msgInput::placeholder { color: var(--text-dim); }
        #sendBtn { background: var(--green); border: none; color: #000; padding: 10px 20px; cursor: pointer; font-family: monospace; font-weight: bold; font-size: 12px; }
        #sendBtn:hover { background: #00cc33; }
        #sendBtn:disabled { background: var(--green-dim); cursor: not-allowed; }
    </style>
</head>
<body>
    <div id="header">
        <div class="title">&#9672; AURA SYSTEM v3.5</div>
        <div id="status"><span class="dot"></span>STANDBY</div>
    </div>
    <div id="news-ticker">
        <span class="label">&#9672; LIVE</span>
        <span id="ticker-content">Cargando noticias...</span>
    </div>
    <div id="main">
        <div id="sidebar">
            <div class="sidebar-title">&#9672; COMANDOS</div>
            <button class="sidebar-btn" onclick="quickCmd('busca: noticias mundiales urgentes hoy')">Mundial</button>
            <button class="sidebar-btn" onclick="loadMarkets()">Mercados</button>
            <button class="sidebar-btn" onclick="quickCmd('busca: ultimas noticias tecnologia')">Tech</button>
            <button class="sidebar-btn" onclick="quickCmd('busca: precio GPU Nvidia hoy')">Hardware</button>
            <button class="sidebar-btn" onclick="quickCmd('que es ')">Wikipedia</button>
            <button class="sidebar-btn" onclick="quickCmd('estado rollercoin')">RollerCoin</button>
            <div class="sidebar-title">&#9672; SISTEMA</div>
            <button class="sidebar-btn" id="notifBtn" onclick="toggleNotifications()">Alertas OFF</button>
            <button class="sidebar-btn" onclick="clearChat()">Limpiar</button>
            <button class="sidebar-btn" onclick="document.getElementById('fileInput').click()">Archivo</button>
            <input type="file" id="fileInput" accept=".cpp,.c,.py,.txt,.js,.ts,.md,.json" style="display:none" onchange="handleFile()">
            <div class="sidebar-title">&#9672; CODIGO</div>
            <button class="sidebar-btn" onclick="quickCmd('ejecuta este codigo python: print(Hola AURA)')">Ejecutar Python</button>
            <button class="sidebar-btn" onclick="quickCmd('ejecuta este codigo cpp: #include iostream')">Ejecutar C++</button>
            <div class="sidebar-title">&#9672; ESTADO</div>
            <div style="font-size:10px; color:#333; padding:5px 8px;" id="mem-status">Noticias: --</div>
            <div style="font-size:10px; color:#00aa2a; padding:5px 8px;">Busqueda: activa</div>
        </div>
        <div id="chat-area">
            <div id="chat">
                <div class="msg system">&#9672; AURA v3.5 -- 5 motores activos -- Busqueda en tiempo real</div>
            </div>
            <div id="typing-indicator">AURA procesando<span class="blink">&#9611;</span></div>
            <div id="input-area">
                <div id="toolbar">
                    <span id="file-name">Sin archivo adjunto</span>
                    <button class="tool-btn" id="clearFileBtn" onclick="clearFile()" style="display:none; color:#ff4444;">X Quitar</button>
                    <button class="tool-btn" id="voiceBtn" onclick="toggleVoice()">VOZ</button>
                </div>
                <div id="input-row">
                    <input type="text" id="msgInput" placeholder="Escribe una orden..." onkeypress="if(event.key==='Enter' && !event.shiftKey) send()">
                    <button id="sendBtn" onclick="send()">EJECUTAR</button>
                </div>
            </div>
        </div>
    </div>
    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('msgInput');
        const status = document.getElementById('status');
        const typingEl = document.getElementById('typing-indicator');
        const sendBtn = document.getElementById('sendBtn');
        let fileContent = null, fileName = null, isListening = false, recognition = null;
        let notificationsOn = false, newsInterval = null;
        let isSending = false;

        async function loadTicker() {
            try {
                const res = await fetch('/news');
                const data = await res.json();
                if (data.news && data.news.length > 0) {
                    document.getElementById('ticker-content').textContent = data.news.join('  --  ');
                    document.getElementById('mem-status').textContent = 'Noticias: OK';
                    document.getElementById('mem-status').style.color = '#00aa2a';
                }
            } catch(e) {}
        }
        loadTicker();
        setInterval(loadTicker, 5 * 60 * 1000);

        async function toggleNotifications() {
            if (!notificationsOn) {
                const perm = await Notification.requestPermission();
                if (perm !== 'granted') { addMsg('system', 'Permiso denegado.'); return; }
                notificationsOn = true;
                document.getElementById('notifBtn').textContent = 'Alertas ON';
                document.getElementById('notifBtn').classList.add('active');
                newsInterval = setInterval(async () => {
                    try {
                        const res = await fetch('/news');
                        const data = await res.json();
                        if (data.news && data.news.length > 0) {
                            new Notification('AURA', { body: data.news[0].trim() });
                        }
                    } catch(e) {}
                }, 10 * 60 * 1000);
                addMsg('system', 'Alertas activadas.');
            } else {
                notificationsOn = false;
                document.getElementById('notifBtn').textContent = 'Alertas OFF';
                document.getElementById('notifBtn').classList.remove('active');
                clearInterval(newsInterval);
                addMsg('system', 'Alertas desactivadas.');
            }
        }

        function handleFile() {
            const file = document.getElementById('fileInput').files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                fileContent = e.target.result;
                fileName = file.name;
                document.getElementById('file-name').textContent = fileName;
                document.getElementById('clearFileBtn').style.display = 'inline';
                addMsg('system', 'Archivo cargado: ' + fileName);
            };
            reader.readAsText(file);
        }

        function clearFile() {
            fileContent = null; fileName = null;
            document.getElementById('file-name').textContent = 'Sin archivo adjunto';
            document.getElementById('clearFileBtn').style.display = 'none';
            document.getElementById('fileInput').value = '';
        }

        function toggleVoice() {
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) { alert('Usa Chrome para voz.'); return; }
            if (isListening) { recognition.stop(); return; }
            recognition = new SR();
            recognition.lang = 'es-ES';
            recognition.onstart = () => {
                isListening = true;
                document.getElementById('voiceBtn').classList.add('active');
                document.getElementById('voiceBtn').textContent = 'ESCUCHANDO';
                setStatus('ESCUCHANDO', 'active');
            };
            recognition.onresult = (e) => { input.value = e.results[0][0].transcript; send(); };
            recognition.onend = () => {
                isListening = false;
                document.getElementById('voiceBtn').classList.remove('active');
                document.getElementById('voiceBtn').textContent = 'VOZ';
                setStatus('STANDBY', '');
            };
            recognition.start();
        }

        function speak(text) {
            if (!window.speechSynthesis) return;
            window.speechSynthesis.cancel();
            var clean = text.replace(/[*#`\[\]]/g, '').substring(0, 300);
            const utt = new SpeechSynthesisUtterance(clean);
            utt.lang = 'es-ES'; utt.rate = 1.1;
            const voices = window.speechSynthesis.getVoices();
            const v = voices.find(function(v) { return v.lang.startsWith('es') && (v.name.includes('Paulina') || v.name.includes('Monica') || v.name.includes('Laura')); })
                   || voices.find(function(v) { return v.lang.startsWith('es'); });
            if (v) utt.voice = v;
            utt.onstart = () => setStatus('HABLANDO', 'speaking');
            utt.onend = () => setStatus('STANDBY', '');
            window.speechSynthesis.speak(utt);
        }

        function setStatus(text, cls) {
            status.innerHTML = '<span class="dot"></span>' + text;
            status.className = cls;
        }

        function addMsg(type, text, meta) {
            meta = meta || {};
            const div = document.createElement('div');
            div.className = 'msg ' + type;
            if (type === 'system') {
                div.textContent = text;
            } else {
                var tags = '';
                if (meta.web)  tags += '<span class="tag web">WEB</span>';
                if (meta.file) tags += '<span class="tag file">ARCHIVO</span>';
                if (meta.mem)  tags += '<span class="tag mem">MEMORIA</span>';
                if (meta.game) tags += '<span class="tag game">JUEGO</span>';
                const label = type === 'aura' ? 'AURA' : 'RAIDEN';
                div.innerHTML = '<div class="msg-header">' + label + ' ' + tags + '</div><div class="msg-body">' + text.replace(/\n/g,'<br>') + '</div>';
            }
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
            return div;
        }

        function clearChat() { chat.innerHTML = '<div class="msg system">Chat limpiado.</div>'; }

        function quickCmd(cmd) {
            input.value = cmd;
            if (cmd.endsWith(' ')) { input.focus(); } else { send(); }
        }

        async function send() {
            if (isSending) return;
            const val = input.value.trim();
            if (!val) return;
            isSending = true;
            input.value = '';
            sendBtn.disabled = true;
            sendBtn.textContent = '...';
            addMsg('user', val + (fileName ? ' [' + fileName + ']' : ''));
            if (typingEl) typingEl.classList.add('show');
            chat.scrollTop = chat.scrollHeight;
            setStatus('PROCESANDO', 'active');
            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        messages: [{ role: 'user', content: val }],
                        file_content: fileContent,
                        file_name: fileName
                    })
                });
                const data = await res.json();
                if (typingEl) typingEl.classList.remove('show');
                addMsg('aura', data.content, {
                    web: data.used_search, file: data.used_file,
                    mem: data.used_memory, game: data.used_game
                });
                speak(data.content);
            } catch(e) {
                if (typingEl) typingEl.classList.remove('show');
                addMsg('system', 'Error: ' + e.message);
            } finally {
                isSending = false;
                sendBtn.disabled = false;
                sendBtn.textContent = 'EJECUTAR';
                setStatus('STANDBY', '');
            }
        }

        async function loadMarkets() {
            addMsg('system', 'Cargando mercados...');
            try {
                const res = await fetch('/markets');
                const data = await res.json();
                addMsg('aura', data.data);
            } catch(e) {
                addMsg('system', 'Error cargando mercados.');
            }
        }

        window.speechSynthesis.onvoiceschanged = function() { window.speechSynthesis.getVoices(); };
    </script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_CHAT

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        file_content = data.get("file_content")
        file_name = data.get("file_name")
        user_query = messages[-1]['content'] if messages else ""
        used_search = used_file = used_memory = used_game = False
        file_ctx = ""
        if file_content:
            used_file = True
            file_ctx = f"\n[Archivo: {file_name}]:\n{file_content[:5000]}"
        mem_ctx = ""
        if vector_index:
            try:
                result = vector_index.query(data=user_query, top_k=1, include_metadata=True)
                for item in result:
                    mem_ctx = f"\n[Memoria]: {item.metadata.get('res')}"
                    used_memory = True
            except:
                pass

        obsidian_data = load_obsidian_memory()
        if obsidian_data["context"]:
            used_memory = True
            if mem_ctx:
                mem_ctx += "\n\n" + obsidian_data["context"]
            else:
                mem_ctx = obsidian_data["context"]
        web_ctx = ""
        keywords = [
            "busca:", "buscar", "que es", "como", "precio", "noticia",
            "noticias", "hoy", "actual", "ultimo", "ultima", "2024",
            "2025", "2026", "error", "solucion", "tutorial", "github",
            "cuanto", "quien", "donde", "importante", "reciente",
            "nuevo", "nueva", "mundial", "guerra", "tecnologia",
            "nvidia", "gpu", "cpu", "intel", "amd", "apple",
            "google", "microsoft"
        ]
        if any(k in user_query.lower() for k in keywords):
            web_ctx = smart_search(user_query.replace("busca:", "").strip())
            if web_ctx:
                used_search = True
        game_ctx = ""
        if any(k in user_query.lower() for k in ["rollercoin", "juego", "jugar", "mining"]):
            used_game = True
            game_ctx = "\n[JUEGO]: Modulo RollerCoin activo."
            if redis_client:
                try:
                    redis_client.lpush("aura_tasks", "check_game")
                except:
                    pass
        messages.insert(0, {
            "role": "system",
            "content": personality.get_system_prompt(mem_ctx, file_ctx, web_ctx) + game_ctx
        })
        ans = call_llm(messages)
        if vector_index and ans:
            try:
                vector_index.upsert(vectors=[(f"msg_{os.urandom(2).hex()}", user_query, {"res": ans})])
            except:
                pass
        return {
            "content": ans,
            "used_search": used_search,
            "used_file": used_file,
            "used_memory": used_memory,
            "used_game": used_game
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "content": f"Error: {str(e)}",
            "used_search": False,
            "used_file": False,
            "used_memory": False,
            "used_game": False
        })

@app.post("/execute")
async def execute(request: Request):
    try:
        data = await request.json()
        code = data.get("code", "")
        language = data.get("language", detect_language(code))
        stdin = data.get("stdin", "")
        if not code:
            return JSONResponse(status_code=400, content={"error": "No hay codigo"})
        result = execute_code(code, language, stdin)
        return {"result": format_result(result), "raw": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

