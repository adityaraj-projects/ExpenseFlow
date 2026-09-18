from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.push_subscription import (
    PushSubscribeRequest,
    PushSubscriptionResponse,
    VapidPublicKeyResponse
)
from app.services.push_service import PushService

router = APIRouter(prefix="/push", tags=["Web Push"])


@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
def get_vapid_public_key(
    current_user: User = Depends(get_current_user)
):
    """Retrieve the VAPID public key for browser pushManager.subscribe()."""
    key = PushService.get_vapid_public_key()
    return VapidPublicKeyResponse(public_key=key)


@router.post("/subscribe", response_model=PushSubscriptionResponse)
def subscribe_to_push(
    data: PushSubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save or update browser Web Push subscription for the authenticated user."""
    sub = PushService.subscribe(
        db=db,
        user_id=current_user.id,
        endpoint=data.endpoint,
        p256dh=data.keys.p256dh,
        auth=data.keys.auth,
        user_agent=data.user_agent
    )
    return PushSubscriptionResponse(status="subscribed", endpoint=sub.endpoint)


@router.delete("/unsubscribe")
def unsubscribe_from_push(
    endpoint: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a browser push subscription for the authenticated user."""
    success = PushService.unsubscribe(db, current_user.id, endpoint)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return {"message": "Unsubscribed successfully"}


@router.post("/test")
def send_test_push_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a test push notification to verify browser push integration."""
    count = PushService.send_notification_to_user(
        db=db,
        user_id=current_user.id,
        title="ExpenseFlow Alert",
        message="Web Push notifications are functioning properly on this device.",
        url="/pages/dashboard.html"
    )
    return {
        "message": f"Test push dispatched to {count} active device subscription(s).",
        "devices_notified": count
    }
