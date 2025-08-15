from typing import Any, Dict

from ..safety.guard import SafetyVerdict


def triage_route(user_message: str, verdict: SafetyVerdict) -> Dict[str, Any]:
    """Return a short, compassionate safety triage response and metadata.

    Disables books and Jesus-invite for this turn. Frontend can render metadata
    through the normal pathway after normalization.
    """
    content_lines = [
        "Thank you for sharing this. I’m really sorry you’re facing this—your safety matters.",
        "If you’re in immediate danger, please contact local emergency services right away.",
        "If you can, would you share what city/region you’re in so a human can help route local support?",
    ]
    md: Dict[str, Any] = {
        "phase": "intake",
        "advice_intent": False,
        "safety_flag_this_turn": True,
        "gate_reason": "safety_triage",
        "book_selection_reason": None,
        "book_attributions": [],
        "scrubbed_books": [],
        "asked_question": True,
        "rooted_in_jesus_emphasis": False,
        "jesus_invite_variant": 0,
        "style_guide": "friend_v1",
        "faith_branch": "unknown_path",
        "topic": None,
        "topic_confidence": 0.0,
    }
    return {"content": "\n".join(content_lines), "metadata": md}
