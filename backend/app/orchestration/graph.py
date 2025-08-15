from typing import Any, Dict, List
from dataclasses import dataclass
import logging

from .llm import llm_structured
from .classify import classify
from ..policies.response_plan import ResponsePlan
from ..policies.validator import validate_response_plan
from ..rag.retrieve import retrieve_snippets
from ..rag.insights import get_insight_clauses
from ..safety.guard import pre_moderate, post_moderate
from .triage import triage_route
from .scrubber import scrub_books_if_gated

logger = logging.getLogger(__name__)


@dataclass
class TurnState:
    conversation_id: str
    turn_index: int
    intake_completed: bool
    last_turn_had_jesus: bool
    last_books: List[str]
    user_message: str
    history_for_model: List[Dict[str, Any]]  # system+history
    # Persisted cadence memory: last assistant turn index where a Jesus invite was used
    last_jesus_invite_turn: int | None = None
    # Cooldown gating after declines/ignores: suppress invites until this assistant turn index (exclusive)
    declined_jesus_until_turn: int | None = None
    # Consent memory
    prayer_consent_known: bool = False
    prayer_consent: bool = False


class Orchestrator:
    def run(self, st: TurnState) -> Dict[str, Any]:
        # 1) safety pre-scan
        safety = pre_moderate(st.user_message)
        # 1a) safety triage short-circuit
        if safety.flag:
            triaged = triage_route(st.user_message, safety)
            # triage_route returns a {content, metadata}
            return triaged
        # 2) lightweight topic classifier (best-effort; does not block planning)
        cls_topic = None
        cls_conf = 0.0
        try:
            cls = classify(st.user_message)
            cls_topic = (cls.get("topic") or None)
            try:
                cls_conf = float(cls.get("confidence", 0.0))
            except Exception:
                cls_conf = 0.0
        except Exception:
            # classifier is optional; continue
            pass

        # 3) plan via Structured Outputs (validate with a single retry)
        retries = 0
        plan: ResponsePlan = llm_structured(
            history=st.history_for_model,
            schema=ResponsePlan,
        )
        ok, errs = validate_response_plan(plan)
        if not ok:
            # One repair retry attempt
            retries = 1
            plan = llm_structured(
                history=st.history_for_model,
                schema=ResponsePlan,
            )
            ok2, errs2 = validate_response_plan(plan)
            if not ok2:
                # propagate for upstream fallback handling
                raise ValueError(f"plan_validation_failed: {errs2}")
        # Effective topic + confidence (prefer classifier when higher or when plan is 'other')
        topic_eff = plan.topic if plan.topic != "other" else (cls_topic or plan.topic)
        conf_eff = max(getattr(plan, "topic_confidence", 0.0) or 0.0, cls_conf or 0.0)

        # 4) Unified Jesus-invite gate
        cooldown_until = st.declined_jesus_until_turn if isinstance(getattr(st, "declined_jesus_until_turn", None), int) else None
        allow_jesus, cadence_reason = invite_gate(
            phase=plan.phase,
            advice_intent=(plan.phase == "advice"),
            intake_completed=bool(st.intake_completed),
            safety_flag=bool(getattr(plan, "safety", None) and plan.safety.flag),
            assistant_turn_index=int(st.turn_index),
            last_jesus_invite_turn=st.last_jesus_invite_turn if isinstance(getattr(st, "last_jesus_invite_turn", None), int) else None,
            declined_jesus_until_turn=cooldown_until,
            last_turn_had_jesus=bool(getattr(st, "last_turn_had_jesus", False)),
            prayer_consent_known=bool(getattr(st, "prayer_consent_known", False)),
            prayer_consent=bool(getattr(st, "prayer_consent", False)),
            jesus_invite_allowed_from_plan=bool(getattr(plan, "jesus_invite_allowed", False)),
        )

        # 5) book gating (topic_confidence + intake gate + defensive safety)
        allow_books = (
            plan.phase == "advice"
            and st.intake_completed
            and (not safety.flag)
            and conf_eff >= 0.6
        )

        # Determine gate reason for observability
        gate_reason = "ok"
        if plan.phase == "advice" and not st.intake_completed:
            gate_reason = "intake_incomplete"
        elif conf_eff < 0.6:
            gate_reason = "low_confidence"

        # 6) Retrieval
        # 6a) Always fetch insight clauses (title-free, paraphrased) for invisible coaching
        insight_clauses = []
        try:
            insight_clauses = get_insight_clauses(topic_eff, limit=6)
        except Exception:
            insight_clauses = []
        used_insights = bool(insight_clauses)
        # 6b) Only fetch explicit attributions when books are allowed
        ctx = retrieve_snippets(topic_eff) if allow_books else []
        # Populate advisory fields on plan for downstream usage/observability
        try:
            setattr(plan, "insight_clauses", insight_clauses)
        except Exception:
            pass
        try:
            if ctx:
                setattr(plan, "attributions", [
                    {
                        "key": c.get("book_key", "?"),
                        "pretty": c.get("book_pretty", "?"),
                        "author": c.get("author", "?")
                    }
                    for c in ctx
                ])
        except Exception:
            pass

        # 6a) Phase gate observability (DB-derived intake_completed passed in TurnState)
        try:
            logger.info(
                "phase_gate",
                extra={
                    "cid": st.conversation_id,
                    "phase": plan.phase,
                    "advice_intent": (plan.phase == "advice"),
                    "intake_complete": bool(st.intake_completed),
                    "topic": topic_eff,
                    "topic_conf": conf_eff,
                },
            )
        except Exception:
            pass

        # 7) Compose final message
        content = compose(plan, ctx, allow_jesus, insight_clauses, allow_books)

        # 8) post moderation
        content = post_moderate(content)

        # 8a) scrub books if gated
        scrubbed_list: List[str] = []
        try:
            content, scrubbed_list = scrub_books_if_gated(content, allow_books)
        except Exception:
            scrubbed_list = []
        # If gated and scrubbing occurred, append a neutral line instead of any recommendation
        if (not allow_books) and scrubbed_list:
            try:
                if content and not content.endswith(('\n', ' ', '.')):
                    content += "\n"
            except Exception:
                pass
            content += "Once we’ve finished intake and I’m confident on the topic, I can suggest resources."

        # 9) metadata (include effective topic and confidence)
        md = derive_metadata(plan, allow_books, allow_jesus, ctx, used_insights)
        try:
            # Preserve any existing scrubs and append new ones
            prior = md.get("scrubbed_books") or []
            if scrubbed_list:
                md["scrubbed_books"] = list(prior) + [s for s in scrubbed_list if s not in prior]
        except Exception:
            pass
        try:
            logger.info(
                "books_gate",
                extra={
                    "cid": st.conversation_id,
                    "path": "orchestrated",
                    "allow": bool(allow_books),
                    "reason": gate_reason,
                    "scrubbed": len(scrubbed_list),
                    "used_insights": used_insights,
                    "phase": plan.phase,
                    "topic": topic_eff,
                    "topic_conf": conf_eff,
                },
            )
        except Exception:
            pass
        md["topic"] = topic_eff
        md["topic_confidence"] = conf_eff
        md["gate_reason"] = gate_reason
        md["path"] = "orchestrated"
        md["allow_books"] = bool(allow_books)
        md["allow_jesus"] = bool(allow_jesus)
        md["cadence_reason"] = cadence_reason
        md["planner_retries"] = int(retries)
        if cooldown_until is not None:
            md["declined_jesus_until_turn"] = int(cooldown_until)
        # Per‑message flag for downstream DB-derived history
        md["had_jesus_invite"] = bool(allow_jesus)
        # Structured one-line log for cadence decision
        try:
            logger.info(
                "gate",
                extra={
                    "cid": st.conversation_id,
                    "path": "orchestrated",
                    "phase": plan.phase,
                    "advice_intent": (plan.phase == "advice"),
                    "intake_completed": bool(st.intake_completed),
                    "safety": bool(getattr(plan, "safety", None) and plan.safety.flag),
                    "consent_known": bool(getattr(st, "prayer_consent_known", False)),
                    "consent": bool(getattr(st, "prayer_consent", False)),
                    "a_idx": int(st.turn_index),
                    "last_invite": st.last_jesus_invite_turn if isinstance(getattr(st, "last_jesus_invite_turn", None), int) else None,
                    "until": cooldown_until,
                    "allow_jesus": bool(allow_jesus),
                    "cadence_reason": cadence_reason,
                },
            )
        except Exception:
            pass

        return {"content": content, "metadata": md}


