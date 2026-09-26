import subprocess
import sys
import os


def run_cmd(cmd, output_file):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    with open(output_file, 'w') as f:
        f.write(r.stdout)
        f.write(r.stderr)
    return r


def main():
    # Radon - complexity
    for d in ['AURA_APP/backend', 'AURA_APP/frontend']:
        cmd = [sys.executable, '-m', 'radon', 'cc', d, '-s']
        r = run_cmd(cmd, 'linting_complexity.txt')
        if r.returncode == 0:
            print(f"Radon CC {d}: done")
        else:
            print(f"Radon CC {d}: error")

    # Append frontend complexity
    for d in ['AURA_APP/frontend']:
        cmd = [sys.executable, '-m', 'radon', 'cc', d, '-s']
        r = run_cmd(cmd, 'linting_complexity_frontend.txt')
        with open('linting_complexity.txt', 'a') as f:
            f.write(f"\n=== {d} ===\n")
            f.write(r.stdout)

    # Radon - maintainability
    for d in ['AURA_APP/backend', 'AURA_APP/frontend']:
        cmd = [sys.executable, '-m', 'radon', 'mi', d, '-m']
        r = run_cmd(cmd, f'linting_maintainability_{d.split("/")[-1]}.txt')
        with open('linting_maintainability.txt', 'a') as f:
            f.write(f"=== {d} ===\n")
            f.write(r.stdout)
        print(f"Radon MI {d}: done")

    # Bandit - security
    for d in ['AURA_APP/backend', 'AURA_APP/frontend']:
        cmd = [sys.executable, '-m', 'bandit', '-r', d, '-f', 'json']
        r = run_cmd(cmd, 'linting_security.json')
        if d == 'AURA_APP/frontend':
            with open('linting_security.json', 'a') as f:
                f.write("\n=== FRONTEND ===\n")
                f.write(r.stdout)
        print(f"Bandit {d}: done")

    print("\nRemaining linting complete.")


if __name__ == '__main__':
    main()
