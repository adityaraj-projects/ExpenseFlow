from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.report import ComprehensiveReport, ReportSummary
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("", response_model=ComprehensiveReport)
def get_comprehensive_report(
    timeframe: str = Query("this_month", pattern="^(this_week|this_month|last_month|this_year|custom)$"),
    start_date: Optional[date] = Query(None, description="Start date for custom timeframe"),
    end_date: Optional[date] = Query(None, description="End date for custom timeframe"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate deep analytics report for the selected timeframe.
    Returns financial KPIs, timeline series for charts, and category breakdowns.
    """
    return ReportService.generate_report(
        db=db,
        user_id=current_user.id,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/summary", response_model=ReportSummary)
def get_report_summary(
    timeframe: str = Query("this_month", pattern="^(this_week|this_month|last_month|this_year|custom)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch quick summary KPIs for the chosen timeframe."""
    rep = ReportService.generate_report(
        db=db,
        user_id=current_user.id,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    return rep.summary
