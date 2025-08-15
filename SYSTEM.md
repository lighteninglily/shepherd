# 2025-08-15 Stability & Persistence Updates (10:18 SGT)

## Summary

- __Intake completion persistence fixed__ in [`backend/app/services/chat.py`](backend/app/services/chat.py):
  - Explicitly mark JSON changes using `flag_modified` on `Conversation.metadata_json` in both the main persistence block and the post-commit verification path to guarantee DB writes for `intake.completed`, `issue_named`, `safety_cleared`, `goal_captured`, and `prayer_consent_known`.
  - Verified by `pytest` passing: [`backend/tests/test_intake_phase.py::test_wrapup_affirmation_flips_intake_complete`](backend/tests/test_intake_phase.py).

- __Frontend dev stability on Windows + Dropbox__:
  - Next.js dist moved to `.next-dev` via [`frontend/next.config.mjs`](frontend/next.config.mjs) to avoid stale `.next/` collisions.
  - Robust dev runner: [`frontend/scripts/dev.ps1`](frontend/scripts/dev.ps1) cleans `.next/` and `.next-dev/`, enables polling-based watchers (`CHOKIDAR_USEPOLLING`, `WATCHPACK_POLLING`), ensures `.env.local`, and starts Next.
  - Scripts updated in [`frontend/package.json`](frontend/package.json): `dev` now routes through `scripts/dev.ps1`; `dev:raw` runs `next dev` directly.
  - Ignore updates: [`frontend/.dropboxignore`](frontend/.dropboxignore) and root [`.gitignore`](.gitignore) include `.next-dev/` to prevent syncing build artifacts.
  - Repair workflow: [`scripts/repair_frontend.ps1`](scripts/repair_frontend.ps1) also removes `.next/` and `.next-dev/` before reinstalling.

## Notes

- __Frontend API base__: Chat UI reads `NEXT_PUBLIC_API_BASE_URL` (fallback `http://127.0.0.1:8000`) in [`frontend/components/chat/chat.tsx`](frontend/components/chat/chat.tsx) and calls `${API_BASE}/api/v1/chat`.
  - The dev runner currently seeds `.env.local` with `NEXT_PUBLIC_API_URL`. Local fallback keeps dev working; consider aligning to `NEXT_PUBLIC_API_BASE_URL` for consistency.

## Local run quickstart

- __Backend__: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- __Frontend__: from `frontend/`, run `npm run dev` (uses `scripts/dev.ps1`).

## Key references

- Chat service (persistence, gating, normalization): [`backend/app/services/chat.py`](backend/app/services/chat.py)
- Intake test: [`backend/tests/test_intake_phase.py`](backend/tests/test_intake_phase.py)
- Next config (distDir): [`frontend/next.config.mjs`](frontend/next.config.mjs)
- Dev runner: [`frontend/scripts/dev.ps1`](frontend/scripts/dev.ps1)
- NPM scripts: [`frontend/package.json`](frontend/package.json)
- Dropbox ignore: [`frontend/.dropboxignore`](frontend/.dropboxignore)
- Repo ignore: [`.gitignore`](.gitignore)
- Frontend chat component: [`frontend/components/chat/chat.tsx`](frontend/components/chat/chat.tsx)

# 2025-08-14 Conversation System — Consolidated Design

# 2025-08-14 Audit Validation & Test Results (15:01 SGT)

This section summarizes the validation work completed today and links to the exact source files.

## What was validated

- **Integration tests (orchestrated path)**: [`backend/tests/test_integration_chat_api.py`](backend/tests/test_integration_chat_api.py)
  - Uses `httpx.AsyncClient` + `ASGITransport` against the FastAPI app.
  - Stubs `Orchestrator` for deterministic invites; forces `ORCHESTRATION_ENABLED=True`.
  - Verifies canonical metadata keys and cooldown persistence in DB.
- **Result**: 2 tests passed in ~1.5s (one benign DeprecationWarning unrelated to chat logic).

## Backend changes and parity

- **Legacy path parity & hygiene** in [`backend/app/services/chat.py`](backend/app/services/chat.py):
  - Always initialize `book_attributions` and `scrubbed_books` across all code paths.
  - Enforce single canonical `gate_reason` values; remove duplicate legacy keys (e.g., `conversation_phase`).
  - Append neutral line when scrubbing under gating; log `books_gate` with phase, reason, scrubbed count.
  - Add `phase_gate` logging for intake/advice transitions.
  - Inject intake wrap‑up prompt when `advice_intent=True` but intake not complete; detect confirmation and persist intake completion using DB metadata as source of truth.
  - Persist cadence fields: `last_jesus_invite_turn`, `declined_jesus_until_turn`; normalize metadata via `normalize_meta()`.
