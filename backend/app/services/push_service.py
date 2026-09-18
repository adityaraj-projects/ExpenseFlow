import json
import base64
from typing import List, Optional
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from pywebpush import webpush, WebPushException
from app.core.config import settings
from app.models.push_subscription import PushSubscription
from app.models.user_preference import UserPreference

# In-memory cached VAPID instance for development when .env keys are not manually provided
_DEV_VAPID_INSTANCE: Optional[Vapid] = None


class PushService:

    @classmethod
    def _get_vapid(cls) -> Vapid:
        global _DEV_VAPID_INSTANCE
        if settings.VAPID_PRIVATE_KEY:
            try:
                v = Vapid.from_string(settings.VAPID_PRIVATE_KEY)
                return v
            except Exception:
                pass

        if _DEV_VAPID_INSTANCE is None:
            _DEV_VAPID_INSTANCE = Vapid()
            _DEV_VAPID_INSTANCE.generate_keys()
        return _DEV_VAPID_INSTANCE

    @classmethod
    def get_vapid_public_key(cls) -> str:
        """Returns the URL-safe base64 encoded public key for browser pushManager.subscribe()."""
        if settings.VAPID_PUBLIC_KEY:
            return settings.VAPID_PUBLIC_KEY

        vapid = cls._get_vapid()
        pub_bytes = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        return base64.urlsafe_b64encode(pub_bytes).decode("utf-8").rstrip("=")

    @classmethod
    def subscribe(
        cls,
        db: Session,
        user_id: int,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: Optional[str] = None
    ) -> PushSubscription:
        sub = db.query(PushSubscription).filter(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint
        ).first()

        if sub:
            sub.p256dh = p256dh
            sub.auth = auth
            sub.user_agent = user_agent
        else:
            sub = PushSubscription(
                user_id=user_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                user_agent=user_agent
            )
            db.add(sub)

        db.commit()
        db.refresh(sub)
        return sub

    @classmethod
    def unsubscribe(cls, db: Session, user_id: int, endpoint: str) -> bool:
        sub = db.query(PushSubscription).filter(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint
        ).first()
        if not sub:
            return False
        db.delete(sub)
        db.commit()
        return True

    @classmethod
    def send_notification_to_user(
        cls,
        db: Session,
        user_id: int,
        title: str,
        message: str,
        url: str = "/pages/dashboard.html"
    ) -> int:
        """
        Dispatches Web Push notification to all active browser subscriptions for this user.
        Respects user push notification preference and automatically cleans up expired subscriptions (HTTP 410/404).
        """
        # Check user preferences
        pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        if pref and (not pref.notifications_enabled or not pref.push_enabled):
            return 0

        subs: List[PushSubscription] = db.query(PushSubscription).filter(
            PushSubscription.user_id == user_id
        ).all()

        if not subs:
            return 0

        vapid = cls._get_vapid()
        private_pem = vapid.private_pem().decode("utf-8")
        payload = json.dumps({
            "title": title,
            "body": message,
            "url": url
        })

        success_count = 0
        stale_subs = []

        for sub in subs:
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth
                }
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=private_pem,
                    vapid_claims={"sub": settings.VAPID_SUBJECT}
                )
                success_count += 1
            except WebPushException as ex:
                # HTTP 404 or 410 means user unregistered or revoked permission
                response = getattr(ex, "response", None)
                if response is not None and response.status_code in [404, 410]:
                    stale_subs.append(sub)
            except Exception:
                pass

        if stale_subs:
            for s in stale_subs:
                db.delete(s)
            db.commit()

        return success_count