# Helpers

def invite_gate(
    *,
    phase: str,
    advice_intent: bool,
    intake_completed: bool,
    safety_flag: bool,
    assistant_turn_index: int,
    last_jesus_invite_turn: int | None,
    declined_jesus_until_turn: int | None,
    last_turn_had_jesus: bool,
    prayer_consent_known: bool,
    prayer_consent: bool,
    jesus_invite_allowed_from_plan: bool,
) -> tuple[bool, str]:
    """
    Unified Jesus-invite gate used by both orchestrator and legacy paths.
    
    Reasons (canonical):
    safety | phase_intake | not_advice | intake | first_turn | last_turn_had_jesus | cadence_window | cooldown_declined | plan_blocked | no_consent | ok
    """
    # 1) Hard blocks (order matters)
    if safety_flag:
        return False, "safety"
    if phase == "intake":
        return False, "phase_intake"
    if phase != "advice" and (not advice_intent):
        return False, "not_advice"
    if not intake_completed:
        return False, "intake"

    # 2) Consent
    # Explicit "no" blocks as plan_blocked; unknown consent does not block
    if prayer_consent_known and (not prayer_consent):
        return False, "plan_blocked"

    # 3) Frequency / duplication
    if assistant_turn_index == 0:
        return False, "first_turn"
    if last_turn_had_jesus:
        return False, "last_turn_had_jesus"
    # 4) Cadence window
    if last_jesus_invite_turn is None:
        # Require more build-up before the first invite
        if assistant_turn_index < 4:
            return False, "cadence_window"
    else:
        if (assistant_turn_index - last_jesus_invite_turn) < 3:
            return False, "cadence_window"

    # 5) Decline cooldown
    if isinstance(declined_jesus_until_turn, int) and assistant_turn_index < declined_jesus_until_turn:
        return False, "cooldown_declined"

    # 6) Planner advisory
    if not jesus_invite_allowed_from_plan:
        return False, "plan_blocked"

    # 7) OK
    return True, "ok"

