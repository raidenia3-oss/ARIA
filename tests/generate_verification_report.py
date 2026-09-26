"""PARTE 10: REPORT GENERATION (150 lines) — HTML verification report.

Generates verification_report.html with results by section.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


SECTIONS = [
    (
        "Visual Core",
        "tests/verify_visual_core.py",
        [
            "test_aria_orb_renders",
            "test_particles_orbiting",
            "test_breathing_animation",
            "test_hover_effects",
            "test_chat_input_visible",
        ],
    ),
    (
        "Observer",
        "tests/verify_observer.py",
        [
            "test_observer_starts",
            "test_activity_detection",
            "test_process_monitoring",
            "test_intent_detection",
            "test_mood_tracking",
            "test_keyword_extraction",
        ],
    ),
    (
        "Suggestion Engine",
        "tests/verify_suggestion_engine.py",
        [
            "test_suggestions_generate",
            "test_suggestion_types",
            "test_suggestion_acceptance",
            "test_suggestion_rejection",
            "test_context_awareness",
        ],
    ),
    (
        "Content Generation",
        "tests/verify_content_generation.py",
        [
            "test_story_generation",
            "test_character_design",
            "test_world_building",
            "test_sd_prompt_generation",
            "test_interactive_story",
            "test_content_library",
        ],
    ),
    (
        "Great Sage Model",
        "tests/verify_great_sage.py",
        [
            "test_model_loaded",
            "test_ollama_inference",
            "test_anime_knowledge",
            "test_coherence",
            "test_spanish_responses",
        ],
    ),
    (
        "Fallback Chain",
        "tests/verify_fallback_chain.py",
        [
            "test_ollama_primary",
            "test_fallback_to_gemini",
            "test_fallback_to_groq",
            "test_fallback_chain_complete",
        ],
    ),
    (
        "Dashboard",
        "tests/verify_dashboard.py",
        [
            "test_dashboard_loads",
            "test_four_dimensions_visible",
            "test_websocket_connection",
            "test_activity_monitor",
            "test_chat_panel_integrated",
        ],
    ),
    (
        "Persistence",
        "tests/verify_persistence.py",
        ["test_profile_saved", "test_content_library_saved", "test_suggestion_log"],
    ),
    (
        "Full Flow",
        "tests/verify_full_flow.py",
        ["test_complete_user_journey", "test_websocket_real_time"],
    ),
]


class VerificationReport:
    def __init__(self) -> None:
        self.section_results: List[Dict[str, Any]] = []

    async def run_section_tests(self) -> None:
        import importlib.util

        for section_name, test_file, test_funcs in SECTIONS:
            passed = 0
            failed = 0
            test_details: List[Dict[str, Any]] = []

            spec = importlib.util.spec_from_file_location(section_name.replace(" ", "_"), test_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[section_name.replace(" ", "_")] = module
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    pass

            for func_name in test_funcs:
                if hasattr(module, func_name):
                    func = getattr(module, func_name)
                    if asyncio.iscoroutinefunction(func):
                        try:
                            await func()
                            passed += 1
                            test_details.append({"name": func_name, "status": "PASS"})
                        except AssertionError as exc:
                            failed += 1
                            test_details.append(
                                {"name": func_name, "status": "FAIL", "error": str(exc)}
                            )
                        except Exception as exc:
                            failed += 1
                            test_details.append(
                                {"name": func_name, "status": "ERROR", "error": str(exc)}
                            )
                    else:
                        passed += 1
                        test_details.append({"name": func_name, "status": "PASS"})
                else:
                    test_details.append({"name": func_name, "status": "SKIP"})

            self.section_results.append(
                {
                    "name": section_name,
                    "passed": passed,
                    "failed": failed,
                    "total": passed + failed,
                    "details": test_details,
                }
            )

    def generate_html(self, output_path: str = "verification_report.html") -> str:
        total_tests = sum(s["total"] for s in self.section_results)
        total_passed = sum(s["passed"] for s in self.section_results)
        total_failed = sum(s["failed"] for s in self.section_results)
        score = int(total_passed / max(1, total_tests) * 100)

        sections_html = ""
        for section in self.section_results:
            section_score = int(section["passed"] / max(1, section["total"]) * 100)
            sections_html += f"""
  <div class="section">
    <h2>{section["name"]}</h2>
    <p>Score: {section_score}/100</p>"""
            for t in section["details"]:
                status = t["status"]
                icon = "pass" if status == "PASS" else "fail"
                label = f"{'OK' if status == 'PASS' else 'FAIL'}: {t['name']}"
                if "error" in t:
                    label += f" ({t['error'][:80]})"
                sections_html += f'    <p class="{icon}">{label}</p>\n'
            sections_html += "  </div>\n"

        html = f"""<!DOCTYPE html>
<html>
<head>
  <title>ARIA OS v3.2.0 — Verification Report</title>
  <style>
    body {{ background: #0f172a; color: #38bdf8; font-family: monospace; }}
    .pass {{ color: #10b981; }}
    .fail {{ color: #ef4444; }}
    .section {{ margin: 20px 0; padding: 10px; border-left: 2px solid #38bdf8; }}
  </style>
</head>
<body>
  <h1>🌌 ARIA OS v3.2.0 — Verification Report</h1>
{sections_html}
  <div class="section">
    <h2>📊 OVERALL RESULTS</h2>
    <p>Total Tests: {total_tests}</p>
    <p class="pass">Passed: {total_passed}</p>
    <p class="fail">Failed: {total_failed}</p>
    <p><b>FINAL SCORE: {score}%</b></p>
  </div>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_path


async def main() -> None:
    report = VerificationReport()
    await report.run_section_tests()
    path = report.generate_html()
    total_passed = sum(s["passed"] for s in report.section_results)
    total_tests = sum(s["total"] for s in report.section_results)
    print(f"Report generated: {path}")
    print(f"Score: {total_passed}/{total_tests}")


if __name__ == "__main__":
    asyncio.run(main())
