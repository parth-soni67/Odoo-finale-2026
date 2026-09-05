from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_roles
from app.models.user import User, Role
from app.schemas.product import (
    ProductResponse,
    ProductCreate,
    ProductUpdate,
    ProductCategoryResponse,
    ProductCategoryCreate,
)
from app.services.product_service import product_service

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=List[ProductResponse])
def list_products(
    search: Optional[str] = Query(None, description="Search by name or SKU"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List products with optional search, category, and active filtering.

    Customers only see active products.
    """
    if current_user.role == Role.CUSTOMER:
        is_active = True

    return product_service.get_products(
        db=db,
        search=search,
        category_id=category_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@router.get("/categories", response_model=List[ProductCategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all product categories."""
    return product_service.get_categories(db)


@router.post("/categories", response_model=ProductCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    cat_in: ProductCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Create a new product category (ADMIN, SALES_MANAGER)."""
    return product_service.create_category(db, cat_in)


@router.get("/{id}", response_model=ProductResponse)
def get_product(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get single product by ID."""
    product = product_service.get_product_by_id(db, id)
    if not product:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product with ID {id} not found"},
        )
    return product


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Create a new product (ADMIN, SALES_MANAGER)."""
    return product_service.create_product(db, product_in, current_user=current_user)


@router.put("/{id}", response_model=ProductResponse)
@router.patch("/{id}", response_model=ProductResponse)
def update_product(
    id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Update an existing product (ADMIN, SALES_MANAGER)."""
    return product_service.update_product(
        db, product_id=id, product_update=product_update, current_user=current_user
    )


@router.delete("/{id}", response_model=ProductResponse)
def delete_or_deactivate_product(
    id: int,
    hard_delete: bool = Query(False, description="Perform hard delete if true, otherwise deactivates"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Deactivate or remove a product (ADMIN, SALES_MANAGER)."""
    return product_service.delete_product(
        db, product_id=id, current_user=current_user, hard_delete=hard_delete
    )
