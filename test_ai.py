import sys
sys.path.insert(0, r"C:\Users\User\Downloads\AURA")
from ai_providers import AIProviderManager
m = AIProviderManager()
print("HF free:", m.providers.get("huggingface_free"))
print("Best:", m.get_best_provider())
print("Available:", m.get_available_providers())
print("Detect:", {k: v["available"] for k, v in m.providers.items() if v["available"]})
