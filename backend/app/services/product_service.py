import json
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.product import Product, ProductCategory
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.product import ProductCreate, ProductUpdate, ProductCategoryCreate


class ProductService:
    def get_products(
        self,
        db: Session,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Product]:
        query = db.query(Product)
        if is_active is not None:
            query = query.filter(Product.is_active == is_active)
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)
        if search:
            search_fmt = f"%{search}%"
            query = query.filter(
                (Product.name.ilike(search_fmt)) | (Product.sku.ilike(search_fmt))
            )
        return query.order_by(Product.id.asc()).offset(skip).limit(limit).all()

    def get_product_by_id(self, db: Session, product_id: int) -> Optional[Product]:
        return db.query(Product).filter(Product.id == product_id).first()

    def get_product_by_sku(self, db: Session, sku: str) -> Optional[Product]:
        return db.query(Product).filter(Product.sku == sku).first()

    def create_product(
        self, db: Session, product_in: ProductCreate, current_user: Optional[User] = None
    ) -> Product:
        existing = self.get_product_by_sku(db, product_in.sku)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "SKU_ALREADY_EXISTS", "message": f"Product with SKU '{product_in.sku}' already exists"}
            )

        product = Product(
            name=product_in.name,
            sku=product_in.sku,
            category_id=product_in.category_id,
            description=product_in.description,
            unit_price=product_in.unit_price,
            cost_price=product_in.cost_price,
            allowed_discount_percent=product_in.allowed_discount_percent,
            is_active=product_in.is_active,
        )
        db.add(product)
        db.commit()
        db.refresh(product)

        # Audit log
        audit = AuditLog(
            user_id=current_user.id if current_user else None,
            entity_type="PRODUCT",
            entity_id=product.id,
            action="CREATE",
            old_value=None,
            new_value=json.dumps({"sku": product.sku, "name": product.name, "unit_price": product.unit_price}),
        )
        db.add(audit)
        db.commit()

        return product

    def update_product(
        self,
        db: Session,
        product_id: int,
        product_update: ProductUpdate,
        current_user: Optional[User] = None,
    ) -> Product:
        product = self.get_product_by_id(db, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product with ID {product_id} not found"}
            )

        old_data = {
            "name": product.name,
            "unit_price": product.unit_price,
            "cost_price": product.cost_price,
            "allowed_discount_percent": product.allowed_discount_percent,
            "is_active": product.is_active,
        }

        update_dict = product_update.model_dump(exclude_unset=True)
        for field, val in update_dict.items():
            setattr(product, field, val)

        db.commit()
        db.refresh(product)

        # Audit log
        audit = AuditLog(
            user_id=current_user.id if current_user else None,
            entity_type="PRODUCT",
            entity_id=product.id,
            action="UPDATE",
            old_value=json.dumps(old_data),
            new_value=json.dumps(update_dict),
        )
        db.add(audit)
        db.commit()

        return product

    def delete_product(
        self, db: Session, product_id: int, current_user: Optional[User] = None, hard_delete: bool = False
    ) -> Product:
        product = self.get_product_by_id(db, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product with ID {product_id} not found"}
            )

        if hard_delete:
            db.delete(product)
            action = "DELETE"
        else:
            product.is_active = False
            action = "DEACTIVATE"

        # Audit log
        audit = AuditLog(
            user_id=current_user.id if current_user else None,
            entity_type="PRODUCT",
            entity_id=product_id,
            action=action,
            old_value=json.dumps({"is_active": True}),
            new_value=json.dumps({"is_active": False}),
        )
        db.add(audit)
        db.commit()
        return product

    def get_categories(self, db: Session) -> List[ProductCategory]:
        return db.query(ProductCategory).order_by(ProductCategory.name.asc()).all()

    def create_category(self, db: Session, cat_in: ProductCategoryCreate) -> ProductCategory:
        existing = db.query(ProductCategory).filter(ProductCategory.name == cat_in.name).first()
        if existing:
            return existing
        cat = ProductCategory(name=cat_in.name, description=cat_in.description)
        db.add(cat)
        db.commit()
        db.refresh(cat)
        return cat


product_service = ProductService()
