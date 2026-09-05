from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, Role
from app.schemas.approval import ApprovalResponse
from app.services.approval_service import approval_service

router = APIRouter(tags=["Approvals"])


@router.get(
    "/approvals/pending",
    response_model=List[ApprovalResponse],
)
def list_pending_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SALES_MANAGER, Role.FINANCE, Role.ADMIN)),
):
    """Lists pending approvals awaiting action by the current manager or finance reviewer."""
    return approval_service.list_pending_approvals(db=db, current_user=current_user)
