#!/usr/bin/env python3
"""LazyIncome-Hub — TUI central para actividades digitales."""

import sys
import asyncio
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Importaciones internas (mocks por ahora)
sys.path.insert(0, str(BASE))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Header,
    Footer,
    Static,
    DataTable,
    RichLog,
    Button,
    Input,
)
from textual.reactive import reactive
from rich.text import Text
from modules.scraper import get_products
from modules.video import list_videos
from modules.tasks import load_tasks, save_task


class LazyIncomeHub(App):
    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    #panels { height: 1fr; }
    #right { width: 40; }
    #footer_bar { height: 3; content-align: center middle; color: #00ff88; background: #0a0a0f; }
    DataTable { height: 100%; border: solid #00ff88; }
    RichLog { height: 100%; border: solid #00ff88; }
    """

    BINDINGS = [
        ("q", "quit", "Salir"),
        ("s", "scrape", "Scrape"),
        ("o", "optimize", "Optimizar"),
        ("t", "add_task", "Nueva tarea"),
        ("tab", "next_panel", "Siguiente panel"),
    ]

    current_panel = reactive(0)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="panels"):
            with Vertical(id="left"):
                yield Static("📦 MercadoLibre Tracker")
                yield DataTable(id="ml_table")
                yield Static("🎬 Video Manager")
                yield DataTable(id="video_table")
            with Vertical(id="right"):
                yield Static("📝 Log de Tareas")
                yield RichLog(id="task_log", wrap=True, markup=True)
        with Horizontal(id="footer_bar"):
            yield Static(" ⌨️  q: Salir | s: Scrape | o: Optimizar | t: Tarea | Tab: Panel ")
        yield Footer()

    def on_mount(self) -> None:
        table_ml = self.query_one("#ml_table", DataTable)
        table_ml.add_columns("Producto", "Stock", "Precio", "Alertas")
        products = get_products()
        for p in products:
            table_ml.add_row(*p)

        table_v = self.query_one("#video_table", DataTable)
        table_v.add_columns("Archivo", "Tamaño", "Estado")
        videos = list_videos()
        for v in videos:
            table_v.add_row(*v)

        log = self.query_one("#task_log", RichLog)
        tasks = load_tasks()
        for t in tasks:
            log.write(Text.from_markup(t))

    def action_scrape(self) -> None:
        log = self.query_one("#task_log", RichLog)
        log.write(Text.from_markup("[yellow]Ejecutando scrape de precios...[/yellow]"))
        try:
            from modules.scraper import run_scrape

            run_scrape()
            log.write(Text.from_markup("[green]Scrape completado.[/green]"))
        except Exception as e:
            log.write(Text.from_markup(f"[red]Error: {e}[/red]"))

    def action_optimize(self) -> None:
        log = self.query_only("#task_log", RichLog)
        log.write(Text.from_markup("[yellow]Optimizando video...[/yellow]"))
        try:
            from modules.video import optimize_selected

            optimize_selected()
            log.write(Text.from_markup("[green]Optimización finalizada.[/green]"))
        except Exception as e:
            log.write(Text.from_markup(f"[red]Error: {e}[/red]"))

    def action_add_task(self) -> None:
        log = self.query_one("#task_log", RichLog)
        log.write(
            Text.from_markup("[cyan]Registrar tarea (formato: horas|plataforma|ingreso)[/cyan]")
        )
        # En una versión completa se abriría un Input modal; por ahora se registra un ejemplo
        save_task("1.5", "Toloka", "3.20 USD")
        log.write(Text.from_markup("[green]Tarea registrada.[/green]"))

    def action_next_panel(self) -> None:
        self.current_panel = (self.current_panel + 1) % 2


if __name__ == "__main__":
    app = LazyIncomeHub()
    app.run()
