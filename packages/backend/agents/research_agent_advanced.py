# -*- coding: utf-8 -*-
"""AURA OS - Research Agent Advanced (OPCION B - SIMULADO)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.ResearchAgent")


def _qwen_generate(prompt: str, max_tokens: int = 256, temperature: float = 0.7) -> str:
    """Generate text using Qwen 0.5B local model (lazy)."""
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
        model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen2.5-0.5B-Instruct",
            torch_dtype=torch.float32,
        )
        messages = [
            {"role": "system", "content": "Eres un analista de investigacion experto."},
            {"role": "user", "content": prompt},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            out = model.generate(
                **inputs, max_new_tokens=max_tokens, temperature=temperature,
                do_sample=True, pad_token_id=tokenizer.eos_token_id,
            )
        result = tokenizer.decode(out[0][len(inputs["input_ids"][0]):], skip_special_tokens=True)
        return result.strip()
    except Exception as exc:
        logger.debug("qwen_generate fallo: %s", exc)
        return ""


async def search_news_deep(query: str = "tecnologia IA", count: int = 5) -> List[Dict[str, Any]]:
    """Busca noticias profundas (SIMULADO - retorna articulos fake)."""
    logger.info("[RESEARCH] Buscando noticias: '%s' (count=%d)", query, count)
    await asyncio.sleep(0.5)  # Simular busqueda

    fake_articles = [
        {
            "title": f"Avances en {query}: Nuevos modelos de IA superan benchmarks",
            "content": "Investigadores revelan arquitecturas innovadoras que reducen error en un 40%...",
            "source": "TechDaily",
            "url": f"https://techdaily.example.com/ia-{query.replace(' ', '-')}",
            "published": datetime.now().isoformat(),
        },
        {
            "title": f"Industria de {query} crece un 150% en 2026",
            "content": "Empresas de todo el mundo incrementan inversiones en capacidades de IA...",
            "source": "AIWeekly",
            "url": f"https://aiweekly.example.com/crecimiento-{query.replace(' ', '-')}",
            "published": datetime.now().isoformat(),
        },
        {
            "title": f"Desafios éticos en {query}: Un marco regulatorio global",
            "content": "Gobiernos y expertos debaten sobre límites éticos y gobernanza...",
            "source": "EthicsReview",
            "url": f"https://ethicsreview.example.com/etica-{query.replace(' ', '-')}",
            "published": datetime.now().isoformat(),
        },
        {
            "title": f"{query} al alcance de PYMES: Precios bajan un 80%",
            "content": "Plataformas en la nube democratizan el acceso a modelos de ultima generacion...",
            "source": "StartupNews",
            "url": f"https://startupnews.example.com/pymes-{query.replace(' ', '-')}",
            "published": datetime.now().isoformat(),
        },
        {
            "title": f"Multi-modalidad en {query}: Vision + lenguaje + audio",
            "content": "Modelos unifican comprension de imagenes, texto y sonido en tiempo real...",
            "source": "VisionLab",
            "url": f"https://visionlab.example.com/multimodal-{query.replace(' ', '-')}",
            "published": datetime.now().isoformat(),
        },
    ]

    return fake_articles[:count]


async def analyze_trends(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analiza tendencias usando Qwen para cada articulo."""
    logger.info("[RESEARCH] Analizando %d articulos...", len(articles))
    await asyncio.sleep(0.3)

    trends = []
    for article in articles:
        prompt = (
            f"Analiza este articulo y extrae:\n"
            f"1. Sentimiento (positivo/negativo/neutral)\n"
            f"2. Impacto (alto/medio/bajo)\n"
            f"3. Relevancia para AURA OS (0-10)\n"
            f"Articulo: {article.get('title', '')} - {article.get('content', '')[:200]}"
        )
        analysis_text = _qwen_generate(prompt, max_tokens=128)

        trends.append({
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "sentimiento": "neutral",
            "impacto": "medio",
            "relevancia": 7,
            "analysis": analysis_text or "Analisis automatico",
            "timestamp": datetime.now().isoformat(),
        })

    summary = f"Analizados {len(articles)} articulos. Tendencia general: crecimiento y adopcion de IA."
    return {"trends": trends, "summary": summary, "count": len(trends)}


async def extract_insights(trends_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extrae insights accionables de las tendencias analizadas."""
    logger.info("[RESEARCH] Extrayendo insights de %d tendencias...", trends_data.get("count", 0))
    await asyncio.sleep(0.3)

    trends = trends_data.get("trends", [])
    insights = []

    for trend in trends:
        prompt = (
            f"De esta tendencia, extrae 3 insights accionables para un asistente de IA:\n"
            f"Tendencia: {trend.get('title', '')}\n"
            f"Analisis: {trend.get('analysis', '')[:200]}"
        )
        insights_text = _qwen_generate(prompt, max_tokens=192)

        insights.append({
            "title": f"Insight: {trend.get('title', '')[:60]}",
            "description": insights_text or "Insight extraido automaticamente",
            "accionable": True,
            "relevancia": trend.get("relevancia", 5),
            "timestamp": datetime.now().isoformat(),
        })

    return insights


async def store_research_findings(insights: List[Dict[str, Any]]) -> str:
    """Guarda findings en data/research_findings.json (append)."""
    data_dir = "data"
    findings_file = os.path.join(data_dir, "research_findings.json")

    os.makedirs(data_dir, exist_ok=True)

    existing = []
    if os.path.exists(findings_file):
        try:
            with open(findings_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    for insight in insights:
        insight["stored_at"] = datetime.now().isoformat()
        existing.append(insight)

    try:
        with open(findings_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("store_research_findings fallo: %s", exc)

    logger.info("[RESEARCH] Guardados %d insights en %s", len(insights), findings_file)
    return findings_file


async def run_research_cycle(query: str = "tecnologia IA") -> Dict[str, Any]:
    """Ejecuta un ciclo completo de investigacion."""
    articles = await search_news_deep(query=query)
    trends = await analyze_trends(articles)
    insights = await extract_insights(trends)
    findings_file = await store_research_findings(insights)

    return {
        "articles": len(articles),
        "trends": trends.get("count", 0),
        "insights": len(insights),
        "findings_file": findings_file,
        "timestamp": datetime.now().isoformat(),
    }