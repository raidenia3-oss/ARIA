"""ARIA Observer — System monitoring in real time."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import win32gui

    try:
        import win32process
    except ImportError:
        win32process = None
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import websocket

    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False


class AriaObserver:
    """Monitors system activity in real time and streams via WebSocket."""

    def __init__(self, backend_url: str = "http://localhost:8000", poll_interval: int = 2):
        self.backend_url = backend_url
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._proc_thread: Optional[threading.Thread] = None
        self._db_path = str(Path.home() / ".aria" / "activity_log.db")
        self._init_db()
        self._activity_log: List[Dict[str, Any]] = []
        self._current_app = ""
        self._app_start_time: Optional[float] = None
        self._ws_url = backend_url.replace("http", "ws") + "/api/aria/observe"
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, float] = {}
        self._cache_ttl = 30
        self._ws: Optional[Any] = None
        self._ws_connected = False
        self._context_cache: Dict[str, Any] = {}
        self._context_cache_time: Optional[float] = None
        self._context_cache_ttl = 3.0

    def _init_db(self) -> None:
        Path(os.path.dirname(self._db_path)).mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                app_name TEXT,
                activity_type TEXT,
                details TEXT,
                duration REAL
            )
        """)
        conn.commit()
        conn.close()

    def _log_activity(
        self, app_name: str, activity_type: str, details: str = "", duration: float = 0.0
    ) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO activity_log (timestamp, app_name, activity_type, details, duration) VALUES (?, ?, ?, ?, ?)",
            (time.time(), app_name, activity_type, details, duration),
        )
        conn.commit()
        conn.close()
        self._activity_log.append(
            {
                "timestamp": time.time(),
                "app_name": app_name,
                "activity_type": activity_type,
                "details": details,
                "duration": duration,
            }
        )
        if len(self._activity_log) > 5000:
            self._activity_log = self._activity_log[-3000:]

    def _track_app(self) -> None:
        while self._running:
            try:
                if HAS_WIN32:
                    hwnd = win32gui.GetForegroundWindow()
                    title = win32gui.GetWindowText(hwnd) or "Unknown"
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    except Exception:
                        pid = 0
                else:
                    title = (
                        os.popen("xdotool getactivewindow getwindowname 2>/dev/null").read().strip()
                        or "Unknown"
                    )
                    pid = 0

                now = time.time()
                if title != self._current_app:
                    if self._current_app and self._app_start_time:
                        duration = now - self._app_start_time
                        self._log_activity(self._current_app, "app_focus", title, duration)
                    self._current_app = title
                    self._app_start_time = now
                    self._log_activity(title, "app_focus", f"Window: {title}")
                    self._emit("app_focus", {"app_name": title, "window_title": title, "pid": pid})

            except Exception:
                pass
            time.sleep(self.poll_interval)

    def _poll_processes(self) -> None:
        while self._running:
            try:
                procs = []
                if HAS_PSUTIL:
                    for p in psutil.process_iter(["name", "pid", "memory_info"]):
                        try:
                            info = p.info
                            mem = (
                                (info["memory_info"].rss / 1048576)
                                if info.get("memory_info")
                                else 0
                            )
                            procs.append(
                                {
                                    "name": info["name"],
                                    "pid": info["pid"],
                                    "memory_mb": round(mem, 1),
                                }
                            )
                        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                            pass
                else:
                    output = os.popen("ps aux --sort=-%mem 2>/dev/null | head -20").read().strip()
                    for line in output.split("\n")[1:10]:
                        parts = line.split()
                        if len(parts) >= 11:
                            procs.append(
                                {"name": parts[10], "pid": parts[1], "memory_mb": parts[5]}
                            )
                self._emit("processes", {"processes": procs[:20], "timestamp": time.time()})
            except Exception:
                pass
            time.sleep(self.poll_interval * 3)

    def _connect_ws(self) -> None:
        if not HAS_WEBSOCKET or self._ws_connected:
            return
        try:
            self._ws = websocket.create_connection(self._ws_url, timeout=2)
            self._ws_connected = True
        except Exception:
            self._ws = None
            self._ws_connected = False

    def _emit(self, event: str, data: Dict[str, Any]) -> None:
        data["event"] = event
        data["timestamp"] = time.time()
        if not self._ws_connected:
            self._connect_ws()
        try:
            if self._ws and self._ws_connected:
                self._ws.send(json.dumps(data))
        except Exception:
            self._ws_connected = False
            self._ws = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._track_app, daemon=True)
        self._thread.start()
        if HAS_PSUTIL or not HAS_WIN32:
            self._proc_thread = threading.Thread(target=self._poll_processes, daemon=True)
            self._proc_thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._proc_thread:
            self._proc_thread.join(timeout=2)
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _cached(self, key: str, func, ttl: int = None) -> Any:
        now = time.time()
        ttl = ttl or self._cache_ttl
        if key in self._cache and (now - self._cache_time.get(key, 0)) < ttl:
            return self._cache[key]
        result = func()
        self._cache[key] = result
        self._cache_time[key] = now
        return result

    def get_active_window(self) -> Dict[str, Any]:
        try:
            if HAS_WIN32:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd) or "Unknown"
                return {"app_name": title, "window_title": title, "pid": 0}
            else:
                title = (
                    os.popen("xdotool getactivewindow getwindowname 2>/dev/null").read().strip()
                    or "Unknown"
                )
                return {"app_name": title, "window_title": title, "pid": 0}
        except Exception:
            return {"app_name": "Unknown", "window_title": "Unknown", "pid": 0}

    def get_open_files(self) -> List[Dict[str, str]]:
        return self._cached("open_files", lambda: self._get_open_files_impl())

    def _get_open_files_impl(self) -> List[Dict[str, str]]:
        files = []
        try:
            if HAS_PSUTIL:
                for p in psutil.process_iter(["name", "open_files"]):
                    try:
                        of = p.info.get("open_files")
                        if of:
                            for f in of[:5]:
                                files.append(
                                    {
                                        "file_path": f.path,
                                        "file_type": (
                                            f.path.split(".")[-1] if "." in f.path else "unknown"
                                        ),
                                    }
                                )
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        pass
            else:
                output = os.popen("lsof 2>/dev/null | head -30").read().strip()
                for line in output.split("\n")[1:]:
                    parts = line.split()
                    if len(parts) >= 9:
                        files.append(
                            {
                                "file_path": parts[8],
                                "file_type": (
                                    parts[8].split(".")[-1] if "." in parts[8] else "unknown"
                                ),
                            }
                        )
        except Exception:
            pass
        return files[:50]

    def get_recent_processes(self) -> List[Dict[str, Any]]:
        return self._cached("recent_procs", lambda: self._get_recent_processes_impl())

    def _get_recent_processes_impl(self) -> List[Dict[str, Any]]:
        procs = []
        try:
            if HAS_PSUTIL:
                for p in psutil.process_iter(["name", "create_time", "memory_info"]):
                    try:
                        info = p.info
                        procs.append(
                            {
                                "name": info["name"],
                                "create_time": info.get("create_time", 0),
                                "memory_mb": (
                                    round(info["memory_info"].rss / 1048576, 1)
                                    if info.get("memory_info")
                                    else 0
                                ),
                            }
                        )
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        pass
            procs.sort(key=lambda x: x.get("create_time", 0), reverse=True)
        except Exception:
            pass
        return procs[:10]

    def get_search_context(self) -> Dict[str, Any]:
        return self._cached("search", lambda: self._get_search_context_impl())

    def _get_search_context_impl(self) -> Dict[str, Any]:
        searches = []
        urls = []
        try:
            browser_path = Path.home() / ".config" / "chromium" / "Default" / "History"
            if not browser_path.exists():
                browser_path = (
                    Path.home()
                    / "AppData"
                    / "Local"
                    / "Google"
                    / "Chrome"
                    / "User Data"
                    / "Default"
                    / "History"
                )
            if browser_path.exists():
                import sqlite3 as _sqlite3

                conn = _sqlite3.connect(str(browser_path))
                rows = conn.execute(
                    "SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 10"
                ).fetchall()
                conn.close()
                for url, title in rows:
                    urls.append({"url": url, "title": title})
                    if any(s in url.lower() for s in ["search", "google", "bing", "duckduckgo"]):
                        searches.append({"query": url, "title": title})
        except Exception:
            pass
        return {"searches": searches, "urls_visited": urls}

    def get_keyboard_activity(self) -> Dict[str, Any]:
        try:
            if HAS_WIN32:
                try:
                    import ctypes

                    layout = ctypes.windll.user32.GetKeyboardLayout(0)
                    return {"layout": str(layout), "note": "Windows keyboard layout detected"}
                except Exception:
                    return {"layout": "windows", "note": "Windows active"}
            else:
                return {"layout": "default", "note": "Keyboard activity monitoring active"}
        except Exception:
            return {"layout": "unknown", "note": "No keyboard access"}

    def build_context(self) -> Dict[str, Any]:
        now = time.time()
        if (self._context_cache and
            self._context_cache_time and
            (now - self._context_cache_time) < self._context_cache_ttl):
            return self._context_cache
        window = self.get_active_window()
        files = self.get_open_files()
        procs = self.get_recent_processes()
        search = self.get_search_context()
        kb = self.get_keyboard_activity()
        result = {
            "activity": "active",
            "current_app": window.get("app_name", "Unknown"),
            "window_title": window.get("window_title", "Unknown"),
            "open_files": files[:10],
            "recent_processes": procs[:5],
            "searches": search.get("searches", [])[:5],
            "urls_visited": search.get("urls_visited", [])[:5],
            "keyboard": kb,
            "timestamp": time.time(),
        }
        self._context_cache = result
        self._context_cache_time = now
        return result
