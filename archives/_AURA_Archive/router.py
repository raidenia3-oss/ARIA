import os
import requests

OLLAMA_BASE = "http://localhost:11434"

# Modelo por defecto para cada conciencia futura
DEFAULT_MODEL = "gemma3:12b"

# Palabras clave para detectar el tipo de tarea
ROUTING_RULES = {
    "code": {
        "model": "qwen2.5-coder:7b",
        "keywords": [
            "código", "codigo", "code", "programa", "script", "función", "funcion",
            "class", "def ", "import ", "python", "javascript", "cpp", "c++",
            "html", "css", "sql", "bug", "error", "debug", "fix", "ejecuta",
            "compila", "algoritmo", "variable", "loop", "array", "lista"
        ]
    },
    "vision": {
        "model": "llama3.2-vision:11b",
        "keywords": [
            "imagen", "image", "foto", "picture", "analiza esta", "describe esta",
            "qué ves", "que ves", "mira esto", "screenshot", "captura"
        ]
    },
    "fast_vision": {
        "model": "moondream",
        "keywords": [
            "descripción rápida", "describe rápido", "imagen rápida", "foto rápida"
        ]
    },
    "reasoning": {
        "model": "deepseek-r1:8b",
        "keywords": [
            "razona", "analiza", "explica paso a paso", "por qué", "por que",
            "cómo funciona", "como funciona", "deduce", "calcula", "matemática",
            "matematica", "lógica", "logica", "filosofía", "filosofia",
            "estrategia", "planifica", "decide", "compara", "evalúa", "evalua"
        ]
    },
    "advanced": {
        "model": "gemma3:12b",
        "keywords": [
            "avanzado", "complejo", "detallado", "profundo", "sofisticado"
        ]
    },
    "multilingual": {
        "model": "qwen2.5:7b",
        "keywords": [
            "traduce", "translate", "japonés", "japones", "chino", "korean",
            "french", "deutsch", "arabic", "hindi", "en inglés", "en ingles",
            "en español", "en espanol"
        ]
    },
    "fast": {
        "model": "llama3.2:3b",
        "keywords": [
            "rápido", "rapido", "breve", "corto", "simple", "sencillo",
            "en una palabra", "sí o no", "si o no"
        ]
    }
}

def detect_task_type(message: str) -> str:
    message_lower = message.lower()
    
    if "[imagen" in message_lower or "[image" in message_lower or "[foto" in message_lower:
        return "vision"
    
    scores = {task: 0 for task in ROUTING_RULES}
    
    for task, config in ROUTING_RULES.items():
        for keyword in config["keywords"]:
            if keyword in message_lower:
                scores[task] += 1
    
    max_score = max(scores.values())
    if max_score == 0:
        return "default"
    
    return max(scores, key=scores.get)

def get_best_model(message: str, has_image: bool = False) -> str:
    if has_image:
        return ROUTING_RULES["vision"]["model"]
    
    task_type = detect_task_type(message)
    
    if task_type == "default":
        return DEFAULT_MODEL
    
    return ROUTING_RULES[task_type]["model"]

def call_ollama_smart(messages: list, has_image: bool = False) -> tuple:
    user_message = messages[-1]["content"] if messages else ""
    model = get_best_model(user_message, has_image)
    
    print(f"[ROUTER]: Tarea detectada → modelo seleccionado: {model}")
    
    try:
        res = requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": model,
                "messages": [{"role": m["role"], "content": m["content"]} 
                             for m in messages if m["role"] != "system"],
                "stream": False
            },
            headers={
                "Content-Type": "application/json",
                "User-Agent": "curl/7.68.0"
            },
            timeout=120.0
        )
        
        if res.status_code == 200:
            data = res.json()
            content = data.get("message", {}).get("content", "")
            if content:
                return content, model
        
        print(f"[ROUTER ERROR]: Status {res.status_code} - {res.text[:100]}")
        return None, model
        
    except Exception as e:
        print(f"[ROUTER EXCEPTION]: {e}")
        return None, model

def get_model_for_consciousness(consciousness_id: str) -> str:
    consciousness_models = {
        "C-01": "dolphin-llama3:8b",
        "C-02": "deepseek-r1:8b",
        "C-03": "qwen2.5:7b",
        "C-04": "llama3.2:3b",
        "CORE": DEFAULT_MODEL
    }
    return consciousness_models.get(consciousness_id, DEFAULT_MODEL)
