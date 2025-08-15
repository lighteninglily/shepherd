from typing import Dict
import json
import re
import urllib.request
import urllib.error

from ..config import get_settings

CLASSIFIER_SYSTEM = """
You are a topic classifier for Christian marriage conversations.
Return ONLY one JSON object with:
- topic: one of [conflict, betrayal, porn, intimacy, finances, parenting, boundaries, other]
- confidence: float from 0.0 to 1.0 representing how confident you are about the topic label.
No markdown, no extra text.
"""


def _extract_json(text: str) -> str:
    m = re.search(r"\{[\s\S]*\}$", text.strip())
    if m:
        return m.group(0)
    m2 = re.search(r"\{[\s\S]*\}", text)
    if m2:
        return m2.group(0)
    return text


def classify(text: str) -> Dict[str, object]:
    """Classify a single user message into a topic + confidence.

    Returns a dict: {"topic": str, "confidence": float}
    May raise on HTTP or parsing failures; callers should handle exceptions and fall back.
    """
    settings = get_settings()
    api_key = (getattr(settings, "OPENAI_API_KEY", "") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing for classifier")

    model = getattr(settings, "MODEL_NAME", "gpt-4o-mini")
    temperature = float(getattr(settings, "TEMPERATURE", 0.1))

    messages = [
        {"role": "system", "content": CLASSIFIER_SYSTEM},
        {"role": "user", "content": text or ""},
    ]

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

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    raw = ""
    try:
        choice0 = (data.get("choices") or [])[0]
        msg_obj = choice0.get("message") if isinstance(choice0, dict) else None
        raw = (msg_obj or {}).get("content") or ""
    except Exception:
        pass

    if not raw.strip():
        raise RuntimeError("Classifier returned empty content")

    js = json.loads(_extract_json(raw))
    topic = str(js.get("topic", "other")).strip().lower()
    if topic not in {"conflict","betrayal","porn","intimacy","finances","parenting","boundaries","other"}:
        topic = "other"
    try:
        conf = float(js.get("confidence", 0.0))
    except Exception:
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    return {"topic": topic, "confidence": conf}
