# -*- coding: utf-8 -*-
"""AURA OS — Social Media Agent.

Genera tweets, LinkedIn posts y gestiona publicacion automatica.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Social")

CYBERPUNK_EMOJIS = ["🔥", "⚡", "🧠", "🤖", "💻", "🌐", "🎯", "🚀", "⚔️", "💠", "🔧", "🛡️"]
HASHTAG_POOL = [
    "AIOps", "AI", "MachineLearning", "Cyberpunk", "Netrunner",
    "Tech", "Innovation", "OpenSource", "AIAlert", "DataScience",
    "DeepLearning", "EdgeAI", "NeuralNet", "FutureTech", "AURA",
]

TWEET_MAX = 280
LINKEDIN_MAX = 3000


def _pick_emojis(n: int = 2) -> str:
    return " ".join(random.sample(CYBERPUNK_EMOJIS, min(n, len(CYBERPUNK_EMOJIS))))


def _pick_hashtags(n: int = 3) -> str:
    return " ".join(f"#{h}" for h in random.sample(HASHTAG_POOL, min(n, len(HASHTAG_POOL))))


class SocialMediaAgent:
    """Genera contenido para redes sociales."""

    def __init__(self) -> None:
        self.posts_today: int = 0
        self.last_tweet: Optional[str] = None
        self.posting_schedule: List[Dict[str, Any]] = []

    async def generate_tweet(self, topic: str) -> Dict[str, Any]:
        templates = [
            f"{_pick_emojis(2)} {topic}: {random.choice(['revolutionizing', 'transforming', 'redefining'])} the game {_pick_hashtags(3)}",
            f"⚡ {topic} update — {random.choice(['big things', 'game-changing', 'next-level'])} coming {_pick_emojis(1)} {_pick_hashtags(2)}",
            f"🧠 Did you know? {topic} is {random.choice(['the future', 'changing everything', 'our next breakthrough'])} {_pick_emojis(2)} {_pick_hashtags(3)}",
        ]

        tweet = random.choice(templates)
        while len(tweet) > TWEET_MAX:
            tweet = tweet[:tweet.rfind(" ", 0, TWEET_MAX)]

        self.last_tweet = tweet
        self.posts_today += 1

        result = {
            "platform": "twitter",
            "text": tweet,
            "length": len(tweet),
            "hashtags": [h for h in HASHTAG_POOL if f"#{h}" in tweet],
            "emojis": [e for e in CYBERPUNK_EMOJIS if e in tweet],
            "scheduled": False,
            "post_id": f"TWT-{int(datetime.now().timestamp())}",
            "generated_at": datetime.now().isoformat(),
        }

        logger.info("Generated tweet (%d chars): %s", len(tweet), tweet[:60])
        return result

    async def generate_linkedin_post(self, topic: str) -> Dict[str, Any]:
        intro = f"🚀 Exciting developments in {topic}."
        body_lines = [
            f"Today I want to share some insights on how {topic} is reshaping the industry.",
            "",
            f"• Key trend: {random.choice(['Automation', 'Intelligence', 'Connectivity'])} is accelerating",
            f"• Impact: Organizations that adapt will {random.choice(['lead', 'thrive', 'transform'])}",
            f"• AURA OS is at the forefront of this change",
            "",
            "What's your take? Let's discuss.",
        ]
        body = "\n".join(body_lines)
        cta = random.choice([
            "🔥 Share this with your network",
            "💬 Drop a comment if you agree",
            "🎯 Follow for more insights",
            "🔗 Read the full analysis on our blog",
        ])

        post = f"{intro}\n{body}\n\n{cta}\n\n{_pick_hashtags(5)}"

        while len(post) > LINKEDIN_MAX:
            post = post[:post.rfind(" ", 0, LINKEDIN_MAX)]

        result = {
            "platform": "linkedin",
            "text": post,
            "length": len(post),
            "hashtags": [h for h in HASHTAG_POOL if f"#{h}" in post],
            "cta": cta,
            "formal_tone": True,
            "post_id": f"LNK-{int(datetime.now().timestamp())}",
            "generated_at": datetime.now().isoformat(),
        }

        logger.info("Generated LinkedIn post (%d chars)", len(post))
        return result

    async def auto_post(self, platform: str, topic: str = "AI") -> Dict[str, Any]:
        if platform == "twitter":
            content = await self.generate_tweet(topic)
        elif platform == "linkedin":
            content = await self.generate_linkedin_post(topic)
        else:
            content = await self.generate_tweet(topic)

        schedule_time = datetime.now() + timedelta(minutes=random.randint(5, 120))

        self.posting_schedule.append({
            "platform": platform,
            "content_id": content["post_id"],
            "scheduled_for": schedule_time.isoformat(),
            "status": "scheduled",
            "topic": topic,
        })

        result = {
            "platform": platform,
            "content": content,
            "scheduled_for": schedule_time.isoformat(),
            "status": "scheduled",
            "analytics": {
                "projected_impressions": random.randint(100, 10000),
                "projected_engagement": random.uniform(0.02, 0.08),
                "best_time": "10:00-12:00 UTC",
            },
        }

        logger.info("Auto-post %s scheduled for %s", platform, schedule_time.strftime("%H:%M"))
        return result


social_agent = SocialMediaAgent()
