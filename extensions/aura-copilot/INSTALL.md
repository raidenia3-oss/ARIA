# AURA Copilot Extension — Installation

## Automated Installation

```bash
python scripts/install_copilot.py
```

This will:
1. Detect extension directory
2. Check Node.js/npm
3. Run npm install
4. Compile TypeScript -> JavaScript
5. Package as .vsix
6. Install in VS Code

## Manual Installation (if needed)

```bash
cd extensions/aura-copilot
npm install
npx tsc
code --install-extension .
```

## Troubleshooting

- Node not found: install from https://nodejs.org/
- Compilation fails: try deleting node_modules and running npm install again
- Extension won't load: check VS Code version 1.70+
