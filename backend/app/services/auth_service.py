from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User, Role
from app.schemas.auth import UserCreate, TokenResponse, UserResponse
from app.core.security import verify_password, get_password_hash, create_access_token


class AuthService:
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email.lower().strip()).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        user = AuthService.get_user_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
        db_user = User(
            email=user_in.email.lower().strip(),
            hashed_password=get_password_hash(user_in.password),
            full_name=user_in.full_name,
            role=user_in.role,
            is_active=True
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def create_user_token(user: User) -> TokenResponse:
        claims = {
            "role": user.role.value,
            "email": user.email,
            "full_name": user.full_name
        }
        token = create_access_token(subject=str(user.id), claims=claims)
        user_response = UserResponse.model_validate(user)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=user_response
        )


auth_service = AuthService()
