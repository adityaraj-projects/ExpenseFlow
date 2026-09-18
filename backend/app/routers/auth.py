from fastapi import APIRouter, Depends, status, Response, Request
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate, UserResponse, UserUpdate, PasswordChangeRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account with secure password hashing.
    Automatically generates initial default categories and returns an access token.
    """
    user = AuthService.register_user(db, user_in)
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=Token)
async def login(request: Request, db: Session = Depends(get_db)):
    """
    Authenticate user via JSON or Form Data and return a signed JWT token.
    Works seamlessly with both standard JSON frontend calls and OAuth2 Swagger.
    """
    content_type = request.headers.get("content-type", "")

    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        email = form.get("username") or form.get("email")
        password = form.get("password")
    else:
        body = await request.json()
        email = body.get("email")
        password = body.get("password")

    if not email or not password:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required."
        )

    user = AuthService.authenticate_user(db, email=email, password=password)
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve the profile of the currently logged-in user."""
    return current_user


@router.put("/profile", response_model=UserResponse)
def update_profile(
    update_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update profile metadata (e.g. display name, currency)."""
    updated = AuthService.update_profile(db, current_user, update_in)
    return updated


@router.put("/change-password")
def change_password(
    pwd_in: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change the account password securely."""
    AuthService.change_password(db, current_user, pwd_in)
    return {"message": "Password changed successfully."}


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint for client confirmation.
    Token invalidation is finalized on the client by deleting the stored token.
    """
    return {"message": "Successfully logged out.", "status": "success"}