def compose(
    plan: ResponsePlan,
    ctx: List[Dict[str, str]],
    allow_jesus: bool,
    insight_clauses: List[str] | None = None,
    allow_books: bool = False,
) -> str:
    lines = []
    lines.append(plan.plan.mirror)
    lines.append(f"**What’s going on (read):** {plan.plan.diagnose}")
    lines.append(f"**Truth anchor:** {plan.plan.truth_anchor}")
    lines.append("\n**Next 7 days**")
    for i, s in enumerate(plan.plan.steps_7day, 1):
        tip = f" (trigger: {s.trigger_if_then})" if s.trigger_if_then else ""
        lines.append(f"{i}. {s.title} — {s.time_estimate_min} min.\n   Say it like this: \"{s.how_to_say_it}\"{tip}")
    lines.append("\n**Likely obstacles & how to handle:**")
    for ob in plan.plan.obstacles:
        lines.append(f"- {ob}")
    lines.append(f"\n**Quick check‑in:** {plan.plan.check_in_question}")
    if allow_jesus:
        lines.append("\nWhere do you sense Jesus inviting you to take one small, grace‑filled step this week?")
    if ctx:
        cites = ", ".join([f"({c['book_pretty']}, {c['section']})" for c in ctx[:3]])
        lines.append(f"\nSources: {cites}")
    return "\n".join(lines)


def derive_metadata(
    plan: ResponsePlan,
    allow_books: bool,
    allow_jesus: bool,
    ctx: List[Dict[str, str]],
    used_insights: bool,
):
    return {
        "phase": plan.phase,
        "advice_intent": plan.phase == "advice",
        "safety_flag_this_turn": plan.safety.flag,
        "gate_reason": "ok" if allow_books else ("gated" if ctx == [] else "gated"),
        "book_selection_reason": "contextual" if ctx else "gated or none",
        "book_attributions": (
            [
                {"key": c.get("book_key", "?"), "pretty": c.get("book_pretty", "?"), "author": c.get("author", "?")}
                for c in ctx
            ] if allow_books else []
        ),
        "scrubbed_books": [] if ctx else plan.book_candidate_keys,
        "asked_question": True,
        "rooted_in_jesus_emphasis": allow_jesus,
        "jesus_invite_variant": plan.jesus_invite_variant if allow_jesus else 0,
        "style_guide": "friend_v1",
        "faith_branch": "unknown_path",
        # New observability flag for insights usage
        "used_book_insights": bool(used_insights),
    }
