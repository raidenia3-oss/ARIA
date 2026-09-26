"""Tests para quality_filter.py."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from training.scripts.quality_filter import compute_score, load_feedback_map, load_jsonl


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_compute_score_feedback_up():
    assert compute_score({"prompt": "x"}, {"x": "up"}) >= 2


def test_compute_score_feedback_down():
    assert compute_score({"prompt": "x"}, {"x": "down"}) <= -3


def test_load_feedback_map():
    records = [{"prompt": "a", "feedback": "up"}, {"prompt": "b", "feedback": "down"}]
    fb = load_feedback_map(records)
    assert fb["a"] == "up"
    assert fb["b"] == "down"


def test_quality_filter_main_empty():
    import io
    import sys

    with tempfile.TemporaryDirectory() as d:
        interactions = os.path.join(d, "interactions.jsonl")
        feedback = os.path.join(d, "feedback.jsonl")
        _write_jsonl(interactions, [])
        _write_jsonl(feedback, [])
        sys.argv = ["quality_filter", "--min-score", "5", "--output", os.path.join(d, "out.jsonl")]
        from training.scripts import quality_filter as qf

        ret = qf.main()
        assert ret == 0
