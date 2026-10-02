import json
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.backup import (
    BackupPayload,
    BackupValidateResponse,
    BackupRestoreResponse
)
from app.services.backup_service import BackupService

router = APIRouter(prefix="/backup", tags=["Data Backup & Restore"])


@router.get("/export")
def export_full_backup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export all authenticated user data as a versioned JSON backup file.
    Strictly scoped to current user. Contains categories, transactions, budgets,
    goals, reminders, recurring rules, and preferences.
    """
    backup_dict = BackupService.export_backup(db=db, user=current_user)
    json_bytes = json.dumps(backup_dict, indent=2, ensure_ascii=False).encode("utf-8")
    filename = f"expenseflow_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/validate", response_model=BackupValidateResponse)
async def validate_backup_file(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Validates uploaded backup JSON file or JSON payload without writing anything to the database.
    Returns counts of items and validation status for the preview modal.
    """
    content_type = request.headers.get("content-type", "").lower()
    data = None

    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload: unable to parse contents."
            )
    elif "multipart/form-data" in content_type:
        form = await request.form()
        file_obj = form.get("file")
        if not file_obj or not hasattr(file_obj, "read"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a backup file in form field 'file'."
            )
        if hasattr(file_obj, "filename") and file_obj.filename and not file_obj.filename.lower().endswith(".json"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JSON backup files (.json) are supported."
            )
        content = await file_obj.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded backup file is empty."
            )
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backup file exceeds maximum allowed size of 10MB."
            )
        try:
            data = json.loads(content.decode("utf-8"))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON file: unable to parse contents."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported content type. Expected application/json or multipart/form-data."
        )

    return BackupService.validate_backup_payload(data)


@router.post("/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Restores validated backup data into the authenticated user's account.
    Never duplicates transactions or existing records.
    Can be invoked with multipart file or JSON payload.
    """
    content_type = request.headers.get("content-type", "").lower()
    backup_payload = None

    if "application/json" in content_type:
        try:
            raw_dict = await request.json()
            backup_payload = BackupPayload(**raw_dict)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse backup payload: {str(e)}"
            )
    elif "multipart/form-data" in content_type:
        form = await request.form()
        file_obj = form.get("file")
        if not file_obj or not hasattr(file_obj, "read"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a backup file in form field 'file'."
            )
        content = await file_obj.read()
        try:
            raw_dict = json.loads(content.decode("utf-8"))
            backup_payload = BackupPayload(**raw_dict)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse backup payload: {str(e)}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported content type. Expected application/json or multipart/form-data."
        )

    return BackupService.restore_backup(
        db=db,
        user_id=current_user.id,
        payload=backup_payload
    )
