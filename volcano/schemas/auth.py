from pydantic import BaseModel, EmailStr, Field, field_validator

from volcano.schemas.user import UserOut, validate_password


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CitizenSignup(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72, description="At least 8 characters")
    municipality_id: int | None = None

    _v = field_validator("password")(validate_password)
