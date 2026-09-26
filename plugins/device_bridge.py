"""AURA Device Bridge Plugin — sync, Chrome bridge, and remote app control."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from aura_plugin_system import AuraPlugin


class DeviceBridgePlugin(AuraPlugin):
    def get_name(self) -> str:
        return "Device Bridge"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return "Cross-device sync, Chrome bridge, and remote app introspection/control"

    def get_tab(self):
        try:
            import tkinter as tk
            from tkinter import ttk
            frame = tk.Frame(self.app.nb, bg=self.app.BG)
            self.app.nb.add(frame, text="Devices")

            top = tk.Frame(frame, bg=self.app.BG)
            top.pack(fill=tk.X, padx=12, pady=12)

            tk.Button(top, text="Discover", command=self._discover, bg=self.app.ACCENT2, fg="white", font=self.app.FONT_BOLD, relief=tk.FLAT, padx=12).pack(side=tk.LEFT, padx=(0, 8))
            tk.Button(top, text="Sync", command=self._sync, bg=self.app.ACCENT, fg="white", font=self.app.FONT_BOLD, relief=tk.FLAT, padx=12).pack(side=tk.LEFT, padx=(0, 8))
            tk.Button(top, text="Bridge Chrome", command=self._bridge_chrome, bg=self.app.PANEL, fg=self.app.TEXT, font=self.app.FONT_BOLD, relief=tk.FLAT, padx=12).pack(side=tk.LEFT)

            self.device_list = tk.Text(frame, bg=self.app.PANEL, fg=self.app.TEXT, font=self.app.FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT)
            scroll = ttk.Scrollbar(frame, command=self.device_list.yview)
            self.device_list.configure(yscrollcommand=scroll.set)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            self.device_list.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

            self.bridge = None
            self._append("[READY] Device Bridge loaded")
            return frame
        except Exception as e:
            self._append(f"[ERROR] Device Bridge tab: {e}")
            return None

    def on_load(self) -> None:
        try:
            from device_bridge import DeviceBridge
            self.bridge = DeviceBridge()
            self.bridge.start()
            self._append("[STARTED] Device bridge server")
        except Exception as e:
            self._append(f"[ERROR] Device bridge: {e}")

    def on_unload(self) -> None:
        if self.bridge:
            self.bridge.stop()

    def _append(self, text: str) -> None:
        try:
            w = getattr(self, "device_list", None)
            if not w:
                return
            w.config(state=tk.NORMAL)
            w.insert(tk.END, text + "\n")
            w.see(tk.END)
            w.config(state=tk.DISABLED)
        except Exception:
            pass

    def _discover(self) -> None:
        if not self.bridge:
            return
        devices = self.bridge.discover_devices()
        self._append(f"[DEVICES] {len(devices)} found")
        for d in devices:
            self._append(f"  - {d['name']} ({d['platform']}) {d['ip']}:{d['port']}")

    def _sync(self) -> None:
        self._append("[SYNC] Starting device sync...")
        if not self.bridge:
            return
        devices = self.bridge.discover_devices()
        for d in devices:
            apps = self.bridge.get_device_apps(d["device_id"])
            self._append(f"[SYNC] {d['name']}: {len(apps)} apps")

    def _bridge_chrome(self) -> None:
        self._append("[CHROME] Bridge requested. Ensure AURA Bridge extension is installed and port 48799 is open.")
        self._append("[CHROME] Install: chrome://extensions -> Load unpacked -> chrome-extension/")
