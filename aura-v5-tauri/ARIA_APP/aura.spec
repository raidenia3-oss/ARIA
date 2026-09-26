# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.builders.main import Analysis, EXE, COLLECT

a = Analysis(
    pathex=[r"C:\Users\User\Downloads\AURA\ARIA_APP", r"C:\Users\User\Downloads\AURA"],
    binaries=[],
    datas=[
        (r"C:\Users\User\Downloads\AURA\ARIA_APP\.env", "."),
        (r"C:\Users\User\Downloads\AURA\ARIA_APP\data", "./data"),
        (r"C:\Users\User\Downloads\AURA\ARIA_APP\frontend", "./frontend"),
    ],
    hiddenimports=[
        "ollama", "httpx", "dotenv",
        "PyQt5", "PyQt5.QtWidgets", "PyQt5.QtCore", "PyQt5.QtGui",
        "keyboard", "pystray", "PIL",
        "ai_providers",
        "backend.skills.registry",
        "backend.tool_registry",
        "backend.agent.core",
        "backend.memory.short_term",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "torch", "torchvision", "torchaudio",
        "sklearn", "scipy", "pandas", "numpy",
        "transformers", "sentence_transformers",
        "faiss", "chromadb", "weasyprint",
        "matplotlib", "seaborn",
        "psycopg2", "redis", "boto3",
        "tkinter", "_tkinter",
    ],
)
pyz = None
exe = EXE(
    a.pure,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ARIA OS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
