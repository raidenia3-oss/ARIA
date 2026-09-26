import sys, os, uvicorn
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ARIA_APP.backend.app import app
print('Starting server...')
uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
