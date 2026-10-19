from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class QuestionOutput(BaseModel):
    id: str
    text: str
    priority: Optional[str] = None
    findingId: Optional[str] = None
    evidenceId: Optional[str] = None
    createdAt: Optional[datetime] = None


class QuestionsResponseData(BaseModel):
    projectId: str
    questionCount: int
    questions: List[QuestionOutput]


class QuestionsResponse(BaseModel):
    success: bool
    message: str
    data: QuestionsResponseData


class QuestionResponse(BaseModel):
    success: bool
    message: str
    data: QuestionOutput


class DeletedQuestion(BaseModel):
    id: str
    projectId: str


class DeleteQuestionResponse(BaseModel):
    success: bool
    message: str
    data: DeletedQuestion
