from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# EVIDENCE
# ============================================================

class AIReviewEvidence(BaseModel):
    page: Optional[int] = None
    section: Optional[str] = None
    quote: str


# ============================================================
# FINDING
# ============================================================

class AIReviewFinding(BaseModel):
    title: str

    summary: str

    priority: str

    category: str

    section: Optional[str] = None

    page: Optional[int] = None

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    needsAttention: bool

    suggestedQuestion: Optional[str] = None

    evidence: List[AIReviewEvidence] = Field(
        default_factory=list
    )


# ============================================================
# CHANGE
# ============================================================

class AIReviewChange(BaseModel):
    title: str

    detail: str

    changeType: Optional[str] = None

    section: Optional[str] = None

    page: Optional[int] = None


# ============================================================
# COMPLETE AI REVIEW OUTPUT
# ============================================================

class AIReviewLLMOutput(BaseModel):
    findings: List[AIReviewFinding] = Field(
        default_factory=list
    )

    changes: List[AIReviewChange] = Field(
        default_factory=list
    )