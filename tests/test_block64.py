"""BLOQUE 64 — Local Multi-Agent Swarm & Parallel Worker Engine tests."""

import asyncio

import pytest

from backend.agent_swarm import (
    AgentRole,
    AgentSwarmManager,
    AsyncTaskQueue,
    InterAgentBus,
    QueuedTask,
    SubAgentTask,
    SwarmMessage,
    TaskPlanner,
    get_swarm_manager,
    reset_swarm_manager,
)


class TestInterAgentBus:
    @pytest.mark.asyncio
    async def test_publish_and_recent(self):
        bus = InterAgentBus()
        await bus.publish("a", "topic-x", {"k": 1})
        msgs = bus.recent(10)
        assert len(msgs) == 1
        assert msgs[0]["src_agent"] == "a"
        assert msgs[0]["topic"] == "topic-x"
        assert msgs[0]["payload"]["k"] == 1

    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self):
        bus = InterAgentBus()
        q = await bus.subscribe("agent-1", "topic-x")
        await bus.publish("a", "topic-x", {"hello": "world"})
        drained = await bus.drain(q, timeout=0.2)
        assert len(drained) == 1
        assert drained[0].payload["hello"] == "world"

    @pytest.mark.asyncio
    async def test_direct_message(self):
        bus = InterAgentBus()
        q = await bus.subscribe("agent-2", "direct")
        await bus.publish("a", "ignored", {"x": 1}, dst_agent="agent-2")
        drained = await bus.drain(q, timeout=0.2)
        assert len(drained) == 1
        assert drained[0].dst_agent == "agent-2"


class TestAsyncTaskQueue:
    @pytest.mark.asyncio
    async def test_enqueue_and_wait(self):
        q = AsyncTaskQueue(max_workers=2)

        async def double(x):
            await asyncio.sleep(0.01)
            return x * 2

        tid = await q.enqueue(double, 5)
        result = await q.wait(tid, timeout=2.0)
        assert result == 10
        await q.stop()

    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        q = AsyncTaskQueue(max_workers=4)
        started = []

        async def slow(i):
            started.append(i)
            await asyncio.sleep(0.05)
            return i

        ids = [await q.enqueue(slow, i, priority=0) for i in range(4)]
        # All should complete within ~0.15s if truly parallel
        results = await asyncio.gather(*[q.wait(t, timeout=2.0) for t in ids])
        assert sorted(results) == [0, 1, 2, 3]
        assert len(started) == 4
        await q.stop()

    @pytest.mark.asyncio
    async def test_error_isolation(self):
        q = AsyncTaskQueue(max_workers=2)

        async def boom():
            raise ValueError("boom")

        async def ok():
            return 42

        tid_bad = await q.enqueue(boom)
        tid_good = await q.enqueue(ok)
        with pytest.raises(RuntimeError):
            await q.wait(tid_bad, timeout=2.0)
        assert await q.wait(tid_good, timeout=2.0) == 42
        await q.stop()

    @pytest.mark.asyncio
    async def test_status(self):
        q = AsyncTaskQueue(max_workers=2)
        await q.start()

        async def quick():
            return 7

        tid = await q.enqueue(quick)
        result = await q.wait(tid, timeout=2.0)
        assert result == 7
        st = q.status()
        assert st["max_workers"] == 2
        assert st["completed"] >= 1
        await q.stop()


class TestTaskPlanner:
    def test_plan_returns_tasks(self):
        p = TaskPlanner()
        tasks = p.plan("Write code. Review it. Test it.")
        assert len(tasks) >= 1
        assert all(isinstance(t, SubAgentTask) for t in tasks)

    def test_empty_description_fallback(self):
        p = TaskPlanner()
        tasks = p.plan("")
        assert len(tasks) == 1

    def test_get_execution_order_respects_deps(self):
        p = TaskPlanner()
        tasks = p.plan("A. B. C.")
        ordered = p.get_execution_order(tasks)
        assert len(ordered) == len(tasks)

    def test_validate_plan(self):
        p = TaskPlanner()
        tasks = p.plan("Do something")
        v = p.validate_plan(tasks)
        assert v["valid"] is True
        assert v["task_count"] == len(tasks)


class TestAgentSwarmManager:
    def test_create_and_list_agents(self):
        m = AgentSwarmManager()
        a = m.create_agent("coder")
        assert a["role"] == "coder"
        assert a["status"] == "idle"
        agents = m.list_agents()
        assert len(agents) >= 1

    def test_invalid_role_falls_back(self):
        m = AgentSwarmManager()
        a = m.create_agent("not-a-role")
        assert a["role"] == "planner"

    @pytest.mark.asyncio
    async def test_submit_task_and_execute(self):
        m = AgentSwarmManager()
        res = await m.submit_task("Plan and code a hello world")
        assert res["status"] == "planned"
        assert res["task_count"] >= 1
        plan_id = res["plan_id"]
        exec_res = await m.execute_plan(plan_id, concurrent=True)
        assert exec_res["status"] == "completed"
        assert exec_res["tasks_executed"] >= 1

    @pytest.mark.asyncio
    async def test_execute_unknown_plan(self):
        m = AgentSwarmManager()
        res = await m.execute_plan("nope")
        assert res["status"] == "error"

    @pytest.mark.asyncio
    async def test_infra_start_stop(self):
        m = AgentSwarmManager()
        started = await m.start_infrastructure()
        assert started["status"] == "started"
        assert started["queue"]["max_workers"] >= 1
        stopped = await m.stop_infrastructure()
        assert stopped["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_bus_publish(self):
        m = AgentSwarmManager()
        msg = await m.publish("agent-a", "events", {"n": 1})
        assert msg["src_agent"] == "agent-a"
        recent = m.get_bus_messages(10)
        assert len(recent) == 1

    @pytest.mark.asyncio
    async def test_enqueue_and_wait_task(self):
        m = AgentSwarmManager()

        async def add(a, b):
            await asyncio.sleep(0.01)
            return a + b

        tid = await m.enqueue_task(add, 2, 3, priority=0)
        result = await m.wait_task(tid, timeout=2.0)
        assert result == 5

    def test_get_status_includes_queue(self):
        m = AgentSwarmManager()
        st = m.get_status()
        assert "queue" in st
        assert "bus_messages" in st
        assert st["agents_total"] == 0


def test_get_swarm_manager_singleton():
    reset_swarm_manager()
    a = get_swarm_manager()
    b = get_swarm_manager()
    assert a is b
    reset_swarm_manager()


def test_queued_task_defaults():
    async def f():
        return 1

    qt = QueuedTask(task_id="t1", fn=f)
    assert qt.priority == 0
    assert qt.args == ()


def test_swarm_message_to_dict():
    msg = SwarmMessage(msg_id="m1", src_agent="a", dst_agent="b", topic="t", payload={"x": 1})
    d = msg.to_dict()
    assert d["msg_id"] == "m1"
    assert d["payload"]["x"] == 1


def test_agent_role_values():
    roles = {r.value for r in AgentRole}
    assert {"planner", "coder", "reviewer", "researcher", "evaluator"} == roles
