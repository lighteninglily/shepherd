from dataclasses import dataclass


@dataclass
class SafetyVerdict:
    flag: bool
    reason: str | None = None


# Stub: integrate a provider moderation model in production

def pre_moderate(text: str) -> SafetyVerdict:
    red_flags = ["suicide", "kill", "abuse", "violence", "child", "assault", "threat"]
    tl = (text or "").lower()
    if any(t in tl for t in red_flags):
        return SafetyVerdict(True, "keyword")
    return SafetyVerdict(False, None)


def post_moderate(text: str) -> str:
    return text
