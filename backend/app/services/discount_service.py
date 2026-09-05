"""Discount Governance & Risk Assessment Service.

Evaluates quote discounts at the individual line item and quote level against:
1. Product allowed discount percentages
2. Product cost price (margin floor / negative margin protection)
3. Customer tier-based discount rules and volume thresholds
4. Customer overall discount ceilings
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from app.models.quote import Quote, QuoteLine
from app.models.customer import Customer
from app.models.product import Product, DiscountRule


class DiscountService:
    @staticmethod
    def get_effective_line_limit(
        db: Session,
        customer: Customer,
        product: Product,
        quantity: int,
    ) -> float:
        """Determines the maximum allowable discount percentage for a specific line item.

        Combines:
        - Product baseline guardrail (product.allowed_discount_percent)
        - Specific active DiscountRule (category + tier + min_quantity)
        - Customer discount ceiling (customer.discount_ceiling)
        """
        # 1. Product baseline ceiling
        product_limit = float(product.allowed_discount_percent or 0.0)

        # 2. Check for active category-specific or tier-specific discount rules
        matching_rules = (
            db.query(DiscountRule)
            .filter(
                DiscountRule.is_active == True,
                (DiscountRule.customer_tier == customer.tier) | (DiscountRule.customer_tier.is_(None)),
                (DiscountRule.category_id == product.category_id) | (DiscountRule.category_id.is_(None)),
                DiscountRule.min_quantity <= quantity,
            )
            .order_by(
                DiscountRule.category_id.is_not(None).desc(),  # Category-specific rules first
                DiscountRule.min_quantity.desc(),               # Higher volume rules first
            )
            .all()
        )

        rule_limit: Optional[float] = None
        if matching_rules:
            # Most specific rule governs
            rule_limit = float(matching_rules[0].max_discount_percent)

        # 3. Customer ceiling
        customer_ceiling = float(customer.discount_ceiling if customer.discount_ceiling is not None else 10.0)

        # The effective limit for the customer tier
        tier_effective_limit = rule_limit if rule_limit is not None else customer_ceiling

        # The final allowed discount respects both product safety limit and tier/customer ceiling
        allowed_discount = min(product_limit, tier_effective_limit)
        return round(allowed_discount, 2)

    def calculate_quote_max_permissible_discount(
        self, db: Session, quote: Quote, allow_manager_override: bool = False
    ) -> Dict[str, Any]:
        """Calculates the value-weighted maximum permissible discount for the entire quotation,
        enforcing product discount caps, category rules, customer tier, margin floor,
        and customer discount ceiling.
        If allow_manager_override is True, customer tier/ceiling rules are bypassed in favor of
        product safety limits and margin floor protection.
        """
        customer = quote.customer
        if not customer:
            customer = db.query(Customer).filter(Customer.id == quote.customer_id).first()

        total_gross = 0.0
        max_discount_value = 0.0
        line_details = []

        for line in quote.lines:
            product = line.product
            if not product:
                product = db.query(Product).filter(Product.id == line.product_id).first()
            if not product:
                continue

            unit_price = float(line.unit_price)
            quantity = int(line.quantity)
            line_gross = round(unit_price * quantity, 2)
            total_gross += line_gross

            # 1. Line-level governance cap
            if allow_manager_override:
                gov_cap = float(product.allowed_discount_percent if product.allowed_discount_percent is not None else 100.0)
            else:
                gov_cap = self.get_effective_line_limit(db, customer, product, quantity)

            # 2. Margin floor cap (discounted unit price >= product cost price)
            if product.cost_price and float(product.cost_price) > 0 and unit_price > 0:
                cost = float(product.cost_price)
                margin_cap = max(0.0, ((unit_price - cost) / unit_price) * 100.0)
            else:
                margin_cap = 100.0

            line_max_allowed = max(0.0, min(gov_cap, margin_cap))
            line_discount_val = line_gross * (line_max_allowed / 100.0)
            max_discount_value += line_discount_val

            line_details.append({
                "line_id": line.id,
                "product_id": product.id,
                "product_name": product.name,
                "quantity": quantity,
                "unit_price": unit_price,
                "cost_price": float(product.cost_price) if product.cost_price else None,
                "line_gross": line_gross,
                "governance_cap": gov_cap,
                "margin_floor_cap": round(margin_cap, 2),
                "line_max_allowed_discount": round(line_max_allowed, 2),
                "line_max_discount_value": round(line_discount_val, 2),
            })

        if total_gross > 0:
            weighted_max_percent = (max_discount_value / total_gross) * 100.0
        else:
            weighted_max_percent = 0.0

        if allow_manager_override:
            quote_max_permissible = round(weighted_max_percent, 2)
            cust_ceiling = float(customer.discount_ceiling if customer and customer.discount_ceiling is not None else 100.0)
        else:
            cust_ceiling = float(customer.discount_ceiling if customer and customer.discount_ceiling is not None else 10.0)
            quote_max_permissible = min(weighted_max_percent, cust_ceiling)
            quote_max_permissible = round(quote_max_permissible, 2)

        return {
            "quote_subtotal": round(total_gross, 2),
            "max_discount_value": round(max_discount_value, 2),
            "weighted_max_discount_percent": round(weighted_max_percent, 2),
            "customer_ceiling": cust_ceiling,
            "quote_max_permissible_discount": quote_max_permissible,
            "lines": line_details,
        }

    def allocate_quote_discount(
        self, db: Session, quote: Quote, target_overall_percent: float, allow_manager_override: bool = False
    ) -> Dict[str, Any]:
        """Allocates a target overall quotation discount across individual lines while strictly
        respecting each line's:
        1. product.allowed_discount_percent
        2. category-level and tier-level discount rules
        3. customer.discount_ceiling
        4. margin floor (cost price protection: discounted_unit_price >= cost_price)

        Ensures sum(line discount amounts) / quote subtotal ≈ target_overall_percent within rounding tolerance.
        Updates line.discount_percent, line.discount_amount, line.line_total, quote.subtotal,
        quote.total_discount, and quote.total_amount.
        """
        gov = self.calculate_quote_max_permissible_discount(db, quote, allow_manager_override=allow_manager_override)
        total_subtotal = gov["quote_subtotal"]
        max_discount_value = gov["max_discount_value"]
        lines_gov = {l["line_id"]: l for l in gov["lines"]}

        if total_subtotal <= 0 or not quote.lines:
            return gov

        target_pct = max(0.0, float(target_overall_percent))
        target_discount_val = round(total_subtotal * (target_pct / 100.0), 2)
        target_discount_val = min(target_discount_val, max_discount_value)

        # 1. Base allocation: assign min(target_pct, line_cap) to each line
        base_line_data = {}
        sum_base_discount = 0.0
        headroom_dict = {}

        for line in quote.lines:
            l_info = lines_gov.get(line.id)
            line_gross = round(float(line.unit_price) * int(line.quantity), 2)
            if not l_info:
                base_line_data[line.id] = {"pct": 0.0, "amount": 0.0, "gross": line_gross, "cap": 0.0}
                continue

            max_cap = float(l_info["line_max_allowed_discount"])
            base_pct = min(target_pct, max_cap)
            base_disc = round(line_gross * (base_pct / 100.0), 2)
            base_line_data[line.id] = {"pct": base_pct, "amount": base_disc, "gross": line_gross, "cap": max_cap}
            sum_base_discount += base_disc

            # Remaining headroom beyond base discount
            max_line_disc = round(line_gross * (max_cap / 100.0), 2)
            line_headroom = max(0.0, max_line_disc - base_disc)
            if line_headroom > 0:
                headroom_dict[line.id] = line_headroom

        # 2. Shortfall redistribution: if some lines were capped below target_pct, distribute shortfall to lines with headroom
        shortfall = round(target_discount_val - sum_base_discount, 2)
        total_headroom = round(sum(headroom_dict.values()), 2)

        if shortfall > 0 and total_headroom > 0:
            redistributed_sum = 0.0
            for line in quote.lines:
                if line.id not in headroom_dict:
                    continue
                h = headroom_dict[line.id]
                extra = min(h, round(shortfall * (h / total_headroom), 2))
                base_line_data[line.id]["amount"] = round(base_line_data[line.id]["amount"] + extra, 2)
                redistributed_sum += extra

        # 3. Fine-tune rounding difference on lines with remaining headroom
        current_allocated = sum(d["amount"] for d in base_line_data.values())
        rounding_diff = round(target_discount_val - current_allocated, 2)
        if abs(rounding_diff) >= 0.01:
            for line in sorted(quote.lines, key=lambda l: float(l.unit_price) * int(l.quantity), reverse=True):
                data = base_line_data.get(line.id)
                if not data:
                    continue
                max_line_disc = round(data["gross"] * (data["cap"] / 100.0), 2)
                new_amount = round(data["amount"] + rounding_diff, 2)
                if 0.0 <= new_amount <= max_line_disc:
                    data["amount"] = new_amount
                    break

        # 4. Commit changes to quote line models
        accum_subtotal = 0.0
        accum_discount = 0.0

        for line in quote.lines:
            d = base_line_data.get(line.id)
            if not d:
                continue
            line_gross = d["gross"]
            line_disc = d["amount"]
            line_pct = round((line_disc / line_gross) * 100.0, 2) if line_gross > 0 else 0.0
            line_tot = round(line_gross - line_disc, 2)

            line.discount_percent = line_pct
            line.discount_amount = line_disc
            line.line_total = line_tot

            accum_subtotal += line_gross
            accum_discount += line_disc

        quote.subtotal = round(accum_subtotal, 2)
        quote.total_discount = round(accum_discount, 2)
        quote.total_amount = round(accum_subtotal - accum_discount, 2)

        return {
            "subtotal": quote.subtotal,
            "total_discount": quote.total_discount,
            "total_amount": quote.total_amount,
            "effective_overall_discount_percent": round((accum_discount / accum_subtotal) * 100.0, 2) if accum_subtotal > 0 else 0.0,
            "target_overall_discount_percent": target_pct,
            "max_permissible_discount_percent": gov["quote_max_permissible_discount"],
        }

    def evaluate_quote_risk(self, db: Session, quote: Quote) -> Dict[str, Any]:
        """Evaluates line-level and quote-level discount risks deterministically.

        Returns:
            Dict containing:
                - risk_score: float (0.0 to 100.0)
                - requires_approval: bool
                - requires_manager_approval: bool
                - requires_finance_approval: bool
                - violations: List[Dict]
                - reasons: List[str]
        """
        customer = quote.customer
        if not customer:
            customer = db.query(Customer).filter(Customer.id == quote.customer_id).first()

        violations: List[Dict[str, Any]] = []
        reasons: List[str] = []

        total_gross = 0.0
        total_discount_val = 0.0
        max_line_excess = 0.0
        weighted_excess_sum = 0.0
        has_negative_margin = False

        for line in quote.lines:
            product = line.product
            if not product:
                product = db.query(Product).filter(Product.id == line.product_id).first()
            if not product:
                continue

            unit_price = float(line.unit_price)
            quantity = int(line.quantity)
            discount_pct = float(line.discount_percent or 0.0)
            gross = round(unit_price * quantity, 2)
            discount_val = round(gross * (discount_pct / 100.0), 2)

            total_gross += gross
            total_discount_val += discount_val

            # Line-level governance
            allowed_limit = self.get_effective_line_limit(db, customer, product, quantity)

            # Check for discount policy violation
            if discount_pct > allowed_limit:
                excess = round(discount_pct - allowed_limit, 2)
                if excess > max_line_excess:
                    max_line_excess = excess

                violations.append({
                    "product": product.name,
                    "product_id": product.id,
                    "line_id": line.id,
                    "allowed_discount": allowed_limit,
                    "requested_discount": discount_pct,
                    "excess": excess,
                })
                reasons.append(
                    f"Line '{product.name}': requested discount {discount_pct:.1f}% exceeds allowed limit {allowed_limit:.1f}% by {excess:.1f}%"
                )

            # Margin floor check: selling below unit cost price
            discounted_unit_price = unit_price * (1.0 - (discount_pct / 100.0))
            if product.cost_price and discounted_unit_price < float(product.cost_price):
                has_negative_margin = True
                loss_per_unit = round(float(product.cost_price) - discounted_unit_price, 2)
                reasons.append(
                    f"Line '{product.name}': selling price (${discounted_unit_price:.2f}) drops below cost (${product.cost_price:.2f}), loss ${loss_per_unit:.2f}/unit"
                )

        # Check overall quote-level discount against customer ceiling
        quote_discount_pct = round((total_discount_val / total_gross * 100.0), 2) if total_gross > 0 else 0.0
        cust_ceiling = float(customer.discount_ceiling if customer and customer.discount_ceiling is not None else 10.0)
        ceiling_excess = 0.0
        if quote_discount_pct > cust_ceiling:
            ceiling_excess = round(quote_discount_pct - cust_ceiling, 2)
            reasons.append(
                f"Quote total discount {quote_discount_pct:.1f}% exceeds customer ceiling of {cust_ceiling:.1f}% by {ceiling_excess:.1f}%"
            )

        # Compute weighted excess for lines
        if total_gross > 0 and violations:
            for v in violations:
                # Approximate weight
                for line in quote.lines:
                    if line.product_id == v["product_id"]:
                        line_gross = float(line.unit_price) * float(line.quantity)
                        weight = line_gross / total_gross
                        weighted_excess_sum += v["excess"] * weight
                        break

        # --- Deterministic Risk Scoring Formula (0 to 100) ---
        # 1. Base Score
        if violations or ceiling_excess > 0 or has_negative_margin:
            # Policy violation baseline
            base_score = 34.0

            # Contribution from maximum line excess (e.g. 8% excess gives 36 points)
            excess_contribution = max_line_excess * 4.5

            # Contribution from weighted aggregate excess
            weighted_contribution = weighted_excess_sum * 1.5

            # Penalty for negative margin
            margin_penalty = 35.0 if has_negative_margin else 0.0

            # Penalty for quote-level ceiling breach
            ceiling_penalty = ceiling_excess * 2.0

            raw_score = base_score + excess_contribution + weighted_contribution + margin_penalty + ceiling_penalty
            risk_score = round(min(100.0, max(36.0, raw_score)), 0)
        else:
            # No violations: low proportional risk based on discount consumption of allowable ceiling
            ratio = (quote_discount_pct / max(cust_ceiling, 1.0)) if cust_ceiling > 0 else 0.0
            risk_score = round(min(25.0, ratio * 20.0), 1)

        # --- Approval Determination ---
        # Low risk (< 35): No approval required
        # Moderate risk (35 <= score < 75): Manager approval required
        # High risk (score >= 75 OR negative margin OR excess > 15% OR total discount > 30%): Both Manager & Finance approval required
        requires_manager_approval = False
        requires_finance_approval = False

        if risk_score >= 75.0 or has_negative_margin or max_line_excess > 15.0 or quote_discount_pct > 30.0:
            requires_manager_approval = True
            requires_finance_approval = True
        elif risk_score >= 35.0 or len(violations) > 0 or ceiling_excess > 0:
            requires_manager_approval = True
            requires_finance_approval = False

        requires_approval = requires_manager_approval or requires_finance_approval

        gov = self.calculate_quote_max_permissible_discount(db, quote)
        quote_max_permissible = gov["quote_max_permissible_discount"]

        return {
            "risk_score": float(risk_score),
            "requires_approval": requires_approval,
            "requires_manager_approval": requires_manager_approval,
            "requires_finance_approval": requires_finance_approval,
            "violations": violations,
            "reasons": reasons,
            "quote_discount_percent": quote_discount_pct,
            "quote_max_permissible_discount": quote_max_permissible,
        }


discount_service = DiscountService()
