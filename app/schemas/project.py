from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Name of the project",
    )

    objective: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Objective of the project",
    )

    analysis_focus: str | None = Field(
        default=None,
        max_length=500,
        description="Specific areas to analyze",
    )