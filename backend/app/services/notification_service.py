from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.notification import Notification, NotificationType
from app.models.user_preference import UserPreference
from app.services.push_service import PushService


class NotificationService:

    @classmethod
    def get_user_preferences(cls, db: Session, user_id: int) -> UserPreference:
        pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        if not pref:
            pref = UserPreference(user_id=user_id)
            db.add(pref)
            db.commit()
            db.refresh(pref)
        return pref

    @classmethod
    def create_notification(
        cls,
        db: Session,
        user_id: int,
        title: str,
        message: str,
        notification_type: NotificationType,
        reference_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        send_push: bool = True
    ) -> Optional[Notification]:
        """
        Creates an in-app notification with strict idempotency and user preferences enforcement.
        Optionally dispatches a Web Push notification.
        """
        pref = cls.get_user_preferences(db, user_id)
        if not pref.notifications_enabled:
            return None

        # Check type-specific preference toggles
        if notification_type in [NotificationType.BUDGET_WARNING, NotificationType.BUDGET_EXCEEDED] and not pref.budget_alerts:
            return None
        if notification_type == NotificationType.REMINDER and not pref.reminder_alerts:
            return None
        if notification_type in [NotificationType.GOAL_MILESTONE, NotificationType.GOAL_DEADLINE] and not pref.goal_alerts:
            return None
        if notification_type == NotificationType.RECURRING_GENERATED and not pref.recurring_alerts:
            return None

        # Idempotency check
        if idempotency_key:
            existing = db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.idempotency_key == idempotency_key
            ).first()
            if existing:
                return None

        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            is_read=False
        )
        try:
            db.add(notif)
            db.commit()
            db.refresh(notif)
        except Exception:
            db.rollback()
            # If a race condition hit the unique constraint, return the existing row
            if idempotency_key:
                return db.query(Notification).filter(
                    Notification.user_id == user_id,
                    Notification.idempotency_key == idempotency_key
                ).first()
            return None

        # Send Web Push if enabled
        if send_push and pref.push_enabled:
            try:
                PushService.send_notification_to_user(
                    db,
                    user_id=user_id,
                    title=f"ExpenseFlow: {title}",
                    message=message
                )
            except Exception:
                pass

        return notif

    @classmethod
    def get_notifications(
        cls,
        db: Session,
        user_id: int,
        limit: int = 50,
        unread_only: bool = False
    ) -> List[Notification]:
        query = db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return query.order_by(desc(Notification.created_at)).limit(limit).all()

    @classmethod
    def get_unread_count(cls, db: Session, user_id: int) -> int:
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()

    @classmethod
    def mark_as_read(cls, db: Session, user_id: int, notification_id: int) -> Optional[Notification]:
        notif = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if not notif:
            return None
        if not notif.is_read:
            notif.is_read = True
            notif.read_at = datetime.utcnow()
            db.commit()
            db.refresh(notif)
        return notif

    @classmethod
    def mark_all_as_read(cls, db: Session, user_id: int) -> int:
        count = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).update({
            Notification.is_read: True,
            Notification.read_at: datetime.utcnow()
        }, synchronize_session=False)
        db.commit()
        return count

    @classmethod
    def delete_notification(cls, db: Session, user_id: int, notification_id: int) -> bool:
        notif = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if not notif:
            return False
        db.delete(notif)
        db.commit()
        return True
