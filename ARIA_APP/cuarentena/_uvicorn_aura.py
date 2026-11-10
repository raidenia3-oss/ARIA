import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import uvicorn
import aura_runner
uvicorn.run(aura_runner.app, host="0.0.0.0", port=8000, log_level="error")
