from typing import Any, Dict


CANONICAL_KEYS = {
    "phase",
    "advice_intent",
    "safety_flag_this_turn",
    "gate_reason",
    "book_selection_reason",
    "book_attributions",
    "scrubbed_books",
    "asked_question",
    "rooted_in_jesus_emphasis",
    "jesus_invite_variant",
    "style_guide",
    "faith_branch",
    "topic",
    "topic_confidence",
    # Insights usage flag
    "used_book_insights",
    # Expanded canonical keys for observability
    "path",
    "allow_books",
    "allow_jesus",
    "cadence_reason",
    "planner_retries",
    "fallback_reason",
    "declined_jesus_until_turn",
}


def normalize_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize metadata across orchestrated and legacy paths.

    - Ensures missing keys exist with safe defaults.
    - Coerces types of common fields.
    """
    out: Dict[str, Any] = dict(meta or {})
    out.setdefault("phase", "intake")
    out.setdefault("advice_intent", False)
    out.setdefault("safety_flag_this_turn", False)
    out.setdefault("gate_reason", None)
    out.setdefault("book_selection_reason", None)
    out.setdefault("book_attributions", [])
    out.setdefault("scrubbed_books", [])
    out.setdefault("asked_question", True)
    out.setdefault("rooted_in_jesus_emphasis", False)
    out.setdefault("jesus_invite_variant", 0)
    out.setdefault("style_guide", "friend_v1")
    out.setdefault("faith_branch", "unknown_path")
    out.setdefault("used_book_insights", False)
    out.setdefault("topic", None)
    try:
        out["topic_confidence"] = float(out.get("topic_confidence", 0.0))
    except Exception:
        out["topic_confidence"] = 0.0
    # Expanded defaults and coercions
    out.setdefault("path", "legacy")
    out.setdefault("allow_books", False)
    out.setdefault("allow_jesus", False)
    out.setdefault("cadence_reason", None)
    try:
        out["planner_retries"] = int(out.get("planner_retries", 0) or 0)
    except Exception:
        out["planner_retries"] = 0
    out.setdefault("fallback_reason", None)
    # Ensure the key exists, then coerce types safely
    out.setdefault("declined_jesus_until_turn", None)
    try:
        djut = out.get("declined_jesus_until_turn", None)
        if isinstance(djut, str) and djut.isdigit():
            out["declined_jesus_until_turn"] = int(djut)
        elif isinstance(djut, (int, type(None))):
            # keep as is (int or None)
            out["declined_jesus_until_turn"] = djut
        else:
            out["declined_jesus_until_turn"] = None
    except Exception:
        out["declined_jesus_until_turn"] = None
    return out
