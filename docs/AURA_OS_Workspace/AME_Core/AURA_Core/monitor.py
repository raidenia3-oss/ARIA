import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- NOTICIAS MUNDIALES ---
def get_world_news() -> list:
    sources = []
    # BBC Mundo
    try:
        res = requests.get("https://feeds.bbci.co.uk/mundo/rss.xml", headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        for item in soup.find_all("item")[:3]:
            title = item.find("title").text if item.find("title") else ""
            desc = item.find("description").text if item.find("description") else ""
            sources.append(f"[BBC] {title}: {desc[:120]}")
    except: pass
    # Reuters RSS
    try:
        res = requests.get("https://feeds.reuters.com/reuters/topNews", headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        for item in soup.find_all("item")[:3]:
            title = item.find("title").text if item.find("title") else ""
            sources.append(f"[Reuters] {title}")
    except: pass
    # Al Jazeera
    try:
        res = requests.get("https://www.aljazeera.com/xml/rss/all.xml", headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        for item in soup.find_all("item")[:2]:
            title = item.find("title").text if item.find("title") else ""
            sources.append(f"[AlJazeera] {title}")
    except: pass
    return sources

# --- PRECIOS: CRYPTO ---
def get_crypto_prices() -> dict:
    try:
        res = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin,ethereum,solana,cardano", "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=5
        )
        data = res.json()
        result = {}
        for coin, info in data.items():
            change = info.get("usd_24h_change", 0)
            result[coin] = {"price": info["usd"], "change_24h": round(change, 2)}
        return result
    except:
        return {}

# --- PRECIOS: ACCIONES ---
def get_stock_prices() -> dict:
    tickers = ["NVDA", "AAPL", "MSFT", "TSLA", "AMD"]
    result = {}
    for ticker in tickers:
        try:
            res = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                headers=HEADERS,
                params={"interval": "1d", "range": "2d"},
                timeout=5
            )
            data = res.json()
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            if len(closes) >= 2 and closes[-1] and closes[-2]:
                price = round(closes[-1], 2)
                change = round(((closes[-1] - closes[-2]) / closes[-2]) * 100, 2)
                result[ticker] = {"price": price, "change_24h": change}
        except:
            continue
    return result

# --- MATERIAS PRIMAS (Gold, Oil via Yahoo) ---
def get_commodities() -> dict:
    symbols = {"GC=F": "Oro", "CL=F": "Petroleo", "SI=F": "Plata"}
    result = {}
    for symbol, name in symbols.items():
        try:
            res = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                headers=HEADERS,
                params={"interval": "1d", "range": "2d"},
                timeout=5
            )
            data = res.json()
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            if len(closes) >= 2 and closes[-1] and closes[-2]:
                price = round(closes[-1], 2)
                change = round(((closes[-1] - closes[-2]) / closes[-2]) * 100, 2)
                result[name] = {"price": price, "change_24h": change}
        except:
            continue
    return result

# --- RESUMEN COMPLETO ---
def get_market_summary() -> str:
    out = "\n=== MERCADOS ===\n"
    crypto = get_crypto_prices()
    for coin, data in crypto.items():
        arrow = "▲" if data["change_24h"] > 0 else "▼"
        out += f"{coin.upper()}: ${data['price']:,} {arrow}{abs(data['change_24h'])}%\n"
    stocks = get_stock_prices()
    out += "\n--- Acciones ---\n"
    for ticker, data in stocks.items():
        arrow = "▲" if data["change_24h"] > 0 else "▼"
        out += f"{ticker}: ${data['price']} {arrow}{abs(data['change_24h'])}%\n"
    commodities = get_commodities()
    out += "\n--- Materias Primas ---\n"
    for name, data in commodities.items():
        arrow = "▲" if data["change_24h"] > 0 else "▼"
        out += f"{name}: ${data['price']} {arrow}{abs(data['change_24h'])}%\n"
    return out