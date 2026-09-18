from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.config import settings
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.post("/process")
def trigger_scheduler_run(
    x_scheduler_key: str = Header(None, alias="X-Scheduler-Key"),
    db: Session = Depends(get_db)
):
    """
    Protected webhook/endpoint to run scheduled checks (reminders, recurring, budgets, goals).
    Requires matching X-Scheduler-Key header for security.
    """
    if not x_scheduler_key or x_scheduler_key != settings.SCHEDULER_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing scheduler secret key."
        )

    results = SchedulerService.process_all_scheduled_events(db)
    return {
        "status": "success",
        "processed": results
    }
