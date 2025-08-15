import pytest

from backend.app.policies.response_plan import ResponsePlan, Plan, Safety, Step
from backend.app.policies.validator import validate_response_plan


def make_step(title: str, minutes: int, trigger: str) -> Step:
    return Step(title=title, how_to_say_it="Say this...", time_estimate_min=minutes, trigger_if_then=trigger)


def make_plan(truth_anchor: str, steps: list[Step]) -> ResponsePlan:
    return ResponsePlan(
        phase="advice",
        safety=Safety(flag=False, reason=None),
        topic="conflict",
        intake_completed_needed=False,
        jesus_invite_allowed=True,
        jesus_invite_variant=1,
        topic_confidence=0.8,
        book_candidate_keys=["love_and_respect"],
        plan=Plan(
            mirror="I hear you...",
            diagnose="You're facing...",
            truth_anchor=truth_anchor,
            steps_7day=steps,
            obstacles=["time", "motivation"],
            check_in_question="How did it go?",
        ),
    )


def test_validator_rejects_short_time_and_missing_trigger_and_trivial_truth_anchor():
    steps = [
        make_step("Try X", 3, ""),  # invalid: < 5 and empty trigger
        make_step("Try Y", 4, None),  # invalid: < 5 and missing trigger
        make_step("Try Z", 2, "if A then B"),  # invalid: < 5 (trigger ok)
    ]
    plan = make_plan("too short", steps)  # invalid: < 10 chars
    ok, errs = validate_response_plan(plan)
    assert ok is False
    assert isinstance(errs, list)


def test_validator_accepts_valid_plan():
    steps = [
        make_step("Try X", 10, "if A then B"),
        make_step("Try Y", 15, "if A then B"),
        make_step("Try Z", 20, "if A then B"),
    ]
    plan = make_plan("Anchor that is sufficiently long.", steps)
    ok, errs = validate_response_plan(plan)
    assert ok is True, f"Unexpected errors: {errs}" 
