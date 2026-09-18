from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.user_preference import UserPreference
from app.schemas.user_preference import UserPreferenceUpdate, UserPreferenceResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/preferences", tags=["User Preferences"])


@router.get("", response_model=UserPreferenceResponse)
def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve notification and alert preferences for the authenticated user."""
    return NotificationService.get_user_preferences(db, current_user.id)


@router.put("", response_model=UserPreferenceResponse)
def update_user_preferences(
    data: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notification preferences for the authenticated user."""
    pref = NotificationService.get_user_preferences(db, current_user.id)
    update_data = data.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(pref, field, val)

    db.commit()
    db.refresh(pref)
    return pref
