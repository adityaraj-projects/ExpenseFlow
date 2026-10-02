from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.report import ComprehensiveReport, ReportSummary, MonthlyFinancialSummary
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("", response_model=ComprehensiveReport)
def get_comprehensive_report(
    timeframe: str = Query("this_month", pattern="^(this_week|this_month|last_month|this_year|custom)$"),
    start_date: Optional[date] = Query(None, description="Start date for custom timeframe"),
    end_date: Optional[date] = Query(None, description="End date for custom timeframe"),
    source: Optional[str] = Query(None, description="Filter by source ('phonepe', 'cash', 'manual', 'all')"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate deep analytics report for the selected timeframe.
    Returns financial KPIs, timeline series for charts, category breakdowns, and source metrics.
    """
    return ReportService.generate_report(
        db=db,
        user_id=current_user.id,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        source=source
    )


@router.get("/summary", response_model=ReportSummary)
def get_report_summary(
    timeframe: str = Query("this_month", pattern="^(this_week|this_month|last_month|this_year|custom)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    source: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch quick summary KPIs for the chosen timeframe."""
    rep = ReportService.generate_report(
        db=db,
        user_id=current_user.id,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        source=source
    )
    return rep.summary


@router.get("/monthly-summary", response_model=MonthlyFinancialSummary)
def get_monthly_financial_summary(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2000, le=2100, description="Year (e.g. 2026)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch smart monthly financial summary containing KPIs, source breakdown,
    top categories, month-over-month comparison, and rule-based insights.
    """
    return ReportService.get_monthly_summary(
        db=db,
        user_id=current_user.id,
        month=month,
        year=year
    )


@router.get("/monthly-pdf")
def export_monthly_pdf(
    month: int = Query(..., ge=1, le=12, description="Month number (1-12)"),
    year: int = Query(..., ge=2000, le=2100, description="Year (e.g. 2026)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate and download a clean, professional monthly financial statement report as a PDF.
    Contains user info, reporting period, summary cards, and full transaction history ledger.
    """
    try:
        pdf_bytes = ReportService.generate_monthly_pdf(
            db=db,
            user=current_user,
            month=month,
            year=year
        )
        filename = f"ExpenseFlow_Statement_{year}_{month:02d}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate monthly PDF report: {str(e)}"
        )
