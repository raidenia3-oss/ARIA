# Contributing to AURA OS

Thank you for your interest in contributing to AURA OS! This document explains how to get started.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Project Structure](#project-structure)
5. [Coding Standards](#coding-standards)
6. [Testing](#testing)
7. [Submitting Changes](#submitting-changes)
8. [Issue Labels](#issue-labels)
9. [Recognition](#recognition)

## Code of Conduct

We follow a simple code of conduct:
- Be respectful and constructive
- Assume good intent
- Focus on the code, not the person
- No harassment or discrimination of any kind

## Getting Started

1. Fork the repository
2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/AURA.git
cd AURA
```

3. Create a branch:
```bash
git checkout -b fix/bug-description
# or
git checkout -b feature/feature-name
```

4. Make your changes
5. Run tests and validation
6. Submit a PR

## Development Setup

### Prerequisites

- Python 3.11+
- Git

### Quick Setup

```bash
# Clone and enter directory
git clone https://github.com/YOUR_USERNAME/AURA.git
cd AURA

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r backend/requirements.txt
pip install -r requirements.txt

# Create .env file
cp backend/.env.example backend/.env
# Edit .env with your API keys

# Run backend
python backend/main.py
```

### Docker Setup

```bash
docker-compose up
```

### Environment Variables

Required variables (create `.env` from `.env.example`):

```bash
# Core
DATABASE_URL=postgresql://user:pass@localhost/aura_db
REDIS_URL=redis://localhost:6379

# AI Providers (at least one required)
GEMINI_API_KEY=your-key-here
GROQ_API_KEY=your-key-here
OPENROUTER_API_KEY=your-key-here

# Security
JWT_SECRET=generate-a-secret-key
ENCRYPTION_KEY=generate-an-encryption-key

# Logging
LOG_LEVEL=info  # Will be normalized automatically
```

## Project Structure

```
AURA/
├── backend/                 # Python backend (FastAPI)
│   ├── main.py             # Main API — 117 routes
│   ├── auth/               # Authentication & multi-tenancy
│   ├── omniroute/          # Multi-provider AI gateway
│   ├── skills/             # Skills registry & execution
│   ├── memory/             # Memory systems (working/short/long-term)
│   ├── proactive/          # Proactive agent engine
│   └── agents/             # ReAct Loop, task delegation
├── frontend/               # Web frontend (HTML/CSS/JS)
├── mobile_client/          # Android APK (AME) source
│   └── requirements.txt
├── aura-os/                # AURA OS installer & scripts
│   └── go-tools/           # Go utilities (6 binaries)
│       ├── cmd/            # Command implementations
│       │   ├── scanner/    # Network discovery
│       │   ├── resolver/   # DNS resolution
│       │   ├── enum/       # HTTP endpoint enumeration
│       │   ├── c2-agent/   # C2 implant
│       │   ├── c2-server/  # C2 server
│       │   └── c2-client/  # C2 operator client
│       ├── go.mod
│       └── Makefile
├── packages/
│   └── discord-bot/        # Ruby Discord bot
│       ├── bot.rb
│       ├── Gemfile
│       ├── spec/
│       └── Dockerfile
├── tests/                  # Test suite (pytest)
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── .github/                # GitHub templates & workflows
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug.md
│   │   ├── feature.md
│   │   └── question.md
│   ├── workflows/
│   │   ├── ci-cd.yml
│   │   └── release.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── AGENTS.md               # Developer instructions
├── PROJECT_STATUS.md       # Current project status
├── CHANGELOG.md            # Version history
├── CONTRIBUTING.md         # This file
└── requirements.txt
```

## Coding Standards

### Python (Backend)

- Follow PEP 8
- Use type hints: `def function(param: str) -> str:`
- Keep files under ~250 lines (per constraint)
- Use absolute imports: `from backend.skills.system import ...`
- Add docstrings to all public functions
- Run linter before committing:
```bash
python -m py_compile backend/main.py
```

### Go (Tools)

- Use `gofmt` for formatting
- Build static binaries: `CGO_ENABLED=0 go build -ldflags "-s -w"`
- Use only standard library in source files (external deps in go.mod for future use)
- Max ~150 lines per file

### Ruby (Discord Bot)

- Use Ruby 3.0+ conventions
- Run `ruby -c` to validate syntax
- Tests with RSpec

### Shell Scripts

- Use `set -e` for error handling
- Validate with `bash -n` before committing
- Add comments for complex logic

## Testing

### Python Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_omniroute.py -v

# Skip integration tests (requires running server)
python -m pytest tests/ -k "not integration"

# With coverage
python -m pytest tests/ --cov=backend --cov-report=html
```

### Current Test Results

- Backend import: 117 routes detected
- Omniroute tests: 7 unit tests + 1 integration (all passing)
- All bash scripts: syntax validated

### Adding New Tests

Create tests in `tests/` directory:
```python
def test_my_function():
    result = my_function(input)
    assert result == expected
```

## Submitting Changes

### Before Submitting

1. **All tests pass**:
```bash
python -m pytest tests/ -k "not integration"
```

2. **Code compiles**:
```bash
python -m py_compile backend/main.py
# For Go tools (if Go is installed):
cd aura-os/go-tools && make build
```

3. **Bash scripts validate**:
```bash
bash -n scripts/my-script.sh
```

4. **Code is formatted**:
```bash
# Python
python -m black backend/ tests/

# Check line length (keep under 250 lines per Python file)
```

5. **Commit message follows conventions**:
```
feat: Add new skill for weather
fix: Resolve omniroute provider timeout
docs: Update API reference
chore: Update dependencies
```

### Pull Request Process

1. Update `CHANGELOG.md` with your changes (under "Unreleased")
2. Ensure `README.md` is updated with any changes
3. Add tests for new functionality
4. Run the full validation suite
5. Submit PR with clear description

### PR Review Process

1. PR requires 1 reviewer approval
2. CI/CD checks must pass
3. Code must follow conventions
4. No security vulnerabilities introduced

## Issue Labels

| Label | Description |
|-------|-------------|
| `bug` | Something isn't working |
| `enhancement` | New feature or improvement |
| `question` | Support request |
| `documentation` | Documentation improvements |
| `good first issue` | Good for newcomers |
| `help wanted` | Extra attention needed |
| `security` | Security-related |
| `backend` | Backend-specific changes |
| `frontend` | Frontend-specific changes |
| `omniroute` | Omniroute gateway changes |

## Recognition

Contributors are recognized in:

1. **CHANGELOG.md** — All contributions listed
2. **Release notes** — Major contributions highlighted
3. **Hall of Fame** (`docs/HALL_OF_FAME.md`) — Top contributors
4. **GitHub contributors graph** — Automatic attribution

### Contributor Tiers

| Level | Requirement | Recognition |
|-------|-------------|-------------|
| Bronze | 1 PR merged | Listed in CHANGELOG |
| Silver | 5 PRs merged | HALL_OF_FAME entry |
| Gold | 10 PRs + significant contribution | Featured in release notes |
| Platinum | 25 PRs + architectural changes | Project co-author status |

---

**Questions?** Open a [discussion](https://github.com/TU_USUARIO/AURA/discussions) or ask in our [Discord](https://discord.gg/aura-os).
