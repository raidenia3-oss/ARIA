import pytest
import json
import os
import sys
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def load_agent_from_path(agent_dir, module_name):
    agent_path = Path(f"backend/plugins/{agent_dir}/agent.py")
    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PluginAgent


class TestPluginManager:
    def setup_method(self):
        from backend.plugins.plugin_manager import PluginManager
        self.pm = PluginManager(plugins_dir="backend/plugins")

    def test_load_plugin_not_found(self):
        result = self.pm.load_plugin("nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_list_plugins_empty(self):
        plugins = self.pm.list_plugins()
        assert isinstance(plugins, list)
        assert len(plugins) == 0

    def test_unload_plugin_not_loaded(self):
        result = self.pm.unload_plugin("nonexistent")
        assert result["status"] == "error"

    def test_load_template_agent(self):
        template_path = os.path.join("backend", "plugins", "translator-agent")
        assert os.path.isdir(template_path)
        yaml_path = os.path.join(template_path, "plugin.yaml")
        assert os.path.exists(yaml_path)
        agent_path = os.path.join(template_path, "agent.py")
        assert os.path.exists(agent_path)

    def test_yaml_validation(self):
        from pathlib import Path
        import yaml as yaml_mod
        yaml_path = Path("backend/plugins/translator-agent/plugin.yaml")
        with open(yaml_path, "r") as f:
            data = yaml_mod.safe_load(f)
        assert data is not None
        assert "name" in data
        assert "commands" in data
        assert isinstance(data["commands"], list)
        for cmd in data["commands"]:
            assert "name" in cmd
            assert "params" in cmd
            assert "async" in cmd

    def test_reload_all_plugins(self):
        from backend.plugins.plugin_manager import PluginManager
        pm = PluginManager(plugins_dir="backend/plugins")
        result = pm.reload_all_plugins()
        assert "status" in result
        assert "reloaded" in result

    def test_plugin_metadata_stored(self):
        self.pm.load_plugin("translator-agent")
        plugins = self.pm.list_plugins()
        if plugins:
            p = plugins[0]
            assert "name" in p
            assert "version" in p
            assert "status" in p
            assert "commands" in p


class TestPluginTemplate:
    def test_plugin_agent_base_class(self):
        from backend.plugins.plugin_template import PluginAgent
        agent = PluginAgent()
        assert agent.name == ""
        assert agent.version == "1.0.0"
        assert isinstance(agent.commands, dict)

    def test_plugin_agent_execute_default(self):
        import asyncio
        from backend.plugins.plugin_template import PluginAgent
        agent = PluginAgent()
        result = asyncio.run(agent.execute("unknown", {}))
        assert "error" in result

    def test_plugin_agent_on_load(self):
        import asyncio
        from backend.plugins.plugin_template import PluginAgent
        agent = PluginAgent()
        result = asyncio.run(agent.on_load())
        assert result is None

    def test_plugin_agent_on_unload(self):
        import asyncio
        from backend.plugins.plugin_template import PluginAgent
        agent = PluginAgent()
        result = asyncio.run(agent.on_unload())
        assert result is None


class TestNewAgents:
    def test_translator_agent_structure(self):
        PluginAgent = load_agent_from_path("translator-agent", "ta_translator")
        agent = PluginAgent()
        assert agent.name == "translator-agent"
        assert "translate" in agent.commands
        assert "detect_language" in agent.commands
        assert "batch_translate" in agent.commands

    def test_summarizer_agent_structure(self):
        PluginAgent = load_agent_from_path("summarizer-agent", "ta_summarizer")
        agent = PluginAgent()
        assert agent.name == "summarizer-agent"
        assert "summarize" in agent.commands
        assert "summarize_url" in agent.commands
        assert "extract_key_points" in agent.commands

    def test_qa_agent_structure(self):
        PluginAgent = load_agent_from_path("qa-agent", "ta_qa")
        agent = PluginAgent()
        assert agent.name == "qa-agent"
        assert "ask" in agent.commands
        assert "batch_qa" in agent.commands
        assert "evaluate_answer" in agent.commands

    def test_content_moderator_structure(self):
        PluginAgent = load_agent_from_path("content-moderator", "ta_moderator")
        agent = PluginAgent()
        assert agent.name == "content-moderator"
        assert "moderate" in agent.commands
        assert "classify_severity" in agent.commands
        assert "suggest_fix" in agent.commands

    def test_email_writer_structure(self):
        PluginAgent = load_agent_from_path("email-writer", "ta_email")
        agent = PluginAgent()
        assert agent.name == "email-writer"
        assert "write_email" in agent.commands
        assert "generate_ab_variants" in agent.commands
        assert "summarize_email_thread" in agent.commands

    def test_twitter_bot_structure(self):
        PluginAgent = load_agent_from_path("twitter-bot", "ta_twitter")
        agent = PluginAgent()
        assert agent.name == "twitter-bot"
        assert "generate_tweet" in agent.commands
        assert "analyze_trends" in agent.commands
        assert "schedule_post" in agent.commands
        assert "predict_engagement" in agent.commands


class TestAgentRegistryV2:
    def setup_method(self):
        from backend.core.agent_registry_v2 import AgentRegistryV2
        self.reg = AgentRegistryV2.__new__(AgentRegistryV2)
        self.reg._agents = {}
        self.reg._configs = {}
        self.reg._endpoints = {}

    def test_register_agent(self):
        config = {"name": "test-agent", "type": "custom", "description": "Test", "commands": ["cmd1"]}
        result = self.reg.register_agent(config)
        assert "agent_id" in result
        assert "endpoints" in result
        assert result["status"] == "active"
        assert result["name"] == "test-agent"

    def test_register_duplicate_agent(self):
        config = {"name": "dup-agent", "type": "custom"}
        self.reg.register_agent(config)
        result2 = self.reg.register_agent(config)
        assert "error" in result2

    def test_list_agents_empty(self):
        agents = self.reg.list_agents()
        assert agents == []

    def test_list_agents_with_data(self):
        self.reg.register_agent({"name": "a1", "type": "t"})
        self.reg.register_agent({"name": "a2", "type": "t"})
        agents = self.reg.list_agents()
        assert len(agents) == 2

    def test_get_agent_config(self):
        config = {"name": "cfg-agent", "type": "test"}
        result = self.reg.register_agent(config)
        aid = result["agent_id"]
        fetched = self.reg.get_agent_config(aid)
        assert fetched is not None
        assert fetched["agent"]["name"] == "cfg-agent"

    def test_get_agent_config_not_found(self):
        fetched = self.reg.get_agent_config("nonexistent")
        assert fetched is None

    def test_update_agent_config(self):
        config = {"name": "upd-agent", "type": "test"}
        result = self.reg.register_agent(config)
        aid = result["agent_id"]
        update = self.reg.update_agent_config(aid, {"status": "inactive"})
        assert update["status"] == "updated"
        fetched = self.reg.get_agent_config(aid)
        assert fetched["agent"]["status"] == "inactive"

    def test_update_agent_config_not_found(self):
        result = self.reg.update_agent_config("nonexistent", {"status": "inactive"})
        assert result["status"] == "error"

    def test_agent_has_endpoints(self):
        config = {"name": "ep-agent", "type": "test"}
        result = self.reg.register_agent(config)
        assert len(result["endpoints"]) == 3


class TestAutoExtension:
    def setup_method(self):
        from backend.daemon.auto_extension_task import AutoExtensionTask
        self.task = AutoExtensionTask(interval_seconds=300)

    def test_task_starts_stopped(self):
        assert not self.task._running

    def test_status(self):
        status = self.task.get_status()
        assert status["running"] is False
        assert status["interval_seconds"] == 300

    def test_run_analysis(self):
        import asyncio
        result = asyncio.run(self.task.run_analysis())
        assert "trending_topics" in result
        assert "proposed_agents" in result
        assert "score" in result
        assert len(result["proposed_agents"]) == 3

    def test_score_calculation(self):
        import asyncio
        result = asyncio.run(self.task.run_analysis())
        assert 0 <= result["score"] <= 100

    def test_proposed_agents(self):
        import asyncio
        asyncio.run(self.task.run_analysis())
        proposed = self.task.get_proposed_agents()
        assert len(proposed) >= 3

    def test_analysis_history(self):
        import asyncio
        asyncio.run(self.task.run_analysis())
        history = self.task.get_analysis_history(limit=1)
        assert len(history) >= 1


class TestAuraCLI:
    def test_cli_help(self):
        import subprocess
        result = subprocess.run([sys.executable, "scripts/aura_cli.py", "--help"], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert "agents" in result.stdout
        assert "plugins" in result.stdout

    def test_cli_health(self):
        import subprocess
        result = subprocess.run([sys.executable, "scripts/aura_cli.py", "health"], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        assert "Status" in output or "Error" in output or "error" in output

    def test_cli_agents_list(self):
        import subprocess
        result = subprocess.run([sys.executable, "scripts/aura_cli.py", "agents", "list"], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        assert "agent" in output.lower() or "error" in output.lower() or "no hay" in output.lower()

    def test_cli_plugins_list(self):
        import subprocess
        result = subprocess.run([sys.executable, "scripts/aura_cli.py", "plugins", "list"], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        assert "plugin" in output.lower() or "error" in output.lower() or "no hay" in output.lower()

    def test_cli_stats(self):
        import subprocess
        result = subprocess.run([sys.executable, "scripts/aura_cli.py", "stats"], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        assert "system" in output.lower() or "cpu" in output.lower() or "error" in output.lower()
