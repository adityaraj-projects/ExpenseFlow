from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PhonePePreviewItem(BaseModel):
    preview_id: str
    transaction_date: str
    transaction_time: Optional[str] = None
    type: str
    amount: Decimal = Field(..., gt=0)
    description: str
    merchant_or_party: str
    external_transaction_id: Optional[str] = None
    external_utr: Optional[str] = None
    source: str = "phonepe"
    suggested_category_id: int
    suggested_category_name: str
    suggested_category_icon: str
    suggested_category_color: str
    is_duplicate: bool = False
    duplicate_reason: str = ""
    status: str
    is_selected: bool = True


class PhonePePreviewResponse(BaseModel):
    statement_format: str = "PhonePe PDF Statement"
    total_count: int
    new_count: int
    duplicate_count: int
    items: List[PhonePePreviewItem]
    user_categories: List[Dict[str, Any]]


class PhonePeImportItem(BaseModel):
    transaction_date: str
    transaction_time: Optional[str] = None
    type: str
    amount: Decimal = Field(..., gt=0)
    description: str
    category_id: int
    external_transaction_id: Optional[str] = None
    external_utr: Optional[str] = None
    source: Optional[str] = "phonepe"


class PhonePeImportRequest(BaseModel):
    transactions: List[PhonePeImportItem]


class PhonePeImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    message: str
