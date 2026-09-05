"""Recommendation Engine Service (M6 Upsell & Cross-Sell).

Provides deterministic, rule-based product recommendations for quotations:
- UPSELL: Higher-value platform licenses and premium capacity upgrades.
- CROSS_SELL: Complementary maintenance/SLA support and professional services.
- Margin impact calculation: suggested_quantity * (unit_price - cost_price).
"""

from typing import List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.quote import Quote, QuoteLine, Recommendation
from app.models.product import Product, ProductCategory


class RecommendationService:
    @staticmethod
    def get_quote_recommendations(db: Session, quote_id: int) -> Dict[str, Any]:
        """Generates deterministic upsell and cross-sell recommendations for a quote."""
        quote = (
            db.query(Quote)
            .options(
                joinedload(Quote.lines).joinedload(QuoteLine.product).joinedload(Product.category),
                joinedload(Quote.recommendations),
            )
            .filter(Quote.id == quote_id)
            .first()
        )
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUOTE_NOT_FOUND", "message": f"Quote with ID {quote_id} does not exist"},
            )

        # Identify products already in the quote
        quote_product_ids = {line.product_id for line in quote.lines}

        # Query all active products from catalog
        active_products = (
            db.query(Product)
            .options(joinedload(Product.category))
            .filter(Product.is_active == True)
            .all()
        )

        # Candidates are active catalog products NOT already in the quote
        candidates = [p for p in active_products if p.id not in quote_product_ids]

        if not candidates or not quote.lines:
            # If no candidates or quote has no items, return empty list
            return {
                "quote_id": quote.id,
                "recommendations": [],
            }

        # Analyze existing quote characteristics
        quote_categories = set()
        max_quote_price = 0.0
        for line in quote.lines:
            if line.product:
                if line.product.category:
                    quote_categories.add(line.product.category.name)
                if line.unit_price and float(line.unit_price) > max_quote_price:
                    max_quote_price = float(line.unit_price)

        has_hardware = "Hardware" in quote_categories
        has_software = "Software" in quote_categories
        has_services = "Professional Services" in quote_categories
        has_support = "Maintenance & Support" in quote_categories

        scored_recommendations: List[Dict[str, Any]] = []

        for candidate in candidates:
            cat_name = candidate.category.name if candidate.category else ""
            unit_price = float(candidate.unit_price or 0.0)
            cost_price = float(candidate.cost_price or 0.0) if candidate.cost_price is not None else 0.0
            suggested_qty = 1
            margin_impact = round(suggested_qty * max(0.0, unit_price - cost_price), 2)

            rec_type = None
            reason = None
            priority = 0

            # 1. UPSELL: High-value Software / Platform upgrade when Hardware is selected
            if cat_name == "Software" and has_hardware:
                rec_type = "UPSELL"
                reason = f"Elevate hardware with central management and analytics via {candidate.name}"
                priority = 100

            # 2. UPSELL: Candidate has higher unit price than existing items
            elif unit_price > max_quote_price and max_quote_price > 0:
                rec_type = "UPSELL"
                reason = f"High-value tier expansion: upgrade operational capabilities with {candidate.name}"
                priority = 90

            # 3. CROSS_SELL: Maintenance & Support for active hardware or software
            elif cat_name == "Maintenance & Support" and not has_support:
                rec_type = "CROSS_SELL"
                reason = f"Protect operational continuity and uptime with {candidate.name}"
                priority = 85

            # 4. CROSS_SELL: Professional Services / Deployment for hardware or software
            elif cat_name == "Professional Services" and not has_services:
                rec_type = "CROSS_SELL"
                reason = f"Ensure turnkey installation, configuration, and ERP integration with {candidate.name}"
                priority = 80

            # 5. CROSS_SELL: Hardware appliances for software licenses
            elif cat_name == "Hardware" and has_software:
                rec_type = "CROSS_SELL"
                reason = f"Complement software licenses with certified {candidate.name} appliances"
                priority = 75

            # 6. Fallback general cross-sell
            else:
                rec_type = "CROSS_SELL"
                reason = f"Complements existing quote items with recommended {candidate.name}"
                priority = 50

            scored_recommendations.append({
                "product_id": candidate.id,
                "product_name": candidate.name,
                "type": rec_type,
                "reason": reason,
                "suggested_quantity": suggested_qty,
                "unit_price": unit_price,
                "estimated_margin_impact": margin_impact,
                "priority": priority,
            })

        # Sort deterministically: highest priority first, then highest margin impact
        scored_recommendations.sort(
            key=lambda x: (x["priority"], x["estimated_margin_impact"]),
            reverse=True,
        )

        # Limit to top 3 to 5 recommendations
        top_recommendations = scored_recommendations[:5]

        # Clean output items (remove internal priority field)
        clean_recommendations = [
            {
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "type": r["type"],
                "reason": r["reason"],
                "suggested_quantity": r["suggested_quantity"],
                "unit_price": r["unit_price"],
                "estimated_margin_impact": r["estimated_margin_impact"],
            }
            for r in top_recommendations
        ]

        # Persist to existing Recommendation database model
        try:
            quote.recommendations.clear()
            db.flush()
            for r in clean_recommendations:
                db_rec = Recommendation(
                    quote_id=quote.id,
                    product_id=r["product_id"],
                    recommendation_type=r["type"],
                    reason=r["reason"],
                    score=r["estimated_margin_impact"],
                )
                quote.recommendations.append(db_rec)
            db.commit()
        except Exception:
            db.rollback()

        return {
            "quote_id": quote.id,
            "recommendations": clean_recommendations,
        }


recommendation_service = RecommendationService()
