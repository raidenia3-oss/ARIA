"""BLOQUE 86 - unit tests for edge-AI dataset + offline LoRA (local)."""

from backend.edge_ai.dataset import DatasetFormatter
from backend.edge_ai.engine import OfflineLoRATrainer, get_edge_trainer, reset_edge_trainer


def test_formatter_builds_and_rejects():
    fmt = DatasetFormatter()
    ex = fmt.build_example("Resume esto", "Resumen ok", "interaction")
    assert ex.instruction and ex.output
    try:
        fmt.build_example("", "", "interaction")
        raise AssertionError("debio fallar")
    except ValueError:
        pass
    try:
        fmt.build_example("a", "b", "cloud")
        raise AssertionError("debio fallar")
    except ValueError:
        pass


def test_synthesize_filters_scores():
    fmt = DatasetFormatter()
    recs = [
        {"instruction": "i1", "output": "o1", "score": 0.9},
        {"instruction": "i2", "output": "o2", "score": 0.1},
        {"instruction": "", "output": ""},
    ]
    out = fmt.synthesize(recs, min_score=0.5)
    assert len(out) == 1 and out[0].instruction == "i1"


def test_train_produces_decreasing_loss():
    tr = OfflineLoRATrainer()
    fmt = DatasetFormatter()
    exs = fmt.synthesize(
        [{"instruction": f"q{i}", "output": f"a{i}", "score": 0.9} for i in range(5)]
    )
    out = tr.train(exs, rank=8, epochs=2)
    lh = out["run"]["loss_history"]
    assert out["run"]["status"] == "completed"
    assert lh[0] > lh[-1]
    assert out["adapter"]["examples"] == 5


def test_train_rejects_empty():
    tr = OfflineLoRATrainer()
    try:
        tr.train([], rank=8)
        raise AssertionError("debio fallar")
    except ValueError:
        pass


def test_hot_swap_guards_regression():
    tr = OfflineLoRATrainer()
    fmt = DatasetFormatter()
    mk = lambda n: fmt.synthesize(
        [{"instruction": f"q{i}-{n}", "output": f"a{i}-{n}", "score": 0.9} for i in range(5)]
    )
    a1 = tr.train(mk("a"), rank=8, epochs=1)["adapter"]["adapter_id"]
    assert tr.hot_swap(a1)["swapped"] is True
    # Segundo adaptador con peor loss simulado: forzar regresion manual
    a2 = tr.train(mk("b"), rank=1, epochs=1)["adapter"]["adapter_id"]
    tr._adapters[a2].final_loss = 99.0
    assert tr.hot_swap(a2)["swapped"] is False
    assert tr.rollback()["rolled_back"] is True


def test_singleton():
    reset_edge_trainer()
    assert get_edge_trainer() is get_edge_trainer()
    reset_edge_trainer()
