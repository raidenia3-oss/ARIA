import subprocess
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')


def get_py_files(dirs):
    all_files = []
    for d in dirs:
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith('.py'):
                        all_files.append(os.path.join(root, f))
    return all_files


def run_cmd(cmd, output_file):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    with open(output_file, 'w') as f:
        f.write(r.stdout)
        f.write(r.stderr)
    return r


def main():
    dirs = ['AURA_APP/backend', 'AURA_APP/frontend', 'tests']
    pyfiles = get_py_files(dirs)
    print(f"Total Python files: {len(pyfiles)}")

    # Black
    print("Running Black...")
    r = run_cmd([sys.executable, '-m', 'black', '--line-length', '100'] + pyfiles, 'linting_black.txt')
    print(f"  Black done")

    # Flake8
    print("Running Flake8...")
    cmd = [sys.executable, '-m', 'flake8', '--count', '--show-source', '--statistics',
           '--max-line-length', '100', '--ignore', 'E501,W503,E203', '--max-complexity', '10'] + pyfiles
    r = run_cmd(cmd, 'linting_flake8.txt')
    print(f"  Flake8 done")

    # Mypy
    print("Running Mypy...")
    r = run_cmd([sys.executable, '-m', 'mypy', '--ignore-missing-imports'] + pyfiles, 'linting_mypy.txt')
    print(f"  Mypy done")

    # Pylint
    print("Running Pylint...")
    r = run_cmd([sys.executable, '-m', 'pylint', '--output-format=parseable'] + pyfiles, 'linting_pylint.txt')
    print(f"  Pylint done")

    # Radon - complexity
    print("Running Radon CC...")
    for d in ['AURA_APP/backend', 'AURA_APP/frontend']:
        r = run_cmd([sys.executable, '-m', 'radon', 'cc', d, '-s'], f'linting_complexity_{d.split(chr(92))[-1]}.txt')
        print(f"  Radon CC {d}: done")

    # Radon - maintainability
    for d in ['AURA_APP/backend', 'AURA_APP/frontend']:
        r = run_cmd([sys.executable, '-m', 'radon', 'mi', d, '-m'], f'linting_maintainability_{d.split(chr(92))[-1]}.txt')
        print(f"  Radon MI {d}: done")

    # Bandit - security
    for d in ['AURA_APP/backend', 'AURA_APP/frontend']:
        r = run_cmd([sys.executable, '-m', 'bandit', '-r', d, '-f', 'json'], f'linting_security_{d.split(chr(92))[-1]}.json')
        print(f"  Bandit {d}: done")

    # Merge linting reports
    with open('linting_flake8.txt', 'w') as f:
        for d in dirs:
            fname = f'linting_flake8_{d.split(chr(92))[-1]}.txt'
            if os.path.exists(fname):
                with open(fname) as src:
                    f.write(f"=== {d} ===\n")
                    f.write(src.read())

    with open('linting_mypy.txt', 'w') as f:
        for d in dirs:
            fname = f'linting_mypy_{d.split(chr(92))[-1]}.txt'
            if os.path.exists(fname):
                with open(fname) as src:
                    f.write(f"=== {d} ===\n")
                    f.write(src.read())

    with open('linting_pylint.txt', 'w') as f:
        for d in dirs:
            fname = f'linting_pylint_{d.split(chr(92))[-1]}.txt'
            if os.path.exists(fname):
                with open(fname) as src:
                    f.write(f"=== {d} ===\n")
                    f.write(src.read())

    with open('linting_security.json', 'w') as f:
        for d in dirs:
            fname = f'linting_security_{d.split(chr(92))[-1]}.json'
            if os.path.exists(fname):
                with open(fname) as src:
                    f.write(src.read())

    with open('linting_complexity.txt', 'w') as f:
        for d in ['AURA_APP/backend', 'AURA_APP/frontend']:
            fname = f'linting_complexity_{d.split(chr(92))[-1]}.txt'
            if os.path.exists(fname):
                with open(fname) as src:
                    f.write(f"=== {d} ===\n")
                    f.write(src.read())

    with open('linting_maintainability.txt', 'w') as f:
        for d in ['AURA_APP/backend', 'AURA_APP/frontend']:
            fname = f'linting_maintainability_{d.split(chr(92))[-1]}.txt'
            if os.path.exists(fname):
                with open(fname) as src:
                    f.write(f"=== {d} ===\n")
                    f.write(src.read())

    # Clean up temp files
    for d in dirs:
        for prefix in ['linting_flake8_', 'linting_mypy_', 'linting_pylint_', 'linting_security_']:
            fname = f'{prefix}{d.split(chr(92))[-1]}.txt' if prefix != 'linting_security_' else f'{prefix}{d.split(chr(92))[-1]}.json'
            if os.path.exists(fname):
                os.remove(fname)

    print("\nLinting complete. Reports generated.")


if __name__ == '__main__':
    main()
