from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.gateway.deps import current_user
from volcano.models import User
from volcano.schemas.auth import CitizenSignup, Token
from volcano.schemas.user import UserOut
from volcano.services.users import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token, summary="Sign in (returns a JWT)")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Standard OAuth2 form: `username` (e-mail) and `password` fields. Works with Swagger's **Authorize**."""
    user, token = AuthService(db).authenticate(form.username, form.password)
    return Token(access_token=token, user=UserOut.from_user(user))


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             summary="Public sign-up for citizens")
def signup(payload: CitizenSignup, db: Session = Depends(get_db)):
    return UserOut.from_user(AuthService(db).register_citizen(payload))


@router.get("/me", response_model=UserOut, summary="Authenticated user")
def me(user: User = Depends(current_user)):
    return UserOut.from_user(user)
