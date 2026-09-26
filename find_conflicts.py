import os

aura_backend = "AURA_APP/backend"
project_backend = "backend"

conflicts = []
for root, dirs, files in os.walk(aura_backend):
    if "__init__.py" in files:
        rel = os.path.relpath(root, aura_backend)
        project_path = os.path.join(project_backend, rel, "__init__.py")
        if os.path.exists(project_path):
            with open(os.path.join(root, "__init__.py"), "r") as f:
                aura_content = f.read().strip()
            with open(project_path, "r") as f:
                project_content = f.read().strip()
            has_extend = "extend_path" in aura_content
            conflicts.append((rel, len(aura_content), len(project_content), has_extend))

print("Directories with __init__.py in BOTH backends:")
for d, al, pl, he in conflicts:
    print(f"  {d}: AURA={al}L, Proj={pl}L, extend={he}")
