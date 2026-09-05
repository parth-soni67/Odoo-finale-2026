from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from app.models.quote import Quote, QuoteLine, QuoteStatus, Recommendation, DealHealthAlert
from app.models.negotiation import Negotiation, NegotiationStatus
from app.models.customer import Customer
from app.models.product import Product
from app.schemas.deal_health import (
    DealHealthSummaryResponse,
    DealHealthItem,
    DealHealthDetailResponse,
    DealHealthAlertResponse,
    RecommendationItem,
)


class DealHealthService:
    def calculate_deal_health(self, db: Session, quote: Quote) -> Dict[str, Any]:
        """Calculates deterministic deal health score (0-100), risk level, signals,

        next action, and recommendations for a quote.
        """
        score = 0.0
        signals = []
        recommendations = []

        customer = quote.customer
        ceiling = customer.discount_ceiling if customer else 10.0

        # 1. Discount Signals
        max_discount = max([line.discount_percent for line in quote.lines], default=0.0)
        if max_discount > ceiling:
            score += 35.0
            signals.append(f"Discount ({max_discount:.1f}%) exceeds customer tier ceiling ({ceiling:.1f}%)")
            recommendations.append(f"Discount exceeds {customer.company_name if customer else 'customer'}'s {ceiling:.0f}% ceiling. Review pricing governance.")
        elif max_discount >= 20.0:
            score += 25.0
            signals.append(f"High discount rate applied ({max_discount:.1f}%)")
        elif max_discount >= 10.0:
            score += 15.0
            signals.append(f"Moderate discount rate applied ({max_discount:.1f}%)")

        # 2. Active Negotiations
        pending_negs = [n for n in quote.negotiations if n.status == NegotiationStatus.PENDING]
        active_negotiation_status = None
        if pending_negs:
            score += 25.0
            neg = pending_negs[0]
            active_negotiation_status = f"PENDING ({neg.requested_change}: {neg.proposed_value})"
            signals.append(f"Active customer counter-offer pending: {neg.requested_change} -> {neg.proposed_value}")
            recommendations.append(f"Customer requested {neg.proposed_value} for {neg.requested_change}. Review margin impact.")

        # 3. Approval State
        if quote.status == QuoteStatus.PENDING_APPROVAL or quote.requires_approval:
            score += 20.0
            signals.append("Pending sales manager or finance approval")
            recommendations.append("Approval is pending. Follow up with sales manager.")
        elif quote.status == QuoteStatus.REJECTED:
            score += 40.0
            signals.append("Quote was previously rejected by reviewer")
            recommendations.append("Quote terms rejected. Schedule discovery call with customer to realign scope.")

        # 4. Revisions / Modifications
        if quote.updated_at is not None:
            score += 10.0
            signals.append("Quote revised post-creation")

        # 5. Margin Floor Heuristics
        for line in quote.lines:
            if line.product and line.product.cost_price > 0:
                net_unit_price = line.unit_price * (1.0 - (line.discount_percent / 100.0))
                margin_threshold = line.product.cost_price * 1.15  # 15% gross margin floor
                if net_unit_price < margin_threshold:
                    score += 25.0
                    signals.append(f"Low profit margin on {line.product.name} (near cost floor ${line.product.cost_price:.2f})")
                    recommendations.append(f"Line item '{line.product.name}' is near cost price. Bundle recurring services to offset margin erosion.")
                    break

        # Bound score between 0 and 100
        score = min(100.0, score)

        # Determine Risk Level
        if score >= 61.0:
            risk_level = "HIGH_RISK"
        elif score >= 31.0:
            risk_level = "MEDIUM_RISK"
        else:
            risk_level = "HEALTHY"

        # Determine Next Action
        if pending_negs:
            next_action = "Review customer negotiation counter-proposal"
        elif quote.status == QuoteStatus.PENDING_APPROVAL:
            next_action = "Follow up with Sales Manager for approval sign-off"
        elif quote.status == QuoteStatus.REJECTED:
            next_action = "Restructure pricing or submit exception request"
        elif risk_level == "HIGH_RISK":
            next_action = "Review deal economics with Finance"
        elif quote.status == QuoteStatus.APPROVED:
            next_action = "Follow up with customer to confirm and execute order"
        else:
            next_action = "Present proposal to customer stakeholder"

        # If healthy and no recommendations, add growth/upsell advisory
        if not recommendations:
            recommendations.append("Healthy deal parameters. Ready to proceed with contract confirmation.")

        return {
            "risk_score": score,
            "risk_level": risk_level,
            "signals": signals,
            "next_action": next_action,
            "recommendations": recommendations,
            "active_negotiation_status": active_negotiation_status,
        }

    def get_deal_health_summary(self, db: Session) -> DealHealthSummaryResponse:
        quotes = (
            db.query(Quote)
            .options(
                joinedload(Quote.customer),
                joinedload(Quote.lines).joinedload(QuoteLine.product),
                joinedload(Quote.negotiations),
            )
            .order_by(Quote.created_at.desc())
            .all()
        )

        total_active = len(quotes)
        healthy = 0
        medium = 0
        high = 0
        pending_approvals = 0
        active_negotiations = 0

        deal_items = []
        for q in quotes:
            health = self.calculate_deal_health(db, q)

            if health["risk_level"] == "HEALTHY":
                healthy += 1
            elif health["risk_level"] == "MEDIUM_RISK":
                medium += 1
            else:
                high += 1

            if q.status == QuoteStatus.PENDING_APPROVAL or q.requires_approval:
                pending_approvals += 1

            if any(n.status == NegotiationStatus.PENDING for n in q.negotiations):
                active_negotiations += 1

            deal_items.append(
                DealHealthItem(
                    quote_id=q.id,
                    quote_number=q.quote_number,
                    customer_id=q.customer_id,
                    customer_name=q.customer.company_name if q.customer else "Unknown",
                    customer_tier=q.customer.tier.value if q.customer else "STANDARD",
                    total_amount=q.total_amount,
                    risk_score=health["risk_score"],
                    risk_level=health["risk_level"],
                    approval_status=q.status.value,
                    requires_approval=q.requires_approval,
                    negotiation_status=health["active_negotiation_status"],
                    signals=health["signals"],
                    next_action=health["next_action"],
                    recommendations=health["recommendations"],
                    created_at=q.created_at,
                )
            )

        return DealHealthSummaryResponse(
            total_active_deals=total_active,
            healthy_count=healthy,
            medium_risk_count=medium,
            high_risk_count=high,
            pending_approval_count=pending_approvals,
            active_negotiations_count=active_negotiations,
            deals=deal_items,
        )

    def get_quote_deal_health(self, db: Session, quote_id: int) -> DealHealthDetailResponse:
        quote = (
            db.query(Quote)
            .options(
                joinedload(Quote.customer),
                joinedload(Quote.lines).joinedload(QuoteLine.product),
                joinedload(Quote.negotiations),
                joinedload(Quote.health_alerts),
                joinedload(Quote.recommendations),
            )
            .filter(Quote.id == quote_id)
            .first()
        )

        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUOTE_NOT_FOUND", "message": f"Quote {quote_id} not found"},
            )

        health = self.calculate_deal_health(db, quote)

        # Sync alerts and recommendations to DB if needed
        existing_alerts = quote.health_alerts
        existing_recs = quote.recommendations

        return DealHealthDetailResponse(
            quote_id=quote.id,
            quote_number=quote.quote_number,
            customer=quote.customer,
            total_amount=quote.total_amount,
            risk_score=health["risk_score"],
            risk_level=health["risk_level"],
            signals=health["signals"],
            next_action=health["next_action"],
            alerts=existing_alerts,
            recommendations=existing_recs,
            quote=quote,
        )


deal_health_service = DealHealthService()
