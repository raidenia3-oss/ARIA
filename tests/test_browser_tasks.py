"""Tests for BrowserTaskManager."""

from __future__ import annotations

import time

import pytest

from backend.browser_task_manager import BrowserTask, BrowserTaskManager


@pytest.fixture
def btm():
    return BrowserTaskManager()


class TestBrowserTaskManager:
    def test_create_task(self, btm):
        task = btm.create("test-1", "open_url", "https://example.com/path?token=secret", tab_id=123)
        assert task.task_id == "test-1"
        assert task.action == "open_url"
        assert task.status == "pending"

    def test_complete_task(self, btm):
        btm.create("test-2", "read_visible", "https://example.com")
        btm.complete("test-2", "Got 500 chars of text")
        task = btm.get("test-2")
        assert task.status == "completed"
        assert "500 chars" in task.result_summary

    def test_fail_task(self, btm):
        btm.create("test-3", "click", "https://example.com")
        btm.fail("test-3", "Element not found")
        task = btm.get("test-3")
        assert task.status == "failed"
        assert "Element not found" in task.error

    def test_cancel_task(self, btm):
        btm.create("test-4", "screenshot", "https://example.com")
        assert btm.cancel("test-4")
        task = btm.get("test-4")
        assert task.status == "cancelled"

    def test_cancel_nonexistent_returns_false(self, btm):
        assert not btm.cancel("nonexistent")

    def test_list_tasks(self, btm):
        btm.create("t1", "open_url", "https://a.com")
        btm.create("t2", "read_visible", "https://b.com")
        tasks = btm.list()
        assert len(tasks) == 2

    def test_url_sanitized_in_to_dict(self):
        task = BrowserTask(
            task_id="test-5",
            action="open_url",
            url="https://example.com/path?api_key=SECRET&session=TOKEN#frag",
            tab_id=None,
        )
        d = task.to_dict()
        assert "SECRET" not in d["url"]
        assert "TOKEN" not in d["url"]
        assert "api_key" not in d["url"]

    def test_get_nonexistent(self, btm):
        assert btm.get("nonexistent") is None

    def test_cleanup(self, btm):
        old_task = btm.create("old-1", "open_url", "https://example.com")
        btm._tasks["old-1"].created_at = time.time() - 7200
        removed = btm.cleanup(max_age_seconds=3600)
        assert removed == 1
        assert btm.get("old-1") is None
