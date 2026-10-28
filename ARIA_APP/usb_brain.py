"""USB Brain: ARIA usa el USB 'ARIA-USB' como disco-cerebro portatil.

Detecta la unidad, carga modelos GGUF, memoria SQLite y skills desde ella,
y sincroniza datos cuando esta conectada. Todo local, sin red.
"""
import os
import glob


def find_usb() -> str | None:
    """Devuelve la letra de unidad (ej. 'E:\\') del USB etiquetado ARIA-USB."""
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if os.path.exists(root):
            try:
                import ctypes
                buf = ctypes.create_unicode_buffer(261)
                ctypes.windll.kernel32.GetVolumeInformationW(root, buf, 261, None, None, None, None, 0)
                if buf.value == "ARIA-USB":
                    return root
            except Exception:
                pass
    return None


def list_models(usb_root: str) -> list:
    return glob.glob(os.path.join(usb_root, "models", "*.gguf"))


def memory_path(usb_root: str) -> str:
    return os.path.join(usb_root, "memory", "aria_memory.db")


def skills_dir(usb_root: str) -> str:
    return os.path.join(usb_root, "skills")


def status() -> dict:
    root = find_usb()
    if not root:
        return {"status": "no_usb", "message": "USB ARIA-USB no detectado"}
    models = list_models(root)
    mem = memory_path(root)
    return {
        "status": "ok",
        "root": root,
        "models": [os.path.basename(m) for m in models],
        "memory_exists": os.path.exists(mem),
        "skills_dir": skills_dir(root),
    }
EOF