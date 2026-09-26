from pathlib import Path

PROJECT_ROOT = Path(".").resolve()
AURA_APP = PROJECT_ROOT / "AURA_APP"

# Add extend_path at END of project root backend __init__.py files
# so they can find sibling modules in AURA_APP/backend/
fixed = 0
for init_file in sorted(PROJECT_ROOT.glob("backend/*/__init__.py")):
    content = init_file.read_text()
    if "extend_path" not in content and content.strip():
        init_file.write_text(content.rstrip() + "\n\nfrom pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n")
        fixed += 1
        print(f"Fixed: {init_file}")

# Same for AURA_APP subdirs (only those without extend_path)
for init_file in sorted(AURA_APP.glob("backend/*/__init__.py")):
    content = init_file.read_text()
    if "extend_path" not in content and content.strip():
        init_file.write_text(content.rstrip() + "\n\nfrom pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n")
        fixed += 1
        print(f"Fixed: {init_file}")

print(f"\nTotal fixed: {fixed}")
