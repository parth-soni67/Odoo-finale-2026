from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.quote import Quote, QuoteStatus
from app.models.negotiation import Negotiation, NegotiationStatus
from app.models.customer import Customer
from app.models.product import Product
from app.services.deal_health_service import deal_health_service


class ReportService:
    def get_sales_summary(self, db: Session) -> Dict[str, Any]:
        quotes = db.query(Quote).all()
        customers_count = db.query(Customer).count()
        products_count = db.query(Product).count()
        active_negotiations_count = (
            db.query(Negotiation).filter(Negotiation.status == NegotiationStatus.PENDING).count()
        )

        total_quotes = len(quotes)
        approved_quotes = sum(1 for q in quotes if q.status in (QuoteStatus.APPROVED, QuoteStatus.ACCEPTED))
        pending_approvals = sum(1 for q in quotes if q.status == QuoteStatus.PENDING_APPROVAL or q.requires_approval)
        rejected_quotes = sum(1 for q in quotes if q.status == QuoteStatus.REJECTED)

        total_value = sum(q.total_amount for q in quotes)
        approved_value = sum(
            q.total_amount for q in quotes if q.status in (QuoteStatus.APPROVED, QuoteStatus.ACCEPTED)
        )

        # Count high-risk deals
        high_risk_count = 0
        for q in quotes:
            health = deal_health_service.calculate_deal_health(db, q)
            if health["risk_level"] == "HIGH_RISK":
                high_risk_count += 1

        return {
            "total_quotes": total_quotes,
            "approved_quotes": approved_quotes,
            "pending_approvals": pending_approvals,
            "rejected_quotes": rejected_quotes,
            "active_negotiations": active_negotiations_count,
            "total_quote_value": round(total_value, 2),
            "approved_quote_value": round(approved_value, 2),
            "high_risk_deals": high_risk_count,
            "customer_count": customers_count,
            "product_count": products_count,
        }


report_service = ReportService()
