# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/User/Downloads/AURA/main_launcher_prod.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/User/AppData/Local/Temp/aura_build_elog2rgk/app', 'aura_app_data')],
    hiddenimports=['backend', 'backend.main', 'backend.orchestrator', 'backend.brain_orchestrator', 'backend.services.audio_pipeline', 'backend.services.tts_engine', 'backend.services.vision_engine', 'backend.services.action_engine', 'backend.services.memory_engine', 'backend.services.swarm_orchestrator', 'backend.services.quickshell_bridge', 'frontend', 'frontend.web_dashboard', 'frontend.quickshell_widgets', 'mobile_client', 'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'passlib.handlers.bcrypt'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'torchao', 'transformers', 'tensorflow', 'triton', 'matplotlib', 'pandas', 'pyarrow', 'gradio', 'datasets', 'bitsandbytes', 'boto3', 'botocore', 'altair', 'narwhals', 'lxml', 'openpyxl', 'tkinter', 'tensorboard', 'pysqlite2', 'MySQLdb', 'gi'],
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
    name='AURA_desktop',
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
