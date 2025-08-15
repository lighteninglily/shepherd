from typing import Any, List, Type, Tuple
from pydantic import BaseModel, ValidationError
import json
import re
import urllib.request
import urllib.error

from ..config import get_settings
from ..policies.validator import validate_response_plan


SYSTEM_POLICY = """
You are a Christian marriage mentor and pastoral counselor.
Return ONLY a single JSON object that validates against the provided schema.
No markdown, no backticks, no explanations.

Content contract (the caller renders this):
- Warm, candid, hopeful, non-shaming.
- Scaffold: Mirror → Diagnose → Truth Anchor → 7‑day Plan (3–5 steps with time+scripts) → Obstacles → One check‑in question.
- Optional Jesus invite is decided by the caller (field: jesus_invite_allowed).

Hard rules about external resources:
- Do NOT include explicit book titles, authors, publishers, URLs, or links anywhere in strings.
- Use paraphrased, principle-level insights only. Never quote or cite.
- If you feel a resource is helpful, paraphrase the idea but do not name it.
- The server controls if/when explicit attributions are revealed; you must not reveal them.
- You may set books_mode_hint to "insights" (default) or "none" based on need, but do not place attributions or titles in any field.
"""


def _extract_json(text: str) -> str:
    # Best-effort: pick the first {...} block
    m = re.search(r"\{[\s\S]*\}$", text.strip())
    if m:
        return m.group(0)
    m2 = re.search(r"\{[\s\S]*\}", text)
    if m2:
        return m2.group(0)
    return text


def llm_structured(history: List[dict], schema: Type[BaseModel]):
    """Call OpenAI with JSON mode and validate into the given Pydantic schema.

    Uses unified settings and retries on JSON/schema/plan validation failures.
    Raises on final failure so the caller can fall back.
    """
    settings = get_settings()
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing for orchestrator")

    model = getattr(settings, "MODEL_NAME", "gpt-4o-mini")
    temperature = float(getattr(settings, "TEMPERATURE", 0.2))
    max_retries = int(getattr(settings, "MAX_PLANNER_RETRIES", 2))

    # Ensure our system policy is present first
    base_messages: List[dict] = []
    base_messages.append({"role": "system", "content": SYSTEM_POLICY})
    # Followed by provided history (usually includes prior system and turns)
    base_messages.extend(history)

    last_err: str = ""
    messages = list(base_messages)
    for attempt in range(max_retries + 1):
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            body = None
            try:
                body = he.read().decode("utf-8", errors="ignore")
            except Exception:
                body = None
            last_err = f"HTTPError: {he} body={body}"
            if attempt >= max_retries:
                raise RuntimeError(f"OpenAI structured call failed: {last_err}")
            # Add correction hint and retry
            messages = list(base_messages)
            messages.append({
                "role": "system",
                "content": "The prior response failed to return valid JSON. Return ONLY a single valid JSON object conforming to the schema, with quoted keys and values and no trailing commas.",
            })
            continue

        raw = ""
        try:
            choice0 = (data.get("choices") or [])[0]
            msg_obj = choice0.get("message") if isinstance(choice0, dict) else None
            raw = (msg_obj or {}).get("content") or ""
        except Exception:
            pass
        if not raw.strip():
            last_err = "empty content"
            if attempt >= max_retries:
                raise RuntimeError("OpenAI structured returned empty content")
            messages = list(base_messages)
            messages.append({
                "role": "system",
                "content": "Your last reply was empty. Return ONLY one JSON object matching the schema.",
            })
            continue

        # Extract and validate JSON
        json_str = _extract_json(raw)
        try:
            obj = json.loads(json_str)
        except Exception as e:
            last_err = f"json decode error: {e}"
            if attempt >= max_retries:
                raise RuntimeError(f"Structured output was not valid JSON: {e}; raw={raw[:300]}")
            messages = list(base_messages)
            messages.append({
                "role": "system",
                "content": f"Fix and return valid JSON only. Error: {e}",
            })
            continue

        # Pydantic v2 vs v1 compatibility
        try:
            parsed = schema.model_validate(obj) if hasattr(schema, "model_validate") else schema.parse_obj(obj)  # type: ignore[attr-defined]
        except Exception as ve:
            last_err = f"schema validation error: {ve}"
            if attempt >= max_retries:
                raise RuntimeError(f"Structured output failed schema validation: {ve}")
            messages = list(base_messages)
            messages.append({
                "role": "system",
                "content": f"Your JSON failed schema validation. Correct the fields and return only the JSON object. Error: {ve}",
            })
            continue

        # Server-side semantic validation
        ok, errs = validate_response_plan(parsed)  # type: ignore[arg-type]
        if not ok:
            if attempt >= max_retries:
                raise RuntimeError(f"Plan failed semantic validation: {errs}")
            messages = list(base_messages)
            messages.append({
                "role": "system",
                "content": "Revise the JSON to satisfy these constraints and return only the fixed JSON object: " + "; ".join(errs),
            })
            continue

        return parsed

    # Should not reach here
    raise RuntimeError(f"Planner failed after retries: {last_err}")
