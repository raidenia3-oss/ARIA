#!/usr/bin/env python3
"""
AURA Copilot Extension Installer & Compiler
Compila TypeScript -> JavaScript y instala en VS Code

Uso:
    python scripts/install_copilot.py
    python scripts/install_copilot.py --no-install  # Solo compilar
    python scripts/install_copilot.py --rebuild     # Clean + rebuild
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def disable() -> None:
        Colors.HEADER = ''
        Colors.BLUE = ''
        Colors.CYAN = ''
        Colors.GREEN = ''
        Colors.YELLOW = ''
        Colors.RED = ''
        Colors.ENDC = ''
        Colors.BOLD = ''


class AuraExtensionCompiler:
    def __init__(self, extension_root: Optional[str] = None, rebuild: bool = False):
        self.project_root = Path.cwd()

        if extension_root:
            self.extension_root = Path(extension_root)
        else:
            possible_paths = [
                self.project_root / "extension" / "vscode",
                self.project_root / "extension",
                self.project_root / "vscode-extension",
                self.project_root / "copilot",
                self.project_root / "aura-copilot",
                self.project_root / "extensions" / "aura-copilot",
            ]

            self.extension_root = None
            for path in possible_paths:
                if (path / "package.json").exists():
                    self.extension_root = path
                    break

            if not self.extension_root:
                print(f"{Colors.RED}[ERROR] Cannot find extension directory. Checked: {possible_paths}{Colors.ENDC}")
                sys.exit(1)

        self.extension_root = self.extension_root.resolve()
        self.out_dir = self.extension_root / "out"
        self.src_dir = self.extension_root / "src"
        self.rebuild = rebuild
        self.node_modules = self.extension_root / "node_modules"

        print(f"{Colors.BLUE}[INFO] Extension root: {self.extension_root}{Colors.ENDC}")

    def log(self, message: str, level: str = "info") -> None:
        if level == "success":
            print(f"{Colors.GREEN}[OK] {message}{Colors.ENDC}")
        elif level == "error":
            print(f"{Colors.RED}[FAIL] {message}{Colors.ENDC}")
        elif level == "warning":
            print(f"{Colors.YELLOW}[WARN] {message}{Colors.ENDC}")
        elif level == "info":
            print(f"{Colors.BLUE}[INFO] {message}{Colors.ENDC}")
        elif level == "header":
            print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}")
            print(f"{Colors.BOLD}{Colors.CYAN}{message.center(60)}{Colors.ENDC}")
            print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}\n")

    def error(self, message: str) -> None:
        print(f"{Colors.RED}[ERROR] {message}{Colors.ENDC}")

    def _npm_cmd(self, base_cmd: list) -> list:
        if sys.platform == "win32":
            if base_cmd and base_cmd[0] == "npm":
                return ["npm.cmd"] + base_cmd[1:]
            if base_cmd and base_cmd[0] == "npx":
                return ["npx.cmd"] + base_cmd[1:]
        return base_cmd

    def run_command(self, cmd: list, cwd: Optional[Path] = None, verbose: bool = False) -> Tuple[bool, str]:
        if cwd is None:
            cwd = self.extension_root

        cmd = self._npm_cmd(cmd)

        if verbose:
            print(f"{Colors.BLUE}[INFO] Running: {' '.join(str(c) for c in cmd)}{Colors.ENDC}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                return True, result.stdout
            return False, result.stderr or result.stdout
        except subprocess.TimeoutExpired:
            return False, "Command timed out (5 minutes)"
        except FileNotFoundError as e:
            return False, f"Command not found: {e}"
        except Exception as e:
            return False, f"Error running command: {e}"

    def check_prerequisites(self) -> bool:
        self.log("Checking prerequisites...", "header")

        success, output = self.run_command(["node", "--version"], verbose=False)
        if not success:
            self.error("Node.js is not installed")
            self.log("Install from: https://nodejs.org/", "warning")
            return False

        self.log(f"Node.js version: {output.strip()}", "success")

        success, output = self.run_command(["npm", "--version"], verbose=False)
        if not success:
            success, output = self.run_command(["npm.cmd", "--version"], verbose=False)
        if not success:
            self.error("npm is not installed")
            return False

        self.log(f"npm version: {output.strip()}", "success")
        self.log("TypeScript will be installed via npm", "info")
        return True

    def verify_package_json(self) -> bool:
        package_json = self.extension_root / "package.json"

        if not package_json.exists():
            self.error(f"package.json not found in {self.extension_root}")
            return False

        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if "name" not in config:
                self.error("package.json missing 'name' field")
                return False

            self.log(f"Extension: {config.get('name', 'unknown')}", "success")
            self.log(f"Version: {config.get('version', 'unknown')}", "success")
            return True
        except json.JSONDecodeError as e:
            self.error(f"Invalid JSON in package.json: {e}")
            return False

    def clean_build(self) -> None:
        if self.rebuild:
            self.log("Cleaning previous build...", "info")
            for dir_path in [self.out_dir, self.node_modules]:
                if dir_path.exists():
                    try:
                        shutil.rmtree(dir_path)
                        self.log(f"Cleaned: {dir_path}", "success")
                    except Exception as e:
                        self.log(f"Could not clean {dir_path}: {e}", "warning")

    def install_dependencies(self) -> bool:
        self.log("Installing npm dependencies...", "header")

        if self.node_modules.exists():
            self.log("node_modules already exists, skipping npm install", "info")
            return True

        success, output = self.run_command(["npm", "install"], cwd=self.extension_root, verbose=True)
        if not success:
            self.error("npm install failed")
            self.log(output, "error")
            return False

        self.log("npm dependencies installed successfully", "success")

        tsc_path = self.node_modules / ".bin" / "tsc"
        if not tsc_path.exists():
            tsc_path = self.node_modules / ".bin" / "tsc.cmd"

        if tsc_path.exists():
            self.log("TypeScript compiler found", "success")
        else:
            self.log("Warning: TypeScript compiler not found, will try npx tsc", "warning")

        return True

    def compile_typescript(self) -> bool:
        self.log("Compiling TypeScript...", "header")

        with open(self.extension_root / "package.json", 'r', encoding='utf-8') as f:
            config = json.load(f)

        if "scripts" in config and "compile" in config["scripts"]:
            self.log("Using npm run compile", "info")
            success, output = self.run_command(["npm", "run", "compile"], cwd=self.extension_root, verbose=True)
        else:
            self.log("Using npx tsc (TypeScript compiler)", "info")

            tsconfig_path = self.extension_root / "tsconfig.json"
            if not tsconfig_path.exists():
                self.error("tsconfig.json not found")
                self.log("Please create tsconfig.json in extension root", "warning")
                return False

            success, output = self.run_command(["npx", "tsc"], cwd=self.extension_root, verbose=True)

        if not success:
            self.error("TypeScript compilation failed")
            self.log(output, "error")
            return False

        extension_js = self.out_dir / "extension.js"
        if extension_js.exists():
            size_kb = extension_js.stat().st_size / 1024
            self.log(f"Compiled successfully: {extension_js} ({size_kb:.1f} KB)", "success")
            return True

        self.error(f"Compilation succeeded but {extension_js} not found")

        if self.out_dir.exists():
            files = list(self.out_dir.glob("**/*.js"))
            if files:
                self.log(f"Found JS files in {self.out_dir}:", "info")
                for f in files:
                    self.log(f"  - {f.relative_to(self.extension_root)}", "info")

        return False

    def package_extension(self) -> bool:
        self.log("Packaging extension as .vsix...", "header")

        success, _ = self.run_command(["npm", "list", "-g", "@vscode/vsce"], verbose=False)
        if not success:
            self.log("Installing vsce globally...", "info")
            success, output = self.run_command(["npm", "install", "-g", "@vscode/vsce"], verbose=False)
            if not success:
                self.log("Warning: Could not install vsce globally", "warning")
                self.log("You can still install extension manually", "info")
                return True

        with open(self.extension_root / "package.json", 'r', encoding='utf-8') as f:
            config = json.load(f)

        extension_name = config.get("name", "aura-copilot")
        extension_version = config.get("version", "1.0.0")
        vsix_name = f"{extension_name}-{extension_version}.vsix"

        success, output = self.run_command(["vsce", "package", "-o", vsix_name], cwd=self.extension_root, verbose=True)
        if not success:
            self.log(f"Warning: Could not package with vsce: {output}", "warning")
            self.log("You can manually create the .vsix or install unpacked", "info")
            return True

        vsix_path = self.extension_root / vsix_name
        if vsix_path.exists():
            size_mb = vsix_path.stat().st_size / (1024 * 1024)
            self.log(f"Packaged: {vsix_path} ({size_mb:.2f} MB)", "success")
            return True

        return True

    def install_in_vscode(self) -> bool:
        self.log("Installing extension in VS Code...", "header")

        vsix_files = list(self.extension_root.glob("*.vsix"))
        if vsix_files:
            vsix_path = vsix_files[0]
            self.log(f"Found .vsix: {vsix_path}", "info")
            success, output = self.run_command(["code", "--install-extension", str(vsix_path)], verbose=True)
            if success:
                self.log("Extension installed via code CLI", "success")
                return True
            self.log("Could not install via code CLI", "warning")

        self.log("Installing in development mode...", "info")
        success, output = self.run_command(["code", "--install-extension", str(self.extension_root), "--dev"], verbose=True)
        if success:
            self.log("Extension installed in development mode", "success")
            return True

        self.log("Install via VS Code GUI: Extensions -> Install from VSIX", "warning")
        self.log(f"VSIX path: {self.extension_root / '*.vsix'}", "info")
        return True

    def compile(self, no_install: bool = False) -> bool:
        try:
            if not self.check_prerequisites():
                return False
            if not self.verify_package_json():
                return False

            self.clean_build()

            if not self.install_dependencies():
                return False
            if not self.compile_typescript():
                return False

            self.package_extension()

            if not no_install:
                self.install_in_vscode()

            return True
        except KeyboardInterrupt:
            self.log("Installation cancelled by user", "warning")
            return False
        except Exception as e:
            self.error(f"Unexpected error: {e}")
            return False

    def print_summary(self, success: bool) -> None:
        self.log("", "header")

        if success:
            print(f"{Colors.GREEN}{Colors.BOLD}")
            print("============================================================")
            print("                                                            ")
            print("          AURA COPILOT COMPILED & INSTALLED!          ")
            print("                                                            ")
            print("  1. TypeScript compiled to JavaScript                     ")
            print("  2. out/extension.js is ready                             ")
            print("  3. Extension installed in VS Code                        ")
            print("  4. Activate with: Ctrl+Shift+P -> AURA Copilot           ")
            print("  5. Voice input: Ctrl+Alt+M                              ")
            print("                                                            ")
            print("============================================================")
            print(f"{Colors.ENDC}\n")
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}")
            print("============================================================")
            print("                                                            ")
            print("  COMPILATION COMPLETED WITH WARNINGS/ERRORS           ")
            print("                                                            ")
            print("  Check output above for details                           ")
            print("  You may need to:                                         ")
            print("    1. Check Node.js/npm installation                      ")
            print("    2. Delete node_modules and retry                       ")
            print("    3. Install manually via VS Code GUI                    ")
            print("                                                            ")
            print("============================================================")
            print(f"{Colors.ENDC}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AURA Copilot Extension Compiler & Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/install_copilot.py
  python scripts/install_copilot.py --no-install
  python scripts/install_copilot.py --rebuild
  python scripts/install_copilot.py --extension-dir ./extension/vscode
        """
    )

    parser.add_argument("--extension-dir", type=str, default=None, help="Path to extension directory (auto-detected if not specified)")
    parser.add_argument("--no-install", action="store_true", help="Only compile, don't install in VS Code")
    parser.add_argument("--rebuild", action="store_true", help="Clean build (delete node_modules and out/)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = parser.parse_args()

    if args.no_color:
        Colors.disable()

    compiler = AuraExtensionCompiler(extension_root=args.extension_dir, rebuild=args.rebuild)
    success = compiler.compile(no_install=args.no_install)
    compiler.print_summary(success)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
