# Shepherd AI — Plan

## 2025-08-12 — Unified Orchestration, Gating, Cadence, and Validation Overhaul

### A. Unified model setup (.env + settings)
- Configure `.env`:
  - `MODEL_NAME=gpt-5`
  - `ORCHESTRATION_ENABLED=true`
  - `TEMPERATURE=0.3`
  - `MAX_PLANNER_RETRIES=2`
- Backend
  - Update `backend/app/core/settings.py` (or equivalent settings module) to read these env vars and expose them via `get_settings()`.
  - Ensure `ChatService` and Orchestrator consume `MODEL_NAME`, `TEMPERATURE`, and `MAX_PLANNER_RETRIES`.

### B. Structured outputs with retries (planner)
- `backend/app/orchestration/llm.py`
  - Call `MODEL_NAME` with JSON mode using `ResponsePlan` schema (`backend/app/policies/response_plan.py`).
  - Retry up to `MAX_PLANNER_RETRIES` on JSON parse/validation errors; surface the last error message.
  - Return retry count for observability (`planner_retries`).

### C. Topic classifier with confidence
- `backend/app/orchestration/classify.py`
  - Implement `classify(text) -> {topic, confidence: float}` with lightweight prompt/zero‑shot.
  - Run before planning; store on the turn (metadata) and pass into Orchestrator for gating.

### D. Topic→book weights (replace keyword mapping)
- Feature flag: `LEGACY_KEYWORDS=false` (default off)
- Use `backend/pastoral/rules/marriage.json` topic→book weights to select attributions with a repetition penalty.
- Remove active `keywords_map` usage; keep code path behind the legacy flag.

### E. Gating rules (books/resources)
- Allow books only if ALL are true:
  - `phase == "advice"`
  - `intake_completed == true`
  - `safety.flag == false`
  - `topic_confidence >= 0.6`
- Record `gate_reason` in metadata.

### F. Intake checklist and persistence
- `backend/app/policies/intake.py`: booleans
  - `issue_named`, `safety_cleared`, `goal_captured`, `prayer_consent_known`
- Flip `conversation.metadata.intake_completed = true` only when all booleans are true.
- Persist checklist on each turn; avoid re‑asking once complete.

### G. Plan validation before compose
- `backend/app/policies/validators.py` (server‑side semantic validator)
  - Enforce: 3–5 steps; each step has `how_to_say_it`; `time_estimate_min >= 5`;
    at least one `trigger_if_then`; non‑trivial `truth_anchor`.
- If invalid: perform one structured repair retry.
- If still invalid: fallback to safe short reply and set `metadata.fallback_reason = "plan_validation_failed"`.

### H. Jesus‑invite cadence with memory
- Track in conversation meta:
  - `last_invite_turn`, `declined_jesus_until_turn`
- Allow invite only if:
  - not safety, `turn_index > 0`, `phase != intake`, frequency gate passes, not in decline cooldown, and `plan.jesus_invite_allowed == true`.
- Record `cadence_reason ∈ {first_turn, safety, intake, frequency, cooldown_declined, ok}`.

### I. Safety triage route
- `backend/app/orchestration/triage.py`:
  - Compose triage replies: mirror → stabilize/boundaries → practical next step → 1 gentle question.
  - If `safety.flag == true`, short‑circuit to triage (no books, no Jesus invite).

### J. Retrieval and citations
- `backend/app/rag/retrieve.py` returns tuples: `(book_key, book_pretty, section, snippet, actionability_score)`.
- In compose(), append “Sources: …” only when retrieved chunks exist. Never fabricate attributions.

### K. Normalized metadata across paths
- `backend/app/orchestration/metadata.py::normalize_meta()` always includes:
  - `path`, `phase`, `topic`, `topic_confidence`, `allow_books`, `allow_jesus`, `cadence_reason`,
    `rooted_in_jesus_emphasis`, `book_attributions`, `gate_reason`, `planner_retries`, `fallback_reason`.
- Ensure both orchestrated and legacy paths call the normalizer before persisting.

### L. Debug Panel upgrade (frontend)
- `frontend/components/chat/chat.tsx`
  - Show chips/rows for: `topic`, `topic_confidence`, `allow_books`, `allow_jesus`, `cadence_reason`, `path`, `planner_retries`, `fallback_reason`, plus existing badges.

### M. Fallback policy
- If JSON parse fails after retries → safe short reply (no books/invite), `fallback_reason = "json_parse"`.
- If plan validation fails → same, `fallback_reason = "plan_validation_failed"`.

### N. History trimming and state hygiene
- Limit `message_history` to last 8 turns (+ system).
- Persist intake facts in conversation meta (not long context).

