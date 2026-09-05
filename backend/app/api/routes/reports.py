from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, Role
from app.services.report_service import report_service

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("/sales-summary", response_model=Dict[str, Any])
def get_sales_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.SALES_REP, Role.FINANCE)
    ),
):
    """Retrieve high-level sales and operational KPIs across quotes and negotiations."""
    return report_service.get_sales_summary(db)
