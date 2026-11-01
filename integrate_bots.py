path = r'C:\Users\User\Downloads\AURA\backend\brain_orchestrator.py'
with open(path, 'r', encoding='utf-8') as f:
    s = f.read()

# add import
if 'bot_api' not in s:
    s = s.replace('from typing import Any, Dict, List, Optional\n', 'from typing import Any, Dict, List, Optional\n\ntry:\n    from backend.bot_api import handle_bot_command\nexcept Exception:\n    try:\n        from bot_api import handle_bot_command\n    except Exception:\n        handle_bot_command = None\n')

# patch think
new_think = '''    def think(self, prompt: str = "", history: list | None = None, tasks: list | None = None, parallel: bool = False, **kwargs) -> dict:
        text = (prompt or "").strip()
        if text and text.lower().startswith("bot:") and handle_bot_command is not None:
            try:
                cmd = text[4:].strip()
                cl = cmd.lower()
                if cl == "list":
                    lst = handle_bot_command("list")
                    return {"message": str(lst), "provider": "unified_brain", "source": "bot_cmd", "confidence": 0.95, "autonomous": True, "should_retrain": False}
                if cl.startswith("create"):
                    name = "grook"
                    if "name=" in cmd:
                        try:
                            name = cmd.split("name=")[-1].strip().split()[0]
                        except Exception:
                            name = "grook"
                    r = handle_bot_command("create", name=name)
                    return {"message": "BOT created: " + str(r.get("bot_id")), "provider": "unified_brain", "source": "bot_cmd", "confidence": 0.95, "autonomous": True, "should_retrain": False}
                if cl.startswith("start"):
                    bid = None
                    if "bot_id=" in cmd:
                        try:
                            bid = cmd.split("bot_id=")[-1].strip().split()[0]
                        except Exception:
                            bid = None
                    r = handle_bot_command("start", bot_id=bid)
                    return {"message": str(r), "provider": "unified_brain", "source": "bot_cmd", "confidence": 0.95, "autonomous": True, "should_retrain": False}
            except Exception as e:
                return {"message": "BOT ERR: " + str(e), "provider": "unified_brain", "source": "bot_cmd", "confidence": 0.9, "autonomous": True, "should_retrain": False}
        if tasks:
            results = []
            items = tasks if isinstance(tasks, list) else [tasks]
            for t in items:
                try:
                    r = self.think(prompt=str(t), history=history, **kwargs)
                    results.append(r)
                except Exception as e:
                    results.append({"message": f"error: {e}", "provider": "unified_brain", "source": "task"})
            return {"message": str(results), "provider": "unified_brain", "source": "multitask", "tasks": len(results)}
        if not text:
            st = self.get_brain_status()
            return {"message": f"[AURA:UNIFIED] idle | samples_7d={st['samples_last_7_days']} | conv={st['state'].get('total_conversations',0)}", "provider": "local", "source": "unified_brain", "confidence": 0.9}
        status = self.get_brain_status()
        should = status.get("should_retrain", False)
        response = f"[AURA:UNIFIED:autonomous] {text} | conv={status['state'].get('total_conversations',0)} | s7d={status['samples_last_7_days']} | retrain={should}"
        try:
            self.learn(device="pc", role="core", prompt=text, response=response, provider="unified_brain")
        except Exception:
            pass
        return {"message": response, "provider": "unified_brain", "source": "think", "confidence": 0.95, "autonomous": True, "should_retrain": should}
'''
# replace
old = s[s.find('    def think'):s.find('    def chat')]
s2 = s.replace(old, new_think + '\n')
with open(path,'w',encoding='utf-8') as f:
    f.write(s2)
print('ok')
