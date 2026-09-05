"""Deterministic seed data for DealFlow360 hackathon environment.

NOTE: All credentials below are strictly for local/demo development.
DO NOT use these credentials in production environments.
"""

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.core.security import get_password_hash
from app.models.user import User, Role
from app.models.customer import Customer, CustomerTier
from app.models.product import ProductCategory, Product, DiscountRule
from app.models.warehouse import Warehouse, Inventory
from app.models.billing import SubscriptionPlan
from app.models.quote import Quote, QuoteLine, QuoteStatus, LineType
from app.models.negotiation import Negotiation, NegotiationStatus

# Common development password for all seed users
DEMO_PASSWORD = "Demo1234!"


def seed_database(db: Session) -> None:
    print("--- Starting DealFlow360 Database Seed ---")
    hashed_password = get_password_hash(DEMO_PASSWORD)

    # 1. Seed Users
    seed_users = [
        {"email": "admin@dealflow360.internal", "full_name": "Admin User", "role": Role.ADMIN},
        {"email": "salesrep@dealflow360.internal", "full_name": "Sam Representative", "role": Role.SALES_REP},
        {"email": "salesmgr@dealflow360.internal", "full_name": "Sarah Manager", "role": Role.SALES_MANAGER},
        {"email": "finance@dealflow360.internal", "full_name": "Fiona Finance", "role": Role.FINANCE},
        {"email": "ops@dealflow360.internal", "full_name": "Oscar Operations", "role": Role.OPERATIONS},
        {"email": "customer@acmecorp.com", "full_name": "Charlie Customer", "role": Role.CUSTOMER},
    ]

    for u_data in seed_users:
        existing = db.query(User).filter(User.email == u_data["email"]).first()
        if not existing:
            user = User(
                email=u_data["email"],
                full_name=u_data["full_name"],
                role=u_data["role"],
                hashed_password=hashed_password,
                is_active=True,
            )
            db.add(user)
            print(f"Created user: {u_data['email']} ({u_data['role'].value})")

    db.commit()

    # 2. Seed Customers
    seed_customers = [
        {
            "company_name": "Acme Corp",
            "contact_name": "Alice Smith",
            "email": "alice@acmecorp.com",
            "phone": "+1-555-0101",
            "tier": CustomerTier.STANDARD,
            "discount_ceiling": 10.0,
        },
        {
            "company_name": "TechNova Solutions",
            "contact_name": "Bob Jones",
            "email": "bob@technova.io",
            "phone": "+1-555-0102",
            "tier": CustomerTier.GROWTH,
            "discount_ceiling": 20.0,
        },
        {
            "company_name": "Global Logistics Inc",
            "contact_name": "Carol White",
            "email": "carol@globallogistics.com",
            "phone": "+1-555-0103",
            "tier": CustomerTier.ENTERPRISE,
            "discount_ceiling": 35.0,
        },
    ]

    for c_data in seed_customers:
        existing = db.query(Customer).filter(Customer.company_name == c_data["company_name"]).first()
        if not existing:
            customer = Customer(**c_data)
            db.add(customer)
            print(f"Created customer: {c_data['company_name']} ({c_data['tier'].value})")

    db.commit()

    # 3. Seed Product Categories
    categories = [
        {"name": "Hardware", "description": "Physical server hardware, gateways, and edge appliances"},
        {"name": "Software", "description": "Platform licensing, digital seats, and software modules"},
        {"name": "Professional Services", "description": "Implementation, architecture advisory, and deployment"},
        {"name": "Maintenance & Support", "description": "Recurring SLA support, patches, and 24/7 coverage"},
    ]

    cat_map = {}
    for cat in categories:
        existing = db.query(ProductCategory).filter(ProductCategory.name == cat["name"]).first()
        if not existing:
            existing = ProductCategory(**cat)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            print(f"Created category: {cat['name']}")
        cat_map[cat["name"]] = existing

    # 4. Seed Products
    products = [
        {
            "name": "Edge IoT Gateway Server",
            "sku": "HW-IOT-100",
            "category_id": cat_map["Hardware"].id,
            "description": "Industrial edge processing unit with redundant power supply",
            "unit_price": 1200.0,
            "cost_price": 800.0,
            "allowed_discount_percent": 15.0,
        },
        {
            "name": "DealFlow Enterprise Platform License",
            "sku": "SW-DF360-LIC",
            "category_id": cat_map["Software"].id,
            "description": "Annual enterprise sales operations platform perpetual license",
            "unit_price": 5000.0,
            "cost_price": 500.0,
            "allowed_discount_percent": 25.0,
        },
        {
            "name": "On-site Deployment & Integration Package",
            "sku": "SRV-DEPLOY-01",
            "category_id": cat_map["Professional Services"].id,
            "description": "Full turnkey configuration, testing, and ERP integration service",
            "unit_price": 2500.0,
            "cost_price": 1500.0,
            "allowed_discount_percent": 10.0,
        },
        {
            "name": "24/7 Mission-Critical SLA Support (Monthly)",
            "sku": "SUB-SUPP-247",
            "category_id": cat_map["Maintenance & Support"].id,
            "description": "Monthly continuous monitoring, incident escalation, and hotline support",
            "unit_price": 800.0,
            "cost_price": 200.0,
            "allowed_discount_percent": 20.0,
        },
    ]

    prod_map = {}
    for prod in products:
        existing = db.query(Product).filter(Product.sku == prod["sku"]).first()
        if not existing:
            existing = Product(**prod)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            print(f"Created product: {prod['name']} ({prod['sku']})")
        prod_map[prod["sku"]] = existing

    # 5. Seed Warehouses
    warehouses = [
        {"name": "Warehouse A (Chicago Central)", "location": "Chicago, IL", "is_active": True},
        {"name": "Warehouse B (Reno West Coast)", "location": "Reno, NV", "is_active": True},
    ]

    wh_map = {}
    for wh in warehouses:
        existing = db.query(Warehouse).filter(Warehouse.name == wh["name"]).first()
        if not existing:
            existing = Warehouse(**wh)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            print(f"Created warehouse: {wh['name']}")
        wh_map[wh["name"]] = existing

    # 6. Seed Inventory (Calculated for Split / Backorder Demos)
    # HW-IOT-100: Warehouse A (15 units) + Warehouse B (10 units) = 25 total
    # An order of 20 units forces multi-warehouse allocation (15 from A, 5 from B).
    # An order of 30 units triggers partial fulfillment and backorders.
    inventory_items = [
        {"warehouse_id": wh_map["Warehouse A (Chicago Central)"].id, "product_id": prod_map["HW-IOT-100"].id, "quantity_available": 15},
        {"warehouse_id": wh_map["Warehouse B (Reno West Coast)"].id, "product_id": prod_map["HW-IOT-100"].id, "quantity_available": 10},
        {"warehouse_id": wh_map["Warehouse A (Chicago Central)"].id, "product_id": prod_map["SW-DF360-LIC"].id, "quantity_available": 10000},
        {"warehouse_id": wh_map["Warehouse A (Chicago Central)"].id, "product_id": prod_map["SRV-DEPLOY-01"].id, "quantity_available": 500},
        {"warehouse_id": wh_map["Warehouse A (Chicago Central)"].id, "product_id": prod_map["SUB-SUPP-247"].id, "quantity_available": 1000},
    ]

    for inv in inventory_items:
        existing = db.query(Inventory).filter(
            Inventory.warehouse_id == inv["warehouse_id"],
            Inventory.product_id == inv["product_id"]
        ).first()
        if not existing:
            item = Inventory(**inv)
            db.add(item)
            print(f"Set inventory: Product {inv['product_id']} in Warehouse {inv['warehouse_id']} -> {inv['quantity_available']} units")
        else:
            existing.quantity_available = inv["quantity_available"]

    db.commit()

    # 7. Seed Discount Rules
    discount_rules = [
        {
            "name": "Standard Tier Base Guardrail",
            "customer_tier": CustomerTier.STANDARD,
            "category_id": None,
            "min_quantity": 1,
            "max_discount_percent": 10.0,
            "is_active": True,
        },
        {
            "name": "Growth Tier Hardware Volume Discount",
            "customer_tier": CustomerTier.GROWTH,
            "category_id": cat_map["Hardware"].id,
            "min_quantity": 5,
            "max_discount_percent": 20.0,
            "is_active": True,
        },
        {
            "name": "Enterprise Strategic Partner Discount",
            "customer_tier": CustomerTier.ENTERPRISE,
            "category_id": None,
            "min_quantity": 1,
            "max_discount_percent": 35.0,
            "is_active": True,
        },
    ]

    for rule in discount_rules:
        existing = db.query(DiscountRule).filter(DiscountRule.name == rule["name"]).first()
        if not existing:
            db.add(DiscountRule(**rule))
            print(f"Created discount rule: {rule['name']}")

    db.commit()

    # 8. Seed Subscription Plans
    subscription_plans = [
        {
            "name": "24/7 Mission-Critical SLA Plan",
            "billing_frequency": "monthly",
            "price": 800.0,
            "description": "Continuous monthly SLA monitoring and emergency hotlines",
        },
        {
            "name": "DealFlow Enterprise Maintenance Agreement",
            "billing_frequency": "annual",
            "price": 9000.0,
            "description": "Comprehensive annual platform maintenance and dedicated TAM",
        },
    ]

    for plan in subscription_plans:
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == plan["name"]).first()
        if not existing:
            db.add(SubscriptionPlan(**plan))
            print(f"Created subscription plan: {plan['name']}")

    db.commit()

    # 9. Seed Demo Quotes and Negotiations
    acme = db.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    technova = db.query(Customer).filter(Customer.company_name == "TechNova Solutions").first()
    global_log = db.query(Customer).filter(Customer.company_name == "Global Logistics Inc").first()
    salesrep = db.query(User).filter(User.email == "salesrep@dealflow360.internal").first()

    iot_prod = db.query(Product).filter(Product.sku == "HW-IOT-100").first()
    lic_prod = db.query(Product).filter(Product.sku == "SW-DF360-LIC").first()
    supp_prod = db.query(Product).filter(Product.sku == "SUB-SUPP-247").first()

    if acme and salesrep and iot_prod:
        # Quote 1: Acme Corp - Demo judge target quote
        q1 = db.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()
        if not q1:
            q1 = Quote(
                quote_number="Q-2026-001",
                customer_id=acme.id,
                created_by=salesrep.id,
                status=QuoteStatus.APPROVED,
                subtotal=3200.0,
                total_discount=232.0,
                total_amount=2968.0,
                risk_score=18.0,
                requires_approval=False,
            )
            db.add(q1)
            db.commit()
            db.refresh(q1)

            line1 = QuoteLine(
                quote_id=q1.id,
                product_id=iot_prod.id,
                quantity=2,
                unit_price=1200.0,
                discount_percent=8.0,
                discount_amount=192.0,
                line_total=2208.0,
                line_type=LineType.ONE_TIME,
            )
            line2 = QuoteLine(
                quote_id=q1.id,
                product_id=supp_prod.id if supp_prod else iot_prod.id,
                quantity=1,
                unit_price=800.0,
                discount_percent=5.0,
                discount_amount=40.0,
                line_total=760.0,
                line_type=LineType.RECURRING,
            )
            db.add_all([line1, line2])
            db.commit()
            print(f"Created demo quote: {q1.quote_number} (Acme Corp)")

        # Quote 2: TechNova - High Risk Deal
        if technova and lic_prod:
            q2 = db.query(Quote).filter(Quote.quote_number == "Q-2026-002").first()
            if not q2:
                q2 = Quote(
                    quote_number="Q-2026-002",
                    customer_id=technova.id,
                    created_by=salesrep.id,
                    status=QuoteStatus.PENDING_APPROVAL,
                    subtotal=10000.0,
                    total_discount=2500.0,
                    total_amount=7500.0,
                    risk_score=68.0,
                    requires_approval=True,
                )
                db.add(q2)
                db.commit()
                db.refresh(q2)

                q2_line = QuoteLine(
                    quote_id=q2.id,
                    product_id=lic_prod.id,
                    quantity=2,
                    unit_price=5000.0,
                    discount_percent=25.0,
                    discount_amount=2500.0,
                    line_total=7500.0,
                    line_type=LineType.ONE_TIME,
                )
                db.add(q2_line)
                db.commit()

                # Seed active negotiation on Q2
                neg = Negotiation(
                    quote_id=q2.id,
                    customer_id=technova.id,
                    requested_change="discount_percent",
                    previous_value="25.0",
                    proposed_value="28.0",
                    status=NegotiationStatus.PENDING,
                )
                db.add(neg)
                db.commit()
                print(f"Created demo quote: {q2.quote_number} (TechNova - Pending Negotiation)")

        # Quote 3: Global Logistics - Enterprise Deal
        if global_log and iot_prod:
            q3 = db.query(Quote).filter(Quote.quote_number == "Q-2026-003").first()
            if not q3:
                q3 = Quote(
                    quote_number="Q-2026-003",
                    customer_id=global_log.id,
                    created_by=salesrep.id,
                    status=QuoteStatus.APPROVED,
                    subtotal=12000.0,
                    total_discount=1800.0,
                    total_amount=10200.0,
                    risk_score=22.0,
                    requires_approval=False,
                )
                db.add(q3)
                db.commit()
                db.refresh(q3)

                q3_line = QuoteLine(
                    quote_id=q3.id,
                    product_id=iot_prod.id,
                    quantity=10,
                    unit_price=1200.0,
                    discount_percent=15.0,
                    discount_amount=1800.0,
                    line_total=10200.0,
                    line_type=LineType.ONE_TIME,
                )
                db.add(q3_line)
                db.commit()
                print(f"Created demo quote: {q3.quote_number} (Global Logistics)")

    print("--- Database Seeding Completed Successfully ---")


if __name__ == "__main__":
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        seed_database(session)
    finally:
        session.close()
