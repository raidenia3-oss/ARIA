import sys
import os

base = r"C:\Users\User\Downloads\AURA\ARIA_APP"
parent = str(os.path.join(base, ".."))

sys.path.insert(0, parent)
sys.path.insert(0, base)
os.chdir(base)

try:
    from backend.app import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("ERROR:", e)
    sys.exit(1)
