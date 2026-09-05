from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_roles
from app.models.user import User, Role
from app.models.customer import CustomerTier
from app.schemas.customer import CustomerResponse, CustomerCreate, CustomerUpdate
from app.services.customer_service import customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=List[CustomerResponse])
def list_customers(
    search: Optional[str] = Query(None, description="Search company, contact, or email"),
    tier: Optional[CustomerTier] = Query(None, description="Filter by customer tier"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.SALES_REP, Role.FINANCE)
    ),
):
    """List all customers with optional search and tier filtering.

    Internal sales/admin access only. Customers cannot view this list.
    """
    return customer_service.get_customers(
        db=db, search=search, tier=tier, skip=skip, limit=limit
    )


@router.get("/{id}", response_model=CustomerResponse)
def get_customer(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get single customer by ID.

    Customers are strictly restricted to only viewing their own customer profile.
    """
    if current_user.role == Role.CUSTOMER:
        own_customer = customer_service.get_customer_for_user(db, current_user)
        if own_customer.id != id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You are not authorized to view this customer's data"},
            )
        return own_customer

    customer = customer_service.get_customer_by_id(db, id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CUSTOMER_NOT_FOUND", "message": f"Customer with ID {id} not found"},
        )
    return customer


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer_in: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Create a new customer (ADMIN, SALES_MANAGER)."""
    return customer_service.create_customer(db, customer_in, current_user=current_user)


@router.put("/{id}", response_model=CustomerResponse)
@router.patch("/{id}", response_model=CustomerResponse)
def update_customer(
    id: int,
    customer_update: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Update customer details (ADMIN, SALES_MANAGER)."""
    return customer_service.update_customer(
        db, customer_id=id, customer_update=customer_update, current_user=current_user
    )
