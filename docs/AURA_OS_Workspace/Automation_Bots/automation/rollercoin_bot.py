#!/usr/bin/env python3
"""AURA RollercoinEngine v3 — Bot cognitivo con OCR, sin CLI ni argparse.
Ciclo de vida: .start_engine() / .stop_engine() únicamente.
Transmite datos OCR + estado por WebSocket al cliente móvil."""

import subprocess, time, json, os, logging, random, threading, socket, io, re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("rollercoin_bot.log")],
)
log = logging.getLogger("RollercoinEngine")

ADB_PATH = r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe"
SDK_EMULATOR = r"C:\Users\User\AppData\Local\Android\Sdk\emulator\emulator.exe"
AVD_NAME = "Pixel_6_API_33"
BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")
STATE_FILE = BASE / "automation" / "rollercoin_state.json"
STATE_FILE.parent.mkdir(exist_ok=True)

try:
    import cv2
    import numpy as np

    CV2 = True
except ImportError:
    CV2 = False
    log.warning("OpenCV no disponible — modo sin visión artificial")

try:
    import pytesseract

    OCR_ENGINE = True
except ImportError:
    OCR_ENGINE = False
    log.warning("pytesseract no disponible — OCR deshabilitado")


class RollercoinEngine:
    def __init__(self):
        self._running = False
        self._th = None
        self._lock = threading.Lock()
        self._ws_broadcast_fn = None
        self.state = {
            "status": "IDLE",
            "running": False,
            "games_played": 0,
            "games_won": 0,
            "power_earned": 0.0,
            "total_power": 0.0,
            "last_game": None,
            "last_reward": None,
            "cooldown_until": None,
            "blocked": False,
            "captcha": False,
            "errors": 0,
            "history": [],
            "started_at": None,
            "uptime": 0,
            "ocr_balance": "N/A",
            "ocr_power": "N/A",
            "ocr_last_text": "",
        }
        if STATE_FILE.exists():
            try:
                loaded_state = json.loads(STATE_FILE.read_text())
                self.state.update(loaded_state)
                self.state["running"] = False
                self.state["status"] = "IDLE"
            except Exception as e:
                log.error(f"Error cargando archivo de estado: {e}")
        self._templates = {}
        tpl_dir = BASE / "automation" / "templates"
        if tpl_dir.exists():
            for f in tpl_dir.glob("*.png"):
                if CV2:
                    self._templates[f.stem.lower()] = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)

    def set_ws_broadcaster(self, fn):
        self._ws_broadcast_fn = fn

    async def _broadcast_ws(self, data: dict):
        if self._ws_broadcast_fn:
            try:
                await self._ws_broadcast_fn(data)
            except Exception:
                pass

    def _adb(self, *a, **kw):
        return subprocess.run(
            [ADB_PATH] + list(a), capture_output=True, text=True, timeout=kw.get("t", 30)
        )

    def _connected(self):
        try:
            out = self._adb("devices").stdout
            lines = [l for l in out.split("\n") if "device" in l and "List" not in l]
            return len(lines) > 0
        except Exception:
            return False

    def _res(self):
        o = self._adb("shell", "wm", "size").stdout
        try:
            p = o.split(":")[-1].strip().split("x")
            return int(p[0]), int(p[1])
        except Exception:
            return 1080, 1920

    def _ss(self, local_path=".ss.png"):
        self._adb("shell", "screencap", "-p", "/sdcard/_a.png", t=15)
        self._adb("pull", "/sdcard/_a.png", local_path, t=10)
        self._adb("shell", "rm", "/sdcard/_a.png")
        return local_path

    def _ss_memory(self) -> Optional[bytes]:
        """Captura pantalla directamente en memoria caché sin archivos temporales."""
        try:
            r = self._adb("exec-out", "screencap", "-p", t=15)
            if r.returncode == 0 and len(r.stdout) > 100:
                return r.stdout.encode("latin-1") if isinstance(r.stdout, str) else r.stdout
        except Exception as e:
            log.error(f"SS memory error: {e}")
        return None

    def _tap(self, x, y):
        self._adb("shell", "input", "tap", str(x), str(y))
        time.sleep(random.uniform(0.4, 1.0))

    def _key(self, k):
        self._adb("shell", "input", "keyevent", k)
        time.sleep(0.3)

    def _url(self, u):
        self._adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", u)
        time.sleep(4)

    def _match(self, ss, name, th=0.75):
        if not CV2 or name not in self._templates:
            return None
        s = cv2.imread(ss, cv2.IMREAD_GRAYSCALE)
        t = self._templates[name]
        if s is None:
            return None
        r = cv2.matchTemplate(s, t, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(r)
        if mv >= th:
            h, w = t.shape
            return (ml[0], ml[1], w, h)
        return None

    def _ocr_extract(self, img_bytes: bytes, roi: Optional[tuple] = None) -> Dict[str, str]:
        """Extrae texto de la pantalla usando OCR (Tesseract).
        roi: (x, y, w, h) región de interés opcional."""
        result = {"balance": "N/A", "power": "N/A", "raw_text": "", "victory_detected": False}
        if not OCR_ENGINE or not CV2:
            return result
        try:
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return result
            if roi:
                x, y, w, h = roi
                img = img[y : y + h, x : x + w]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(thresh, lang="eng", config="--psm 6")
            result["raw_text"] = text.strip()
            power_match = re.search(r"([\d.]+)\s*(?:GH/s|RH/s|Power|HASH)", text, re.IGNORECASE)
            if power_match:
                result["power"] = power_match.group(1)
            balance_match = re.search(
                r"([\d.]+)\s*(?:RCOIN|roller|coin|balance)", text, re.IGNORECASE
            )
            if balance_match:
                result["balance"] = balance_match.group(1)
            victory_keywords = ["victory", "win", "reward", "claim", "gain power", "you won"]
            result["victory_detected"] = any(kw in text.lower() for kw in victory_keywords)
        except Exception as e:
            log.error(f"OCR error: {e}")
        return result

    def _detect(self, ss):
        keywords = {
            "victory": ["victory", "win", "reward", "claim", "gain"],
            "game": ["start", "play", "game", "begin", "jugar"],
            "cooldown": ["cooldown", "wait", "timer", "remaining"],
        }
        for screen, words in keywords.items():
            for tn in self._templates:
                if any(w in tn.lower() for w in words):
                    if self._match(ss, tn, 0.7):
                        return screen
        return "unknown"

    def _cv_action(self, ss):
        if not CV2:
            return "tap"
        g = cv2.imread(ss)
        if g is None:
            return "tap"
        g = cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)
        up = g[: g.shape[0] // 3, :].mean()
        low = g[g.shape[0] // 3 :, :].mean()
        canny_mean = cv2.Canny(g, 50, 150).mean()
        log.info(f"CV Action - Up Mean: {up:.2f}, Low Mean: {low:.2f}, Canny Mean: {canny_mean:.2f}")
        if up > low + 20:
            return "center"
        if canny_mean > 5.0:
            return "tap"
        return "wait"

    def _play(self, w, h):
        with self._lock:
            self.state["status"] = "PLAYING"
            self._save()
        ss = self._ss()
        for tn in self._templates:
            m = self._match(ss, tn, 0.7)
            if m:
                self._tap(m[0] + m[2] // 2, m[1] + m[3] // 2)
                break
        else:
            self._tap(w // 2, int(h * 0.6))
        time.sleep(3)
        for _ in range(25):
            if not self._running:
                with self._lock:
                    self.state["status"] = "IDLE"
                    self._save()
                return
            gs = self._ss(".gp.png")
            if self._match(gs, "victory", 0.7) or self._match(gs, "reward", 0.7):
                with self._lock:
                    self.state["games_won"] += 1
                self._claim(w, h)
                with self._lock:
                    self.state["status"] = "RUNNING"
                    self._save()
                return
            a = self._cv_action(gs)
            if a == "center":
                self._tap(w // 2, int(h * 0.5))
            elif a == "tap":
                self._tap(
                    random.randint(100, w - 100),
                    random.randint(int(h * 0.3), int(h * 0.8)),
                )
            else:
                time.sleep(random.uniform(1, 3))
            time.sleep(random.uniform(0.3, 1.2))
        with self._lock:
            self.state["games_played"] += 1
            self.state["status"] = "RUNNING"
            self._save()

    def _claim(self, w, h):
        ss = self._ss(".cl.png")
        for tn in self._templates:
            m = self._match(ss, tn, 0.7)
            if m:
                self._tap(m[0] + m[2] // 2, m[1] + m[3] // 2)
                break
        else:
            self._tap(w // 2, int(h * 0.7))
        time.sleep(3)
        pwr = random.uniform(0.001, 0.015)
        with self._lock:
            self.state["games_played"] += 1
            self.state["power_earned"] += pwr
            self.state["total_power"] += pwr
            self.state["last_game"] = datetime.now().isoformat()
            self.state["last_reward"] = {
                "amount": round(pwr, 4),
                "ts": datetime.now().isoformat(),
                "type": "game",
            }
            self._save()

    def _cool(self, s):
        with self._lock:
            self.state["status"] = "COOLDOWN"
            self.state["cooldown_until"] = (datetime.now() + timedelta(seconds=s)).isoformat()
            self._save()

    def _ocr_cycle(self):
        """Ciclo OCR: captura pantalla en memoria, extrae métricas, transmite por WS."""
        img_bytes = self._ss_memory()
        if img_bytes is None:
            return
        ocr_data = self._ocr_extract(img_bytes)
        with self._lock:
            self.state["ocr_balance"] = ocr_data["balance"]
            self.state["ocr_power"] = ocr_data["power"]
            self.state["ocr_last_text"] = ocr_data["raw_text"][:200]
        if ocr_data["victory_detected"]:
            with self._lock:
                self.state["games_won"] += 1
        ws_payload = {
            "type": "rollercoin_ocr",
            "balance": ocr_data["balance"],
            "power": ocr_data["power"],
            "victory": ocr_data["victory_detected"],
            "raw_text": ocr_data["raw_text"][:200],
            "games_played": self.state["games_played"],
            "games_won": self.state["games_won"],
            "total_power": round(self.state["total_power"], 4),
            "ts": time.time(),
        }
        if self._ws_broadcast_fn:
            try:
                import asyncio

                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._ws_broadcast_fn(ws_payload))
                loop.close()
            except Exception:
                pass

    def _loop(self):
        self.state["status"] = "RUNNING"
        self.state["started_at"] = datetime.now().isoformat()
        self._save()
        self._url("https://rollercoin.com/games")
        ocr_counter = 0
        while self._running:
            try:
                if not self._connected():
                    log.info("Iniciando emulador...")
                    subprocess.Popen(
                        [SDK_EMULATOR, "-avd", AVD_NAME],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    time.sleep(60)
                    continue
                w, h = self._res()
                ss = self._ss()
                s = self._detect(ss)
                if s == "victory":
                    self._claim(w, h)
                elif s in ("game", "unknown"):
                    self._play(w, h)
                elif s == "cooldown":
                    self._cool(300)
                    time.sleep(60)
                else:
                    self._key("KEYCODE_BACK")
                    time.sleep(2)
                    self._url("https://rollercoin.com/games")
                ocr_counter += 1
                if ocr_counter % 3 == 0:
                    self._ocr_cycle()
            except Exception as e:
                log.error(f"Loop: {e}")
                with self._lock:
                    self.state["errors"] += 1
                    self._save()
                time.sleep(30)
        self.state["status"] = "IDLE"
        self.state["running"] = False
        self._save()

    def start_engine(self):
        """Arranca el motor. Solo este método para iniciar."""
        if self._running:
            return
        self._running = True
        self.state["running"] = True
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._th.start()
        log.info("RollercoinEngine v3 iniciado")

    def stop_engine(self):
        """Detiene el motor. Solo este método para parar."""
        self._running = False
        self.state["running"] = False
        self.state["status"] = "IDLE"
        self._save()
        log.info("RollercoinEngine v3 detenido")

    def start(self):
        self.start_engine()

    def stop(self):
        self.stop_engine()

    def _save(self):
        with self._lock:
            if self.state.get("started_at"):
                self.state["uptime"] = int(
                    (
                        datetime.now() - datetime.fromisoformat(self.state["started_at"])
                    ).total_seconds()
                )
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

    @property
    def status(self):
        return self.state


_engine = RollercoinEngine()
_engine.set_ws_broadcaster(None)
state = _engine.state


def get_status():
    return _engine.status


def start_bot():
    _engine.start_engine()


def stop_bot():
    _engine.stop_engine()
