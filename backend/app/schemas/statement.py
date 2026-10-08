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


from datetime import datetime


class PhonePeImportRequest(BaseModel):
    transactions: List[PhonePeImportItem]
    filename: Optional[str] = None
    statement_period: Optional[str] = None
    total_found: Optional[int] = None


class PhonePeImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    message: str
    import_id: Optional[int] = None
    statement_period: Optional[str] = None


class StatementImportResponse(BaseModel):
    id: int
    user_id: int
    source: str
    statement_period: Optional[str] = None
    imported_at: datetime
    filename: Optional[str] = None
    total_found: int
    total_new: int
    total_duplicates: int
    total_failed: int
    status: str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True
