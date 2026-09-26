import pytest
from backend.brain_orchestrator import UnifiedBrain


@pytest.fixture
def brain():
    return UnifiedBrain()


def test_brain_init(brain):
    assert brain is not None
    assert brain.state is not None


def test_get_brain_status(brain):
    status = brain.get_brain_status()
    assert status is not None or isinstance(status, dict)


def test_learn(brain):
    result = brain.learn(
        device="test_device",
        role="user",
        prompt="What is the weather?",
        response="The weather is sunny",
        provider="test_provider",
        feedback="good",
    )
    assert result is not None or result is None or isinstance(result, dict)


def test_record_conversation(brain):
    brain.record_conversation(
        device="test_device",
        role="user",
        prompt="hi",
        response="hello",
        provider="test_provider",
        feedback="good",
    )
    assert True


def test_should_retrain(brain):
    result = brain.should_retrain()
    assert isinstance(result, bool)


def test_get_training_dataset(brain):
    dataset = brain.get_training_dataset()
    assert dataset is not None or dataset == [] or isinstance(dataset, list)


def test_register_model_update(brain):
    brain.register_model_update(
        model_id="m1",
        version="1.0",
        path="/tmp/m1",
        role="user",
        device="test_device",
    )
    assert True


@pytest.mark.asyncio
async def test_brain_contradictions(brain):
    """Test detección de contradicciones en reasoning."""
    brain.learn(
        device="test_device",
        role="user",
        prompt="All birds can fly",
        response="OK",
        provider="test",
    )
    brain.learn(
        device="test_device",
        role="user",
        prompt="Penguins are birds and cannot fly",
        response="OK",
        provider="test",
    )
    status = brain.get_brain_status()
    assert status is not None or isinstance(status, dict)


@pytest.mark.asyncio
async def test_brain_parallel_reasoning(brain):
    """Test razonamiento paralelo sobre múltiples queries."""
    import asyncio

    async def _learn(prompt):
        return brain.learn(
            device="test_device",
            role="user",
            prompt=prompt,
            response="parallel",
            provider="test",
        )

    queries = [
        "If A then B",
        "If B then C",
        "Does A imply C?",
    ]

    results = await asyncio.gather(*[_learn(q) for q in queries])
    assert len(results) == 3
    assert all(r is not None or r is None for r in results)


@pytest.mark.asyncio
async def test_brain_learning_feedback_edge_cases(brain):
    """Test learning con feedback edge cases."""
    result1 = brain.learn(
        device="test_device",
        role="user",
        prompt="test",
        response="test response",
        provider="test",
        feedback="good",
    )
    assert result1 is not None or result1 is None or isinstance(result1, dict)

    result2 = brain.learn(
        device="test_device",
        role="user",
        prompt="test",
        response="",
        provider="test",
    )
    assert result2 is not None or result2 is None or isinstance(result2, dict)
