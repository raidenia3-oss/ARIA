"""Cliente de terminal interactivo para AURA.

Interfaz CLI usando rich para:
- Chat interactivo (POST /api/local-ai/chat)
- Seleccion dinamica de personajes (GET/POST /api/personas/cards)
- Ejecucion de comandos Swarm (POST /api/swarm/tasks)
- Estado de salud del sistema (GET /api/production/health)
- Reporte maestro del sistema (GET /api/production/system-report)

Conexion con reconexion automatica si el servidor no esta disponible.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.theme import Theme

console = Console(theme=Theme({
    "aura.green": "green",
    "aura.blue": "cyan",
    "aura.yellow": "yellow",
    "aura.red": "red",
    "aura.bold": "bold",
}))

DEFAULT_BASE_URL = os.getenv("AURA_API_URL", "http://localhost:8000")


@dataclass
class CLIConfig:
    base_url: str = DEFAULT_BASE_URL
    session_id: str = field(default_factory=lambda: f"cli_{int(time.time())}")
    current_persona: Optional[str] = None
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("AURA_API_KEY"))


class AURAClient:
    """Cliente HTTP para la API de AURA con reconexion automatica."""

    def __init__(self, config: CLIConfig) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        if config.api_key:
            self.session.headers.update({"X-API-Key": config.api_key})
        self.connected = False
        self._reconnect_attempts = 0
        self._max_reconnect = 5

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        if not self.connected:
            if not self._reconnect():
                raise ConnectionError(f"No se pudo conectar a {self.base_url}")
        try:
            resp = self.session.request(
                method, f"{self.base_url}{path}", timeout=30, **kwargs
            )
            self.connected = True
            self._reconnect_attempts = 0
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {"raw": resp.text, "status_code": resp.status_code}
        except requests.ConnectionError:
            self.connected = False
            raise ConnectionError("Conexion perdida con el servidor AURA")
        except requests.HTTPError as exc:
            self.connected = True
            try:
                error_detail = resp.json()
            except (ValueError, NameError):
                error_detail = {"detail": str(exc)}
            raise APIError(error_detail, resp.status_code)

    def _reconnect(self) -> bool:
        for attempt in range(1, self._max_reconnection + 1):
            try:
                resp = self.session.get(f"{self.base_url}/api/production/health", timeout=5)
                if resp.status_code == 200:
                    self.connected = True
                    self._reconnect_attempts = 0
                    return True
            except requests.RequestException:
                pass
            wait = min(2 ** attempt, 10)
            console.print(f"[aura.yellow]Reconectando... intento {attempt}/{self._max_reconnection} ({wait}s)[/aura.yellow]")
            time.sleep(wait)
        return False

    @property
    def _max_reconnection(self) -> int:
        return 5

    def check_connection(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/api/production/health", timeout=5)
            self.connected = resp.status_code == 200
            return self.connected
        except requests.RequestException:
            self.connected = False
            return False


class APIError(Exception):
    def __init__(self, detail: Any, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(f"API Error {status_code}: {detail}")


def show_banner() -> None:
    banner = """
    [aura.bold]  ___  ___ ___    ___   _   _ ___ _   _  ___
  / __|/ __/ __|  |   \\ / (A) | | | |/ __| | | |/ _ \\
  \\__ \\ (_| (__    | |\\/| | | |_| | |_| | (__| |_| |  _/
  |___/\\___\\___|   |_|  |_|_\\__/_\\__|____/\\___|\\__, | |_|
                                              |___/
    [/aura.bold]
           [aura.blue]Autonomous Unified Reasoning Architecture[/aura.blue]
           v30.0 — CLI Interactive Client
    """
    console.print(Panel(banner, border_style="cyan", expand=False))


def show_health(client: AURAClient) -> bool:
    try:
        data = client._request("GET", "/api/production/health")
        console.print(Panel(
            f"[aura.green]Status: {data.get('status', 'unknown')}[/aura.green]\n"
            f"Liveness: {data.get('liveness', {}).get('passed', '?')}\n"
            f"Readiness: {data.get('readiness', {}).get('passed', '?')}\n"
            f"Startup: {data.get('startup', {}).get('passed', '?')}\n"
            f"All passed: {data.get('all_passed', False)}",
            title="System Health",
            border_style="green" if data.get("all_passed") else "yellow",
        ))
        return data.get("all_passed", False)
    except (ConnectionError, APIError) as exc:
        console.print(f"[aura.red]Error al consultar health: {exc}[/aura.red]")
        return False


def show_system_report(client: AURAClient) -> None:
    try:
        data = client._request("GET", "/api/production/system-report")
        console.print(f"\n[aura.bold]AURA System Report[/aura.bold]")
        console.print(f"  Generated: {data.get('generated_at', 'n/a')}")
        console.print(f"  System: {data.get('system_name', 'n/a')}")
        console.print(f"  Total modules: {data.get('total_modules', 0)}")
        console.print(f"  Existing modules: {data.get('existing_modules', 0)}")
        console.print(f"  Compiled modules: {data.get('compiled_modules', 0)}")

        report = data.get("readiness", {})
        console.print(f"  Readiness: {'READY' if report.get('ready') else 'NOT READY'}")

        env = data.get("environment", {})
        console.print(f"  Environment valid: {env.get('valid', False)}")
        if env.get("required_missing"):
            console.print(f"  Missing env: {env['required_missing']}")

        migration = data.get("migration", {})
        console.print(f"  Migration up-to-date: {migration.get('up_to_date', False)}")

        table = Table(title="Module Status", show_lines=False)
        table.add_column("File", style="cyan", no_wrap=True)
        table.add_column("Exists", justify="center")
        table.add_column("Compiles", justify="center")
        for mod in data.get("modules", [])[:15]:
            exists = "✓" if mod.get("exists") else "✗"
            compiles = "✓" if mod.get("compiles") else "✗"
            table.add_row(
                mod.get("file", "?"),
                f"[green]{exists}[/green]" if exists == "✓" else f"[red]{exists}[/red]",
                f"[green]{compiles}[/green]" if compiles == "✓" else f"[red]{compiles}[/red]",
            )
        console.print(table)
        remaining = len(data.get("modules", [])) - 15
        if remaining > 0:
            console.print(f"  ... and {remaining} more modules")
    except (ConnectionError, APIError) as exc:
        console.print(f"[aura.red]Error al obtener system-report: {exc}[/aura.red]")


def list_personas(client: AURAClient) -> List[Dict[str, Any]]:
    try:
        data = client._request("GET", "/api/personas/cards")
        cards = data.get("cards", [])
        if not cards:
            console.print("[aura.yellow]No hay personajes disponibles.[/aura.yellow]")
            return []

        table = Table(title="Personajes Disponibles", show_lines=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Nombre", style="cyan")
        table.add_column("Descripcion", style="white")
        table.add_column("Tags", style="green")
        for i, card in enumerate(cards):
            card_id_short = card.get("card_id", "?")[:8]
            tags = ", ".join(card.get("tags", []))
            table.add_row(str(i + 1), card.get("name", "?"), card.get("description", "?")[:50], tags)
        console.print(table)
        return cards
    except (ConnectionError, APIError) as exc:
        console.print(f"[aura.red]Error al listar personajes: {exc}[/aura.red]")
        return []


def select_persona(client: AURAClient) -> None:
    cards = list_personas(client)
    if not cards:
        return
    console.print("\n[aura.bold]Selecciona un personaje:[/aura.bold]")
    idx_str = Prompt.ask("Numero", default="1")
    try:
        idx = int(idx_str) - 1
        if 0 <= idx < len(cards):
            card = cards[idx]
            card_id = card.get("card_id", "")
            try:
                result = client._request("POST", "/api/personas/set-active", json={
                    "session_id": client.config.session_id,
                    "card_id": card_id,
                })
                if "error" in result:
                    console.print(f"[aura.red]Error: {result['error']}[/aura.red]")
                else:
                    client.config.current_persona = card.get("name", card_id)
                    console.print(f"[aura.green]✓ Personaje activo: {client.config.current_persona}[/aura.green]")
            except (ConnectionError, APIError) as exc:
                console.print(f"[aura.red]Error al activar personaje: {exc}[/aura.red]")
        else:
            console.print("[aura.red]Seleccion invalida.[/aura.red]")
    except ValueError:
        console.print("[aura.red]Debe ingresar un numero.[/aura.red]")


def chat_session(client: AURAClient) -> None:
    console.print(Panel(
        f"Sesion: [cyan]{client.config.session_id}[/cyan]\n"
        f"Personaje: [cyan]{client.config.current_persona or 'default'}[/cyan]\n"
        "[aura.yellow]Escribe 'salir' o 'exit' para terminar[/aura.yellow]",
        title="Chat con AURA",
        border_style="blue",
    ))
    while True:
        try:
            user_input = Prompt.ask("\n[aura.blue]Tu[/aura.blue]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[aura.yellow]Saliendo del chat...[/aura.yellow]")
            break
        if user_input.lower() in ("salir", "exit", "quit"):
            break
        if not user_input:
            continue

        messages = [{"role": "user", "content": user_input}]
        payload: Dict[str, Any] = {
            "messages": messages,
            "session_id": client.config.session_id,
        }
        if client.config.current_persona:
            payload["preferred_model"] = "auto"

        try:
            with console.status("[aura.blue]Pensando...[/aura.blue]", spinner="dots"):
                response = client._request("POST", "/api/local-ai/chat", json=payload)
            ai_response = response.get("response", "")
            model = response.get("model_used", "unknown")
            console.print(f"\n[aura.green]AURA ({model})[/aura.green]: ", end="")
            console.print(Markdown(ai_response))
        except (ConnectionError, APIError) as exc:
            console.print(f"[aura.red]Error: {exc}[/aura.red]")


def submit_swarm_task(client: AURAClient) -> None:
    console.print(Panel(
        "[aura.bold]Crear Tarea para Swarm[/aura.bold]\n"
        "Describe una tarea para el Agent Swarm de AURA.",
        border_style="magenta",
    ))
    description = Prompt.ask("Descripcion de la tarea").strip()
    if not description:
        console.print("[aura.red]La descripcion es requerida.[/aura.red]")
        return
    priority = Prompt.ask("Prioridad", choices=["low", "normal", "high"], default="normal")
    max_subtasks_str = Prompt.ask("Max subtasks", default="5")
    try:
        max_subtasks = int(max_subtasks_str)
    except ValueError:
        max_subtasks = 5
    execute = Confirm.ask("Ejecutar automaticamente?", default=False)

    payload = {
        "description": description,
        "priority": priority,
        "max_subtasks": max_subtasks,
        "execute": execute,
    }
    try:
        with console.status("[aura.blue]Enviando tarea al swarm...[/aura.blue]"):
            result = client._request("POST", "/api/swarm/tasks", json=payload)
        console.print(Panel(
            f"[aura.green]✓ Tarea enviada[/aura.green]\n"
            f"Status: {result.get('status', '?')}\n"
            f"Plan ID: {result.get('plan_id', '?')}\n"
            f"Tasks: {result.get('task_count', result.get('tasks', {}).get('count', 'n/a'))}",
            title="Swarm Task Result",
            border_style="magenta",
        ))
        if result.get("status") == "executed":
            exec_result = result.get("execution", {})
            completed = exec_result.get("completed_tasks", 0)
            console.print(f"  Tareas completadas: {completed}")
    except (ConnectionError, APIError) as exc:
        console.print(f"[aura.red]Error: {exc}[/aura.red]")


def show_swarm_status(client: AURAClient) -> None:
    try:
        data = client._request("GET", "/api/swarm/status")
        console.print(Panel(
            f"Total agents: {data.get('total_agents', 0)}\n"
            f"Active plans: {data.get('active_plans', 0)}\n"
            f"Active tasks: {data.get('active_tasks', 0)}\n"
            f"Execution history: {data.get('execution_history_count', 0)}\n"
            f"Status: {data.get('status', 'unknown')}",
            title="Swarm Status",
            border_style="magenta",
        ))
    except (ConnectionError, APIError) as exc:
        console.print(f"[aura.red]Error: {exc}[/aura.red]")


def main_menu(client: AURAClient) -> None:
    while True:
        console.print()
        table = Table(title="AURA CLI — Menu Principal", show_lines=True, border_style="cyan")
        table.add_column("[aura.bold]#[/aura.bold]", style="dim", width=4)
        table.add_column("Opcion", style="cyan")
        table.add_column("Descripcion", style="white")
        table.add_row("1", "Chat", "Conversacion interactiva con AURA")
        table.add_row("2", "Personajes", "Listar y seleccionar personajes")
        table.add_row("3", "Swarm Task", "Crear y ejecutar tareas en el Agent Swarm")
        table.add_row("4", "Swarm Status", "Estado del Agent Swarm")
        table.add_row("5", "Health", "Estado de salud del sistema (liveness/readiness)")
        table.add_row("6", "System Report", "Reporte maestro de los 30 modulos")
        table.add_row("7", "Reconnect", "Reconectar al servidor")
        table.add_row("0", "Exit", "Salir del cliente AURA")
        console.print(table)

        choice = Prompt.ask("\nSelecciona", default="1")
        if choice == "1":
            chat_session(client)
        elif choice == "2":
            select_persona(client)
        elif choice == "3":
            submit_swarm_task(client)
        elif choice == "4":
            show_swarm_status(client)
        elif choice == "5":
            show_health(client)
        elif choice == "6":
            show_system_report(client)
        elif choice == "7":
            if client._reconnect():
                console.print("[aura.green]✓ Reconectado exitosamente.[/aura.green]")
            else:
                console.print("[aura.red]✗ No se pudo reconectar.[/aura.red]")
        elif choice == "0":
            console.print("[aura.yellow]Hasta luego![/aura.yellow]")
            break
        else:
            console.print(f"[aura.red]Opcion invalida: {choice}[/aura.red]")


def main() -> None:
    show_banner()

    config = CLIConfig()
    client = AURAClient(config)

    console.print(f"[aura.blue]Conectando a {config.base_url}[/aura.blue]")
    if not client._reconnect():
        console.print(f"[aura.red]No se pudo conectar a {config.base_url}.[/aura.red]")
        console.print("[aura.yellow]El servidor AURA backend debe estar corriendo en localhost:8000.[/aura.yellow]")
        console.print("[aura.yellow]Ejecuta: python backend/main.py  o  uvicorn backend.main:app --reload[/aura.yellow]")
        retry = Confirm.ask("¿Intentar reconectar?", default=False)
        if retry:
            if client._reconnect():
                console.print("[aura.green]✓ Conectado.[/aura.green]")
            else:
                console.print("[aura.red]No se pudo conectar. Saliendo.[/aura.red]")
                sys.exit(1)
        else:
            sys.exit(1)

    show_health(client)
    main_menu(client)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[aura.yellow]Interrupcion del usuario. Saliendo...[/aura.yellow]")
        sys.exit(0)
