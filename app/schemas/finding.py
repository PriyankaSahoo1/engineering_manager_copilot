from typing import List, Optional
from pydantic import BaseModel

class FindingEvidence(BaseModel):
    id: str
    source_id: str
    source_name: str
    page: Optional[int] = None
    section: Optional[str] = None
    quote: str

class FindingOutput(BaseModel):
    title: str
    summary: str
    priority: str
    category: str
    section: Optional[str] = None
    page: Optional[int] = None
    confidence: float
    needsAttention: bool
    suggestedQuestion: Optional[str] = None
    evidence: List[FindingEvidence] = []

class FindingsResponseData(BaseModel):
    projectId: str
    findingCount: int
    findings: List[dict]

class FindingsResponse(BaseModel):
    success: bool
    message: str
    data: FindingsResponseData
