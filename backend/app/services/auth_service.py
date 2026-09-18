from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.models.category import Category, CategoryType
from app.schemas.user import UserCreate, UserUpdate, PasswordChangeRequest
from app.core.security import hash_password, verify_password, create_access_token

DEFAULT_EXPENSE_CATEGORIES = [
    {"name": "Food & Dining", "icon": "utensils", "color": "#EF4444"},
    {"name": "Travel & Commute", "icon": "navigation", "color": "#3B82F6"},
    {"name": "Shopping", "icon": "shopping-bag", "color": "#EC4899"},
    {"name": "Bills & Utilities", "icon": "file-text", "color": "#F59E0B"},
    {"name": "Education", "icon": "book-open", "color": "#8B5CF6"},
    {"name": "Entertainment", "icon": "film", "color": "#10B981"},
    {"name": "Health & Medical", "icon": "heart", "color": "#14B8A6"},
    {"name": "Rent & Housing", "icon": "home", "color": "#6366F1"},
    {"name": "Groceries", "icon": "shopping-cart", "color": "#84CC16"},
    {"name": "Other Expense", "icon": "more-horizontal", "color": "#64748B"},
]

DEFAULT_INCOME_CATEGORIES = [
    {"name": "Salary", "icon": "briefcase", "color": "#10B981"},
    {"name": "Freelance", "icon": "laptop", "color": "#06B6D4"},
    {"name": "Business", "icon": "trending-up", "color": "#3B82F6"},
    {"name": "Investments", "icon": "pie-chart", "color": "#8B5CF6"},
    {"name": "Gifts & Grants", "icon": "gift", "color": "#EC4899"},
    {"name": "Other Income", "icon": "plus-circle", "color": "#64748B"},
]


class AuthService:
    @staticmethod
    def seed_default_categories(db: Session, user_id: int) -> None:
        """Seed default income and expense categories for a newly registered user."""
        categories_to_add: List[Category] = []

        for item in DEFAULT_EXPENSE_CATEGORIES:
            categories_to_add.append(
                Category(
                    user_id=user_id,
                    name=item["name"],
                    type=CategoryType.EXPENSE,
                    icon=item["icon"],
                    color=item["color"],
                    is_default=True
                )
            )

        for item in DEFAULT_INCOME_CATEGORIES:
            categories_to_add.append(
                Category(
                    user_id=user_id,
                    name=item["name"],
                    type=CategoryType.INCOME,
                    icon=item["icon"],
                    color=item["color"],
                    is_default=True
                )
            )

        db.add_all(categories_to_add)

    @staticmethod
    def register_user(db: Session, user_in: UserCreate) -> User:
        """Register a new user, hash credentials, and generate default categories."""
        normalized_email = user_in.email.strip().lower()

        existing_user = db.query(User).filter(User.email == normalized_email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists."
            )

        hashed_pw = hash_password(user_in.password)
        new_user = User(
            full_name=user_in.full_name.strip(),
            email=normalized_email,
            password_hash=hashed_pw,
            currency=user_in.currency or "INR"
        )
        db.add(new_user)
        db.flush()  # Populates new_user.id before seeding categories

        AuthService.seed_default_categories(db, new_user.id)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        """Verify user credentials and return the user if valid."""
        normalized_email = email.strip().lower()
        user = db.query(User).filter(User.email == normalized_email).first()

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password. Please try again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    @staticmethod
    def update_profile(db: Session, user: User, update_in: UserUpdate) -> User:
        """Update user profile metadata."""
        if update_in.full_name is not None:
            user.full_name = update_in.full_name.strip()
        if update_in.currency is not None:
            user.currency = update_in.currency.strip().upper()

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: User, pwd_in: PasswordChangeRequest) -> None:
        """Verify current password and set new password."""
        if not verify_password(pwd_in.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect."
            )

        user.password_hash = hash_password(pwd_in.new_password)
        db.commit()
