"""BLOQUE 65 — Local Advanced Computer Vision & Dynamic UI Template Tracking Engine tests."""

import time

import pytest

from backend.vision.tracker import (
    CoordinateMapper,
    MatchMode,
    TemplateMatcher,
    TemplateRegistry,
    UIMatchResult,
    UIRegion,
    UITemplate,
    get_template_tracker,
    reset_template_tracker,
)


class TestTemplateMatcher:
    def test_match_returns_match_result(self):
        m = TemplateMatcher()
        result = m.match([(0, 0), (10, 0), (10, 10), (0, 10)], [(0, 0), (10, 0), (10, 10), (0, 10)])
        assert isinstance(result, UIMatchResult)
        assert result.matched is True
        assert result.confidence >= 0.99

    def test_no_match_returns_low_confidence(self):
        m = TemplateMatcher(threshold=0.95)
        result = m.match(
            [(0, 0), (10, 0), (10, 10), (0, 10)], [(100, 100), (110, 100), (110, 110), (100, 110)]
        )
        assert result.matched is False
        assert result.confidence < 0.95

    def test_partial_match(self):
        m = TemplateMatcher(threshold=0.8)
        result = m.match([(0, 0), (10, 0), (10, 10), (0, 10)], [(0, 0), (10, 0), (10, 10), (0, 11)])
        assert result.matched is True
        assert result.confidence >= 0.8

    def test_empty_template(self):
        m = TemplateMatcher()
        result = m.match([], [(0, 0), (10, 0), (10, 10), (0, 10)])
        assert result.matched is False

    def test_sample_distance(self):
        m = TemplateMatcher()
        d = m._sample_distance([(0, 0), (10, 0)], [(0, 0), (10, 0)])
        assert d == 0.0
        d2 = m._sample_distance([(0, 0)], [(10, 10)])
        assert d2 > 0


class TestCoordinateMapper:
    def test_map_simple(self):
        cm = CoordinateMapper()
        pt = cm.map(5, 5)
        assert pt == (5, 5)

    def test_map_with_scale(self):
        cm = CoordinateMapper(scale=2.0)
        pt = cm.map(50, 50)
        assert pt == (100, 100)

    def test_map_with_offset(self):
        cm = CoordinateMapper(offset_x=10, offset_y=20)
        pt = cm.map(0, 0)
        assert pt == (10, 20)

    def test_map_with_region(self):
        cm = CoordinateMapper()
        region = UIRegion(left=100, top=200, width=10, height=10)
        pt = cm.map(5, 5, region=region)
        assert pt == (105, 205)


class TestTemplateRegistry:
    def test_register_and_get(self):
        reg = TemplateRegistry()
        t = UITemplate(name="btn", points=[(0, 0), (10, 0), (10, 10), (0, 10)])
        reg.register(t)
        assert reg.get("btn") is t

    def test_list_templates(self):
        reg = TemplateRegistry()
        reg.register(UITemplate(name="a", points=[(0, 0)]))
        reg.register(UITemplate(name="b", points=[(1, 1)]))
        assert len(reg.list_templates()) == 2

    def test_remove(self):
        reg = TemplateRegistry()
        reg.register(UITemplate(name="x", points=[(0, 0)]))
        reg.remove("x")
        assert reg.get("x") is None


class TestTrackerSingleton:
    def test_singleton(self):
        a = get_template_tracker()
        b = get_template_tracker()
        assert a is b

    def test_reset(self):
        a = get_template_tracker()
        reset_template_tracker()
        b = get_template_tracker()
        assert a is not b
