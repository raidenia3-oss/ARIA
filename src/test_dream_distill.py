#!/usr/bin/env python3
# Test mínimo Dream & Distill + Chronos

import sys
sys.path.insert(0, '.')

from AURA_Core.dream_and_distill import run_dream, run_distill

print("[TEST] run_dream():")
dream_report = run_dream()
print(dream_report)

print("\n[TEST] run_distill():")
distill_report = run_distill()
print(distill_report)

print("\n[TEST] skills_distilled.json:")
import json
try:
    with open('AURA_Core/skills_distilled.json', 'r', encoding='utf-8') as f:
        skills = json.load(f)
    print(f"  skills: {len(skills.get('skills', []))}")
    for s in skills.get('skills', [])[:3]:
        print(f"  - {s.get('name')}: {s.get('steps')}")
except Exception as e:
    print(f"  Error: {e}")

print("\n[TEST] knowledge_graph.json:")
try:
    with open('AURA_Core/knowledge_graph.json', 'r', encoding='utf-8') as f:
        kg = json.load(f)
    print(f"  nodes: {len(kg.get('nodes', []))}, edges: {len(kg.get('edges', []))}")
except Exception as e:
    print(f"  Error: {e}")

print("\n[TEST] chat_history.json:")
try:
    with open('AURA_Core/chat_history.json', 'r', encoding='utf-8') as f:
        chat = json.load(f)
    print(f"  messages: {len(chat)}")
except Exception as e:
    print(f"  Error: {e}")

print("\nTest mínimo finalizado.")