- **Orchestrated path**:
  - Unified invite gating via `invite_gate()` in [`backend/app/orchestration/graph.py`](backend/app/orchestration/graph.py), producing canonical `allow_jesus` and `cadence_reason`.
  - Resource gating + scrubbing via `scrub_books_if_gated()` in [`backend/app/orchestration/scrubber.py`](backend/app/orchestration/scrubber.py); append neutral line when scrubbed.
  - Canonical metadata normalization via `normalize_meta()` in [`backend/app/orchestration/metadata.py`](backend/app/orchestration/metadata.py).
- **App startup/shutdown hygiene** in [`backend/app/main.py`](backend/app/main.py): lifespan cleanup (`SessionLocal.remove()`, `engine.dispose()`), log file encoding UTF‑8.

## Frontend + UX notes

- Chat component [`frontend/components/chat/chat.tsx`](frontend/components/chat/chat.tsx) uses `NEXT_PUBLIC_API_BASE_URL` (fallback `http://127.0.0.1:8000`).
- Phase‑1 friend‑like style enforced from backend (short empathic replies, one open question, optional scripture), with assistant metadata `{ style_guide: 'friend_v1', asked_question: true }`.

## Manual validation tooling

- Scripts (PowerShell) under `scripts/`:
  - `run_manual_scenario.ps1` — run 7‑turn scenario, write transcript.
  - `print_latest_transcript.ps1` — print latest transcript.
  - `scan_transcript.ps1` — scan transcripts for placeholders like `[resource removed]`.
- Expected: when `allow_books=false`, transcripts contain placeholder and `metadata.scrubbed_books` lists scrubbed titles.

## Canonical references

- Invite gating: [`backend/app/orchestration/graph.py`](backend/app/orchestration/graph.py)
- Metadata normalization: [`backend/app/orchestration/metadata.py`](backend/app/orchestration/metadata.py)
- Scrubber: [`backend/app/orchestration/scrubber.py`](backend/app/orchestration/scrubber.py)
- Chat service integration: [`backend/app/services/chat.py`](backend/app/services/chat.py)
- Integration tests: [`backend/tests/test_integration_chat_api.py`](backend/tests/test_integration_chat_api.py)

---

This document consolidates the current conversation system behavior across gating, scrubbing, metadata normalization, response generation, and frontend mappings. All references link to the exact source files to ensure precise review.


## Architecture Overview

- **Source of truth:** Conversation state and gating live in DB metadata (not message history).
- **Paths:** Orchestrated path (planner-driven) with legacy fallback. Both share unified gating and normalization.
- **Key modules:**
  - Orchestrator and invite gating: [`backend/app/orchestration/graph.py`](backend/app/orchestration/graph.py)
  - Metadata normalization: [`backend/app/orchestration/metadata.py`](backend/app/orchestration/metadata.py)
  - Scrubber: [`backend/app/orchestration/scrubber.py`](backend/app/orchestration/scrubber.py)
  - Chat service integration: [`backend/app/services/chat.py`](backend/app/services/chat.py)


## Jesus‑Invite Gating (invite_gate)

Function location: [`backend/app/orchestration/graph.py`](backend/app/orchestration/graph.py)

Purpose: Provide a single, canonical decision for whether a Jesus invite may appear this turn. Returns `(allow_jesus: bool, cadence_reason: str)`.

Inputs (canonical):
- `phase` (e.g., `intake`, `advice`)
- `advice_intent` (bool)
- `intake_completed` (bool)
- `safety_flag` (bool)
- `assistant_turn_index` (int)
- `last_jesus_invite_turn` (int | None)
- `declined_jesus_until_turn` (int | None)
- `last_turn_had_jesus` (bool)
- `prayer_consent_known` (bool)
- `prayer_consent` (bool)
- `jesus_invite_allowed_from_plan` (bool)

Decision order (short‑circuit):
1. **Hard blocks:** `safety` → `phase_intake` → `not_advice` → `intake`.
2. **Consent:** explicit “no” → `plan_blocked`; unknown consent does not block.
3. **Duplication:** `first_turn` → `last_turn_had_jesus`.
4. **Cadence window:** before first invite requires ≥ 4 assistant turns; subsequent invites require ≥ 3 turns gap → `cadence_window`.
5. **Decline cooldown:** active cooldown → `cooldown_declined`.
6. **Planner advisory:** if the plan disallows → `plan_blocked`.
7. **OK:** invite allowed → `ok`.

Canonical reasons: `safety | phase_intake | not_advice | intake | first_turn | last_turn_had_jesus | cadence_window | cooldown_declined | plan_blocked | no_consent | ok`.

Result usage:
- `allow_jesus` persisted as `metadata.allow_jesus`.
- `cadence_reason` persisted as `metadata.cadence_reason`.


## Book/Resource Gating and Scrubber

Function location: [`backend/app/orchestration/scrubber.py`](backend/app/orchestration/scrubber.py)

- `scrub_books_if_gated(text, allow_books) -> (clean_text, scrubbed_titles)`.
- When `allow_books=False`, the scrubber removes:
  - Known titles/authors (loaded from `backend/app/pastoral/rules/marriage.json`).
  - Generic resource patterns: quoted titles, explicit resource words, URLs, and "by <Name>" mentions.
