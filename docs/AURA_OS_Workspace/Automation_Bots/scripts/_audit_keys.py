import os
import re

skip_dirs = {'env','otro_proyecto','__pycache__','.git','AURA-Brain','blobs','_AURA_Archive',
             'discord_service','manifests','knowledge_base','Setup','venv','logs','targets'}

# Pattern: API keys that look hardcoded (not using os.environ.get)
patterns = [
    (r'(?<![.\w])sk-[a-zA-Z0-9_-]{20,}(?![\w"])', 'OpenAI/OpenRouter'),
    (r'(?<![.\w])AIza[0-9A-Za-z_-]{35}(?![\w"])', 'Google/Gemini'),
    (r'api_key\s*=\s*["\'](?!os\.environ|os\.getenv)', 'api_key hardcoded'),
]

found_any = False

for root, dirs, files in os.walk('.'):
    # Skip excluded dirs
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    # Also skip if path contains excluded dir
    if any(s in root for s in skip_dirs):
        continue

    for fname in files:
        if not fname.endswith(('.py', '.html', '.js', '.txt', '.json')):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
        except:
            continue

        for pattern, label in patterns:
            for m in re.finditer(pattern, content):
                # Check context around match for os.environ/getenv
                start = max(0, m.start() - 60)
                end = min(len(content), m.end() + 60)
                context = content[start:end]

                # Skip if it's in .env file or using os.environ
                if 'os.environ' in context or 'getenv' in context or '.env' in context:
                    continue
                # Skip if it's clearly an example/template
                if 'example' in context.lower() or 'template' in context.lower():
                    continue

                print(f'  ⚠️  {label} → {fpath}')
                print(f'       Context: ...{context.strip()[:80]}...')
                found_any = True

if not found_any:
    print('  ✅ No se encontraron API keys hardcodeadas en el código fuente')
else:
    print(f'\n  ⚠️  Se encontraron posibles keys hardcodeadas — revisar arriba')

print('\n  📋 Nota: El archivo .env contiene keys reales (GEMINI, OPENROUTER)')
print('         Estas NO están hardcodeadas en código, solo en .env (excluído por gitignore)')