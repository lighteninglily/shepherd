from typing import Dict, Any
from pydantic import BaseModel

class IntakeState(BaseModel):
    issue_named: bool = False
    safety_cleared: bool = False
    goal_captured: bool = False
    prayer_consent_known: bool = False

    def is_complete(self) -> bool:
        return (
            bool(self.issue_named)
            and bool(self.safety_cleared)
            and bool(self.goal_captured)
            and bool(self.prayer_consent_known)
        )

    @classmethod
    def from_meta(cls, meta: Dict[str, Any] | None) -> "IntakeState":
        m = dict(meta or {})
        if isinstance(m.get("intake"), dict):
            m = m["intake"]  # unwrap nested
        return cls(
            issue_named=bool(m.get("issue_named", False)),
            safety_cleared=bool(m.get("safety_cleared", False)),
            goal_captured=bool(m.get("goal_captured", False)),
            prayer_consent_known=bool(m.get("prayer_consent_known", False)),
        )

    def to_meta(self) -> Dict[str, Any]:
        return {
            "intake": {
                "issue_named": bool(self.issue_named),
                "safety_cleared": bool(self.safety_cleared),
                "goal_captured": bool(self.goal_captured),
                "prayer_consent_known": bool(self.prayer_consent_known),
                "completed": self.is_complete(),
            }
        }
