from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic import BaseModel, Field


class DecisionStatus(str, Enum):
    open = "open"
    resolved = "resolved"



# # ============================================================
# # DECISION STATUS
# # ============================================================

# class DecisionStatus(str, Enum):
#     open = "open"
#     resolved = "resolved"


# # ============================================================
# # REQUESTS
# # ============================================================

# class CreateDecisionRequest(BaseModel):
#     title: str = Field(
#         ...,
#         min_length=1,
#         max_length=200,
#         description="Short title of the decision",
#     )

#     description: str | None = Field(
#         default=None,
#         max_length=2000,
#         description="Details of the decision",
#     )

#     owner_name: str | None = Field(
#         default=None,
#         max_length=120,
#         description="Person accountable for the decision",
#     )

#     finding_id: str | None = Field(
#         default=None,
#         description="Finding this decision was raised from",
#     )


# class UpdateDecisionRequest(BaseModel):
#     title: str | None = Field(
#         default=None,
#         min_length=1,
#         max_length=200,
#     )

#     description: str | None = Field(
#         default=None,
#         max_length=2000,
#     )

#     owner_name: str | None = Field(
#         default=None,
#         max_length=120,
#     )

#     finding_id: str | None = None

#     status: DecisionStatus | None = None


# # ============================================================
# # RESPONSES
# # ============================================================

# class DecisionOutput(BaseModel):
#     id: str
#     projectId: str
#     title: str
#     description: Optional[str] = None
#     ownerName: Optional[str] = None
#     findingId: Optional[str] = None
#     status: DecisionStatus
#     createdAt: Optional[datetime] = None
#     updatedAt: Optional[datetime] = None
#     resolvedAt: Optional[datetime] = None


# class DecisionsResponseData(BaseModel):
#     projectId: str
#     decisionCount: int
#     decisions: List[DecisionOutput]


# class DecisionsResponse(BaseModel):
#     success: bool
#     message: str
#     data: DecisionsResponseData


# class DecisionResponse(BaseModel):
#     success: bool
#     message: str
#     data: DecisionOutput


class CreateDecisionRequest(BaseModel):
    finding_id: str | None = None
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    owner_name: str | None = None


class UpdateDecisionRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    owner_name: str | None = None
    status: DecisionStatus | None = None

# ============================================================
# RESPONSES
# ============================================================

class DecisionOutput(BaseModel):
    id: str
    projectId: str
    title: str
    description: Optional[str] = None
    ownerName: Optional[str] = None
    findingId: Optional[str] = None
    status: DecisionStatus
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    resolvedAt: Optional[datetime] = None


class DecisionResponse(BaseModel):
    success: bool
    message: str
    data: DecisionOutput


class DecisionsResponseData(BaseModel):
    projectId: str
    decisionCount: int
    decisions: List[DecisionOutput]


class DecisionsResponse(BaseModel):
    success: bool
    message: str
    data: DecisionsResponseData


class DeletedDecision(BaseModel):
    id: str
    projectId: str


class DeleteDecisionResponse(BaseModel):
    success: bool
    message: str
    data: DeletedDecision
