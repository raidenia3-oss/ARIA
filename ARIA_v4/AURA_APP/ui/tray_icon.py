"""Tray Icon — System tray + hotkeys"""

try:
    import pystray
    from PIL import Image
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


class TrayIcon:
    """System tray icon for ARIA"""

    def __init__(self, engine=None):
        self.engine = engine
        self.icon = None

    def create(self, name: str = "ARIA") -> None:
        if not PYSTRAY_AVAILABLE:
            print("[TrayIcon] pystray no disponible")
            return

        # Create simple icon
        image = Image.new('RGB', (64, 64), color=(40, 40, 80))

        menu = pystray.Menu(
            pystray.MenuItem('Prendete', self._activate),
            pystray.MenuItem('Salir', self._exit),
        )

        self.icon = pystray.Icon(name, image, "ARIA OS v4.0", menu)
        self.icon.run()

    def _activate(self, icon, item):
        if self.engine:
            import asyncio
            asyncio.run(self.engine.process_input("prendete"))

    def _exit(self, icon, item):
        icon.stop()

    def stop(self):
        if self.icon:
            self.icon.stop()
