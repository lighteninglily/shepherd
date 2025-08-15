from typing import List, Tuple

from .response_plan import ResponsePlan


def validate_response_plan(plan: ResponsePlan) -> Tuple[bool, List[str]]:
    """Validate a ResponsePlan beyond basic Pydantic constraints.

    Returns (ok, errors)
    """
    errors: List[str] = []

    # Phase sanity
    if plan.phase not in ("intake", "chat", "advice"):
        errors.append(f"invalid phase: {plan.phase}")

    # Safety object must exist (pydantic guarantees), but check reason type
    if plan.safety.flag and (plan.safety.reason is not None) and not isinstance(plan.safety.reason, str):
        errors.append("safety.reason must be a string when provided")

    # Topic confidence
    if not (0.0 <= float(plan.topic_confidence) <= 1.0):
        errors.append(f"topic_confidence out of range: {plan.topic_confidence}")

    # Jesus invite gating coherence
    if plan.jesus_invite_allowed and plan.jesus_invite_variant == 0:
        errors.append("jesus_invite_allowed but variant == 0")
    if (not plan.jesus_invite_allowed) and plan.jesus_invite_variant > 0:
        errors.append("jesus_invite_variant > 0 but not allowed")

    # Steps count and contents
    steps = plan.plan.steps_7day
    if not (3 <= len(steps) <= 5):
        errors.append(f"steps_7day must be 3-5 items, got {len(steps)}")
    for i, s in enumerate(steps, 1):
        if not s.title or not isinstance(s.title, str):
            errors.append(f"step {i} missing title")
        if not s.how_to_say_it or not isinstance(s.how_to_say_it, str):
            errors.append(f"step {i} missing how_to_say_it")
        # Enforce min 5 and max 180 minutes per step
        try:
            tmin = int(s.time_estimate_min)
        except Exception:
            tmin = -1
        if not (5 <= tmin <= 180):
            errors.append(f"step {i} time_estimate_min out of range (5-180): {s.time_estimate_min}")
        # Require a non-empty trigger_if_then string
        trig = getattr(s, "trigger_if_then", None)
        if not (isinstance(trig, str) and trig.strip()):
            errors.append(f"step {i} missing trigger_if_then")

    # Obstacles
    if len(plan.plan.obstacles) == 0:
        errors.append("at least one obstacle required")

    # Check-in question
    if not plan.plan.check_in_question or not isinstance(plan.plan.check_in_question, str):
        errors.append("missing check_in_question")

    # Truth anchor must be present and non-trivial
    ta = getattr(plan.plan, "truth_anchor", "")
    if not (isinstance(ta, str) and ta.strip() and len(ta.strip()) >= 10):
        errors.append("truth_anchor is missing or too trivial")

    return (len(errors) == 0, errors)
