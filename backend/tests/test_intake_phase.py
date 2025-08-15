import json
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient

# Import the FastAPI app
from backend.app.main import app


@pytest.fixture()
async def client_legacy(monkeypatch):
    # Force orchestration OFF to exercise legacy compose path in ChatService.generate_response
    from backend.app import config as app_config

    real_get_settings = app_config.get_settings

    def fake_get_settings():
        s = real_get_settings()
        # Ensure legacy path is used
        object.__setattr__(s, "ORCHESTRATION_ENABLED", False)
        # Keep any other defaults as-is
        return s

    # Patch get_settings used within ChatService
    monkeypatch.setattr("backend.app.services.chat.get_settings", fake_get_settings)

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
async def test_wrapup_affirmation_flips_intake_complete(client_legacy):
    # Start a conversation on legacy path
    data1 = await _post_chat(
        client_legacy,
        messages=[{"role": "user", "content": "We argue a lot lately."}],
    )
    conversation_id = data1["conversation_id"]

    # Ask for advice before intake is complete -> should trigger wrap-up gating in legacy path
    data2 = await _post_chat(
        client_legacy,
        messages=[{"role": "user", "content": "What should I do next?"}],
        conversation_id=conversation_id,
    )
    meta2: Dict[str, Any] = data2["message"]["metadata"]

    # Canonical keys should exist
    assert "allow_books" in meta2
    assert "gate_reason" in meta2
    assert "phase" in meta2
    # Intake should not be complete yet
    intake2 = (meta2.get("intake") or {})
    assert intake2.get("completed") in (False, None)
    # Books should be gated due to intake incomplete
    assert meta2.get("allow_books") is False
    assert meta2.get("gate_reason") == "intake_incomplete"

    # User explicitly affirms wrap-up readiness
    data3 = await _post_chat(
        client_legacy,
        messages=[{"role": "user", "content": "That's enough, I'm ready for advice."}],
        conversation_id=conversation_id,
    )
    meta3: Dict[str, Any] = data3["message"]["metadata"]

    # Intake completion should now be persisted True
    intake3 = (meta3.get("intake") or {})
    assert intake3.get("completed") is True
    # Once complete, gate_reason should no longer be intake_incomplete
    assert meta3.get("gate_reason") != "intake_incomplete"

    # Validate persistence in DB
    from backend.app.models.sql_models import Conversation as SQLConversation
    from backend.app.db.base import SessionLocal

    db = SessionLocal()
    try:
        row = db.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
        assert row is not None
        conv_meta = getattr(row, "metadata_json", {}) or {}
        intake_meta = (conv_meta.get("intake") or {})
        assert intake_meta.get("completed") is True
    finally:
        db.close()
