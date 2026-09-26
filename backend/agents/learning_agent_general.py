# -*- coding: utf-8 -*-
"""AURA OS - General Learning Agent (arXiv + News + Failures)."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Dict, List

logger = logging.getLogger("AURA.GeneralLearning")

JAN_URL = os.getenv("JAN_URL", "http://localhost:1337/v1")


async def _call_jan(prompt: str, system: str = "") -> str:
    try:
        import urllib.request
        import json

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = json.dumps({
            "model": "gemma-3-1b-it",
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": 1024,
            "stream": False,
        }).encode()

        req = urllib.request.Request(
            f"{JAN_URL}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
        return ((result.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    except Exception as exc:
        logger.warning("[LEARNING] Jan no disponible: %s", exc)
        return ""


async def learn_from_arxiv() -> List[Dict[str, Any]]:
    """Aprende de papers recientes de arxiv.org."""
    insights = []
    try:
        import urllib.request

        url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+AND+cat:cs.LG&start=0&max_results=5&sortBy=submittedDate&sortOrder=descending"
        with urllib.request.urlopen(url, timeout=30) as r:
            data = r.read().decode("utf-8")

        titles = re.findall(r"<title>(.*?)</title>", data, re.DOTALL)
        papers = [t.strip() for t in titles[1:6] if t.strip()]

        if papers:
            analysis = await _call_jan(
                f"Resumen ejecutivo de estos 5 papers de IA:\n{papers}",
                system="Eres un investigador de IA. Extrae conceptos clave, aplicaciones e innovaciones.",
            )
            insights.append({
                "source": "arxiv",
                "papers": papers,
                "analysis": analysis,
                "timestamp": asyncio.get_event_loop().time(),
            })
            logger.info("[LEARNING] arXiv: %d papers analizados", len(papers))
    except Exception as exc:
        logger.error("[LEARNING] arXiv error: %s", exc)

    return insights


async def learn_from_news() -> List[Dict[str, Any]]:
    """Aprende de noticias tech (HackerNews)."""
    insights = []
    try:
        import urllib.request
        import json

        with urllib.request.urlopen("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15) as r:
            story_ids = json.loads(r.read())[:5]

        stories = []
        for sid in story_ids:
            try:
                with urllib.request.urlopen(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=10) as r:
                    story = json.loads(r.read())
                    stories.append(story.get("title", ""))
            except Exception:
                pass

        if stories:
            analysis = await _call_jan(
                f"Noticias tech de hoy:\n{stories}\n¿Qué significa esto para AURA? ¿Qué oportunidades ves?",
                system="Eres un estratega de technology. Analiza tendencias y oportunidades de negocio.",
            )
            insights.append({
                "source": "hackernews",
                "stories": stories,
                "analysis": analysis,
                "timestamp": asyncio.get_event_loop().time(),
            })
            logger.info("[LEARNING] News: %d historias analizadas", len(stories))
    except Exception as exc:
        logger.error("[LEARNING] News error: %s", exc)

    return insights


async def learn_from_failures() -> List[Dict[str, Any]]:
    """Aprende de errores recientes en logs."""
    insights = []
    try:
        log_dir = "logs"
        if os.path.isdir(log_dir):
            log_files = sorted(os.listdir(log_dir), reverse=True)
            if log_files:
                log_path = os.path.join(log_dir, log_files[0])
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    log_content = f.read()[-2000:]

                analysis = await _call_jan(
                    f"Analiza estos logs de error y sugiere fixes:\n{log_content}",
                    system="Eres un ingeniero de software. Identifica la causa raiz y sugiere fixes automaticos.",
                )
                insights.append({
                    "source": "logs",
                    "log_file": log_files[0],
                    "analysis": analysis,
                    "timestamp": asyncio.get_event_loop().time(),
                })
                logger.info("[LEARNING] Failures analizados de %s", log_files[0])
    except Exception as exc:
        logger.error("[LEARNING] Failures error: %s", exc)

    return insights


class GeneralLearningAgent:
    """Agente de aprendizaje general."""

    async def learn_all(self) -> Dict[str, Any]:
        """Ejecuta todos los ciclos de aprendizaje."""
        arxiv_insights = await learn_from_arxiv()
        news_insights = await learn_from_news()
        failure_insights = await learn_from_failures()

        total = len(arxiv_insights) + len(news_insights) + len(failure_insights)
        return {
            "arxiv": arxiv_insights,
            "news": news_insights,
            "failures": failure_insights,
            "total_insights": total,
        }
