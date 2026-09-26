"""Localization manager for AURA."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SupportedLanguage(str, Enum):
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    CHINESE_SIMPLIFIED = "zh-cn"
    CHINESE_TRADITIONAL = "zh-tw"
    JAPANESE = "ja"
    KOREAN = "ko"
    THAI = "th"
    VIETNAMESE = "vi"
    TURKISH = "tr"
    POLISH = "pl"
    DUTCH = "nl"
    SWEDISH = "sv"
    NORWEGIAN = "no"
    DANISH = "da"
    FINNISH = "fi"


@dataclass
class LanguageMetrics:
    language: str
    stories_generated: int
    stories_published: int
    avg_quality_score: float
    engagement_rate: float
    monthly_earnings: float
    last_updated: str


class LocalizationManager:
    def __init__(self, db) -> None:
        self.db = db
        self.supported_langs = [lang.value for lang in SupportedLanguage]
        self.prompt_templates = self._init_prompt_templates()

    async def detect_language(self, text: str) -> str:
        try:
            from langdetect import detect
            detected = detect(text)
            if detected in self.supported_langs:
                return detected
        except Exception:
            pass
        return SupportedLanguage.ENGLISH.value

    def get_supported_languages(self) -> List[Dict[str, Any]]:
        return [
            {
                "code": lang.value,
                "name": self._get_language_name(lang),
                "native_name": self._get_native_name(lang),
                "region": self._get_region(lang),
            }
            for lang in SupportedLanguage
        ]

    def _get_language_name(self, lang: SupportedLanguage) -> str:
        names = {
            SupportedLanguage.ENGLISH: "English",
            SupportedLanguage.SPANISH: "Spanish",
            SupportedLanguage.FRENCH: "French",
            SupportedLanguage.GERMAN: "German",
            SupportedLanguage.ITALIAN: "Italian",
            SupportedLanguage.PORTUGUESE: "Portuguese",
            SupportedLanguage.RUSSIAN: "Russian",
            SupportedLanguage.CHINESE_SIMPLIFIED: "Chinese (Simplified)",
            SupportedLanguage.CHINESE_TRADITIONAL: "Chinese (Traditional)",
            SupportedLanguage.JAPANESE: "Japanese",
            SupportedLanguage.KOREAN: "Korean",
            SupportedLanguage.THAI: "Thai",
            SupportedLanguage.VIETNAMESE: "Vietnamese",
            SupportedLanguage.TURKISH: "Turkish",
            SupportedLanguage.POLISH: "Polish",
            SupportedLanguage.DUTCH: "Dutch",
            SupportedLanguage.SWEDISH: "Swedish",
            SupportedLanguage.NORWEGIAN: "Norwegian",
            SupportedLanguage.DANISH: "Danish",
            SupportedLanguage.FINNISH: "Finnish",
        }
        return names.get(lang, "Unknown")

    def _get_native_name(self, lang: SupportedLanguage) -> str:
        names = {
            SupportedLanguage.ENGLISH: "English",
            SupportedLanguage.SPANISH: "Español",
            SupportedLanguage.FRENCH: "Français",
            SupportedLanguage.GERMAN: "Deutsch",
            SupportedLanguage.ITALIAN: "Italiano",
            SupportedLanguage.PORTUGUESE: "Português",
            SupportedLanguage.RUSSIAN: "Русский",
            SupportedLanguage.CHINESE_SIMPLIFIED: "简体中文",
            SupportedLanguage.CHINESE_TRADITIONAL: "繁體中文",
            SupportedLanguage.JAPANESE: "日本語",
            SupportedLanguage.KOREAN: "한국어",
            SupportedLanguage.THAI: "ไทย",
            SupportedLanguage.VIETNAMESE: "Tiếng Việt",
            SupportedLanguage.TURKISH: "Türkçe",
            SupportedLanguage.POLISH: "Polski",
            SupportedLanguage.DUTCH: "Nederlands",
            SupportedLanguage.SWEDISH: "Svenska",
            SupportedLanguage.NORWEGIAN: "Norsk",
            SupportedLanguage.DANISH: "Dansk",
            SupportedLanguage.FINNISH: "Suomi",
        }
        return names.get(lang, "?")

    def _get_region(self, lang: SupportedLanguage) -> str:
        regions = {
            SupportedLanguage.ENGLISH: "Global",
            SupportedLanguage.SPANISH: "Latin America, Spain",
            SupportedLanguage.FRENCH: "France, Africa",
            SupportedLanguage.GERMAN: "Germany, Austria",
            SupportedLanguage.PORTUGUESE: "Brazil, Portugal",
            SupportedLanguage.RUSSIAN: "Russia, Eastern Europe",
            SupportedLanguage.CHINESE_SIMPLIFIED: "China",
            SupportedLanguage.CHINESE_TRADITIONAL: "Taiwan, Hong Kong",
            SupportedLanguage.JAPANESE: "Japan",
            SupportedLanguage.KOREAN: "South Korea",
            SupportedLanguage.THAI: "Thailand",
        }
        return regions.get(lang, "Unknown")

    def _init_prompt_templates(self) -> Dict[str, Dict[str, str]]:
        return {
            "es": {
                "system_prompt": "Eres un escritor de historias épicas en español. Genera narrativas coherentes sin clichés.",
                "generation_instruction": "Escribe la primera escena cautivadora de la historia.",
            },
            "en": {
                "system_prompt": "You are an epic storyteller in English. Generate coherent narratives without clichés.",
                "generation_instruction": "Write the gripping first scene of the story.",
            },
            "fr": {
                "system_prompt": "Vous êtes un conteur épique en français. Générez des récits cohérents sans clichés.",
                "generation_instruction": "Écrivez la première scène captivante de l'histoire.",
            },
            "de": {
                "system_prompt": "Du bist ein epischer Geschichtenerzähler auf Deutsch. Generiere kohärente Erzählungen ohne Klischees.",
                "generation_instruction": "Schreiben Sie die fesselnde erste Szene der Geschichte.",
            },
            "pt": {
                "system_prompt": "Você é um narrador épico em português. Gere narrativas coerentes sem clichês.",
                "generation_instruction": "Escreva a primeira cena cativante da história.",
            },
            "ja": {
                "system_prompt": "あなたは日本語の壮大なストーリーテラーです。陳腐な言い回しを避けた一貫性のある物語を生成します。",
                "generation_instruction": "物語の魅力的な最初のシーンを書いてください。",
            },
            "zh-cn": {
                "system_prompt": "你是一位中文叙事大师。生成连贯的故事，避免陈词滥调。",
                "generation_instruction": "写出这个故事的引人入胜的开场景。",
            },
        }

    def get_language_metrics(self) -> List[LanguageMetrics]:
        metrics: List[LanguageMetrics] = []
        for lang in SupportedLanguage:
            data: Dict[str, Any] = {}
            if self.db:
                try:
                    data = self.db.get_language_metrics(lang.value) or {}
                except Exception:
                    data = {}
            metrics.append(
                LanguageMetrics(
                    language=lang.value,
                    stories_generated=int(data.get("generated", 0)),
                    stories_published=int(data.get("published", 0)),
                    avg_quality_score=float(data.get("avg_quality", 0)),
                    engagement_rate=float(data.get("engagement", 0)),
                    monthly_earnings=float(data.get("earnings", 0)),
                    last_updated=datetime.now().isoformat(),
                )
            )
        return metrics

    def get_trending_languages(self, limit: int = 5) -> List[Dict[str, Any]]:
        metrics = self.get_language_metrics()
        sorted_metrics = sorted(metrics, key=lambda m: m.engagement_rate, reverse=True)
        return [
            {
                "language": m.language,
                "name": self._get_language_name(SupportedLanguage(m.language)),
                "stories_published": m.stories_published,
                "engagement_rate": m.engagement_rate,
                "monthly_earnings": m.monthly_earnings,
            }
            for m in sorted_metrics[:limit]
        ]

    async def optimize_by_language_demand(self) -> Dict[str, Any]:
        trending = self.get_trending_languages(10)
        weights = {
            item["language"]: max(0.1, 0.8 - (i * 0.1))
            for i, item in enumerate(trending[:3])
        }
        if self.db:
            try:
                self.db.update_language_weights(weights)
            except Exception:
                pass
        return {"status": "optimized", "weights": weights}

    def build_localized_prompt(self, params: Dict[str, Any], language: str) -> str:
        template = self.prompt_templates.get(language, self.prompt_templates.get("en", {}))
        prompt = f"""
{template.get('system_prompt', '')}

Título: {params.get('title', '')}
Premisa: {params.get('premise', '')}
Personajes: {', '.join(params.get('characters', []))}
Tono: {params.get('tone', 'dramatic')}

{template.get('generation_instruction', 'Write the first scene.')}
""".strip()
        return prompt
