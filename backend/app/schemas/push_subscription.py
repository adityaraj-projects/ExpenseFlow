from typing import Optional
from pydantic import BaseModel, Field


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(..., min_length=10)
    auth: str = Field(..., min_length=10)


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=500)
    keys: PushSubscriptionKeys
    user_agent: Optional[str] = Field(None, max_length=255)


class PushSubscriptionResponse(BaseModel):
    status: str
    endpoint: str


class VapidPublicKeyResponse(BaseModel):
    public_key: str
