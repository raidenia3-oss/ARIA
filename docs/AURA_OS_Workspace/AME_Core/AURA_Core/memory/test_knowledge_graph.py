#!/usr/bin/env python
# Test formal: guarda/lee disco y valida consulta contextual

import json
import os

from AURA_Core.memory.knowledge_graph import KnowledgeGraph, bootstrap_ecosystem

TEST_PATH = "AURA_Core/memory/test_knowledge_graph.json"


def main() -> None:
    if os.path.exists(TEST_PATH):
        os.remove(TEST_PATH)

    kg = KnowledgeGraph(path=TEST_PATH)
    bootstrap_ecosystem(kg)

    context = kg.query_graph_context("AME_Mobile", max_depth=1)
    assert context["node"] == "AME_Mobile"

    rels = context["relations"]
    assert any(
        r["dst"] == "Telemetria" and r["rel"] == "ALIMENTA_DE_DATOS" for r in rels
    ), f"Rela AME_Mobile->Telemetria ausente: {rels}"

    tele_ctx = kg.query_graph_context("Telemetria", max_depth=1)
    assert any(
        r["dst"] == "JARVIS_HUD" and r["rel"] == "MONITOREA" for r in tele_ctx["relations"]
    ), f"Rela Telemetria->JARVIS_HUD ausente: {tele_ctx}"

    # Reload from disk
    kg2 = KnowledgeGraph(path=TEST_PATH)
    assert len(kg2.nodes) == len(kg.nodes)
    assert len(kg2.edges) == len(kg.edges)

    print("knowledge_graph tests passed")


if __name__ == "__main__":
    main()