- Placeholder: all removed content replaced with `"[resource removed]"`.
- Metadata: return value `scrubbed_titles` is stored in `metadata.scrubbed_books`.

Allow‑books policy (orchestrated path):
- Typically allowed when `plan.phase == 'advice'`, intake is completed, topic confidence is adequate, and no safety flag is raised. Final allow flag is persisted as `metadata.allow_books`. When disallowed and the plan includes candidate books, `scrubbed_books` captures them.


## Metadata Normalization

Function location: [`backend/app/orchestration/metadata.py`](backend/app/orchestration/metadata.py)

- `normalize_meta(meta) -> meta`: Ensures keys are present with defaults and coerces types consistently across orchestrated and legacy paths.
- Canonical keys include (non‑exhaustive):
  - `phase`, `advice_intent`, `safety_flag_this_turn`, `gate_reason`
  - `book_selection_reason`, `book_attributions`, `scrubbed_books`
  - `asked_question`, `rooted_in_jesus_emphasis`, `jesus_invite_variant`, `style_guide`, `faith_branch`
  - `topic`, `topic_confidence`
  - `path`, `allow_books`, `allow_jesus`, `cadence_reason`, `planner_retries`, `fallback_reason`, `declined_jesus_until_turn`
- Defaults reflect friend‑like style and observability needs,
  e.g., `style_guide='friend_v1'`, `asked_question=True`, booleans default safe.


## Chat Service Integration

Location: [`backend/app/services/chat.py`](backend/app/services/chat.py)

High‑level flow (orchestrated, with legacy fallback):
1. Compute DB‑derived turn indexes and last assistant text (`_get_turn_indexes`).
2. Build history for the model (`_get_history_for_model`).
3. Orchestrator `run()` plans response (structured), performs safety checks, and derives topic/confidence.
4. Apply **invite gating** (`invite_gate`) to produce `allow_jesus` and `cadence_reason`.
5. Determine `allow_books` defensively (phase, intake, topic confidence, safety).
6. If gated, **scrub** assistant content using `scrub_books_if_gated(…, allow_books=False)`; collect `scrubbed_books`.
7. Compose metadata via orchestrator and then **normalize** using `normalize_meta()` before DB persistence.
8. Persist both assistant message and conversation metadata to DB.

Style & UX conventions:
- Phase‑1 “friend‑like” replies (`style_guide='friend_v1'`), short empathic response, one open question, optional scripture.
- Persist `asked_question=True` on assistant turns to help the UI.


## Frontend Mappings and Env Vars

- Chat component: [`frontend/components/chat/chat.tsx`](frontend/components/chat/chat.tsx)
  - Uses `NEXT_PUBLIC_API_BASE_URL` for API calls (fallback: `http://127.0.0.1:8000`).
- Badges / Debug panel expect canonical metadata fields:
  - **Phase** → `metadata.phase`
  - **Resources (Books)** → `metadata.allow_books` (tooltip references `gate_reason`; show `scrubbed_books.length` when present)
  - **Jesus** → `metadata.allow_jesus` + `metadata.cadence_reason`
- Debug panel toggle: `NEXT_PUBLIC_DEBUG_PANEL`.


## Manual Validation (PowerShell)

Scripts location: `scripts/`
- `run_manual_scenario.ps1` — runs a 7‑turn scenario and writes a UTF‑8 transcript under `scripts/artifacts/`.
- `print_latest_transcript.ps1` — prints the latest transcript.
- `scan_transcript.ps1` — scans transcripts for a literal token (regex‑escaped), e.g., to find scrubber placeholders.

Usage examples (from repo root, PowerShell):
```powershell
# Run the scenario
./scripts/run_manual_scenario.ps1

# Print latest transcript
./scripts/print_latest_transcript.ps1

# Verify scrubber placeholder occurred when books are gated
./scripts/scan_transcript.ps1 -Needle "\[resource removed\]"
```
Expected outcomes:
- When `allow_books=False`, transcripts show `"[resource removed]"` where book/resource mentions were scrubbed.
- Metadata on assistant turns shows `allow_jesus`, `cadence_reason`, `allow_books`, `scrubbed_books` as applicable.


## Observability & Logging

- Planner retries and fallback reasons recorded: `planner_retries`, `fallback_reason`.
- Invite cadence/audit: `allow_jesus`, `cadence_reason`, `declined_jesus_until_turn`.
- Normalization ensures stable shapes for FE and telemetry across code paths.


## Notes and Improvement Areas

- Better recognition of nuanced scenarios (e.g., faith difference vs. emotional disconnect) can adjust:
  - Gating thresholds (cadence windows and cooldowns) conservatively.
  - Advice composition to include both emotional safety and spiritual direction.
- Consider capturing explicit consent cues earlier to prevent premature invites.
- Expand scrubber resource patterns only if false positives remain low; keep placeholder stable.
