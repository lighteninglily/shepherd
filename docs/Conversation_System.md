## Recent Changes — 2025-08-13 — Timezone-aware UTC & Unified Invite Gate

- __Timezone-aware UTC everywhere__
  - API response timestamp now uses timezone-aware UTC in [`backend/app/api/v1/routers/chat.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/api/v1/routers/chat.py).
  - Message persistence uses timezone-aware `created_at` in [`backend/app/services/chat.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/services/chat.py).
  - Pydantic base model `created_at` default is UTC-aware in [`backend/app/models/base.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/models/base.py).
  - SQLAlchemy models use a single `now_utc()` for defaults/updates (e.g., `Conversation.created_at/updated_at`) in [`backend/app/models/sql_models.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/models/sql_models.py).

- __Unified Jesus‑invite gating aligned with tests__
  - Gate implementation lives in `invite_gate()` within [`backend/app/orchestration/graph.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/graph.py).
  - Added `last_turn_had_jesus` check to prevent consecutive invites.
  - Consent gating: blocks only if consent is known and declined; unknown consent does not block base cadence.
  - Phase gate: returns `phase_intake` when plan phase is intake.
  - Cadence reason renamed: `frequency` → `cadence_window`.
  - Orchestrator passes `last_turn_had_jesus` to `invite_gate()` and persists cadence decisions in metadata.
  - Canonical `cadence_reason` values now include:
    - `first_turn`, `safety`, `phase_intake`, `intake`, `not_advice`, `cadence_window`, `cooldown_declined`, `last_turn_had_jesus`, `plan_blocked`, `ok`.

- __Structured logging of gating decisions__
  - Per‑turn JSON log with key `gate` includes: `cid`, `path`, `phase`, `advice_intent`, `intake_completed`, `safety`, `consent_known`, `consent`, `a_idx`, `last_invite`, `until`, `allow_jesus`, `cadence_reason` from [`backend/app/orchestration/graph.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/graph.py).

- __Metadata hygiene and parity__
  - Normalized assistant metadata includes `allow_jesus`, `cadence_reason`, `declined_jesus_until_turn` (when present), `topic`, `topic_confidence`, `style_guide: friend_v1`, `asked_question`.
  - Book gating remains: `gate_reason` of `ok | intake_incomplete | low_confidence` with `allow_books` reflecting decision.

- __Tests__
  - Cadence tests updated/validated: all pass in `tests/test_cadence.py` (e.g., reasons `ok`, `cooldown_declined`, `cadence_window`, `last_turn_had_jesus`, `phase_intake`).
  - Integration tests pass: cooldown persistence and metadata normalization verified in `tests/test_integration_chat_api.py`.

---

## Recent Changes — 2025-08-13 — Jesus Invite Cooldown Persistence & Legacy Gating

