import os
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')


def generate_report():
    report = {
        'timestamp': None,
        'files_analyzed': 0,
        'total_lines': 0,
        'linting': {},
        'profiling': {},
        'memory': {},
        'security': {}
    }

    for key, filename in [
        ('flake8', 'linting_flake8.txt'),
        ('mypy', 'linting_mypy.txt'),
        ('pylint', 'linting_pylint.txt'),
        ('complexity', 'linting_complexity.txt'),
    ]:
        if os.path.exists(filename):
            try:
                with open(filename, encoding='utf-8') as f:
                    report['linting'][key] = f.read()
            except (UnicodeDecodeError, UnicodeError):
                with open(filename, encoding='latin-1') as f:
                    report['linting'][key] = f.read()

    for key, filename in [
        ('think', 'profile_think.txt'),
        ('connectors', 'profile_connectors.txt'),
        ('memory', 'profile_memory.txt'),
    ]:
        if os.path.exists(filename):
            with open(filename, encoding='utf-8') as f:
                report['profiling'][key] = f.read()

    if os.path.exists('memory_leaks.txt'):
        with open('memory_leaks.txt', encoding='utf-8') as f:
            report['memory']['leaks'] = f.read()

    if os.path.exists('linting_security.json'):
        try:
            with open('linting_security.json', encoding='utf-8') as f:
                report['security'] = json.load(f)
        except json.JSONDecodeError:
            with open('linting_security.json', encoding='utf-8') as f:
                report['security'] = {'raw': f.read()}

    total_lines = 0
    file_count = 0
    for root, dirs, files in os.walk('AURA_APP'):
        for file in files:
            if file.endswith('.py'):
                file_count += 1
                path = os.path.join(root, file)
                try:
                    with open(path, encoding='utf-8') as f:
                        total_lines += len(f.readlines())
                except (UnicodeDecodeError, PermissionError):
                    pass

    report['files_analyzed'] = file_count
    report['total_lines'] = total_lines

    html = f"""
    <html>
    <head>
        <title>AURA OS - Code Quality Report</title>
        <style>
            body {{ font-family: monospace; background: #0a0e27; color: #00ff88; }}
            h1 {{ color: #ff006e; }}
            h2 {{ color: #00d9ff; }}
            pre {{ background: #1a1f3a; padding: 10px; overflow-x: auto; }}
            .stat {{ color: #ffd600; }}
        </style>
    </head>
    <body>
        <h1>AURA OS - Code Quality Report</h1>
        <p class="stat">Files Analyzed: {report['files_analyzed']}</p>
        <p class="stat">Total Lines: {report['total_lines']}</p>
        <h2>Linting Results</h2>
        <pre>{json.dumps(report['linting'], indent=2, ensure_ascii=False)}</pre>
        <h2>Profiling Results</h2>
        <pre>{json.dumps(report['profiling'], indent=2, ensure_ascii=False)}</pre>
        <h2>Memory Analysis</h2>
        <pre>{json.dumps(report['memory'], indent=2, ensure_ascii=False)}</pre>
        <h2>Security Scan</h2>
        <pre>{json.dumps(report['security'], indent=2, ensure_ascii=False, default=str)}</pre>
    </body>
    </html>
    """

    with open('code_quality_report.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print("Reporte generado: code_quality_report.html")


if __name__ == '__main__':
    generate_report()
