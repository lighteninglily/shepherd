from backend.app.orchestration.metadata import normalize_meta


def test_normalize_meta_defaults_and_types():
    md = normalize_meta({})
    # Defaults
    assert md["phase"] == "intake"
    assert md["advice_intent"] is False
    assert md["safety_flag_this_turn"] is False
    assert md["book_attributions"] == []
    assert md["scrubbed_books"] == []
    assert md["style_guide"] == "friend_v1"
    assert md["path"] == "legacy"
    assert md["allow_books"] is False
    assert md["allow_jesus"] is False
    assert md["planner_retries"] == 0
    assert md["declined_jesus_until_turn"] is None
    assert isinstance(md["topic_confidence"], float)


def test_normalize_meta_coercions():
    md = normalize_meta({
        "topic_confidence": "0.75",
        "planner_retries": "2",
        "declined_jesus_until_turn": "12",
        "path": "orchestrated",
        "allow_books": True,
        "allow_jesus": True,
        "cadence_reason": "ok",
    })
    assert md["topic_confidence"] == 0.75
    assert md["planner_retries"] == 2
    assert md["declined_jesus_until_turn"] == 12
    assert md["path"] == "orchestrated"
    assert md["allow_books"] is True
    assert md["allow_jesus"] is True
    assert md["cadence_reason"] == "ok"
