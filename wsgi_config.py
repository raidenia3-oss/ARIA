import sys
import os

path = '/home/USERNAME/aura'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

from backend.main import app

application = app