### O. Tests (prevent regressions)
- `tests/test_cadence.py`: first‑turn/safety/frequency/cooldown gates.
- `tests/test_intake.py`: checklist flips only when all true.
- `tests/test_plan_validator.py`: rejects/accepts properly.
- `tests/test_safety.py`: triage path; no books/invite.
- `tests/test_topic_confidence.py`: <0.6 gates books; ≥0.6 allows (with other gates).

### P. Smoke cases
- (A) “We are arguing a lot lately.” → no Jesus invite on turn 1; plan with steps/time/scripts; books gated by intake+confidence.
- (B) “I feel unsafe; he hit me last night.” → triage path; no books/invite.
- (C) “Porn relapse again; we’re in separate rooms.” → betrayal/porn plan; cadence respected.

## 2025-08-11 — Full System Upgrade (Statefulness, RAG, Scripture fidelity, Safety, Eval)

### A. Stateful conversations (backend + frontend)
- Backend
  - Update `backend/app/api/v1/routers/chat.py` to accept optional `conversation_id`, persist user messages, and load DB-backed history via `ChatService.get_conversation_history()`.
  - Ensure `ChatService.generate_response()` is called with `message_history` and continues to persist assistant responses.
- Frontend
  - Persist and send `conversation_id` with every request; start a new one when absent.
- Test
  - Manual: Start new convo, send 3 turns, verify continuity and single assistant message per turn.
  - DB: Confirm `conversations` row created once and `messages` grows by 2 per turn (user + assistant).

### B. Scripture fidelity (ground verses from DB)
- Backend
  - Populate `bible_verses` table from a licensed/public dataset (NIV or chosen translation) via an admin/import script.
  - Modify `ChatService.generate_response()` contract: model outputs a verse reference; server fetches exact verse text from `bible_verses` and renders it.
- Test
  - Unit: parsing of references (single verse, ranges) and fallback handling.
  - Manual: Responses include one correct verse text and citation.

### C. RAG (retrieval‑augmented generation)
- Ingestion
  - Create `backend/scripts/ingest.py` to chunk pastoral docs and marriage resources; embed with OpenAI `text-embedding-3-large`; store in FAISS (or pgvector later).
- Retrieval
  - Add retrieval step in `ChatService.generate_response()` to inject top‑k relevant chunks with provenance.
- Test
  - Manual: Topic prompts surface cited snippets; model references retrieved content.
  - Sanity: Disable retrieval flag -> behavior reverts to baseline.

### D. Safety and moderation
- Backend
  - Add pre/post moderation using OpenAI `omni-moderation-latest`; adapt tone or decline for flagged categories; crisis flow triggers human escalation language only.
- Test
  - Manual: Submit risky content; verify safe response and logged flags in message metadata.

### E. Structured outputs
- Backend
  - Request JSON schema fields: `reflection`, `scripture_ref`, `action_step`, `follow_up_question`, `risk_flags`.
  - Validate server-side; render into frontend; store fields in `messages.metadata`.
- Frontend
  - Display the structured fields; enforce “exactly one verse + one action step”.
- Test
  - Unit: JSON parsing/validation; Manual: UI renders structured content cleanly.

### F. Config flags wiring
- Backend
  - Enforce `PASTORAL_MODE_STRICT` and prayer forwarding flags from `backend/app/config.py` within prompt assembly and flow control.
- Test
  - Toggle flags in `.env`; verify prompt length/behavior and optional webhook posting change accordingly.

### G. Evaluation harness
- Add offline evaluation using RAGAS and DeepEval with a small, consented, anonymized test set across common marriage scenarios.
- Metrics: faithfulness, answer relevancy, scripture accuracy, safety.
- Test
  - Baseline run committed; future changes compared against baseline to catch regressions.

### H. Intent classification improvements
- Replace brittle keyword checks with a lightweight classifier (few‑shot or zero‑shot) storing `last_intent` in `conversations.metadata`.
- Centralize system prompt composition to reduce drift.
- Test
  - Unit/manual: Tagging accuracy on a small labeled set; reduced prompt diffs per change.

### I. Observability
- Persist token counts, latency, moderation outcomes, retrieval hits into `messages.metadata`.
- Optional: BigQuery export behind feature flag.
- Test
-  Logs/DB show metrics for each turn; dashboards can be built later.

### J. Frontend updates
- Ensure API base URL env var is consistent.
- Use structured fields in rendering; preserve `conversation_id` across refresh.
- Test
  - Manual: New UI shows one verse + one action; conversation continuity intact.

---

## 2025-08-08 — Pastoral intake, training strategy, and UI redesign (Top Priority)

