from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User, Role
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, UserCreate
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(
    signup_data: UserCreate,
    db: Session = Depends(get_db)
) -> UserResponse:
    """Registers a new user account (public signup strictly assigns CUSTOMER role)."""
    existing_user = auth_service.get_user_by_email(db, signup_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMAIL_EXISTS", "message": "An account with this email already exists."}
        )

    # Prevent privilege escalation: public signup always creates CUSTOMER
    signup_data.role = Role.CUSTOMER
    user = auth_service.create_user(db, signup_data)

    # Ensure corresponding Customer profile exists for portal integration
    from app.models.customer import Customer, CustomerTier
    existing_cust = db.query(Customer).filter(Customer.email == user.email).first()
    if not existing_cust:
        company_name = f"{user.full_name}'s Company" if user.full_name else "Customer Company"
        new_cust = Customer(
            company_name=company_name,
            contact_name=user.full_name,
            email=user.email,
            tier=CustomerTier.STANDARD,
            discount_ceiling=10.0,
        )
        db.add(new_cust)
        db.commit()

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """Authenticates a user and issues a signed JWT access token."""
    user = auth_service.authenticate_user(
        db,
        email=login_data.email,
        password=login_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INACTIVE_USER", "message": "Account is inactive"}
        )
    return auth_service.create_user_token(user)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """Returns profile details for the currently authenticated user."""
    return UserResponse.model_validate(current_user)
