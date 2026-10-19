from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class ChangeOutput(BaseModel):
    id: str
    title: str
    detail: Optional[str] = None
    changeType: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None
    createdAt: Optional[datetime] = None


class ChangesResponseData(BaseModel):
    projectId: str
    changeCount: int
    changes: List[ChangeOutput]


class ChangesResponse(BaseModel):
    success: bool
    message: str
    data: ChangesResponseData


class ChangeResponse(BaseModel):
    success: bool
    message: str
    data: ChangeOutput


class DeletedChange(BaseModel):
    id: str
    projectId: str


class DeleteChangeResponse(BaseModel):
    success: bool
    message: str
    data: DeletedChange
