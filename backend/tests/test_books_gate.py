import types
from typing import Any, Dict, List

import pytest

import backend.app.orchestration.graph as graph_mod


class DummySafety:
    def __init__(self, flag: bool = False):
        self.flag = flag


def _dummy_plan(check_in: str, phase: str = "advice", conf: float = 0.5) -> Any:
    Step = types.SimpleNamespace
    inner = types.SimpleNamespace(
        mirror="I hear you.",
        diagnose="You're feeling stuck.",
        truth_anchor="Jesus is near.",
        steps_7day=[
            Step(title="Talk gently", time_estimate_min=10, how_to_say_it='Say "I care"', trigger_if_then=None)
        ],
        obstacles=["fatigue"],
        check_in_question=check_in,
    )
    plan = types.SimpleNamespace(
        phase=phase,
        safety=DummySafety(flag=False),
        plan=inner,
        jesus_invite_allowed=True,
        jesus_invite_variant=1,
        topic="marriage",
        topic_confidence=conf,
        book_candidate_keys=["dummy"],
    )
    return plan


@pytest.fixture(autouse=True)
def _isolate_defaults(monkeypatch):
    # Prevent external network/moderation variation
    monkeypatch.setattr(graph_mod, "pre_moderate", lambda _: DummySafety(False))
    monkeypatch.setattr(graph_mod, "post_moderate", lambda s: s)
    yield


def test_low_confidence_gates_and_scrubs(monkeypatch):
    # Plan and classifier both low to ensure conf_eff < 0.6
    plan_obj = _dummy_plan(check_in='Have you tried reading "A Made Up Title" together?', conf=0.3)
    monkeypatch.setattr(graph_mod, "llm_structured", lambda **kwargs: plan_obj)
    monkeypatch.setattr(graph_mod, "validate_response_plan", lambda _p: (True, []))
    monkeypatch.setattr(graph_mod, "classify", lambda _msg: {"topic": "marriage", "confidence": 0.2})
    # Insights should still be retrieved (title-free)
    monkeypatch.setattr(graph_mod, "get_insight_clauses", lambda _t, limit=6: ["Seek to understand before being understood."])
    # Retrieval must not be used when gated
    monkeypatch.setattr(graph_mod, "retrieve_snippets", lambda _t: [{"book_pretty": "ShouldNotAppear", "section": "1"}])

    st = graph_mod.TurnState(
        conversation_id="c-low",
        turn_index=3,
        intake_completed=True,  # intake ok
        last_turn_had_jesus=False,
        last_books=[],
        user_message="Help us with conflict",
        history_for_model=[{"role": "user", "content": "Hi"}],
    )

    out = graph_mod.Orchestrator().run(st)
    content = out["content"]
    md: Dict[str, Any] = out["metadata"]

    assert "[resource removed]" in content
    assert md.get("allow_books") is False
    assert md.get("gate_reason") == "low_confidence"
    # Insights used flag should be true even though attributions are gated
    assert md.get("used_book_insights") is True
    # No sources line should be present since ctx should be empty
    assert "Sources:" not in content


def test_allows_books_when_confident(monkeypatch):
    plan_obj = _dummy_plan(check_in="What feels hardest?", conf=0.9)
    monkeypatch.setattr(graph_mod, "llm_structured", lambda **kwargs: plan_obj)
    monkeypatch.setattr(graph_mod, "validate_response_plan", lambda _p: (True, []))
    monkeypatch.setattr(graph_mod, "classify", lambda _msg: {"topic": "marriage", "confidence": 0.85})
    # Insights present regardless of gating
    monkeypatch.setattr(graph_mod, "get_insight_clauses", lambda _t, limit=6: ["Name the pattern, not the person."])
    # Provide retrieval context so compose adds Sources
    monkeypatch.setattr(
        graph_mod,
        "retrieve_snippets",
        lambda _t: [
            {"book_key": "k1", "book_pretty": "A Real Book", "author": "Jane Doe", "section": "ch1"},
            {"book_key": "k2", "book_pretty": "Another Book", "author": "John Roe", "section": "ch3"},
        ],
    )

    st = graph_mod.TurnState(
        conversation_id="c-high",
        turn_index=5,
        intake_completed=True,
        last_turn_had_jesus=False,
        last_books=[],
        user_message="Help us with conflict",
        history_for_model=[{"role": "user", "content": "Hi"}],
    )

    out = graph_mod.Orchestrator().run(st)
    content = out["content"]
    md: Dict[str, Any] = out["metadata"]

    assert md.get("allow_books") is True
    assert md.get("gate_reason") == "ok"
    assert md.get("used_book_insights") is True
    assert "Sources:" in content
    assert "[resource removed]" not in content
