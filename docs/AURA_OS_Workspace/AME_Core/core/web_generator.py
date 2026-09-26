"""AURA WebFactory — Generador autónomo de sitios web."""

import json, os, shutil, hashlib, random, string, secrets
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
WEB_VAULT = BASE / "web_vault" / "generated"
WEB_VAULT.mkdir(parents=True, exist_ok=True)


class WebFactory:
    def __init__(self):
        self._reg = BASE / "web_vault" / "registry.json"
        self._registry = []
        if self._reg.exists():
            try:
                self._registry = json.loads(self._reg.read_text())
            except:
                self._registry = []

    def _save_reg(self):
        self._reg.parent.mkdir(parents=True, exist_ok=True)
        self._reg.write_text(json.dumps(self._registry, indent=2))

    def _slug(self, title: str) -> str:
        s = title.lower().strip().replace(" ", "-").replace("_", "-")
        s = "".join(c for c in s if c.isalnum() or c in "-")
        return s[:30] + "-" + secrets.token_hex(4)

    def generate(
        self,
        title: str,
        niche: str = "generico",
        style: str = "cyberpunk",
        monetize: bool = False,
        with_seo: bool = True,
    ) -> dict:
        slug = self._slug(title)
        out = WEB_VAULT / slug
        out.mkdir(parents=True, exist_ok=True)

        accent = {
            "cyberpunk": "#00ff41",
            "dark": "#3b82f6",
            "neon": "#ff00ff",
            "corp": "#ffffff",
        }.get(style, "#00ff41")
        bg = {"cyberpunk": "#0a0e17", "dark": "#111827", "neon": "#0a0e17", "corp": "#f8fafc"}.get(
            style, "#0a0e17"
        )
        fg = {"cyberpunk": "#00ff41", "dark": "#3b82f6", "neon": "#ff00ff", "corp": "#1e293b"}.get(
            style, "#00ff41"
        )
        font = "monospace" if style in ("cyberpunk", "neon") else "sans-serif"
        ad_code = (
            """<div style="background:#1a1a2e;padding:8px;text-align:center;border:1px solid #00ff41;margin:10px 0;font-family:monospace;font-size:11px;color:#00ff41">[ AD SPACE — MONETIZE HERE ]</div>"""
            if monetize
            else ""
        )
        seo_meta = (
            """<meta name="description" content="%s"><meta name="keywords" content="%s,%s,aura,web"><meta name="author" content="AURA WebFactory">"""
            % (title, niche, title)
            if with_seo
            else ""
        )

        tpl = """<!DOCTYPE html><html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
%(seo)s<title>%(title)s | AURA WebFactory</title>
<link rel="stylesheet" href="styles.css">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:%(bg)s;color:%(fg)s;font-family:%(font)s;padding:20px;line-height:1.6}
.container{max-width:1200px;margin:0 auto}
.header{border-bottom:1px solid %(accent)s;padding:20px 0;margin-bottom:30px}
.header h1{font-size:2em;color:%(accent)s;text-transform:uppercase;letter-spacing:3px}
.header .sub{color:#484f58;font-size:0.8em;margin-top:5px}
.card{background:%(bg)s;border:1px solid %(accent)s;padding:20px;margin:15px 0;border-radius:0}
.card h2{color:%(accent)s;margin-bottom:10px;font-size:1.2em}
.card p{color:#94a3b8;font-size:0.9em}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:15px}
.btn{display:inline-block;background:transparent;border:1px solid %(accent)s;color:%(accent)s;padding:10px 20px;
text-decoration:none;font-family:%(font)s;cursor:pointer;transition:all 0.3s;margin:5px}
.btn:hover{background:%(accent)s;color:%(bg)s}
.footer{margin-top:50px;padding:20px 0;border-top:1px solid %(accent)s;text-align:center;color:#484f58;font-size:0.8em}
.tag{display:inline-block;background:%(accent)s;color:%(bg)s;padding:2px 8px;font-size:0.7em;margin:2px}
%%s
</style></head><body>
<div class="container">
<div class="header"><h1>◆ %(title)s ◆</h1><div class="sub">Generado por AURA WebFactory · %(niche)s · %(style)s</div></div>
<div class="grid">
<div class="card"><h2>📊 Dashboard</h2><p>Panel de control generado dinámicamente por AURA para el nicho <strong>%(niche)s</strong>.</p></div>
<div class="card"><h2>🤖 IA Integrada</h2><p>Contenido optimizado con inteligencia artificial para máxima relevancia y engagement.</p></div>
<div class="card"><h2>⚡ Rendimiento</h2><p>Hosting estático de alta velocidad servido directamente desde AURA Orchestrator.</p></div>
</div>
%(ad)s
<script>console.log("AURA WebFactory | %(title)s | %(ts)s")</script>
<script src="app.js"></script>
<div class="footer">AURA WebFactory v1.0 · %(ts)s · <span id="status">● ONLINE</span></div>
</div></body></html>""" % {
            "title": title,
            "niche": niche,
            "style": style,
            "accent": accent,
            "bg": bg,
            "fg": fg,
            "font": font,
            "seo": seo_meta,
            "ad": ad_code,
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        css = """*{margin:0;padding:0;box-sizing:border-box}
body{background:%(bg)s;color:%(fg)s;font-family:%(font)s;padding:20px;overflow-x:hidden}
.container{max-width:1200px;margin:0 auto;animation:fadeIn 0.5s}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.header{border-bottom:1px solid %(accent)s;padding:20px 0;margin-bottom:30px}
.header h1{font-size:2em;color:%(accent)s;text-shadow:0 0 10px %(accent)s}""" % {
            "accent": accent,
            "bg": bg,
            "fg": fg,
            "font": font,
        }

        js = """document.addEventListener('DOMContentLoaded',()=>{
console.log('AURA WebFactory | Page ready');
setInterval(()=>{let e=document.getElementById('status');if(e)e.textContent='● ONLINE'},3000);
});"""

        (out / "index.html").write_text(tpl)
        (out / "styles.css").write_text(css)
        (out / "app.js").write_text(js)

        entry = {
            "slug": slug,
            "title": title,
            "niche": niche,
            "style": style,
            "monetize": monetize,
            "timestamp": datetime.now().isoformat(),
            "url": f"/webflux/{slug}/",
            "files": ["index.html", "styles.css", "app.js"],
        }
        self._registry.append(entry)
        self._save_reg()
        return entry

    def list_pages(self) -> list:
        return self._registry

    def remove(self, slug: str) -> bool:
        out = WEB_VAULT / slug
        if out.exists():
            shutil.rmtree(out)
        self._registry = [e for e in self._registry if e["slug"] != slug]
        self._save_reg()
        return True


_factory = WebFactory()


def generate_page(title, niche="generico", style="cyberpunk", monetize=False):
    return _factory.generate(title, niche, style, monetize)


def list_pages():
    return _factory.list_pages()
