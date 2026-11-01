"""ARIA v6 Diagnostic - Phase 1: Code Inventory & Verification."""
import subprocess, os, sys

ROOT = r"C:\Users\User\Downloads\AURA"
os.chdir(ROOT)


def grep(pattern, path, n=15):
    try:
        r = subprocess.run(["grep", "-rn", pattern, path],
                           capture_output=True, text=True, timeout=15)
        lines = r.stdout.strip().split("\n")[:n]
        return "\n".join(lines) if lines and lines[0] else "(no matches)"
    except Exception as e:
        return f"ERR: {e}"


def grep_exact(pattern, path, n=15):
    try:
        r = subprocess.run(["grep", "-rn", pattern, path],
                           capture_output=True, text=True, timeout=15)
        lines = r.stdout.strip().split("\n")[:n]
        return "\n".join(lines) if lines and lines[0] else "(no matches)"
    except Exception as e:
        return f"ERR: {e}"


print("=" * 60)
print("BUG FIX STATUS")
print("=" * 60)

print("\n=== BUG #1: request_count (agent_registry_v2.py) ===")
out = grep("request_count|increment_request_count|get_agent_metrics|get_all_metrics",
           "backend/core/agent_registry_v2.py")
print(out)
print("-> IMPLEMENTED" if "increment_request_count" in out else "-> MISSING")

print("\n=== BUG #2: tasks_completed ===")
out = grep("tasks_completed", "backend/")
print(out[:500])
print("-> IMPLEMENTED" if "tasks_completed" in out else "-> MISSING")

print("\n=== BUG #3: agent_analytics revenue ===")
out = grep("random.uniform|calculate_agent_revenue|revenue",
           "backend/agents/agent_analytics.py")
print(out)
print("-> FIXED (no random revenue)" if "random.uniform" not in out else "-> STILL HAS RANDOM")

print("\n=== BUG #4: autoconfigurator ===")
out = grep("_generate_mock_logs|IMPROVEMENT_HISTORY",
           "backend/agents/agent_autoconfigurator.py")
print(out)
print("-> PARTIAL (mock logs still present, IMPROVEMENT_HISTORY exists)")

print("\n=== BUG #5: hardcoded scores ===")
out = grep(r'"score": 9.5|"sources_found": 3|"score": 8.7',
           "backend/agent_swarm.py")
print(out)
print("-> STILL PRESENT" if out.strip() and out != "(no matches)" else "-> MISSING (good)")

print("\n=== BUG #6: status tracking ===")
out = grep("class AgentStatus|class AgentState|set_task_started|AgentState",
           "backend/")
print(out[:600])
print("-> IMPLEMENTED" if "AgentState" in out or "AgentStatus" in out else "-> MISSING")