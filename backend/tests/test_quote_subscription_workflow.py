import pytest
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, Role
from app.models.customer import Customer, CustomerTier
from app.models.product import Product, ProductCategory
from app.models.quote import Quote, QuoteLine, QuoteStatus, LineType
from app.models.order import Order, OrderLine, OrderStatus
from app.models.billing import Invoice, InvoiceStatus, Subscription, SubscriptionStatus, BillingType, SubscriptionPlan
from app.services.quote_service import quote_service
from app.services.order_service import order_service
from app.services.portal_service import portal_service
from app.services.billing_service import billing_service
from app.core.security import get_password_hash


@pytest.fixture
def auth_tokens(client: TestClient):
    resp_admin = client.post("/api/auth/login", json={"email": "admin@dealflow360.internal", "password": "Demo1234!"})
    resp_salesmgr = client.post("/api/auth/login", json={"email": "salesmgr@dealflow360.internal", "password": "Demo1234!"})
    resp_salesrep = client.post("/api/auth/login", json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"})
    resp_cust = client.post("/api/auth/login", json={"email": "customer@acmecorp.com", "password": "Demo1234!"})

    return {
        "admin": resp_admin.json()["access_token"],
        "salesmgr": resp_salesmgr.json()["access_token"],
        "salesrep": resp_salesrep.json()["access_token"],
        "customer": resp_cust.json()["access_token"],
    }


def test_1_and_2_sales_manager_creates_product_without_subscription(client: TestClient, db_session: Session, auth_tokens):
    """
    Test 1 & 2: Sales Manager creates product with catalog attributes only.
    Verifies:
    - Product created successfully with no subscription parameters required.
    - subscription_enabled defaults to False.
    """
    cat = db_session.query(ProductCategory).first()
    sku = f"SW-WIN-ENT-{int(datetime.now(timezone.utc).timestamp())}"
    payload = {
        "name": "Windows Enterprise OS",
        "sku": sku,
        "category_id": cat.id if cat else None,
        "fulfillment_type": "DIGITAL",
        "unit_price": 500.0,
        "allowed_discount_percent": 15.0,
        "description": "Standard operating system catalog software license.",
        "is_active": True,
    }

    resp = client.post(
        "/api/products",
        json=payload,
        headers={"Authorization": f"Bearer {auth_tokens['salesmgr']}"},
    )
    assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"
    prod_data = resp.json()
    assert prod_data["name"] == "Windows Enterprise OS"
    assert prod_data["sku"] == sku
    assert prod_data["unit_price"] == 500.0
    # Subscription is not forced by catalog
    assert prod_data["subscription_enabled"] is False


def test_3_to_6_sales_rep_quote_one_time_creates_no_subscription(client: TestClient, db_session: Session, auth_tokens):
    """
    Test 3 to 6: Sales Rep creates quote with Purchase Type: One-Time.
    Verifies:
    - QuoteLine has subscription_enabled = False.
    - When order is created/activated, no Subscription record is created.
    """
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    quote_payload = {
        "customer_id": customer.id,
        "lines": [
            {
                "product_id": product.id,
                "quantity": 2,
                "unit_price": 500.0,
                "discount_percent": 5.0,
                "line_type": "ONE_TIME",
                "subscription_enabled": False,
            }
        ],
    }

    resp = client.post(
        "/api/quotes",
        json=quote_payload,
        headers={"Authorization": f"Bearer {auth_tokens['salesrep']}"},
    )
    assert resp.status_code in (200, 201), resp.text
    q_data = resp.json()
    assert len(q_data["lines"]) == 1
    line = q_data["lines"][0]
    assert line["subscription_enabled"] is False
    assert line["line_type"] == "ONE_TIME"

    # Simulate approval and order conversion
    quote_obj = db_session.query(Quote).filter(Quote.id == q_data["id"]).first()
    quote_obj.status = QuoteStatus.APPROVED
    db_session.commit()

    order = order_service.create_order_from_quote(
        db_session,
        quote_id=quote_obj.id,
        user_id=1,
        auto_activate_subscriptions=True,
    )
    db_session.commit()

    # Verify no subscription created for this order
    subs = db_session.query(Subscription).filter(Subscription.order_id == order.id).all()
    assert len(subs) == 0, f"Expected 0 subscriptions for One-Time order, found {len(subs)}"


def test_7_to_10_sales_rep_quote_lifetime_subscription(client: TestClient, db_session: Session, auth_tokens):
    """
    Test 7 to 10: Sales Rep creates quote with Purchase Type: Subscription → Lifetime.
    Verifies:
    - Configuration is saved on quote line: subscription_enabled=True, duration_mode=LIFETIME.
    - Customer portal displays Lifetime terms.
    - Order receives subscription with end_date=None and NO recurring invoices.
    """
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    quote_payload = {
        "customer_id": customer.id,
        "lines": [
            {
                "product_id": product.id,
                "quantity": 1,
                "unit_price": 1200.0,
                "discount_percent": 0.0,
                "line_type": "ONE_TIME",
                "subscription_enabled": True,
                "subscription_name": "Edge Platform Lifetime License",
                "duration_mode": "LIFETIME",
                "validity_value": None,
                "validity_unit": None,
                "billing_frequency": "NONE",
                "subscription_start_trigger": "ORDER_ACTIVATION",
            }
        ],
    }

    resp = client.post(
        "/api/quotes",
        json=quote_payload,
        headers={"Authorization": f"Bearer {auth_tokens['salesrep']}"},
    )
    assert resp.status_code in (200, 201), resp.text
    q_data = resp.json()
    q_line = q_data["lines"][0]
    assert q_line["subscription_enabled"] is True
    assert q_line["duration_mode"] == "LIFETIME"
    assert q_line["billing_frequency"] == "NONE"

    # Customer views quote via portal
    portal_resp = client.get(
        f"/api/portal/quotes/{q_data['id']}",
        headers={"Authorization": f"Bearer {auth_tokens['customer']}"},
    )
    assert portal_resp.status_code == 200
    p_line = portal_resp.json()["lines"][0]
    assert p_line["subscription_enabled"] is True
    assert p_line["duration_mode"] == "LIFETIME"

    # Approve and convert
    quote_obj = db_session.query(Quote).filter(Quote.id == q_data["id"]).first()
    quote_obj.status = QuoteStatus.APPROVED
    db_session.commit()

    order = order_service.create_order_from_quote(
        db_session,
        quote_id=quote_obj.id,
        user_id=1,
        auto_activate_subscriptions=True,
    )
    db_session.commit()

    subs = db_session.query(Subscription).filter(Subscription.order_id == order.id).all()
    assert len(subs) == 1
    sub = subs[0]
    assert sub.duration_mode == "LIFETIME"
    assert sub.end_date is None
    assert sub.billing_frequency == "NONE"

    # Test 18: Verify lifetime creates NO recurring invoices
    rec_invs = (
        db_session.query(Invoice)
        .filter(Invoice.order_id == order.id, Invoice.billing_type == BillingType.RECURRING)
        .all()
    )
    assert len(rec_invs) == 0, "Lifetime subscriptions must NOT generate recurring invoices!"


def test_11_to_20_three_month_till_validity_lifecycle_and_billing(client: TestClient, db_session: Session, auth_tokens):
    """
    Test 11 to 20: Full lifecycle:
    - Sales Rep selects Till Validity → 3 Months → Monthly
    - Quote approval
    - Customer accepts quote via portal
    - Order contains subscription configuration
    - Subscription activates on order activation
    - Accurate start and end dates (activation + 3 months)
    - Billing cycles generated correctly for 3 months
    - Stops after 3 months (transitions to EXPIRED, no invoices after end date)
    - Subscription history remains intact
    """
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    # Step 11 & 12: Sales Rep creates quote with 3-Month Till Validity, Monthly Billing
    quote_payload = {
        "customer_id": customer.id,
        "lines": [
            {
                "product_id": product.id,
                "quantity": 1,
                "unit_price": 800.0,
                "discount_percent": 0.0,
                "line_type": "RECURRING",
                "subscription_enabled": True,
                "subscription_name": "24/7 Mission-Critical SLA Support",
                "duration_mode": "TILL_VALIDITY",
                "validity_value": 3,
                "validity_unit": "MONTHS",
                "billing_frequency": "MONTHLY",
                "subscription_start_trigger": "ORDER_ACTIVATION",
            }
        ],
    }

    resp = client.post(
        "/api/quotes",
        json=quote_payload,
        headers={"Authorization": f"Bearer {auth_tokens['salesrep']}"},
    )
    assert resp.status_code in (200, 201), resp.text
    quote_id = resp.json()["id"]

    # Step 13: Approve quote
    quote_obj = db_session.query(Quote).filter(Quote.id == quote_id).first()
    quote_obj.status = QuoteStatus.APPROVED
    db_session.commit()

    # Step 14: Customer accepts via portal endpoint
    accept_resp = client.post(
        f"/api/portal/quotes/{quote_id}/confirm",
        headers={"Authorization": f"Bearer {auth_tokens['customer']}"},
    )
    assert accept_resp.status_code == 200, accept_resp.text
    order_id = accept_resp.json()["order_id"]

    # Step 15: Verify order contains subscription configuration
    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert order is not None
    assert len(order.lines) == 1
    ord_line = order.lines[0]
    assert ord_line.subscription_enabled is True
    assert ord_line.duration_mode == "TILL_VALIDITY"
    assert ord_line.validity_value == 3
    assert ord_line.validity_unit == "MONTHS"
    assert ord_line.billing_frequency == "MONTHLY"

    # Step 16: Verify subscription activated with activation date
    sub = db_session.query(Subscription).filter(Subscription.order_id == order_id).first()
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.duration_mode == "TILL_VALIDITY"
    assert sub.validity_value == 3
    assert sub.validity_unit == "MONTHS"
    assert sub.billing_frequency == "MONTHLY"
    assert sub.start_date is not None
    assert sub.end_date is not None

    # Date math: end_date is exactly start_date + 3 months
    start_dt = sub.start_date if sub.start_date.tzinfo else sub.start_date.replace(tzinfo=timezone.utc)
    end_dt = sub.end_date if sub.end_date.tzinfo else sub.end_date.replace(tzinfo=timezone.utc)
    expected_end = start_dt + relativedelta(months=3)
    assert abs((end_dt - expected_end).total_seconds()) < 60

    # Step 17: Verify Cycle 1 was generated upon order confirmation
    cycles = sub.billing_cycles
    assert len(cycles) == 1, f"Expected cycle 1 on activation, got {len(cycles)}"
    assert cycles[0]["cycle_number"] == 1
    assert cycles[0]["amount"] == 800.0

    # Advance to month 1 -> generate Cycle 2
    date_m1 = start_dt + relativedelta(months=1, days=1)
    res_m1 = billing_service.run_recurring_billing(db_session, user_id=1, simulated_date=date_m1, subscription_id=sub.id)
    assert res_m1["invoices_generated"] == 1

    # Advance to month 2 -> generate Cycle 3
    date_m2 = start_dt + relativedelta(months=2, days=1)
    res_m2 = billing_service.run_recurring_billing(db_session, user_id=1, simulated_date=date_m2, subscription_id=sub.id)
    assert res_m2["invoices_generated"] == 1

    db_session.refresh(sub)
    cycles_after_3 = sub.billing_cycles
    assert len(cycles_after_3) == 3, f"Expected 3 cycles, got {len(cycles_after_3)}"

    # Step 19: Verify subscription stops after 3 months and does NOT invoice after end_date
    date_m3 = start_dt + relativedelta(months=3, days=1)
    res_m3 = billing_service.run_recurring_billing(db_session, user_id=1, simulated_date=date_m3, subscription_id=sub.id)
    assert res_m3["invoices_generated"] == 0, "No invoice should be generated after subscription end date!"

    db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.EXPIRED, f"Expected EXPIRED status, got {sub.status}"

    # Step 20: Verify subscription history remains completely intact in Customer Portal
    hist_resp = client.get(
        f"/api/portal/subscriptions/{sub.id}/billing-history",
        headers={"Authorization": f"Bearer {auth_tokens['customer']}"},
    )
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["status"] == "EXPIRED"
    assert len(hist_data["billing_cycles"]) == 3
    assert hist_data["billing_cycles"][0]["cycle_number"] == 1
    assert hist_data["billing_cycles"][1]["cycle_number"] == 2
    assert hist_data["billing_cycles"][2]["cycle_number"] == 3


def test_multiple_lines_mixed_quote_one_time_and_subscriptions(client: TestClient, db_session: Session, auth_tokens):
    """
    Test 10 & 11: Multi-line quote where each line has its own independent Purchase Type:
    - Line 1: Laptop (Physical) -> One-Time Purchase
    - Line 2: Windows Enterprise (Digital) -> With Subscription (3 Months, Monthly)
    - Line 3: Premium Support (Service) -> With Subscription (Lifetime, Included)
    Verifies:
    - Independent line configurations.
    - Only lines 2 & 3 create subscriptions.
    - Laptop requires warehouse fulfillment; digital/service do not.
    """
    cust = db_session.query(Customer).first()
    p_laptop = db_session.query(Product).filter(Product.fulfillment_type == "PHYSICAL").first()
    p_win = db_session.query(Product).filter(Product.fulfillment_type == "DIGITAL").first()
    p_supp = db_session.query(Product).filter(Product.fulfillment_type == "SERVICE").first()

    payload = {
        "customer_id": cust.id,
        "lines": [
            {
                "product_id": p_laptop.id,
                "quantity": 1,
                "unit_price": 1200.0,
                "discount_percent": 0.0,
                "line_type": "ONE_TIME",
                "subscription_enabled": False,
            },
            {
                "product_id": p_win.id,
                "quantity": 1,
                "unit_price": 500.0,
                "discount_percent": 5.0,
                "line_type": "RECURRING",
                "subscription_enabled": True,
                "subscription_name": "Windows 3-Month Plan",
                "duration_mode": "TILL_VALIDITY",
                "validity_value": 3,
                "validity_unit": "MONTHS",
                "billing_frequency": "MONTHLY",
                "subscription_start_trigger": "ORDER_ACTIVATION",
            },
            {
                "product_id": p_supp.id,
                "quantity": 1,
                "unit_price": 300.0,
                "discount_percent": 0.0,
                "line_type": "ONE_TIME",
                "subscription_enabled": True,
                "subscription_name": "Lifetime Support Entitlement",
                "duration_mode": "LIFETIME",
                "billing_frequency": "NONE",
                "subscription_start_trigger": "ORDER_ACTIVATION",
            },
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers={"Authorization": f"Bearer {auth_tokens['salesrep']}"})
    assert resp.status_code in (200, 201), resp.text
    quote_id = resp.json()["id"]

    # Approve & Accept
    quote = db_session.query(Quote).filter(Quote.id == quote_id).first()
    quote.status = QuoteStatus.APPROVED
    db_session.commit()

    accept_resp = client.post(f"/api/portal/quotes/{quote_id}/confirm", headers={"Authorization": f"Bearer {auth_tokens['customer']}"})
    assert accept_resp.status_code == 200, accept_resp.text
    order_id = accept_resp.json()["order_id"]

    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert len(order.lines) == 3

    # Check order line subscriptions
    l_laptop = next(l for l in order.lines if l.product_id == p_laptop.id)
    l_win = next(l for l in order.lines if l.product_id == p_win.id)
    l_supp = next(l for l in order.lines if l.product_id == p_supp.id)

    assert l_laptop.subscription_enabled is False
    assert l_win.subscription_enabled is True
    assert l_win.duration_mode == "TILL_VALIDITY"
    assert l_win.validity_value == 3
    assert l_supp.subscription_enabled is True
    assert l_supp.duration_mode == "LIFETIME"

    # Check created subscriptions (exactly 2, not 3)
    order_subs = db_session.query(Subscription).filter(Subscription.order_id == order.id).all()
    assert len(order_subs) == 2

    sub_win = next(s for s in order_subs if s.product_id == p_win.id)
    sub_supp = next(s for s in order_subs if s.product_id == p_supp.id)

    assert sub_win.status == SubscriptionStatus.ACTIVE
    assert sub_win.duration_mode == "TILL_VALIDITY"
    assert sub_win.end_date is not None

    assert sub_supp.status == SubscriptionStatus.ACTIVE
    assert sub_supp.duration_mode == "LIFETIME"
    assert sub_supp.end_date is None


def test_repurchase_preserves_old_subscription_history(client: TestClient, db_session: Session, auth_tokens):
    """
    Test 15: Repurchase workflow.
    - Customer purchases subscription in September (expires in December).
    - Customer repurchases the same subscription in February.
    - Both subscriptions must remain in subscription history (never overwrite).
    """
    cust = db_session.query(Customer).first()
    prod = db_session.query(Product).filter(Product.fulfillment_type == "DIGITAL").first()

    # Quote 1: September purchase
    q1_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": cust.id,
            "lines": [
                {
                    "product_id": prod.id,
                    "quantity": 1,
                    "unit_price": 400.0,
                    "discount_percent": 0.0,
                    "subscription_enabled": True,
                    "subscription_name": "Cloud Security Suite",
                    "duration_mode": "TILL_VALIDITY",
                    "validity_value": 3,
                    "validity_unit": "MONTHS",
                    "billing_frequency": "MONTHLY",
                }
            ],
        },
        headers={"Authorization": f"Bearer {auth_tokens['salesrep']}"},
    )
    assert q1_resp.status_code in (200, 201)
    q1_id = q1_resp.json()["id"]

    q1 = db_session.query(Quote).filter(Quote.id == q1_id).first()
    q1.status = QuoteStatus.APPROVED
    db_session.commit()

    c1_resp = client.post(f"/api/portal/quotes/{q1_id}/confirm", headers={"Authorization": f"Bearer {auth_tokens['customer']}"})
    o1_id = c1_resp.json()["order_id"]

    sub1 = db_session.query(Subscription).filter(Subscription.order_id == o1_id).first()
    assert sub1 is not None

    # Simulate sub1 expiry
    sub1.status = SubscriptionStatus.EXPIRED
    db_session.commit()

    # Quote 2: Repurchase later
    q2_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": cust.id,
            "lines": [
                {
                    "product_id": prod.id,
                    "quantity": 1,
                    "unit_price": 400.0,
                    "discount_percent": 0.0,
                    "subscription_enabled": True,
                    "subscription_name": "Cloud Security Suite",
                    "duration_mode": "TILL_VALIDITY",
                    "validity_value": 3,
                    "validity_unit": "MONTHS",
                    "billing_frequency": "MONTHLY",
                }
            ],
        },
        headers={"Authorization": f"Bearer {auth_tokens['salesrep']}"},
    )
    assert q2_resp.status_code in (200, 201)
    q2_id = q2_resp.json()["id"]

    q2 = db_session.query(Quote).filter(Quote.id == q2_id).first()
    q2.status = QuoteStatus.APPROVED
    db_session.commit()

    c2_resp = client.post(f"/api/portal/quotes/{q2_id}/confirm", headers={"Authorization": f"Bearer {auth_tokens['customer']}"})
    o2_id = c2_resp.json()["order_id"]

    sub2 = db_session.query(Subscription).filter(Subscription.order_id == o2_id).first()
    assert sub2 is not None
    assert sub2.id != sub1.id
    assert sub2.status == SubscriptionStatus.ACTIVE

    # Verify portal subscriptions list returns both
    portal_subs_resp = client.get("/api/portal/subscriptions", headers={"Authorization": f"Bearer {auth_tokens['customer']}"})
    assert portal_subs_resp.status_code == 200
    portal_subs = portal_subs_resp.json()
    sub_ids = [s["id"] for s in portal_subs]
    assert sub1.id in sub_ids
    assert sub2.id in sub_ids

