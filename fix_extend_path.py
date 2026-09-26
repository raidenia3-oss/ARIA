import os

aura_backend = "AURA_APP/backend"
project_backend = "backend"

dirs_to_fix = [
    "agent", "agents", "api", "automation", "core",
    "evolution", "memory", "mobile", "plugins", "vision",
]

for rel_dir in dirs_to_fix:
    init_path = os.path.join(aura_backend, rel_dir, "__init__.py")
    if rel_dir == ".":
        init_path = os.path.join(aura_backend, "__init__.py")

    with open(init_path, "r") as f:
        content = f.read().strip()

    if "extend_path" in content:
        print(f"SKIP (has extend): {rel_dir}")
        continue

    if not content:
        # Empty - just add extend_path
        new_content = "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"
    elif content.startswith("from pkgutil"):
        print(f"SKIP: {rel_dir}")
        continue
    else:
        # Has content - prepend extend_path
        new_content = "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n\n" + content

    with open(init_path, "w") as f:
        f.write(new_content)
    print(f"FIXED: {rel_dir} -> {len(new_content)}L")
