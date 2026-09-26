# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['ollama', 'httpx', 'dotenv', 'PyQt5', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui', 'keyboard', 'pystray', 'PIL', 'ai_providers', 'desktop_ui', 'backend.skills.registry', 'backend.tool_registry', 'backend.agent.core', 'backend.memory.short_term', 'backend.aria_brain', 'backend.connectors']
hiddenimports += collect_submodules('backend')


a = Analysis(
    ['C:/Users/User/Downloads/AURA/ARIA_APP/aria_main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/User/Downloads/AURA/ARIA_APP/.env', '.'), ('C:/Users/User/Downloads/AURA/ARIA_APP/ai_providers.py', '.'), ('C:/Users/User/Downloads/AURA/ARIA_APP/data', 'data'), ('C:/Users/User/Downloads/AURA/ARIA_APP/frontend', 'frontend')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'sklearn', 'scipy', 'pandas', 'numpy', 'transformers', 'sentence_transformers', 'faiss', 'chromadb', 'weasyprint', 'matplotlib', 'seaborn', 'psycopg2', 'redis', 'boto3', 'tkinter', '_tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ARIA OS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
