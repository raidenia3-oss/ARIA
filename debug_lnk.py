# -*- coding: utf-8 -*-
"""Debug shortcut resolution."""
import subprocess, os

lnk = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Godot_v4.lnk')
print('LNK exists:', os.path.exists(lnk))

# Try with single quotes
ps = f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}').Targetpath"
r = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, timeout=10)
print('stdout:', repr(r.stdout.strip()))
print('stderr:', repr(r.stderr.strip()[:300]))
print('rc:', r.returncode)