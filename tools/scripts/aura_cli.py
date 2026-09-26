import sys
import os
import json
import time
import argparse
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")


def cmd_agents_list(args) -> None:
    try:
        from backend.core.agent_registry_v2 import AgentRegistryV2
        reg = AgentRegistryV2()
        agents = reg.list_agents()
        if not agents:
            print("No hay agentes registrados.")
            return
        print(f"{'Agent ID':<16} {'Nombre':<25} {'Tipo':<15} {'Estado':<10} {'Reqs':<8} {'Revenue'}")
        print("-" * 90)
        for a in agents:
            print(f"{a['agent_id']:<16} {a['name']:<25} {a['type']:<15} {a['status']:<10} {a.get('request_count', 0):<8} ${a.get('revenue', 0.0):.2f}")
    except Exception as e:
        print(f"Error: {e}")


def cmd_plugins_load(args) -> None:
    try:
        from backend.plugins import plugin_manager
        result = plugin_manager.load_plugin(args.name)
        if result.get("status") == "loaded":
            print(f"Plugin '{args.name}' cargado exitosamente.")
        else:
            print(f"Error: {result.get('error')}")
    except Exception as e:
        print(f"Error: {e}")


def cmd_plugins_unload(args) -> None:
    try:
        from backend.plugins import plugin_manager
        result = plugin_manager.unload_plugin(args.name)
        if result.get("status") == "unloaded":
            print(f"Plugin '{args.name}' descargado.")
        else:
            print(f"Error: {result.get('error')}")
    except Exception as e:
        print(f"Error: {e}")


def cmd_plugins_list(args) -> None:
    try:
        from backend.plugins import plugin_manager
        plugins = plugin_manager.list_plugins()
        if not plugins:
            print("No hay plugins cargados.")
            return
        for p in plugins:
            cmds = ", ".join(p.get("commands", []))
            print(f"  {p['name']} v{p['version']} [{p['status']}] — {cmds}")
    except Exception as e:
        print(f"Error: {e}")


def cmd_stats(args) -> None:
    async def _stats():
        try:
            from backend.monitoring.dashboard_manager import DashboardManager
            dm = DashboardManager()
            if args.agent:
                result = await dm.get_agent_stats(args.agent)
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                result = await dm.get_system_stats()
                print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Error: {e}")
    asyncio.run(_stats())


def cmd_config_set(args) -> None:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "aura_config.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception:
            pass
    config[args.key] = args.value
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Configuracion: {args.key} = {args.value}")
    except Exception as e:
        print(f"Error saving: {e}")


def cmd_health(args) -> None:
    try:
        from backend.plugins import plugin_manager
        from backend.core.agent_registry_v2 import AgentRegistryV2
        plugins_count = len(plugin_manager.list_plugins())
        reg = AgentRegistryV2()
        agents = reg.list_agents()
        status = "HEALTHY"
        if plugins_count == 0 and len(agents) == 0:
            status = "DEGRADED"
        print(f"Status: {status}")
        print(f"Plugins: {plugins_count}")
        print(f"Agentes: {len(agents)}")
        print(f"Uptime: {round(time.time() - os.path.getmtime(__file__))}s")
    except Exception as e:
        print(f"Health check error: {e}")


def cmd_logs(args) -> None:
    try:
        from backend.monitoring.dashboard_manager import DashboardManager
        dm = DashboardManager()
        logs = dm.get_logs(lines=args.lines)
        for line in logs:
            print(line.rstrip())
    except Exception as e:
        print(f"Error: {e}")


def cmd_reload_plugins(args) -> None:
    try:
        from backend.plugins import plugin_manager
        result = plugin_manager.reload_all_plugins()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")


def cmd_dashboard(args) -> None:
    import webbrowser
    dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dashboard_v3.html")
    if os.path.exists(dashboard_path):
        webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")
        print(f"Dashboard abierto: {dashboard_path}")
    else:
        print("Dashboard no encontrado.")


def main() -> None:
    parser = argparse.ArgumentParser(description="AURA CLI - Mantenimiento y Control")
    sub = parser.add_subparsers(dest="command")

    # agents
    p_agents = sub.add_parser("agents", help="Gestionar agentes")
    a_sub = p_agents.add_subparsers(dest="action")
    a_list = a_sub.add_parser("list")

    # plugins
    p_plugins = sub.add_parser("plugins", help="Gestionar plugins")
    p_sub = p_plugins.add_subparsers(dest="action")
    p_load = p_sub.add_parser("load")
    p_load.add_argument("name")
    p_unload = p_sub.add_parser("unload")
    p_unload.add_argument("name")
    p_list = p_sub.add_parser("list")
    p_reload = p_sub.add_parser("reload")

    # stats
    p_stats = sub.add_parser("stats", help="Ver estadisticas")
    p_stats.add_argument("--agent", default=None)

    # config
    p_config = sub.add_parser("config", help="Configuracion")
    c_sub = p_config.add_subparsers(dest="action")
    c_set = c_sub.add_parser("set")
    c_set.add_argument("key")
    c_set.add_argument("value")

    # misc
    sub.add_parser("health", help="Health check")
    sub.add_parser("dashboard", help="Abrir dashboard")

    p_logs = sub.add_parser("logs", help="Ver logs")
    p_logs.add_argument("--lines", type=int, default=50)

    args = parser.parse_args()

    if args.command == "agents":
        if args.action == "list":
            cmd_agents_list(args)
    elif args.command == "plugins":
        if args.action == "load":
            cmd_plugins_load(args)
        elif args.action == "unload":
            cmd_plugins_unload(args)
        elif args.action == "list":
            cmd_plugins_list(args)
        elif args.action == "reload":
            cmd_reload_plugins(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "config":
        if args.action == "set":
            cmd_config_set(args)
    elif args.command == "health":
        cmd_health(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "logs":
        cmd_logs(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
