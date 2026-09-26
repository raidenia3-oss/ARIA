import sys
sys.path.insert(0, '.')

from fastapi import FastAPI
from backend.brain_router import router as brain_router
from backend.narrative_routes import router as narrative_router

app = FastAPI()

print('Before include - Routes:', len(app.routes))
app.include_router(brain_router)
print('After brain_router - Routes:', len(app.routes))
for route in app.routes:
    if hasattr(route, 'path'):
        print(route.path, route.methods)

app.include_router(narrative_router)
print('After narrative_router - Routes:', len(app.routes))
for route in app.routes:
    if hasattr(route, 'path') and 'narrative' in route.path:
        print('FOUND:', route.path, route.methods)
