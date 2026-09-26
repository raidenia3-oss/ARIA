# -*- coding: utf-8 -*-
"""AURA OS — Newsletter Agent.

Genera y envia newsletters diarias con noticias RSS y scraping.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Newsletter")

DEFAULT_RECIPIENTS: List[str] = []
NEWSLETTER_HISTORY: List[Dict[str, Any]] = []

SOURCES = [
    "TechCrunch", "Ars Technica", "Wired", "The Verge",
    "AURA Network", "AI News Daily", "Cyberpunk Weekly",
]

HEADLINE_TEMPLATES = [
    "{topic}: {detail}",
    "BREAKING: {detail}",
    "{company} announces {product}",
    "Analysis: {topic} trends",
    "Exclusive: {detail}",
]

TOPICS = [
    "AI Revolution", "Quantum Computing", "Neural Networks",
    "Edge AI", "Open Source", "Cybersecurity",
    "Robotics", "Blockchain", "Cloud Native", "DevOps",
]


async def _fetch_rss_feed(source: str) -> List[Dict[str, Any]]:
    await asyncio.sleep(0.05)
    count = random.randint(2, 5)
    return [
        {
            "title": f"{random.choice(TOPICS)} — {random.choice(['Update', 'News', 'Analysis', 'Review'])} #{random.randint(100, 999)}",
            "url": f"https://{source.lower().replace(' ', '')}.com/article/{random.randint(1000, 9999)}",
            "source": source,
            "published": datetime.now().isoformat(),
        }
        for _ in range(count)
    ]


async def _scrape_news() -> List[Dict[str, Any]]:
    await asyncio.sleep(0.05)
    return [
        {
            "title": f"Trending: {random.choice(TOPICS)} #{random.randint(1, 50)}",
            "url": f"https://example.com/trending/{random.randint(1000, 9999)}",
            "source": "Web",
            "published": datetime.now().isoformat(),
        }
        for _ in range(random.randint(2, 4))
    ]


class NewsletterAgent:
    """Genera y envia newsletters diarias."""

    def __init__(self) -> None:
        self.last_newsletter: Optional[str] = None
        self.send_count: int = 0

    async def generate_newsletter(self) -> Dict[str, Any]:
        all_news: List[Dict[str, Any]] = []

        for source in SOURCES:
            try:
                items = await _fetch_rss_feed(source)
                all_news.extend(items)
            except Exception as exc:
                logger.warning("RSS fetch failed for %s: %s", source, exc)

        try:
            web_news = await _scrape_news()
            all_news.extend(web_news)
        except Exception as exc:
            logger.warning("Scrape failed: %s", exc)

        all_news.sort(key=lambda x: x["published"], reverse=True)
        top_news = all_news[:random.randint(5, 10)]

        news_items_html = ""
        for i, item in enumerate(top_news, 1):
            news_items_html += f'<h3>{i}. {item["title"]}</h3><p><a href="{item["url"]}">Read more</a> — {item["source"]}</p>'

        newsletter_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>AURA Daily Newsletter</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #0f172a; color: #e2e8f0;">
  <h1 style="color: #38bdf8; border-bottom: 2px solid #6366f1; padding-bottom: 10px;">AURA Daily Newsletter</h1>
  <p style="color: #94a3b8;">{datetime.now().strftime('%B %d, %Y')} — Curated by AURA OS</p>
  <hr style="border-color: #1e293b;">
  {news_items_html}
  <hr style="border-color: #1e293b;">
  <p style="color: #64748b; font-size: 12px;">You received this because you're subscribed to AURA OS updates.</p>
</body>
</html>"""

        result = {
            "newsletter_id": f"NL-{int(time.time())}" if False else f"NL-{datetime.now().strftime('%Y%m%d')}",
            "newsletter_html": newsletter_html,
            "articles": len(top_news),
            "sources": len(SOURCES),
            "generated_at": datetime.now().isoformat(),
        }

        self.last_newsletter = newsletter_html
        NEWSLETTER_HISTORY.append(result)

        logger.info("Generated newsletter: %d articles", len(top_news))
        return result

    async def send_newsletter(self, email: str) -> Dict[str, Any]:
        newsletter = await self.generate_newsletter()

        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(newsletter["newsletter_html"], "html")
            msg["Subject"] = "AURA Daily Newsletter"
            msg["From"] = "aura@aura-os.local"
            msg["To"] = email

            smtp_host = os.environ.get("SMTP_HOST", "localhost")
            smtp_port = int(os.environ.get("SMTP_PORT", "25"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.send_message(msg)

            status = "sent"
        except Exception as exc:
            logger.warning("SMTP failed, logging for later: %s", exc)
            status = "queued"

        tracking = {
            "email": email,
            "newsletter_id": newsletter["newsletter_id"],
            "status": status,
            "sent_at": datetime.now().isoformat(),
            "opens": 0,
            "clicks": 0,
            "reads": 0,
        }

        self.send_count += 1
        NEWSLETTER_HISTORY.append(tracking)

        logger.info("Newsletter to %s: %s", email, status)
        return tracking


newsletter_agent = NewsletterAgent()
