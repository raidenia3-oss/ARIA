import asyncio, json, re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

class SkillSynthesizer:
    def __init__(self, atria_client):
        self.client = atria_client
        self.skills_dir = Path("ARIA_APP/backend/skills/custom")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.generated_skills = []

    async def analyze_needs(self):
        prompt = (
            "Return a JSON array of 10 skill objects for ARIA. "
            "Each object must have: name (string), description (string), category (string). "
            "Return ONLY valid JSON array, no markdown, no explanation."
        )
        result = await self.client.request(prompt, max_tokens=4000, category="skills")
        if result.get("success"):
            try:
                response_text = result["response"]
                match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response_text, re.DOTALL)
                if match:
                    response_text = match.group(1)
                return json.loads(response_text)
            except:
                return []
        return []

    async def generate_skill(self, spec):
        prompt = str(spec)
        result = await self.client.request(prompt, max_tokens=3000, category="skills")
        if result.get("success"):
            return {"name": spec.get("name"), "code": result["response"]}
        return None

    async def synthesize_skills(self, count=10):
        needs = await self.analyze_needs()
        gen = 0
        for s in needs[:count]:
            r = await self.generate_skill(s)
            if r: self.generated_skills.append(r); gen += 1
        return gen

    def get_stats(self):
        return {"count": len(self.generated_skills)}