- __Legacy path gating aligned with orchestrator__: The fallback flow in [`backend/app/services/chat.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/services/chat.py) now enforces Jesus-invite gating using DB-derived indices and conversation metadata, mirroring orchestrator behavior.
  - Reads assistant turn index and last assistant text via `ChatService._get_turn_indexes()` inside `ChatService.generate_response()`.
  - Reads cooldown from conversation metadata (`declined_jesus_until_turn`) via a fresh DB read before gating.
- __Cooldown persistence__: Declines/ignores increment `jesus_decline_count`. At 2+, we set/extend `declined_jesus_until_turn = assistant_turn_index + 6` and persist to the conversation row. See legacy block in `ChatService.generate_response()`.
- __Invite append + metadata__: When an invite is actually appended in legacy flow:
  - Persist `last_jesus_invite_turn = assistant_turn_index` (DB-derived), matching orchestrator semantics.
  - Per-message metadata uses `allow_jesus` (boolean decision) and records `cadence_reason` for observability; `jesus_invite_variant` is preserved. Normalization still ensures canonical keys.
- __Canonical cadence_reason values__ now standardized and logged as one of:
  - `safety`, `intake`, `last_turn_had_jesus`, `first_assistant_turn`, `cooldown`, `frequency_gate`, `ok`.
- __Logging__: Each assistant turn logs a single line summarizing gating: `cadence_gate cid=<id> allow=<bool> reason=<reason> a_turns=<int> cooldown_until=<int|None> phase=<str|None> safety=<bool> last_turn_had_jesus=<bool>`.
- __Where__: All changes localized to `ChatService.generate_response()` (legacy branch) and reuse existing helpers `ChatService._get_turn_indexes()` and `ChatService.update_conversation()` for consistent state hygiene.

Testing notes (manual):
- Trigger an invite, decline twice across turns → expect `jesus_decline_count >= 2`, `declined_jesus_until_turn` set, and `cadence_reason = "cooldown"` until threshold is passed.
- After threshold, invite resumes on an even eligible assistant turn (`frequency_gate` on odd turns).
- Safety or intake turns should not invite (`cadence_reason = "safety" | "intake"`).

---

# Shepherd Conversation System Guide

This document describes the end-to-end conversation system: lifecycle, decision trees, gating rules, metadata, configuration files, and how to tune behaviors.

- Backend: FastAPI service and conversation logic in `backend/app/services/chat.py`.
- Frontend: Next.js chat UI in `frontend/components/chat/chat.tsx`.
- Topic rules: `backend/app/pastoral/rules/marriage.json`.

Useful file links (click to open):
- [backend/app/services/chat.py](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/services/chat.py)
- [frontend/components/chat/chat.tsx](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/frontend/components/chat/chat.tsx)
- [backend/app/pastoral/rules/marriage.json](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/pastoral/rules/marriage.json)

---

## 1) High-level Flow

1. User message is posted to `POST /api/v1/chat`.
2. Backend `ChatService.generate_response()` now supports a feature-flagged orchestration path:
   - If `ORCHESTRATION_ENABLED=true`, the turn is routed through the Orchestrator which performs safety pre-checks with triage short-circuit, calls an LLM in JSON mode to produce a structured `ResponsePlan`, applies cadence gating (Jesus invite with persisted cadence window + books), stubs retrieval, composes the final message, runs post-moderation, and returns metadata. If anything errors, it safely falls back to the legacy flow.
   - If the flag is off, the legacy flow runs unchanged.
   - In both paths, assistant message metadata is normalized via `normalize_meta()` to ensure consistent keys and types.
   - History windowing: keep the first system message (if any) and the last 8 user/assistant turns (16 messages) when forming the model history.
3. Frontend renders the assistant reply with phase and gating badges. When `NEXT_PUBLIC_DEBUG_PANEL=true`, a per-message Debug Panel exposes the metadata and rationale.

---

## 2) API Contract

- Endpoint: `POST /api/v1/chat` (base from `NEXT_PUBLIC_API_BASE_URL`, e.g., `http://127.0.0.1:8000/api/v1/chat`).
- Request (typical):
```json
{
  "conversation_id": "<uuid or null>",
  "message": "We are arguing a lot lately.",
  "message_history": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ]
}
```
- Response (typical):
```json
{
  "id": "<message id>",
  "conversation_id": "<uuid>",
  "user_id": "assistant",
  "role": "assistant",
  "content": "...",
  "created_at": "2025-08-12T06:55:00Z",
  "metadata": {
    "phase": "intake|chat|advice",
    "advice_intent": true,
    "advice_patterns_matched": ["any advice"],
    "safety_flag_this_turn": false,
    "safety_terms_matched": [],
    "gate_reason": "ok",
    "book_selection_reason": "contextual: finances -> The Meaning of Marriage",
    "book_attributions": [
      {"key": "the_meaning_of_marriage", "pretty": "The Meaning of Marriage", "author": "Timothy Keller"}
    ],
    "scrubbed_books": [],
    "asked_question": true,
    "rooted_in_jesus_emphasis": true,
    "jesus_invite_variant": 0,
    "style_guide": "friend_v1",
    "faith_branch": "unknown_path",
    "topic": "marriage_conflict",
    "topic_confidence": 0.72
  }
}
```

---

## 2.1) Metadata Normalization

All assistant messages (orchestrated and legacy paths) pass through a metadata normalizer: [`backend/app/orchestration/metadata.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/metadata.py).

- Canonical keys ensured by `normalize_meta()` with safe defaults and types:
  - `phase: str` (default `intake`)
  - `advice_intent: bool` (default `false`)
  - `safety_flag_this_turn: bool` (default `false`)
  - `gate_reason: str|null`
  - `book_selection_reason: str|null`
  - `book_attributions: list` (default `[]`)
  - `scrubbed_books: list` (default `[]`)
  - `asked_question: bool` (default `true`)
  - `rooted_in_jesus_emphasis: bool` (default `false`)
  - `jesus_invite_variant: int` (default `0`)
  - `style_guide: str` (default `friend_v1`)
  - `faith_branch: str` (default `unknown_path`)
  - `topic: str|null`
  - `topic_confidence: float` (default `0.0`, coerced to float)
  - `path: str` (e.g., `orchestrated` or `legacy`)
  - `allow_books: bool` (effective decision this turn)
  - `allow_jesus: bool` (effective decision this turn)
  - `cadence_reason: str|null` (one of `first_turn|safety|intake|frequency|cooldown_declined|ok`)
  - `planner_retries: int` (number of structured plan attempts for this turn)
  - `fallback_reason: str|null` (e.g., `plan_validation_failed`)

- Back-compat keys (legacy path emits these alongside canonical keys):
  - `conversation_phase` mirrors `phase`
  - `book_scrubbed` mirrors `scrubbed_books`

- Legacy-only diagnostic fields may still appear (e.g., `advice_patterns_matched`, `safety_terms_matched`). Frontend should prefer canonical keys for badges/logic.

## 3) Conversation Phases and State

- Phase is computed in `ChatService.generate_response()` and stored in the assistant message `metadata.phase`.
- Phases:
  - `intake`: early messages where the system is learning context.
  - `chat`: ongoing pastoral conversation.
  - `advice`: explicit advice intent detected (see regex below).
- Intake completion: stored in conversation metadata (via `update_conversation()`), and read each turn to decide gating.

Relevant code:
- Function: `ChatService.generate_response()` in [chat.py](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/services/chat.py)
- Persistence helpers: `add_message()`, `update_conversation()`, `get_conversation_history()`

---

## 4) Intent Detection

### Advice Intent
- Regex list (subset):
```python
advice_patterns = [
    r"\bwhat should i do\b",
    r"\bwhat do i do\b",
    r"\bany advice\b",
    r"\bcan you (?:give|offer) advice\b",
    r"\bwhat advice(?: can you (?:offer|give)(?: me)?)?\b",
    r"\bdo you have advice\b",
    r"\bany guidance\b",
    r"\bcan you (?:give|offer) guidance\b",
    r"\brecommend (?:a )?(?:book|resource|next steps)\b",
    r"\bdo you have (?:a )?(?:book|resource|author)\b",
    r"\bhow (?:do|can) i (?:handle|respond|change|stop)\b",
    r"\bhow (?:should|can) i\b",
    r"\bwhat can i do\b",
    r"\bany suggestions\b",
    r"\bany tips\b",
    r"\bcan you help\b",
    r"\bsteps? (?:i|we) can take\b",
]
```
- If any pattern matches the lowercased user message, `advice_intent=true` and the matched patterns are stored in `metadata.advice_patterns_matched`.

### Safety Detection
- Safety detection scans for risk/abuse/self-harm terms.
- When matched, `safety_flag_this_turn=true` and `safety_terms_matched=[...]` are recorded.
- Safety triage short-circuits the orchestrator: a compassionate triage response is returned immediately for that turn (no resources, no Jesus invite on that turn).

---

## 5) Resource/Book Gating Logic

- Orchestrated path book/resource allowance requires:
  - `plan.phase == "advice"`
  - `intake_completed == true` (conversation-level flag, derived from `IntakeState` in conversation metadata)
  - `safety.flag == false` (defensive; safety triage short-circuits earlier)
  - `plan.topic_confidence >= 0.6`
- Expressed as (orchestrator):
```python
allow_books = (
    plan.phase == "advice"
    and intake_completed
    and (not safety.flag)
    and plan.topic_confidence >= 0.6
)
```
- `gate_reason` values:
  - `ok` — resources allowed
  - `intake_incomplete` — intake gating prevented resources
  - `low_confidence` — topic confidence below threshold prevented resources
  - `safety_triage` — safety short-circuit (no resources this turn)
- Legacy path continues to use advice-intent + intake + safety logic.

---

## 6) Book Attribution Selection

- Rules source: [backend/app/pastoral/rules/marriage.json](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/pastoral/rules/marriage.json)
- No keyword mapping heuristics are used.
- Attributions come from either:
  - Explicit mentions detected in the model output (scrubbed if gated), or
  - Orchestrator retrieval results when resources are allowed.

Only when retrieval returns chunks do we attach citations (see §7/§8). Never fabricate sources.

---

## 7) Jesus-centered Cadence and Questioning

The system balances pastoral questioning with explicit Jesus-centered invitations.

- If no question was asked in the turn, we end with a short, generic pastoral prompt (no Jesus mention) to avoid repetition and keep the conversation moving.
- Orchestrated path Jesus invitation is appended only when all conditions hold:
  - Not a safety triage turn (triage turns never append)
  - `st.turn_index > 0` (suppress first assistant turn)
  - `plan.phase != "intake"`
  - At least 3 assistant turns since the last invite persisted in conversation metadata: `last_jesus_invite_turn`
  - `assistant_turn_index < declined_jesus_until_turn` (decline cooldown)
  - `plan.jesus_invite_allowed == true`
- Phrasing rotates via `plan.jesus_invite_variant`.

Decline cooldown memory:
- The system tracks a cooldown based on declines/ignores to recent invites.
- If two declines/ignores occur, suppress invites for 6 assistant turns using `declined_jesus_until_turn` (conversation metadata).
- Record `cadence_reason` in metadata as one of: `first_turn`, `safety`, `intake`, `frequency`, `cooldown_declined`, `ok`.

Retrieval-only citations: Only print a "Sources" section when retrieval returned chunks for this turn; never fabricate.

Example (simplified):
```python
# generic fallback if no question yet
if not asked_question:
    assistant_message += choose([
        " What feels most important to tackle first?",
        " What would be a small, doable next step?",
        " What would be helpful for me to understand better?",
    ])
    asked_question = True

# append Jesus-centered invite under cadence/eligibility rules
if not safety_hit and not last_turn_had_jesus and cadence_allows:
    assistant_message += choose([
        " Where do you sense Jesus inviting you to take one small, grace-filled step this week?",
        " What might Jesus be leading you to try as a small next step right now?",
        " How could you bring this to Jesus in a practical way this week?",
    ])
    rooted_in_jesus_emphasis = True
```

Tuning note:
- First-turn Jesus invite is already suppressed in the orchestrator (`st.turn_index > 0`).
- Adjust cadence by changing the cadence window (default 3 turns) and using the persisted `last_jesus_invite_turn` stored in conversation metadata.

---

## 8) Message Metadata Schema (Assistant)

Each assistant message includes a rich `metadata` object for observability and frontend badges.

Orchestrated path (sample):
```json
{
  "phase": "advice",
  "advice_intent": true,
  "safety_flag_this_turn": false,
  "gate_reason": "ok",
  "path": "orchestrated",
  "allow_books": true,
  "allow_jesus": true,
  "cadence_reason": "ok",
  "planner_retries": 1,
  "fallback_reason": null,
  "book_selection_reason": "contextual",
  "book_attributions": [
    {"key": "the_meaning_of_marriage", "pretty": "The Meaning of Marriage", "author": "Timothy Keller"}
  ],
  "scrubbed_books": [],
  "asked_question": true,
  "rooted_in_jesus_emphasis": true,
  "jesus_invite_variant": 2,
  "style_guide": "friend_v1",
  "faith_branch": "unknown_path"
}
```
Notes:
- Both orchestrated and legacy paths are normalized to the same canonical schema via `normalize_meta()`.
- Legacy path may additionally include: `advice_patterns_matched`, `safety_terms_matched`.

---

## 9) Frontend Behavior and Debug Panel

- Chat UI: [frontend/components/chat/chat.tsx](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/frontend/components/chat/chat.tsx)
- Uses `NEXT_PUBLIC_API_BASE_URL` to call `/api/v1/chat`.
- Badges:
  - Phase badge from `metadata.phase`.
  - "Resources gated" vs "Resources allowed" from `metadata.gate_reason`.
  - "Jesus-centered" badge when `metadata.rooted_in_jesus_emphasis` is true (orchestrated path may also show `jesus_invite_variant`).
- Debug Panel (gated behind `NEXT_PUBLIC_DEBUG_PANEL=true`): per-assistant message toggle shows:
  - `advice_intent`, `advice_patterns_matched`
  - `safety_flag_this_turn`, `safety_terms_matched`
  - `gate_reason`, `book_selection_reason`
  - `path`, `allow_books`, `allow_jesus`, `cadence_reason`, `planner_retries`, `fallback_reason`
  - `book_attributions`, `scrubbed_books`
  - `asked_question`, `rooted_in_jesus_emphasis`, `faith_branch`
  - Raw JSON metadata

---

## 10) Conversation Persistence

- Conversations and messages are persisted via SQLAlchemy models (see `..models.sql_models`).
- Helpers in `ChatService`:
  - `create_conversation()`
  - `add_message()`
  - `get_conversation()` / `get_conversation_history()`
  - `update_conversation()` (stores conversation-level metadata like intake completion)

---

## 11) Configuration & Environment

- Frontend:
  - `NEXT_PUBLIC_API_BASE_URL` (e.g., `http://127.0.0.1:8000`)
  - `NEXT_PUBLIC_DEBUG_PANEL=true` to enable Debug Panel
- Backend:
  - `OPENAI_API_KEY`
  - `ORCHESTRATION_ENABLED` (boolean): when true, uses Orchestrator with structured outputs and safe fallback on errors
  - `MODEL_NAME`: model used by both orchestrated and fallback paths
  - `TEMPERATURE`: generation temperature used across both paths
  - `MAX_PLANNER_RETRIES`: retry count for structured LLM planning (schema + semantic validation)
  - `MAX_TOKENS`: response token cap (direct HTTPS path)
  - `PRESENCE_PENALTY`, `FREQUENCY_PENALTY`: penalties (direct HTTPS path)
  - Orchestrator LLM: JSON-mode `chat.completions` using configured `MODEL_NAME`/`TEMPERATURE` and `MAX_PLANNER_RETRIES` from [backend/app/orchestration/llm.py](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/llm.py)
  - ChatService unified config: `ChatService.__init__()` now applies these settings so fallback and orchestrator use the same model/temperature/penalties
- Topic rules: `backend/app/pastoral/rules/marriage.json`

---

## 12) Decision Trees (Textual)

### Book/Resource Gating (Orchestrated)
- If `plan.safety.flag == true` ⇒ Gate.
- Else if `plan.phase != "advice"` ⇒ Gate.
- Else if `intake_completed == false` ⇒ Gate.
- Else if `plan.topic_confidence < 0.6` ⇒ Gate.
- Else ⇒ Allow resources (`gate_reason = ok`), choose attribution.

### Jesus Invitation (Orchestrated)
 If triage this turn ⇒ don’t append.
 - Else if `st.turn_index == 0` ⇒ don’t append (first turn suppression).
 - Else if `plan.phase == "intake"` ⇒ don’t append.
 - Else if `st.last_turn_had_jesus == true` ⇒ don’t append.
 - Else if fewer than 3 assistant turns since `last_jesus_invite_turn` ⇒ don’t append (cadence window).
 - Else if `assistant_turn_index < declined_jesus_until_turn` ⇒ don’t append (decline cooldown).
 - Else if `plan.jesus_invite_allowed == false` ⇒ don’t append.
 - Else ⇒ append invite; include `jesus_invite_variant` in metadata and persist `last_jesus_invite_turn`.

### Phase Progression (simplified)
- Start at `intake`.
- On explicit advice intent ⇒ `advice`.
- Otherwise ongoing `chat`.
- Intake completion flips a conversation-level flag enabling resources later.

---

## 13) Tuning Knobs

- Advice regex list (expand/trim to your needs).
- Safety terms list (expand/trim; adjust severity).
- Cadence rules for Jesus invite:
  - Suppress on first assistant turn.
  - Change frequency (e.g., every 3rd eligible turn).
  - Customize phrasing variants.
- Classifier-weighted topic→book mapping (adjust weights per topic; consider repetition penalty window).
- Repetition guard depth for book attributions.

---

## 14) Testing & Troubleshooting

- Use the Debug Panel to verify: `advice_intent`, `gate_reason`, `book_selection_reason`, `rooted_in_jesus_emphasis`.
- Toggle orchestration: set `ORCHESTRATION_ENABLED=true|false`, restart backend, send a message. Both paths should honor the configured `MODEL_NAME`/`TEMPERATURE`.
- Explicit tests to add/run:
  - `tests/test_cadence.py` (first-turn, safety, frequency window, decline cooldown)
  - `tests/test_intake.py` (intake gating via `IntakeState`)
  - `tests/test_plan_validator.py` (rules + repair retry; fallback on failure)
  - `tests/test_safety.py` (triage short-circuit)
  - `tests/test_topic_confidence.py` (confidence < 0.6 gates books)
- Startup config log: on service init, `ChatService` logs `ChatService config: model=... temperature=... max_tokens=... presence_penalty=... frequency_penalty=...` confirming unified settings were applied.
- Scripts (repo root `scripts/`):
  - `run_conversation_tests.ps1` for end-to-end smoke checks.
  - `print_latest_transcript.ps1` to export conversations.
- Dropbox + Next.js:
  - Exclude `.next/` and `.turbo/` using `.dropboxignore` to prevent file-lock errors.
  - If you see `UNKNOWN: unknown error, open ...middleware-react-loadable-manifest.js`, delete `.next/` and restart dev.

---

## 15) Roadmap Ideas

- First-turn Jesus suppression toggle (default off): append only from the second assistant message onward.
- Formalize phase transitions (explicit intake complete event) and surface a Phase badge in the UI toolbar.
- Extend `marriage.json` with topic → book weights rather than pure keyword lists.
- Add unit tests for advice regex, safety matches, cadence behavior, and book selection mapping.

---

## 16) Pointers to Key Functions

- `ChatService.generate_response()` — main orchestration
- Orchestrator: [`backend/app/orchestration/graph.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/graph.py)
- Safety triage router: [`backend/app/orchestration/triage.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/triage.py)
- Structured LLM wrapper: [`backend/app/orchestration/llm.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/llm.py)
- Response schema: [`backend/app/policies/response_plan.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/policies/response_plan.py)

---

## 17) Debugging Log — 2025-08-13: Jesus-invite cooldown persistence

This section documents the ongoing investigation into the cadence gating “decline cooldown” not persisting correctly in conversation metadata, causing integration tests to fail.

### Summary of the issue

- __Symptom__: After two user declines to Jesus-centered invites, the cooldown metadata key `declined_jesus_until_turn` should be persisted on the conversation (`conversations.metadata`). In practice, it remains `None` in the DB, causing assertions to fail.
- __Expected__: `declined_jesus_until_turn` is an integer turn index (>=1) stored in conversation metadata after repeated declines.

### Failing test and setup

- Test file: [`backend/tests/test_integration_chat_api.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/tests/test_integration_chat_api.py)
- Relevant test: `test_chat_cadence_decline_cooldown`
- Key excerpt (final DB assertion):

```python
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
```

- The test enables orchestration and injects a deterministic stub orchestrator that returns a Jesus-invite on the first two assistant turns, then a neutral reply.

### What we’ve observed so far

- __Normalization works__: Assistant message metadata always contains the normalized key `declined_jesus_until_turn` (present but often `None`).
- __Cooldown not persisted__: After the third user message (second decline), the conversation row’s `metadata` JSON still lacks a non-null `declined_jesus_until_turn`.
- __Session staleness suspected__: Given a scoped_session (`SessionLocal`) is used, we suspected identity map caching across requests masked updates.

### Code paths and findings

- Primary logic: `ChatService.generate_response()` in [`backend/app/services/chat.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/services/chat.py)
  - Orchestrator path is feature-flagged via `ORCHESTRATION_ENABLED`. The test monkeypatches `get_settings()` and `Orchestrator` to force use of the stub.
  - The test’s stub returns only per-message metadata like `rooted_in_jesus_emphasis` and `cadence_reason`; it does not itself persist cooldown fields. That must be handled in `generate_response()` by interpreting declines and updating conversation metadata.

- In the legacy path metadata assembly, we found this snippet:

```python
_legacy_meta = {
    ...
    "declined_jesus_until_turn": locals().get("declined_jesus_until_turn_local", None),
    ...
}
```

Issues identified:

- __Undefined variable__: `declined_jesus_until_turn_local` is never defined anywhere in `generate_response()` for the legacy path. Searching the file also shows no `jesus_decline_count` or related updates. Hence, this field is always `None` in legacy metadata.
- __No decline detection implemented__: There is currently no logic that:
  - Detects a user decline to a prior invite (e.g., patterns like “No thanks”, “Not now”).
  - Increments a `jesus_decline_count` in conversation metadata.
  - Computes and persists `declined_jesus_until_turn` when the decline threshold is reached.

Because of the two issues above, even when the orchestrator stub asks an invite and the user declines twice, the system never updates conversation-level cooldown fields.

### Session management adjustments made

To rule out session-staleness masking writes, we added explicit `scoped_session` cleanup after DB operations:

- In `ChatService.update_conversation()` (file: [`backend/app/services/chat.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/services/chat.py)) — after `db.close()` we now call `SessionLocal.remove()` to clear the identity map.
- In the legacy inline metadata update block in `generate_response()` — after committing and closing, we call `SessionLocal.remove()` as well.
- In `ChatService.add_message()` — after closing, we also call `SessionLocal.remove()`.

DB/session files for reference:

- Scoped session setup: [`backend/app/db/base.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/db/base.py)
- SQL models (note JSON columns `metadata`): [`backend/app/models/sql_models.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/models/sql_models.py)

Outcome: While good hygiene, these removals do not address the missing cooldown computation; the test still fails.

### Additional contributing factors and hypotheses

- __Assistant turn index and history source__: In cadence logic we compute assistant turn counts from the provided `message_history`. In the integration test, the request payload sends only the current user message and `conversation_id`, not the full prior assistant messages. If we rely solely on `message_history` (request body) rather than persisted DB history, turn counts (and therefore cadence windows) can be incorrect or reset each request.
- __Orchestrator vs legacy overwrite risk__: If both orchestrator and a legacy DB update block modify conversation metadata in the same turn, ordering or shallow merges might inadvertently drop fields unless carefully merged. We did not find direct evidence of overwrite here, but it is a potential hazard.
- __Feature flag timing__: `get_settings()` is called at runtime; the test monkeypatches `get_settings` before making requests, so this should be fine. Still, verify `settings.ORCHESTRATION_ENABLED` at the start of each turn via logs.

### Why the tests currently fail

- The test expects that after two declines the conversation metadata contains an integer `declined_jesus_until_turn`. Our codebase currently does not implement decline counting or cooldown computation/persistence in `generate_response()`. The field is referenced in metadata using an undefined local (`declined_jesus_until_turn_local`), so it remains `None`.

### What’s been done so far

- __Logging__: Added extensive logging in `generate_response` to surface gating variables (assistant turn counts, phase, safety flags, book gating).
- __Session hygiene__: Added `SessionLocal.remove()` after DB session closure in `update_conversation()`, `add_message()`, and the legacy inline metadata update block to avoid stale cached rows between requests/tests.
- __Verification__: Confirmed that normalized assistant message metadata always includes the canonical keys. Verified the orchestrator stub is injected by the test and returns Jesus-invite content the first two turns.

### Concrete fixes to implement next (design outline)

1. __Implement decline detection and cooldown__: In `ChatService.generate_response()`:
   - Read conversation metadata to get prior `jesus_decline_count` (default 0), `last_jesus_invite_turn`, and current `assistant_turn_index`.
   - Detect a decline in the current user message when the last assistant turn was a Jesus-invite question (regex: e.g., `\bno thanks\b|\bnot now\b|\brather not\b|\bno\b` with context guards).
   - On decline: increment `jesus_decline_count`. When it reaches 2 within the recent cadence window, set `declined_jesus_until_turn = assistant_turn_index + 6` (or configured window) and reset `jesus_decline_count`.
   - Persist to conversation via `update_conversation(conversation_id, user_id, metadata=...)`.

2. __Track `last_jesus_invite_turn` consistently__:
   - Whenever we append a Jesus-centered invite (or when orchestrator plan indicates we asked one), update `last_jesus_invite_turn = assistant_turn_index` in conversation metadata.

3. __Use persisted history for turn counts__:
   - If the request `message_history` is partial, derive `assistant_turn_index` from DB messages for the `conversation_id` to avoid resets across requests.

4. __Remove undefined locals from legacy path__:
   - Replace `locals().get("declined_jesus_until_turn_local", None)` with the actual computed value or remove from legacy block and rely on the orchestrator/centralized update path after computing cooldowns.

5. __Add granular test logging__:
   - During the test run, log `assistant_turn_index`, `last_jesus_invite_turn`, `jesus_decline_count`, and the final `declined_jesus_until_turn` each turn to validate sequencing.

### Short-term validation plan

- Implement step (1)–(2), run `backend/tests/test_integration_chat_api.py::test_chat_cadence_decline_cooldown`.
- If still failing, add explicit DB refresh `SessionLocal.remove()` between turns in the test (as a diagnostic) to eliminate any remaining session caching ambiguity.
- Add a unit test that posts synthetic history ensuring the decline patterns are recognized and `declined_jesus_until_turn` is computed deterministically.

### Files to inspect/update

- `backend/app/services/chat.py` — implement decline detection, turn counting from DB, and metadata persistence.
- `backend/app/orchestration/metadata.py` — ensure normalization preserves `declined_jesus_until_turn` and include counters if added (e.g., `jesus_decline_count`).
- `backend/app/tests/...` — consider adding direct unit tests for cadence decline cooldown independent of the integration path.

### Known non-blockers already addressed

- Session staleness: mitigated via `SessionLocal.remove()` after session close in write paths.
- Config parity between orchestrator and fallback ensured in `ChatService.__init__()` (model, temperature, penalties unified).

---
- Intake state model: [`backend/app/policies/intake.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/policies/intake.py)
- Safety stubs: [`backend/app/safety/guard.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/safety/guard.py)
- Retrieval stubs: [`backend/app/rag/retrieve.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/rag/retrieve.py)
- Metadata normalizer: [`backend/app/orchestration/metadata.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/metadata.py)
- `ChatService.add_message()` — DB persistence for messages
- `ChatService.update_conversation()` — stores conversation-level metadata
- `key_to_pretty()` — converts book keys to display names
- Frontend `Chat` component — request/response flow and Debug Panel

Open files quickly:
- [Generate response](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/services/chat.py)
- [Chat component](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/frontend/components/chat/chat.tsx)
- [Marriage rules JSON](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/pastoral/rules/marriage.json)

---

## 17) Recent Changes — 2025-08-12

- __Unified settings in ChatService__: `ChatService.__init__()` now reads `MODEL_NAME`, `TEMPERATURE`, `MAX_TOKENS`, `PRESENCE_PENALTY`, and `FREQUENCY_PENALTY` from [`backend/app/config.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/config.py) via `get_settings()`. The fallback HTTP path and orchestrator now share the same model/temperature.
- __Structured planner settings__: Orchestrator already uses `MODEL_NAME`, `TEMPERATURE`, and `MAX_PLANNER_RETRIES` in [`backend/app/orchestration/llm.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/llm.py). It validates JSON against `ResponsePlan` and performs semantic validation with retries.
- __Config observability__: On startup, `ChatService` logs a single line summarizing applied config (model, temperature, tokens, penalties) to verify environment wiring.
- __Docs updated__: This file now documents the unified configuration variables and testing steps to verify orchestration gating and fallback behavior.

## 18) Recent Changes — 2025-08-13

- __Safety triage short-circuit__: Orchestrator now returns a compassionate triage response immediately when safety is flagged. See [`backend/app/orchestration/triage.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/triage.py). Metadata includes `gate_reason: "safety_triage"`, `safety_flag_this_turn: true`, and disables resources and Jesus invite for that turn.
- __Intake gating via IntakeState__: Intake completion is derived from conversation metadata using [`backend/app/policies/intake.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/policies/intake.py). Books are allowed only when intake is complete and `topic_confidence >= 0.6`.
- __Jesus-invite cadence persistence__: A cadence window of 3 assistant turns is enforced using conversation metadata `last_jesus_invite_turn`. `ChatService` persists this after an invite; cadence logic is applied in [`backend/app/orchestration/graph.py`](file:///c:/Users/ryans/ASW%20Dropbox/Ryan%20Sobey/Sheperd/backend/app/orchestration/graph.py).
- __Metadata observability__: `gate_reason` now conveys `ok`, `intake_incomplete`, `low_confidence`, or `safety_triage`. `topic` and `topic_confidence` are always set by the orchestrator.
