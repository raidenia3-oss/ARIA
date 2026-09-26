"""Scraper y datos de MercadoLibre."""

from pathlib import Path
import json

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "products"
DATA.mkdir(parents=True, exist_ok=True)
PRODUCTS_FILE = DATA / "products.json"


def _seed_products() -> list:
    if not PRODUCTS_FILE.exists():
        data = [
            ["Auriculares Sony", "15", "120.00 USD", "Nuevo competidor"],
            ["Mouse Logitech", "8", "45.50 USD", ""],
            ["Teclado Mecánico", "3", "89.99 USD", "Stock bajo"],
        ]
        PRODUCTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))


def get_products() -> list:
    return _seed_products()


def run_scrape() -> None:
    # Simula un scrape de precios: en una versión real se consultan enlaces
    data = _seed_products()
    # modificación simulada: bajar 1 USD al primer producto
    if data:
        row = data[0]
        price = float(row[2].split()[0]) - 1.0
        row[2] = f"{price:.2f} USD"
        PRODUCTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
