#!/bin/bash

echo "🔍 AURA OS — Linting Phase"
echo "════════════════════════════════════════════════════════"

# Black formatting
echo "▶ Black (code formatter)..."
black AURA_APP/backend --line-length 100 --quiet
black AURA_APP/frontend --line-length 100 --quiet
black tests --line-length 100 --quiet

# Flake8 style check
echo "▶ Flake8 (style checker)..."
flake8 AURA_APP/backend --count --show-source --statistics > linting_flake8.txt
flake8 AURA_APP/frontend --count --show-source --statistics >> linting_flake8.txt
flake8 tests --count --show-source --statistics >> linting_flake8.txt

# Mypy type checking
echo "▶ Mypy (type checker)..."
mypy AURA_APP/backend --ignore-missing-imports > linting_mypy.txt 2>&1
mypy AURA_APP/frontend --ignore-missing-imports >> linting_mypy.txt 2>&1
mypy tests --ignore-missing-imports >> linting_mypy.txt 2>&1

# Pylint code quality
echo "▶ Pylint (code quality)..."
pylint AURA_APP/backend --output-format=parseable > linting_pylint.txt 2>&1
pylint AURA_APP/frontend >> linting_pylint.txt 2>&1
pylint tests >> linting_pylint.txt 2>&1

# Radon complexity
echo "▶ Radon (complexity analysis)..."
radon cc AURA_APP/backend -s > linting_complexity.txt
radon cc AURA_APP/frontend -s >> linting_complexity.txt
radon mi AURA_APP/backend -m > linting_maintainability.txt
radon mi AURA_APP/frontend -m >> linting_maintainability.txt

# Bandit security scan
echo "▶ Bandit (security scanner)..."
bandit -r AURA_APP/backend -f json > linting_security.json 2>&1
bandit -r AURA_APP/frontend -f json >> linting_security.json 2>&1

echo ""
echo "════════════════════════════════════════════════════════"
echo "✅ Linting completado. Ver:"
echo "   - linting_flake8.txt"
echo "   - linting_mypy.txt"
echo "   - linting_pylint.txt"
echo "   - linting_complexity.txt"
echo "   - linting_maintainability.txt"
echo "   - linting_security.json"
