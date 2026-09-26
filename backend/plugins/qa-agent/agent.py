import asyncio
import time
from typing import Any, Dict, List, Optional
from backend.plugins.plugin_template import PluginAgent


class PluginAgent(PluginAgent):
    def __init__(self):
        super().__init__()
        self.name = "qa-agent"
        self.version = "1.0.0"
        self.commands = {
            "ask": self.ask,
            "batch_qa": self.batch_qa,
            "evaluate_answer": self.evaluate_answer,
        }
        self._knowledge: List[Dict[str, str]] = []

    async def on_load(self):
        print("[QAAgent] Plugin cargado — sistema de preguntas y respuestas activo")

    async def ask(self, args: dict) -> dict:
        question = args.get("question", "")
        context = args.get("context", "")
        start = time.time()
        try:
            from openai import OpenAI
            client = OpenAI()
            system_msg = "Responde la pregunta basándote en el contexto proporcionado. Si no sabes, di 'no sé' con confianza 0.0."
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Contexto: {context}\n\nPregunta: {question}"},
                ],
                temperature=0.2,
            )
            answer = response.choices[0].message.content
            confidence = self._calc_confidence(question, answer, context)
            return {
                "status": "ok", "question": question, "answer": answer,
                "confidence": round(confidence, 3),
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "latency_ms": round((time.time() - start) * 1000, 2)}

    async def batch_qa(self, args: dict) -> dict:
        questions = args.get("questions", [])
        context = args.get("context", "")
        results = []
        for q in questions:
            res = await self.ask({"question": q, "context": context})
            results.append(res)
        avg_conf = sum(r.get("confidence", 0) for r in results if r.get("status") == "ok") / max(len(results), 1)
        return {"status": "ok", "answers": results, "avg_confidence": round(avg_conf, 3)}

    async def evaluate_answer(self, args: dict) -> dict:
        question = args.get("question", "")
        answer = args.get("answer", "")
        context = args.get("context", "")
        confidence = self._calc_confidence(question, answer, context)
        relevant = self._check_relevance(answer, context) if context else True
        return {
            "status": "ok",
            "confidence": round(confidence, 3),
            "relevant": relevant,
            "score": round(confidence * (1.0 if relevant else 0.5), 3),
        }

    def _calc_confidence(self, question: str, answer: str, context: str) -> float:
        if not answer or answer.lower().startswith("no sé"):
            return 0.1
        base = 0.7
        if context and len(answer) > 20:
            base += 0.15
        if not question.endswith("?"):
            base -= 0.05
        return min(base, 0.99)

    def _check_relevance(self, answer: str, context: str) -> bool:
        if not context:
            return True
        return len(answer) > 10
