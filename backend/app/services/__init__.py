from app.services.auth_service import auth_service, AuthService
from app.services.product_service import product_service, ProductService
from app.services.customer_service import customer_service, CustomerService
from app.services.portal_service import portal_service, PortalService
from app.services.negotiation_service import negotiation_service, NegotiationService
from app.services.deal_health_service import deal_health_service, DealHealthService
from app.services.report_service import report_service, ReportService

__all__ = [
    "auth_service",
    "AuthService",
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
]
