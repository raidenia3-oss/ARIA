import subprocess
import sys
import os


def instalar():
    jarvis_dir = r"C:\Users\User\Downloads\JARVIS"
    if not os.path.exists(jarvis_dir):
        subprocess.run(
            ["git", "clone", "https://github.com/pausiar/JARVIS", jarvis_dir], check=True
        )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "PySide6",
            "requests",
            "psutil",
            "keyboard",
            "pynput",
            "pyautogui",
            "faster-whisper",
            "numpy",
            "sounddevice",
            "pycaw",
            "comtypes",
            "PyMuPDF",
            "python-docx",
            "openpyxl",
            "Pillow",
            "websockets",
        ],
        check=True,
    )
    print("JARVIS-HRZ instalado")


if __name__ == "__main__":
    instalar()
