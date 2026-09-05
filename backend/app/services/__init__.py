from app.services.auth_service import auth_service, AuthService
from app.services.audit_service import audit_service, AuditService
from app.services.discount_service import discount_service, DiscountService
from app.services.approval_service import approval_service, ApprovalService
from app.services.quote_service import quote_service, QuoteService
from app.services.order_service import order_service, OrderService
from app.services.fulfillment_service import fulfillment_service, FulfillmentService
from app.services.billing_service import billing_service, BillingService
from app.services.product_service import product_service, ProductService
from app.services.customer_service import customer_service, CustomerService
from app.services.portal_service import portal_service, PortalService
from app.services.negotiation_service import negotiation_service, NegotiationService
from app.services.deal_health_service import deal_health_service, DealHealthService
from app.services.report_service import report_service, ReportService
from app.services.recommendation_service import recommendation_service, RecommendationService

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
    "order_service",
    "OrderService",
    "fulfillment_service",
    "FulfillmentService",
    "billing_service",
    "BillingService",
    "product_service",
    "ProductService",
    "customer_service",
    "CustomerService",
    "portal_service",
    "PortalService",
    "negotiation_service",
    "NegotiationService",
    "deal_health_service",
    "DealHealthService",
    "report_service",
    "ReportService",
    "recommendation_service",
    "RecommendationService",
]
