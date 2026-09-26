"""BLOQUE 62 — Organic Motion & Anti-Detection Stealth Controller tests."""

import asyncio
import time

import pytest

from backend.automation.stealth_controller import (
    BezierCurveGenerator,
    HumanProfile,
    OrganicMove,
    StealthActionExecutor,
    StealthMacroRunner,
    StochasticDelayEngine,
    StochasticTiming,
    get_stealth_controller,
)


class TestBezierCurveGenerator:
    def test_generate_returns_organic_move(self):
        gen = BezierCurveGenerator()
        move = gen.generate(0, 0, 200, 150, duration=0.3)
        assert isinstance(move, OrganicMove)
        assert len(move.curve) == 20
        assert move.curve[0].t == 0.0
        assert move.curve[-1].t == 1.0

    def test_short_distance_returns_direct_move(self):
        gen = BezierCurveGenerator()
        move = gen.generate(10, 10, 10.5, 10.5)
        assert move.curve == []

    def test_curve_is_not_linear(self):
        gen = BezierCurveGenerator(jitter=0.4)
        move = gen.generate(0, 0, 200, 0)
        ys = [pt.y for pt in move.curve]
        # At least one point should deviate from the straight line y=0
        assert any(abs(y) > 0.01 for y in ys)

    def test_sample_interpolates_between_points(self):
        gen = BezierCurveGenerator()
        move = gen.generate(0, 0, 100, 100)
        x0, y0 = gen.sample(move, 0.0)
        x1, y1 = gen.sample(move, 1.0)
        assert abs(x0 - 0.0) < 1.0 and abs(y0 - 0.0) < 1.0
        # Overshoot may push the final sample slightly past the target.
        assert abs(x1 - 100.0) < 15.0 and abs(y1 - 100.0) < 15.0

    def test_sample_clamps_t(self):
        gen = BezierCurveGenerator()
        move = gen.generate(0, 0, 100, 100)
        xa, ya = gen.sample(move, -0.5)
        xb, yb = gen.sample(move, 1.5)
        # Clamped extremes should both land on the move's own endpoints.
        assert xa == move.curve[0].x and ya == move.curve[0].y
        assert xb == move.curve[-1].x and yb == move.curve[-1].y


class TestStochasticDelayEngine:
    def test_returns_stochastic_timing(self):
        engine = StochasticDelayEngine()
        t = engine.next_delay("click")
        assert isinstance(t, StochasticTiming)
        assert t.actual_delay > 0

    def test_jitter_within_bounds(self):
        engine = StochasticDelayEngine(profile=HumanProfile.NORMAL)
        for _ in range(20):
            engine.next_delay("click")
        lo, hi = engine.jitter_range()
        assert lo < hi

    def test_mean_delay_reflects_history(self):
        engine = StochasticDelayEngine(base_delay=0.2)
        for _ in range(30):
            engine.next_delay("click")
        assert engine.mean_delay() > 0

    def test_different_profiles(self):
        slow = StochasticDelayEngine(profile=HumanProfile.CAUTION, base_delay=0.2)
        fast = StochasticDelayEngine(profile=HumanProfile.FAST, base_delay=0.2)
        for _ in range(30):
            slow.next_delay("click")
            fast.next_delay("click")
        assert slow.mean_delay() > fast.mean_delay()


class TestStealthActionExecutor:
    @pytest.mark.asyncio
    async def test_move_without_os_controller(self):
        ex = StealthActionExecutor()
        res = await ex.move(100, 100, 0, 0)
        assert res["status"] == "ok"
        assert "move_id" in res

    @pytest.mark.asyncio
    async def test_click_records_action(self):
        ex = StealthActionExecutor()
        await ex.click(50, 50)
        actions = ex.recent_actions(10)
        assert any(a["kind"] == "click" for a in actions)

    @pytest.mark.asyncio
    async def test_type_text_records_chars(self):
        ex = StealthActionExecutor()
        res = await ex.type_text("hello")
        assert res["status"] == "ok"
        assert res["chars"] == 5

    @pytest.mark.asyncio
    async def test_keypress(self):
        ex = StealthActionExecutor()
        res = await ex.keypress("enter")
        assert res["status"] == "ok"
        assert res["key"] == "enter"

    @pytest.mark.asyncio
    async def test_scroll(self):
        ex = StealthActionExecutor()
        res = await ex.scroll(5)
        assert res["status"] == "ok"
        assert res["amount"] == 5

    def test_movement_stats(self):
        ex = StealthActionExecutor()
        stats = ex.movement_stats()
        assert stats["total_actions"] == 0
        assert stats["profile"] == "normal"


class TestStealthMacroRunner:
    def test_register_and_list(self):
        ex = StealthActionExecutor()
        runner = StealthMacroRunner(ex)
        runner.register("demo", [{"action": "click", "params": {"x": 1, "y": 2}}])
        assert "demo" in runner.list_macros()

    def test_run_unknown_macro(self):
        ex = StealthActionExecutor()
        runner = StealthMacroRunner(ex)
        res = asyncio.run(runner.run("does_not_exist"))
        assert res["status"] == "error"

    @pytest.mark.asyncio
    async def test_run_registered_macro(self):
        ex = StealthActionExecutor()
        runner = StealthMacroRunner(ex)
        runner.register(
            "seq",
            [
                {"action": "click", "params": {"x": 1, "y": 2}},
                {"action": "keypress", "params": {"key": "a"}},
            ],
        )
        res = await runner.run("seq")
        assert res["status"] == "ok"
        assert res["entry"]["steps"] == 2
        assert len(runner.history(10)) == 1


def test_get_stealth_controller_returns_instances():
    ex, runner = get_stealth_controller()
    assert isinstance(ex, StealthActionExecutor)
    assert isinstance(runner, StealthMacroRunner)


def test_default_profiles_cover_all():
    import backend.automation.stealth_controller as sc

    assert set(sc._DEFAULT_PROFILES) == set(HumanProfile)
