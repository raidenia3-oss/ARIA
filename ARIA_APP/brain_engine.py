"""ARIA brain engine: LLM local dentro del proceso (llama.cpp).
Sin servidores, sin puertos, sin red. Formato ChatML (Qwen) para fluidez real.
"""
import os


class LlamaEngine:
    def __init__(self, model_path):
        self.model_path = str(model_path)
        self.available = False
        self.error = None
        self._llm = None

    def load(self):
        try:
            if not os.path.isfile(self.model_path):
                self.error = "no existe el modelo: %s" % self.model_path
                return
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=4096,
                n_threads=max(2, (os.cpu_count() or 4) - 2),
                n_batch=256,
                verbose=False,
            )
            self.available = True
        except Exception as exc:
            self.available = False
            self.error = "%s: %s" % (type(exc).__name__, exc)

    # ---- ChatML (Qwen) : da fluidez, razonamiento y memoria de turno ----
    @staticmethod
    def _to_chatml(messages):
        partes = []
        for m in messages:
            rol = m.get("role", "user")
            cont = (m.get("content") or "").strip()
            if not cont:
                continue
            partes.append("<|im_start|>%s\n%s<|im_end|>" % (rol, cont))
        partes.append("<|im_start|>assistant\n")
        return "\n".join(partes)

    def chat(self, messages, max_tokens=320):
        """messages = [{'role':'system'|'user'|'assistant','content':...}, ...]"""
        if not self.available or self._llm is None:
            return ""
        try:
            prompt = self._to_chatml(messages)
            out = self._llm.create_completion(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=0.6,
                top_p=0.9,
                top_k=40,
                repeat_penalty=1.15,
                stop=["<|im_end|>", "<|im_start|>"],
            )
            txt = (out.get("choices") or [{}])[0].get("text", "")
            return txt.strip()
        except Exception:
            return ""

    # compat: generacion plana (ruta antigua)
    def generate(self, prompt, max_tokens=160):
        if not self.available or self._llm is None:
            return ""
        try:
            out = self._llm.create_completion(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=0.6,
                top_p=0.9,
                repeat_penalty=1.15,
                stop=["<|im_end|>", "\nUsuario:", "\nRaiden:"],
            )
            txt = (out.get("choices") or [{}])[0].get("text", "")
            return txt.strip()
        except Exception:
            return ""
