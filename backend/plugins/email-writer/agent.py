import asyncio
import time
from typing import Any, Dict, List, Optional
from backend.plugins.plugin_template import PluginAgent


class PluginAgent(PluginAgent):
    def __init__(self):
        super().__init__()
        self.name = "email-writer"
        self.version = "1.0.0"
        self.commands = {
            "write_email": self.write_email,
            "generate_ab_variants": self.generate_ab_variants,
            "summarize_email_thread": self.summarize_email_thread,
        }
        self._templates = {
            "formal": "Estimado/a {recipient},\n\n{body}\n\nAtentamente,\nAURA",
            "casual": "¡Hola {recipient}!\n\n{body}\n\n¡Saludos!\nAURA",
            "persuasive": "{recipient},\n\n{body}\n\nNo pierdas esta oportunidad.\nAURA",
        }
        self._tone_descriptions = {
            "formal": "tono formal y profesional",
            "casual": "tono casual y amigable",
            "persuasive": "tono persuasivo y comercial",
        }

    async def on_load(self):
        print("[EmailWriter] Plugin cargado — redacción de emails activa")

    async def write_email(self, args: dict) -> dict:
        recipient = args.get("recipient", "destinatario")
        subject = args.get("subject", "")
        body = args.get("body", "")
        tone = args.get("tone", "formal")
        template_name = args.get("template", tone)
        start = time.time()
        try:
            from openai import OpenAI
            client = OpenAI()
            tone_desc = self._tone_descriptions.get(tone, "profesional")
            system = f"Eres un experto redactor de correos. Usa un {tone_desc}. El asunto ya está definido."
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": body}],
                temperature=0.4,
            )
            generated_body = response.choices[0].message.content
            template = self._templates.get(template_name, self._templates["formal"])
            formatted = template.replace("{recipient}", recipient).replace("{body}", generated_body)
            return {
                "status": "ok",
                "to": recipient,
                "subject": subject,
                "body": generated_body,
                "formatted_email": formatted,
                "tone": tone,
                "template": template_name,
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "latency_ms": round((time.time() - start) * 1000, 2)}

    async def generate_ab_variants(self, args: dict) -> dict:
        subject = args.get("subject", "")
        body = args.get("body", "")
        count = args.get("count", 2)
        variants = []
        tones = ["formal", "casual", "persuasive"]
        for i in range(min(count, 3)):
            tone = tones[i % len(tones)]
            res = await self.write_email({
                "recipient": "usuario", "subject": subject, "body": body, "tone": tone,
            })
            variants.append({"variant": i + 1, "tone": tone, "email": res})
        return {"status": "ok", "variants": variants, "count": len(variants)}

    async def summarize_email_thread(self, args: dict) -> dict:
        emails = args.get("emails", [])
        if not emails:
            return {"status": "ok", "summary": "Sin emails para resumir"}
        try:
            from openai import OpenAI
            client = OpenAI()
            thread_text = "\n---\n".join(str(e) for e in emails[:10])
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "Resume este hilo de emails en 5 líneas máximo."}, {"role": "user", "content": thread_text}],
                temperature=0.3,
            )
            return {"status": "ok", "summary": response.choices[0].message.content, "emails_summarized": len(emails)}
        except Exception as e:
            return {"status": "error", "error": str(e)}
