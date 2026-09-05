from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, Role
from app.schemas.deal_health import DealHealthSummaryResponse, DealHealthDetailResponse
from app.services.deal_health_service import deal_health_service

router = APIRouter(prefix="/deal-health", tags=["Deal Health"])


@router.get("", response_model=DealHealthSummaryResponse)
def get_deal_health_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.SALES_REP, Role.FINANCE)
    ),
):
    """Retrieve deal health dashboard summary, counts, risk levels, and deal list."""
    return deal_health_service.get_deal_health_summary(db)


@router.get("/{quote_id}", response_model=DealHealthDetailResponse)
def get_quote_deal_health_detail(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.SALES_REP, Role.FINANCE)
    ),
):
    """Retrieve detailed deal health diagnostic, signals, alerts, and recommendations for a single quote."""
    return deal_health_service.get_quote_deal_health(db, quote_id)
