from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.category import CategoryType


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    type: CategoryType = CategoryType.EXPENSE
    icon: Optional[str] = Field("tag", max_length=50)
    color: Optional[str] = Field("#6366F1", max_length=20)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    type: Optional[CategoryType] = None
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=20)


class CategoryResponse(CategoryBase):
    id: int
    user_id: int
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
