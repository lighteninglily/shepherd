import types
from typing import Any, Dict, List

import pytest

import backend.app.orchestration.graph as graph_mod


class DummySafety:
    def __init__(self, flag: bool = False):
        self.flag = flag


def _dummy_plan_with_resource() -> Any:
    # Build a minimal plan object with the attributes used by Orchestrator
    Step = types.SimpleNamespace
    inner = types.SimpleNamespace(
        mirror="I hear you.",
        diagnose="You're feeling stuck.",
        truth_anchor="Jesus is near.",
        steps_7day=[
            Step(title="Talk gently", time_estimate_min=10, how_to_say_it='Say "I care"', trigger_if_then=None)
        ],
        obstacles=["fatigue"],
        check_in_question='Have you tried reading "A Made Up Title" together?',
    )
    plan = types.SimpleNamespace(
        phase="advice",
        safety=DummySafety(flag=False),
        plan=inner,
        jesus_invite_allowed=True,
        jesus_invite_variant=1,
        topic="marriage",
        topic_confidence=0.1,
        book_candidate_keys=["dummy"],
    )
    return plan


@pytest.fixture(autouse=True)
def _isolate_imports(monkeypatch):
    # Ensure no external calls happen
    monkeypatch.setattr(graph_mod, "pre_moderate", lambda _: DummySafety(False))
    monkeypatch.setattr(graph_mod, "post_moderate", lambda s: s)
    monkeypatch.setattr(graph_mod, "classify", lambda _msg: {"topic": "marriage", "confidence": 0.9})
    monkeypatch.setattr(graph_mod, "validate_response_plan", lambda _p: (True, []))
    monkeypatch.setattr(graph_mod, "llm_structured", lambda **kwargs: _dummy_plan_with_resource())
    # Retrieval should not be used when allow_books is False
    monkeypatch.setattr(graph_mod, "retrieve_snippets", lambda _t: [
        # Would have become sources if allowed; ensure disallowed path does not include
        {"book_pretty": "Some Known Book", "section": "1"}
    ])
    yield


def test_orchestrator_scrubs_when_books_gated(monkeypatch):
    orch = graph_mod.Orchestrator()
    st = graph_mod.TurnState(
        conversation_id="cid-1",
        turn_index=1,
        intake_completed=False,  # gate books even though phase is advice
        last_turn_had_jesus=False,
        last_books=[],
        user_message="Help us with conflict",
        history_for_model=[{"role": "user", "content": "Hi"}],
        last_jesus_invite_turn=None,
        declined_jesus_until_turn=None,
        prayer_consent_known=True,
        prayer_consent=True,
    )

    out = orch.run(st)
    content = out["content"]
    md: Dict[str, Any] = out["metadata"]

    assert "[resource removed]" in content
    assert md.get("allow_books") is False
    assert isinstance(md.get("scrubbed_books"), list) and len(md.get("scrubbed_books")) >= 1
    assert md.get("gate_reason") == "intake_incomplete"
    assert md.get("path") == "orchestrated"
