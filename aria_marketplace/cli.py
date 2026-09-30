"""ARIA Plugin CLI - F-Droid 2.0 marketplace commands.

Commands:
  aria plugin search <query>
  aria plugin install <name> [--version <ver>]
  aria plugin list
  aria plugin remove <name>
  aria plugin info <name>
"""

from __future__ import annotations

import sys
from pathlib import Path

from aria_marketplace import (
    PluginInstaller,
    PluginRegistry,
    DependencyResolver,
)


def _get_aria_home() -> Path:
    return Path(__file__).resolve().parent


def cmd_search(query: str) -> int:
    """Search for plugins in the marketplace."""
    aria_home = _get_aria_home()
    registry = PluginRegistry(aria_home / "cache" / "marketplace")

    try:
        results = registry.search(query)
    except Exception as e:
        print(f"Search failed: {e}")
        return 1

    if not results:
        print(f"No plugins found matching '{query}'")
        return 0

    print(f"\nFound {len(results)} plugin(s) matching '{query}':\n")
    for p in results[:20]:
        print(f"  {p.get('name', '?'):40s} v{p.get('latest', '?'):10s} "
              f"↓{p.get('downloads', 0):>6d}  ⭐{p.get('rating', 0)}")
    if len(results) > 20:
        print(f"  ... and {len(results) - 20} more")
    return 0


def cmd_list() -> int:
    """List installed plugins."""
    aria_home = _get_aria_home()
    installer = PluginInstaller(aria_home)
    plugins = installer.list_installed()

    if not plugins:
        print("No plugins installed.")
        return 0

    print(f"\n{len(plugins)} installed plugin(s):\n")
    for p in plugins:
        print(f"  {p.get('name', '?'):40s} v{p.get('version', '?')}")
    return 0


def cmd_install(name: str, version: str = "latest") -> int:
    """Install a plugin from the marketplace."""
    aria_home = _get_aria_home()
    installer = PluginInstaller(aria_home)

    print(f"Installing {name}@{version}...")
    result = installer.install(name, version)

    if result["status"] == "success":
        print(f"✅ Installed {len(result['installed'])} package(s)")
        for pkg in result["installed"]:
            print(f"  - {pkg['name']}@{pkg['version']} ({pkg['type']})")
    elif result["status"] == "partial":
        print(f"⚠️  Partial install: {len(result['installed'])} ok, "
              f"{len(result['errors'])} error(s)")
        for err in result["errors"]:
            print(f"  ❌ {err}")
    else:
        print(f"❌ Install failed:")
        for err in result["errors"]:
            print(f"  - {err}")
    return 0 if result["status"] == "success" else 1


def cmd_remove(name: str) -> int:
    """Remove an installed plugin."""
    aria_home = _get_aria_home()
    installer = PluginInstaller(aria_home)
    result = installer.uninstall(name)

    if result["status"] == "success":
        print(f"✅ Removed {name}")
    else:
        print(f"❌ {result.get('error', 'Unknown error')}")
    return 0 if result["status"] == "success" else 1


def cmd_info(name: str) -> int:
    """Show plugin info."""
    aria_home = _get_aria_home()
    registry = PluginRegistry(aria_home / "cache" / "marketplace")

    try:
        info = registry.get_plugin_info(name)
        versions = registry.get_versions(name)
    except Exception as e:
        print(f"Failed to fetch info: {e}")
        return 1

    if not info:
        print(f"Plugin '{name}' not found in registry")
        return 1

    print(f"\n📦 {info.get('name', name)}")
    print(f"   Version: {info.get('latest', '?')}")
    print(f"   Description: {info.get('description', 'N/A')}")
    print(f"   Author: {info.get('author', 'N/A')}")
    print(f"   Downloads: {info.get('downloads', 0)}")
    print(f"   Rating: {info.get('rating', 0)}⭐")
    if versions:
        print(f"   Versions: {', '.join(versions[:5])}")
    return 0


def main() -> None:
    """Plugin CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: aria plugin <command> [args]")
        print("\nCommands:")
        print("  search <query>     Search plugins")
        print("  install <name>     Install plugin")
        print("  list               List installed")
        print("  remove <name>      Remove plugin")
        print("  info <name>        Plugin details")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "search":
        sys.exit(cmd_search(" ".join(args)))
    elif command == "install":
        name = args[0] if args else ""
        version = "latest"
        if "--version" in args:
            idx = args.index("--version")
            if idx + 1 < len(args):
                version = args[idx + 1]
        sys.exit(cmd_install(name, version))
    elif command == "list":
        sys.exit(cmd_list())
    elif command == "remove":
        sys.exit(cmd_remove(args[0] if args else ""))
    elif command == "info":
        sys.exit(cmd_info(args[0] if args else ""))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()