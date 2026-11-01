path = r"C:\Users\User\Downloads\AURA\backend\brain_orchestrator.py"
with open(path, "r", encoding="utf-8") as f:
    s = f.read()
marker = "brain = UnifiedBrain()"
idx = s.find(marker)
if idx == -1:
    raise SystemExit("not found")
start = s.find("    def think(self,", idx)
if start != -1:
    end_block = s.find("\n\n", start + 20)
    if end_block == -1:
        end_block = len(s)
    s2 = s[:start] + s[end_block:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(s2)
    print("ok")
else:
    print("none")
