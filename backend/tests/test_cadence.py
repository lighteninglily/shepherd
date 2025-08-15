import types

from backend.app.orchestration.graph import Orchestrator, TurnState
from backend.app.policies.response_plan import ResponsePlan, Plan, Safety, Step


def _valid_plan(phase: str = "advice", jesus_allowed: bool = True) -> ResponsePlan:
    steps = [
        Step(title="Step 1", how_to_say_it="Say..", time_estimate_min=10, trigger_if_then="if A then B"),
        Step(title="Step 2", how_to_say_it="Say..", time_estimate_min=10, trigger_if_then="if A then B"),
        Step(title="Step 3", how_to_say_it="Say..", time_estimate_min=10, trigger_if_then="if A then B"),
    ]
    return ResponsePlan(
        phase=phase,
        safety=Safety(flag=False, reason=None),
        topic="conflict",
        intake_completed_needed=False,
        jesus_invite_allowed=jesus_allowed,
        jesus_invite_variant=1,
        topic_confidence=0.8,
        book_candidate_keys=[],
        plan=Plan(
            mirror="m",
            diagnose="d",
            truth_anchor="This is a sufficiently long anchor.",
            steps_7day=steps,
            obstacles=["time"],
            check_in_question="ok?",
        ),
    )


def _mk_state(**overrides):
    base = dict(
        conversation_id="c1",
        turn_index=5,
        intake_completed=True,
        last_turn_had_jesus=False,
        last_jesus_invite_turn=1,
        declined_jesus_until_turn=None,
        last_books=[],
        user_message="help us with conflict",
        history_for_model=[{"role": "user", "content": "..."}],
    )
    base.update(overrides)
    return TurnState(**base)  # type: ignore[arg-type]


def _patch_dependencies(monkeypatch, plan: ResponsePlan):
    # Always safe
    from backend.app.orchestration import graph as g

    monkeypatch.setattr(g, "pre_moderate", lambda text: types.SimpleNamespace(flag=False))
    monkeypatch.setattr(g, "post_moderate", lambda text: text)
    monkeypatch.setattr(g, "classify", lambda text: {"topic": plan.topic, "confidence": plan.topic_confidence})
    monkeypatch.setattr(g, "retrieve_snippets", lambda topic: [])
    monkeypatch.setattr(g, "triage_route", lambda text, safety: {"content": "triage", "metadata": {}})
    # Structured LLM returns our injected plan
    monkeypatch.setattr(g, "llm_structured", lambda history, schema: plan)


def test_allows_jesus_when_ok(monkeypatch):
    plan = _valid_plan(phase="advice", jesus_allowed=True)
    _patch_dependencies(monkeypatch, plan)
    st = _mk_state(turn_index=5, last_jesus_invite_turn=1, declined_jesus_until_turn=None)
    md = Orchestrator().run(st)["metadata"]
    assert md["allow_jesus"] is True
    assert md["cadence_reason"] == "ok"


def test_blocks_in_cooldown(monkeypatch):
    plan = _valid_plan(phase="advice", jesus_allowed=True)
    _patch_dependencies(monkeypatch, plan)
    st = _mk_state(turn_index=7, last_jesus_invite_turn=1, declined_jesus_until_turn=10)
    md = Orchestrator().run(st)["metadata"]
    assert md["allow_jesus"] is False
    assert md["cadence_reason"] == "cooldown_declined"
    assert md["declined_jesus_until_turn"] == 10


def test_blocks_in_cadence_window(monkeypatch):
    plan = _valid_plan(phase="advice", jesus_allowed=True)
    _patch_dependencies(monkeypatch, plan)
    st = _mk_state(turn_index=6, last_jesus_invite_turn=4, declined_jesus_until_turn=None)
    md = Orchestrator().run(st)["metadata"]
    assert md["allow_jesus"] is False
    assert md["cadence_reason"] == "cadence_window"


def test_blocks_when_last_turn_had_jesus(monkeypatch):
    plan = _valid_plan(phase="advice", jesus_allowed=True)
    _patch_dependencies(monkeypatch, plan)
    st = _mk_state(turn_index=5, last_turn_had_jesus=True)
    md = Orchestrator().run(st)["metadata"]
    assert md["allow_jesus"] is False
    assert md["cadence_reason"] == "last_turn_had_jesus"


def test_blocks_in_intake_phase(monkeypatch):
    plan = _valid_plan(phase="intake", jesus_allowed=True)
    _patch_dependencies(monkeypatch, plan)
    st = _mk_state(turn_index=5)
    md = Orchestrator().run(st)["metadata"]
    assert md["allow_jesus"] is False
    assert md["cadence_reason"] == "phase_intake"
