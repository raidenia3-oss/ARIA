"""Tests para validate_dataset.py."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from training.scripts.validate_dataset import validate, load_jsonl


def test_valid_jsonl():
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write(json.dumps({"text": "hola", "output": "mundo"}) + "\n")
        f.write(json.dumps({"text": "foo", "output": "bar"}) + "\n")
        path = f.name
    try:
        records = load_jsonl(path)
        report = validate(records)
        assert report["total_samples"] == 2
        assert report["duplicates"] == 0
        assert report["empty_text"] == 0
        assert report["empty_output"] == 0
    finally:
        os.unlink(path)


def test_empty_jsonl():
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        path = f.name
    try:
        records = load_jsonl(path)
        report = validate(records)
        assert report["total_samples"] == 0
    finally:
        os.unlink(path)


def test_missing_fields():
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write(json.dumps({"text": "solo texto"}) + "\n")
        path = f.name
    try:
        records = load_jsonl(path)
        report = validate(records)
        assert report["missing_output"] >= 1
    finally:
        os.unlink(path)
