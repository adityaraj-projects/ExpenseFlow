from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.dashboard import DashboardData, DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardData)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch comprehensive real-time dashboard data including KPIs,
    income vs expense monthly trend, category distribution, recent transactions,
    budget progress, and active savings goals.
    """
    return DashboardService.get_dashboard_data(db, current_user.id)


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch high-level financial summary KPIs."""
    data = DashboardService.get_dashboard_data(db, current_user.id)
    return data.summary
