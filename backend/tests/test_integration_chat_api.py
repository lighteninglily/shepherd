import json
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient

# Import the FastAPI app
from backend.app.main import app


class StubOrchestrator:
    """A stub Orchestrator that returns deterministic content/metadata.

    On first call: returns a Jesus-centered invite question.
    Subsequent calls: returns a neutral reply.
    """

    def __init__(self):
        self.calls = 0

    def run(self, turn_state: Any) -> Dict[str, Any]:
        self.calls += 1
        if self.calls in (1, 2):
            return {
                "content": "I hear you. Would you like to bring this to Jesus together this week?",
                "metadata": {
                    "rooted_in_jesus_emphasis": True,
                    "cadence_reason": "invite_initial" if self.calls == 1 else "invite_repeat",
                },
            }
        # Neutral content afterwards
        return {
            "content": "Thanks for sharing that. I'm here with you.",
            "metadata": {
                "rooted_in_jesus_emphasis": False,
                "cadence_reason": "neutral_followup",
            },
        }


@pytest.fixture()
async def client(monkeypatch):
    # Force orchestration ON and stable settings
    from backend.app import config as app_config

    real_get_settings = app_config.get_settings

    def fake_get_settings():
        s = real_get_settings()
        # Ensure orchestration path is used
        object.__setattr__(s, "ORCHESTRATION_ENABLED", True)
        # Keep short limits for any branching
        object.__setattr__(s, "FAITH_QUESTION_TURN_LIMIT", 2)
        return s

    monkeypatch.setattr("backend.app.services.chat.get_settings", fake_get_settings)

    # Patch the Orchestrator used inside ChatService.generate_response
    stub = StubOrchestrator()
    monkeypatch.setattr("backend.app.services.chat.Orchestrator", lambda: stub)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        # Explicit cleanup to emulate lifespan shutdown for older httpx versions
        try:
            from backend.app.db.base import SessionLocal, engine
            SessionLocal.remove()
            engine.dispose()
        except Exception:
            pass
        # Close logging file handlers to avoid unclosed file warnings
        import logging
        try:
            root_logger = logging.getLogger()
            for h in list(root_logger.handlers):
                try:
                    h.flush()
                except Exception:
                    pass
                try:
                    h.close()
                except Exception:
                    pass
                try:
                    root_logger.removeHandler(h)
                except Exception:
                    pass
        except Exception:
            pass


async def _post_chat(client, messages, conversation_id=None):
    payload = {
        "messages": messages,
        "user_id": "user-1",
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    res = await client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    return data


@pytest.mark.anyio
async def test_chat_cadence_decline_cooldown(client):
    # 1) First user message -> assistant returns a Jesus invite question (stub)
    data1 = await _post_chat(
        client,
        messages=[{"role": "user", "content": "We argue a lot lately."}],
    )
    conversation_id = data1["conversation_id"]
    meta1 = data1["message"]["metadata"]
    assert meta1.get("rooted_in_jesus_emphasis") is True
    # Ensure our stub orchestrator path was used
    assert meta1.get("cadence_reason") == "invite_initial"
    # Normalizer should include key even if not set yet
    assert "declined_jesus_until_turn" in meta1

    # 2) User declines the invite -> decline count increments, but cooldown not necessarily set yet
    data2 = await _post_chat(
        client,
        messages=[{"role": "user", "content": "No thanks."}],
        conversation_id=conversation_id,
    )
    meta2 = data2["message"]["metadata"]
    # Normalized keys should be present
    assert "declined_jesus_until_turn" in meta2

    # 3) User declines again -> cooldown should set in conversation metadata
    data3 = await _post_chat(
        client,
        messages=[{"role": "user", "content": "I'd rather not."}],
        conversation_id=conversation_id,
    )
    meta3 = data3["message"]["metadata"]
    assert "declined_jesus_until_turn" in meta3

    # Read conversation metadata from DB to verify persistence of cooldown fields
    from backend.app.models.sql_models import Conversation as SQLConversation
    from backend.app.db.base import SessionLocal

    db = SessionLocal()
    try:
        row = db.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
        assert row is not None
        conv_meta = getattr(row, "metadata_json", {}) or {}
        # Cooldown should be set to an integer turn index
        djut = conv_meta.get("declined_jesus_until_turn")
        assert isinstance(djut, int)
        assert djut >= 1
    finally:
        db.close()


@pytest.mark.anyio
async def test_metadata_normalization_keys_present(client):
    # Single turn should already include normalized keys
    data = await _post_chat(
        client,
        messages=[{"role": "user", "content": "We feel distant lately."}],
    )
    meta = data["message"]["metadata"]
    # Ensure canonical keys are present
    assert "cadence_reason" in meta
    assert "declined_jesus_until_turn" in meta
    # Value may be None initially, but key must exist after normalization
    assert meta.get("declined_jesus_until_turn") is None or isinstance(
        meta.get("declined_jesus_until_turn"), int
    )
