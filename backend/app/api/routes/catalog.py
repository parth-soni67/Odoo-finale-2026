from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_roles
from app.models.user import User, Role
from app.models.product import Product
from app.models.customer import Customer
from app.schemas.product import ProductResponse
from app.schemas.customer import CustomerResponse
from app.schemas.approval import ApprovalResponse
from app.services.approval_service import approval_service

router = APIRouter(tags=["catalog & approvals"])


@router.get("/products", response_model=List[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lists available products with unit prices, categories, and allowed discount ceilings."""
    return (
        db.query(Product)
        .options(joinedload(Product.category))
        .filter(Product.is_active == True)
        .order_by(Product.id.asc())
        .all()
    )


@router.get("/customers", response_model=List[CustomerResponse])
def list_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lists customer accounts with customer tier and discount ceiling thresholds."""
    return db.query(Customer).order_by(Customer.id.asc()).all()


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
