# Shepherd AI — Plan

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
