from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# Steps 2025-08-15: Insights vs Attributions split
# - Added optional planner hint to indicate desired books usage: none | insights | attributions.
# - This is advisory; server-side gating determines visibility. Defaults preserve current behavior.

Phase = Literal["intake", "chat", "advice"]
Topic = Literal[
    "conflict","betrayal","porn","intimacy","finances",
    "parenting","boundaries","other"
]

BooksMode = Literal["none", "insights", "attributions"]


class Step(BaseModel):
    title: str
    how_to_say_it: str
    time_estimate_min: int = Field(ge=1, le=180)
    trigger_if_then: Optional[str] = None


class Safety(BaseModel):
    flag: bool
    reason: Optional[str] = None


class Plan(BaseModel):
    mirror: str
    diagnose: str
    truth_anchor: str
    steps_7day: List[Step]
    obstacles: List[str]
    check_in_question: str


class ResponsePlan(BaseModel):
    phase: Phase
    safety: Safety
    topic: Topic
    intake_completed_needed: bool
    jesus_invite_allowed: bool
    jesus_invite_variant: int = Field(0, ge=0, le=6)
    topic_confidence: float = 0.0
    book_candidate_keys: List[str] = []
    # Planner hint for how to use books this turn (server may override via gating)
    books_mode_hint: Optional[BooksMode] = "insights"
    # Paraphrased, title-free clauses derived from vetted resources
    insight_clauses: List[str] = []
    # Full attributions (only revealed when books are allowed by server gating)
    attributions: List[dict] = []
    plan: Plan
