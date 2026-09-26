# AURA Autonomous News Worker
# Corre cada 6 horas, busca noticias, analiza, guarda, recomienda

import os
import requests
import psycopg2
import feedparser
import time
import schedule
from datetime import datetime

# ENV VARS
DATABASE_URL = os.getenv("DATABASE_URL")
QWEN_URL = os.getenv("QWEN_URL", "https://raiden456-slut.hf.space/v1/chat/completions")
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")


# Conexión PostgreSQL (con reintentos ante caídas transitorias)
def get_db(retries=3, delay=2):
    last_error = None
    for attempt in range(retries):
        try:
            return psycopg2.connect(DATABASE_URL)
        except Exception as e:
            last_error = e
            print(f"[AURA] Reintento {attempt + 1}/{retries} de conexión a DB: {e}")
            time.sleep(delay)
    raise last_error


# Buscar noticias desde RSS
def fetch_news():
    articles = []

    # MyAnimeList RSS
    feed = feedparser.parse("https://myanimelist.net/rss.php")
    for entry in feed.entries[:5]:
        articles.append(
            {
                "title": entry.title,
                "url": entry.link,
                "source": "MyAnimeList",
                "summary": entry.get("summary", ""),
            }
        )

    # Anime News Network
    feed = feedparser.parse("https://www.animenewsnetwork.com/news/rss.xml")
    for entry in feed.entries[:5]:
        articles.append(
            {
                "title": entry.title,
                "url": entry.link,
                "source": "ANN",
                "summary": entry.get("summary", ""),
            }
        )

    # HackerNews (via API)
    try:
        r = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5
        )
        top_ids = r.json()[:5]
        for story_id in top_ids:
            story = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            ).json()
            articles.append(
                {
                    "title": story.get("title", ""),
                    "url": story.get("url", ""),
                    "source": "HackerNews",
                    "summary": "",
                }
            )
    except:
        pass

    return articles


# Analizar con Qwen2.5
def analyze_article(article):
    prompt = f"""Analiza este artículo en JSON puro:

Título: {article['title']}
Resumen: {article['summary']}

Retorna SOLO JSON (sin backticks):
{{"tema": "string", "relevancia": "1-10", "por_que": "razón corta", "keywords": ["array"]}}
"""

    try:
        r = requests.post(
            QWEN_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": "Qwen2.5-Coder-3B",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=15,
        )

        if r.status_code == 200:
            response = r.json()
            text = response["choices"][0]["message"]["content"]
            import json

            analysis = json.loads(text)
            return analysis

        return {"tema": "unknown", "relevancia": 5, "por_que": "no-200", "keywords": []}
    except Exception as e:
        print(f"Error analizando: {e}")
        return {"tema": "unknown", "relevancia": 5, "por_que": "error", "keywords": []}


# Guardar en PostgreSQL
def save_to_db(article, analysis):
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO news_articles
            (url, title, source, summary, analysis, relevance, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            (
                article["url"],
                article["title"],
                article["source"],
                article["summary"],
                str(analysis),
                int(analysis.get("relevancia", 5)),
                datetime.now(),
            ),
        )
        conn.commit()
    except Exception as e:
        print(f"Error guardando en DB: {e}")
    finally:
        cur.close()
        conn.close()


# Recomendar y notificar
def recommend_news():
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, title, source, relevance, analysis
            FROM news_articles
            ORDER BY relevance DESC
            LIMIT 3
        """)

        recommendations = []
        for row in cur.fetchall():
            recommendations.append(
                {
                    "id": row[0],
                    "title": row[1],
                    "source": row[2],
                    "relevance": row[3],
                    "analysis": row[4],
                }
            )

        try:
            requests.post(
                f"{FASTAPI_URL}/api/news/recommend",
                json={"articles": recommendations},
                timeout=10,
            )
        except Exception as e:
            print(f"Error enviando recomendaciones: {e}")

    except Exception as e:
        print(f"Error obteniendo recomendaciones: {e}")
    finally:
        cur.close()
        conn.close()


# Main loop
def run_worker():
    print("[AURA] Iniciando News Worker...")
    articles = fetch_news()
    print(f"[AURA] Encontradas {len(articles)} noticias")

    for article in articles:
        print(f"[AURA] Analizando: {article['title'][:50]}")
        analysis = analyze_article(article)
        save_to_db(article, analysis)

    print("[AURA] Generando recomendaciones...")
    recommend_news()
    print("[AURA] Ciclo completado")


# Schedule each 6 hours
schedule.every(6).hours.do(run_worker)

if __name__ == "__main__":
    run_worker()  # First run immediately

    while True:
        schedule.run_pending()
        time.sleep(60)
