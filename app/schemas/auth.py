from pydantic import BaseModel, ConfigDict, EmailStr, Field, AliasChoices


class SignInRequest(BaseModel):
    """Same body as old signup — email + password — but for login only."""

    model_config = ConfigDict(populate_by_name=True)

    email_id: EmailStr = Field(
        ...,
        validation_alias=AliasChoices("emailId", "email", "email_id"),
        serialization_alias="emailId",
    )
    password: str = Field(..., min_length=1, max_length=128)


class LoginRequest(SignInRequest):
    pass


class OnboardingCompleteRequest(BaseModel):
    role: str | None = None
    company: str | None = None
    job_title: str | None = None
    team_size: int | None = None
