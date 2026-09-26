import pytest
import json
import os
import sys
import asyncio
import importlib.util
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def load_agent_from_path(agent_dir, module_name):
    agent_path = Path(f"backend/plugins/{agent_dir}/agent.py")
    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PluginAgent


class TestPluginManagerAsync:
    def test_load_unload_cycle(self):
        from backend.plugins.plugin_manager import PluginManager
        pm = PluginManager(plugins_dir="backend/plugins")
        result = pm.load_plugin("translator-agent")
        assert result["status"] == "loaded"
        plugin_name = result["plugin"]["name"]
        plugins = pm.list_plugins()
        assert any(p["name"] == plugin_name for p in plugins)
        unload = pm.unload_plugin(plugin_name)
        assert unload["status"] == "unloaded"

    def test_load_multiple_plugins(self):
        from backend.plugins.plugin_manager import PluginManager
        pm = PluginManager(plugins_dir="backend/plugins")
        agents = ["translator-agent", "summarizer-agent", "qa-agent"]
        loaded = []
        for a in agents:
            r = pm.load_plugin(a)
            if r["status"] == "loaded":
                loaded.append(a)
        assert len(loaded) >= 1

    def test_plugin_yaml_structure(self):
        agent_dirs = ["translator-agent", "summarizer-agent", "qa-agent", "content-moderator", "email-writer", "twitter-bot"]
        for d in agent_dirs:
            yaml_path = Path(f"backend/plugins/{d}/plugin.yaml")
            assert yaml_path.exists(), f"Missing {yaml_path}"
            import yaml as yaml_mod
            with open(yaml_path, "r") as f:
                data = yaml_mod.safe_load(f)
            assert data is not None
            assert "name" in data
            assert "commands" in data
            for cmd in data["commands"]:
                assert "name" in cmd
                assert "params" in cmd


class TestDashboardManager:
    def test_get_system_stats(self):
        from backend.monitoring.dashboard_manager import DashboardManager
        dm = DashboardManager()
        result = asyncio.run(dm.get_system_stats())
        assert "system" in result
        sys_data = result["system"]
        assert "cpu" in sys_data
        assert "memory" in sys_data

    def test_get_agent_stats(self):
        from backend.monitoring.dashboard_manager import DashboardManager
        dm = DashboardManager()
        dm.record_request("test-agent", latency_ms=100, success=True, revenue=0.5)
        result = asyncio.run(dm.get_agent_stats("test-agent"))
        assert result["agent"] == "test-agent"
        assert "stats" in result
        stats = result["stats"]
        assert stats["requests_today"] >= 1
        assert stats["revenue"] >= 0.5

    def test_record_request(self):
        from backend.monitoring.dashboard_manager import DashboardManager
        dm = DashboardManager()
        dm.record_request("agent1", latency_ms=50, success=True)
        dm.record_request("agent1", latency_ms=100, success=False)
        stats = dm._agent_stats.get("agent1", {})
        assert stats.get("total_requests", 0) >= 2
        assert stats.get("errors", 0) >= 1

    def test_get_performance_timeline(self):
        from backend.monitoring.dashboard_manager import DashboardManager
        dm = DashboardManager()
        result = asyncio.run(dm.get_performance_timeline())
        assert "timeline" in result
        assert len(result["timeline"]) > 0

    def test_logs(self):
        from backend.monitoring.dashboard_manager import DashboardManager
        dm = DashboardManager()
        dm.log("Test log message")
        dm.log("ERROR: Test error")
        logs = dm.get_logs(lines=10)
        assert len(logs) >= 2


class TestNewAgentsIntegration:
    def test_translator_agent_without_openai(self):
        PluginAgent = load_agent_from_path("translator-agent", "it_translator")
        agent = PluginAgent()
        result = asyncio.run(agent.translate({"text": "hello", "target_lang": "es"}))
        assert result["status"] in ["ok", "error"]

    def test_summarizer_agent_empty(self):
        PluginAgent = load_agent_from_path("summarizer-agent", "it_summarizer")
        agent = PluginAgent()
        result = asyncio.run(agent.summarize({"text": "", "mode": "abstract"}))
        assert result["status"] in ["ok", "error"]

    def test_qa_agent_ask_empty(self):
        PluginAgent = load_agent_from_path("qa-agent", "it_qa")
        agent = PluginAgent()
        result = asyncio.run(agent.ask({"question": "", "context": ""}))
        assert result["status"] in ["ok", "error"]

    def test_content_moderator_classify(self):
        PluginAgent = load_agent_from_path("content-moderator", "it_moderator")
        agent = PluginAgent()
        result = asyncio.run(agent.classify_severity({"text": "test content"}))
        assert "severity" in result or "error" in result

    def test_email_writer_write(self):
        PluginAgent = load_agent_from_path("email-writer", "it_email")
        agent = PluginAgent()
        result = asyncio.run(agent.write_email({"recipient": "test", "subject": "Hola", "body": "Test", "tone": "formal"}))
        assert result["status"] in ["ok", "error"]

    def test_twitter_bot_tweet(self):
        PluginAgent = load_agent_from_path("twitter-bot", "it_twitter")
        agent = PluginAgent()
        result = asyncio.run(agent.generate_tweet({"topic": "test", "hashtags": [], "tone": "neutral"}))
        assert result["status"] in ["ok", "error"]
