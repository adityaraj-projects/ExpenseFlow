from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from typing import List
from app.models.statement_import import StatementImport
from app.schemas.statement import (
    PhonePePreviewResponse,
    PhonePeImportRequest,
    PhonePeImportResponse,
    StatementImportResponse
)
from app.services.statement_parser_service import StatementParserService

router = APIRouter(prefix="/statements", tags=["Statement Import"])


@router.post("/parse-phonepe", response_model=PhonePePreviewResponse)
async def parse_phonepe_statement(
    file: UploadFile = File(..., description="PhonePe PDF Statement"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Parse an uploaded PhonePe PDF transaction statement, extract transactions,
    suggest categories, detect duplicates scoped to the authenticated user,
    and return an interactive preview.
    """
    filename = file.filename or "statement.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files (.pdf) are supported. Please upload a valid PhonePe statement."
        )

    # Read bytes safely into memory
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF file is empty."
        )

    result = StatementParserService.parse_statement_preview(
        db=db,
        user_id=current_user.id,
        pdf_bytes=content,
        filename=filename
    )
    return result


@router.post("/import-phonepe", response_model=PhonePeImportResponse)
def import_phonepe_transactions(
    req: PhonePeImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Import user-confirmed PhonePe transactions into ExpenseFlow.
    Participates directly in all calculations, charts, and reports.
    Logs an audit entry in statement_imports table.
    """
    transactions_data = [item.model_dump() for item in req.transactions]
    result = StatementParserService.import_transactions(
        db=db,
        user_id=current_user.id,
        transactions_to_import=transactions_data,
        filename=req.filename,
        statement_period=req.statement_period,
        total_found=req.total_found
    )
    return result


@router.get("/history", response_model=List[StatementImportResponse])
def get_statement_import_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch statement import history strictly scoped to the authenticated user.
    Never exposes other users' imports.
    """
    history = db.query(StatementImport).filter(
        StatementImport.user_id == current_user.id
    ).order_by(StatementImport.imported_at.desc(), StatementImport.id.desc()).all()
    return history


@router.get("/history/{import_id}", response_model=StatementImportResponse)
def get_statement_import_detail(
    import_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch details for a specific statement import, verified against authenticated user.
    """
    entry = db.query(StatementImport).filter(
        StatementImport.id == import_id,
        StatementImport.user_id == current_user.id
    ).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement import record not found."
        )
    return entry
