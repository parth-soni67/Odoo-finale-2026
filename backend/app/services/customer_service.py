import json
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.customer import Customer, CustomerTier
from app.models.audit import AuditLog
from app.models.user import User, Role
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerService:
    def get_customers(
        self,
        db: Session,
        search: Optional[str] = None,
        tier: Optional[CustomerTier] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Customer]:
        query = db.query(Customer)
        if tier is not None:
            query = query.filter(Customer.tier == tier)
        if search:
            search_fmt = f"%{search}%"
            query = query.filter(
                (Customer.company_name.ilike(search_fmt))
                | (Customer.contact_name.ilike(search_fmt))
                | (Customer.email.ilike(search_fmt))
            )
        return query.order_by(Customer.id.asc()).offset(skip).limit(limit).all()

    def get_customer_by_id(self, db: Session, customer_id: int) -> Optional[Customer]:
        return db.query(Customer).filter(Customer.id == customer_id).first()

    def get_customer_by_email(self, db: Session, email: str) -> Optional[Customer]:
        return db.query(Customer).filter(Customer.email == email).first()

    def get_customer_for_user(self, db: Session, user: User) -> Customer:
        """Derive the Customer record corresponding to a User with Role.CUSTOMER.

        Matches:
        1. Exact email match (Customer.email == user.email)
        2. Domain match (user's email domain matches Customer's email domain, e.g. acmecorp.com)
        """
        # 1. Exact email
        customer = self.get_customer_by_email(db, user.email)
        if customer:
            return customer

        # 2. Domain match
        if "@" in user.email:
            domain = user.email.split("@")[1]
            candidates = db.query(Customer).filter(Customer.email.ilike(f"%@{domain}")).all()
            if candidates:
                return candidates[0]

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "CUSTOMER_PROFILE_NOT_FOUND",
                "message": f"No customer account is linked to user {user.email}",
            },
        )

    def create_customer(
        self, db: Session, customer_in: CustomerCreate, current_user: Optional[User] = None
    ) -> Customer:
        existing = self.get_customer_by_email(db, customer_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CUSTOMER_ALREADY_EXISTS", "message": f"Customer with email '{customer_in.email}' already exists"}
            )

        customer = Customer(
            company_name=customer_in.company_name,
            contact_name=customer_in.contact_name,
            email=customer_in.email,
            phone=customer_in.phone,
            tier=customer_in.tier,
            discount_ceiling=customer_in.discount_ceiling,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        audit = AuditLog(
            user_id=current_user.id if current_user else None,
            entity_type="CUSTOMER",
            entity_id=customer.id,
            action="CREATE",
            old_value=None,
            new_value=json.dumps({"company_name": customer.company_name, "email": customer.email, "tier": customer.tier.value}),
        )
        db.add(audit)
        db.commit()

        return customer

    def update_customer(
        self,
        db: Session,
        customer_id: int,
        customer_update: CustomerUpdate,
        current_user: Optional[User] = None,
    ) -> Customer:
        customer = self.get_customer_by_id(db, customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CUSTOMER_NOT_FOUND", "message": f"Customer with ID {customer_id} not found"}
            )

        old_data = {
            "company_name": customer.company_name,
            "contact_name": customer.contact_name,
            "email": customer.email,
            "phone": customer.phone,
            "tier": customer.tier.value,
            "discount_ceiling": customer.discount_ceiling,
        }

        update_dict = customer_update.model_dump(exclude_unset=True)
        for field, val in update_dict.items():
            setattr(customer, field, val)

        db.commit()
        db.refresh(customer)

        audit = AuditLog(
            user_id=current_user.id if current_user else None,
            entity_type="CUSTOMER",
            entity_id=customer.id,
            action="UPDATE",
            old_value=json.dumps(old_data),
            new_value=json.dumps({k: (v.value if hasattr(v, "value") else v) for k, v in update_dict.items()}),
        )
        db.add(audit)
        db.commit()

        return customer


customer_service = CustomerService()
