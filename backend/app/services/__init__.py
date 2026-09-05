from app.services.auth_service import auth_service, AuthService
from app.services.audit_service import audit_service, AuditService
from app.services.discount_service import discount_service, DiscountService
from app.services.approval_service import approval_service, ApprovalService
from app.services.quote_service import quote_service, QuoteService

__all__ = [
    "auth_service",
    "AuthService",
    "audit_service",
    "AuditService",
    "discount_service",
    "DiscountService",
    "approval_service",
    "ApprovalService",
    "quote_service",
    "QuoteService",
]