- "Act like a pastor" before advice: gather context with clarifying questions and empathy.
- Define/train Shepherd’s unique pastoral voice; guardrails for safety and theology.
- Refactor UX/UI to a strong, inviting, “manly leader” visual direction.

### A. Pastoral context‑gathering flow (clarifying before advising)
- Behavior
  - Always respond first with “Let me understand this better” and ask focused questions (e.g., marital issues: gender, duration of marriage, current state, safety concerns, counseling history, faith background) before offering any guidance.
  - After sufficient context, provide biblically grounded, practical steps, and suggest professional help when appropriate.
- Backend changes
  - Update pastoral system instruction and topic‑aware clarifying prompts in `backend/app/services/chat.py` → `ChatService.generate_response()`.
  - Add a lightweight “intake mode” heuristic in the prompt for sensitive topics (marriage, sexual integrity, finances, crisis, grief, parenting) to prioritize questions before advice.
  - Optional: add configurable flags in `.env` (e.g., `PASTORAL_MODE_STRICT=true`) read in `backend/app/config.py` and used in `ChatService`.
  - Future: persist “intake complete” state per conversation (DB) to avoid re‑asking once context is gathered.
- Frontend changes
  - Refine `frontend/components/chat/chat.tsx` to visually group context questions and user answers.
  - Show progress chips (e.g., “Context 3/5”), allow quick‑reply buttons for common answers, and display a subtle “Why I’m asking” tooltip.

### B. Training strategy (near‑term to advanced)
- Phase 1: Prompt and policy tuning (immediate)
  - Enrich the system prompt in `ChatService.generate_response()` with Shepherd’s voice: pastoral, firm yet warm, grounded in Scripture, never medical/clinical advice, escalate to human pastor for crises.
  - Add topic‑specific clarifying templates (e.g., marriage, addiction, crisis).
- Phase 2: RAG (retrieval‑augmented generation) (short‑term)
  - Content: church doctrinal statements, counseling guidelines, sermon outlines, small‑group resources, curated Scripture passages and commentaries.
  - Ingestion: build a simple loader script (`backend/scripts/ingest.py`) to chunk, embed (OpenAI embeddings), and store in a lightweight vector store (e.g., SQLite + pgvector later, or a local FAISS index).
  - Retrieval: when a topic is detected, fetch top‑k passages and citations; inject into context for grounded answers.
  - Safety: filter sources; tag each chunk with provenance; surface citations in the response.
- Phase 3: Evaluation harness (short‑term)
  - Golden prompts and expected behaviors; run regular evals (accuracy, tone, safety) with a small scoring script.
- Phase 4: Fine‑tuning (later)
  - Only after we have a curated dataset of Q&A/intakes. Scope and cost review required; keep the base model updated.

### C. Frontend redesign — “manly leader” aesthetic
- Direction
  - Palette: deep navy/ink, slate/graphite neutrals, subtle warm gold accents; minimal gradients; high contrast and clarity.
  - Typography: strong sans (e.g., Inter/Manrope) with measured weight; ample whitespace; calm motion.
  - Imagery: abstract texture or subtle geometric patterns; avoid literal clichés; dark mode as default.
- Work items
  - `frontend/app/page.tsx`: restructure layout (hero heading, description, primary chat entry), tighten spacing.
  - `frontend/components/chat/chat.tsx`: chat bubbles with clear author identity, timestamp row, input bar with actions (send, quick replies), progress chips for context flow, loading states.
  - `frontend/components/ui/*`: align buttons, cards, tabs to the new design tokens in Tailwind (extend theme) and update CSS variables; never inline styles.
  - Accessibility: focus states, color contrast, semantic roles; performance: defer non‑critical assets.

### D. Safety, privacy, and guardrails
- Do not store sensitive personal data beyond session unless consented; show privacy notice in the UI.
- Crisis handling: if harm risk is detected, avoid advice and escalate to human pastor with appropriate language; never give medical/legal advice.
- Log redaction for PII in backend; configurable retention.

### E. Milestones
1) Working intake behavior with prompt tuning (1–2 days)
2) UI redesign pass (2–3 days)
3) RAG v1 (ingest + retrieve, citations) (3–5 days)
4) Evaluation harness v1 (1 day)
5) Optional: fine‑tuning scoping (document only) (0.5 day)

---

## Backlog / Next Level (post‑MVP polish)
- Auth + profiles (e.g., Clerk) and preference‑driven tone/denomination settings.
- Journal and Scripture study saved history with search and tags.
- Analytics (anonymous) for topics, helpfulness, drop‑off points.
- Admin tools to review content sources, redactions, and model updates.
