import os, sys
sys.path.insert(0, 'C:\\Users\\User\\Downloads\\AURA')
os.environ['HF_HOME'] = 'C:\\Users\\User\\.cache\\huggingface'
print('STARTING')
from backend.main import app
print('IMPORT OK')
import uvicorn
print('SERVING')
uvicorn.run(app, host='127.0.0.1', port=8000, log_level='info')