import pytest
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, Role
from app.models.customer import Customer, CustomerTier
from app.models.product import Product, ProductCategory, FulfillmentType
from app.models.order import Order, OrderLine, OrderStatus
from app.models.billing import Invoice, InvoiceLine, InvoiceStatus, BillingType, Subscription, SubscriptionStatus, Payment, PaymentStatus
from app.services.order_service import order_service
from app.services.billing_service import billing_service
from app.core.security import get_password_hash


@pytest.fixture
def auth_tokens(client: TestClient):
    resp_admin = client.post("/api/auth/login", json={"email": "admin@dealflow360.internal", "password": "Demo1234!"})
    resp_cust_a = client.post("/api/auth/login", json={"email": "customer@acmecorp.com", "password": "Demo1234!"})

    return {
        "admin": resp_admin.json()["access_token"],
        "customer_a": resp_cust_a.json()["access_token"],
    }


@pytest.fixture
def customer_b_setup(db_session: Session, client: TestClient):
    user_b = db_session.query(User).filter(User.email == "portal_user_b@corp.com").first()
    if not user_b:
        user_b = User(
            email="portal_user_b@corp.com",
            hashed_password=get_password_hash("Demo1234!"),
            full_name="Portal User B",
            role=Role.CUSTOMER,
            is_active=True,
        )
        db_session.add(user_b)
        db_session.flush()

    cust_b = db_session.query(Customer).filter(Customer.company_name == "Beta Corp").first()
    if not cust_b:
        cust_b = Customer(
            company_name="Beta Corp",
            contact_name="Beta Manager",
            email="portal_user_b@corp.com",
            tier=CustomerTier.GROWTH,
        )
        db_session.add(cust_b)
        db_session.flush()

    db_session.commit()

    resp = client.post("/api/auth/login", json={"email": "portal_user_b@corp.com", "password": "Demo1234!"})
    return {
        "token": resp.json()["access_token"],
        "customer": cust_b,
        "user": user_b,
    }


def test_1_three_month_subscription_billing_cycles(client: TestClient, db_session: Session, auth_tokens):
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    order = Order(
        order_number="ORD-TEST-3M-SUB-001",
        customer_id=customer.id,
        status=OrderStatus.CONFIRMED,
        total_amount=300.0,
        created_at=now,
    )
    db_session.add(order)
    db_session.flush()

    sub = Subscription(
        order_id=order.id,
        customer_id=customer.id,
        product_id=product.id,
        name="Cloud Analytics 3-Month",
        status=SubscriptionStatus.ACTIVE,
        duration_mode="TILL_VALIDITY",
        validity_value=3,
        validity_unit="MONTHS",
        billing_frequency="MONTHLY",
        start_date=now,
        end_date=now + relativedelta(months=3),
        next_billing_date=now + relativedelta(months=1),
    )
    db_session.add(sub)
    db_session.flush()

    # Create cycle 1 (initial order invoice)
    inv1 = Invoice(
        invoice_number="INV-3M-CYC-01",
        order_id=order.id,
        subscription_id=sub.id,
        customer_id=customer.id,
        billing_type=BillingType.RECURRING,
        period_start=now,
        period_end=now + relativedelta(months=1),
        status=InvoiceStatus.PAID,
        subtotal=100.0,
        tax=0.0,
        total_amount=100.0,
        created_at=now,
    )
    db_session.add(inv1)
    db_session.flush()

    # Run recurring generation at month 1
    run_date_m1 = now + relativedelta(months=1, days=1)
    billing_service.run_recurring_billing(db_session, user_id=1, simulated_date=run_date_m1, subscription_id=sub.id)
    # Run recurring generation at month 2
    run_date_m2 = now + relativedelta(months=2, days=1)
    billing_service.run_recurring_billing(db_session, user_id=1, simulated_date=run_date_m2, subscription_id=sub.id)
    db_session.commit()

    # Check cycles
    db_session.refresh(sub)
    cycles = sub.billing_cycles
    assert len(cycles) == 3, f"Expected 3 cycles, got {len(cycles)}"
    assert cycles[0]["cycle_number"] == 1
    assert cycles[1]["cycle_number"] == 2
    assert cycles[2]["cycle_number"] == 3

    # Dates are consecutive
    assert cycles[0]["period_end"] == cycles[1]["period_start"]
    assert cycles[1]["period_end"] == cycles[2]["period_start"]
    assert cycles[0]["amount"] == 100.0


def test_2_lifetime_subscription_no_recurring_cycles(client: TestClient, db_session: Session, auth_tokens):
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    order = Order(
        order_number="ORD-TEST-LIFETIME-001",
        customer_id=customer.id,
        status=OrderStatus.CONFIRMED,
        total_amount=999.0,
        created_at=now,
    )
    db_session.add(order)
    db_session.flush()

    sub = Subscription(
        order_id=order.id,
        customer_id=customer.id,
        product_id=product.id,
        name="Enterprise Lifetime License",
        status=SubscriptionStatus.ACTIVE,
        duration_mode="LIFETIME",
        validity_value=None,
        validity_unit=None,
        billing_frequency="NONE",
        start_date=now,
        end_date=None,
        next_billing_date=None,
    )
    db_session.add(sub)
    db_session.flush()

    # Lifetime order creates one one-time invoice
    inv = Invoice(
        invoice_number="INV-LIFE-001",
        order_id=order.id,
        subscription_id=sub.id,
        customer_id=customer.id,
        billing_type=BillingType.ONE_TIME,
        status=InvoiceStatus.PAID,
        subtotal=999.0,
        tax=0.0,
        total_amount=999.0,
        created_at=now,
    )
    db_session.add(inv)
    db_session.commit()

    # Recurring invoice generation run
    recurring = billing_service.run_recurring_billing(db_session, user_id=1, simulated_date=now + relativedelta(years=2), subscription_id=sub.id)
    assert recurring["invoices_generated"] == 0

    # Check cycles via API
    resp = client.get(
        f"/api/portal/subscriptions/{sub.id}/billing-history",
        headers={"Authorization": f"Bearer {auth_tokens['customer_a']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["duration_mode"] == "LIFETIME"
    assert data["end_date"] is None
    assert data["billing_frequency"] == "NONE"
    assert len(data["billing_cycles"]) == 0


def test_3_expired_subscription_handling(client: TestClient, db_session: Session, auth_tokens):
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    start_date = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2025, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

    sub = Subscription(
        customer_id=customer.id,
        product_id=product.id,
        name="Expired Quarterly Add-on",
        status=SubscriptionStatus.EXPIRED,
        duration_mode="TILL_VALIDITY",
        validity_value=3,
        validity_unit="MONTHS",
        billing_frequency="MONTHLY",
        start_date=start_date,
        end_date=end_date,
        next_billing_date=None,
    )
    db_session.add(sub)
    db_session.commit()

    # Try running recurring generator today
    res = billing_service.run_recurring_billing(db_session, user_id=1, simulated_date=datetime.now(timezone.utc), subscription_id=sub.id)
    assert res["invoices_generated"] == 0


def test_4_subscription_gap_and_repurchase(client: TestClient, db_session: Session, auth_tokens):
    """
    Customer had a 3-month subscription, expired. 2 months later purchased the same product again.
    Verifies:
    - 2 separate Subscription records exist
    - Old sub is EXPIRED with original dates
    - New sub is ACTIVE with new dates
    - Gap is clearly visible between old end_date and new start_date
    """
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    sub1_start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sub1_end = datetime(2025, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

    sub1 = Subscription(
        customer_id=customer.id,
        product_id=product.id,
        name="Pro Service Tier (Initial)",
        status=SubscriptionStatus.EXPIRED,
        duration_mode="TILL_VALIDITY",
        validity_value=3,
        validity_unit="MONTHS",
        billing_frequency="MONTHLY",
        start_date=sub1_start,
        end_date=sub1_end,
        next_billing_date=None,
    )
    db_session.add(sub1)

    # 2 months later (June 1)
    sub2_start = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    sub2_end = datetime(2025, 9, 1, 0, 0, 0, tzinfo=timezone.utc)

    sub2 = Subscription(
        customer_id=customer.id,
        product_id=product.id,
        name="Pro Service Tier (Renewed)",
        status=SubscriptionStatus.ACTIVE,
        duration_mode="TILL_VALIDITY",
        validity_value=3,
        validity_unit="MONTHS",
        billing_frequency="MONTHLY",
        start_date=sub2_start,
        end_date=sub2_end,
        next_billing_date=datetime(2025, 7, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(sub2)
    db_session.commit()

    resp = client.get(
        "/api/portal/subscriptions",
        headers={"Authorization": f"Bearer {auth_tokens['customer_a']}"},
    )
    assert resp.status_code == 200
    subs = resp.json()
    sub1_res = next(s for s in subs if s["id"] == sub1.id)
    sub2_res = next(s for s in subs if s["id"] == sub2.id)

    assert sub1_res["status"] == "EXPIRED"
    assert sub2_res["status"] == "ACTIVE"
    # Gap exists: sub2 start is after sub1 end
    assert sub2_res["start_date"] > sub1_res["end_date"]


def test_5_yearly_subscription_billing_cycles(client: TestClient, db_session: Session, auth_tokens):
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    start_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = start_date + relativedelta(years=2)

    sub = Subscription(
        customer_id=customer.id,
        product_id=product.id,
        name="Enterprise Support 2-Year",
        status=SubscriptionStatus.ACTIVE,
        duration_mode="TILL_VALIDITY",
        validity_value=2,
        validity_unit="YEARS",
        billing_frequency="YEARLY",
        start_date=start_date,
        end_date=end_date,
        next_billing_date=start_date + relativedelta(years=1),
    )
    db_session.add(sub)
    db_session.flush()

    inv1 = Invoice(
        invoice_number="INV-YEAR-CYC-01",
        subscription_id=sub.id,
        customer_id=customer.id,
        billing_type=BillingType.RECURRING,
        period_start=start_date,
        period_end=start_date + relativedelta(years=1),
        status=InvoiceStatus.PAID,
        subtotal=1200.0,
        total_amount=1200.0,
        created_at=start_date,
    )
    db_session.add(inv1)
    db_session.flush()

    # Run generator at Year 1
    billing_service.run_recurring_billing(db_session, user_id=1, simulated_date=start_date + relativedelta(years=1, days=1), subscription_id=sub.id)
    db_session.commit()

    db_session.refresh(sub)
    cycles = sub.billing_cycles
    assert len(cycles) == 2
    assert cycles[0]["period_end"] == cycles[1]["period_start"]


def test_6_monthly_subscription_consecutive_dates(client: TestClient, db_session: Session):
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sub = Subscription(
        customer_id=customer.id,
        product_id=product.id,
        name="Monthly SaaS",
        status=SubscriptionStatus.ACTIVE,
        duration_mode="TILL_VALIDITY",
        validity_value=2,
        validity_unit="MONTHS",
        billing_frequency="MONTHLY",
        start_date=start,
        end_date=start + relativedelta(months=2),
        next_billing_date=start + relativedelta(months=1),
    )
    db_session.add(sub)
    db_session.flush()

    inv1 = Invoice(
        invoice_number="INV-MO-01",
        subscription_id=sub.id,
        customer_id=customer.id,
        billing_type=BillingType.RECURRING,
        period_start=start,
        period_end=start + relativedelta(months=1),
        status=InvoiceStatus.PAID,
        subtotal=50.0,
        total_amount=50.0,
        created_at=start,
    )
    inv2 = Invoice(
        invoice_number="INV-MO-02",
        subscription_id=sub.id,
        customer_id=customer.id,
        billing_type=BillingType.RECURRING,
        period_start=start + relativedelta(months=1),
        period_end=start + relativedelta(months=2),
        status=InvoiceStatus.ISSUED,
        subtotal=50.0,
        total_amount=50.0,
        created_at=start + relativedelta(months=1),
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()

    cycles = sub.billing_cycles
    assert len(cycles) == 2
    assert cycles[0]["cycle_number"] == 1
    assert cycles[1]["cycle_number"] == 2
    assert cycles[0]["period_end"] == cycles[1]["period_start"]


def test_7_invoice_and_payment_history_in_cycles(client: TestClient, db_session: Session):
    customer = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    product = db_session.query(Product).first()

    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sub = Subscription(
        customer_id=customer.id,
        product_id=product.id,
        name="Paid/Unpaid Test Sub",
        status=SubscriptionStatus.ACTIVE,
        duration_mode="TILL_VALIDITY",
        validity_value=2,
        validity_unit="MONTHS",
        billing_frequency="MONTHLY",
        start_date=start,
        end_date=start + relativedelta(months=2),
    )
    db_session.add(sub)
    db_session.flush()

    inv1 = Invoice(
        invoice_number="INV-CYC-PAID",
        subscription_id=sub.id,
        customer_id=customer.id,
        billing_type=BillingType.RECURRING,
        period_start=start,
        period_end=start + relativedelta(months=1),
        status=InvoiceStatus.PAID,
        subtotal=75.0,
        total_amount=75.0,
        created_at=start,
    )
    db_session.add(inv1)
    db_session.flush()

    payment = Payment(
        invoice_id=inv1.id,
        amount=75.0,
        payment_status=PaymentStatus.SUCCESSFUL,
        payment_method="CARD",
    )
    db_session.add(payment)

    inv2 = Invoice(
        invoice_number="INV-CYC-UNPAID",
        subscription_id=sub.id,
        customer_id=customer.id,
        billing_type=BillingType.RECURRING,
        period_start=start + relativedelta(months=1),
        period_end=start + relativedelta(months=2),
        status=InvoiceStatus.ISSUED,
        subtotal=75.0,
        total_amount=75.0,
        created_at=start + relativedelta(months=1),
    )
    db_session.add(inv2)
    db_session.commit()

    cycles = sub.billing_cycles
    assert cycles[0]["invoice_status"] == "PAID"
    assert cycles[0]["payment_status"] == "PAID"
    assert cycles[1]["invoice_status"] == "ISSUED"
    assert cycles[1]["payment_status"] == "UNPAID"


def test_8_customer_isolation_subscriptions_list(client: TestClient, db_session: Session, auth_tokens, customer_b_setup):
    customer_a = db_session.query(Customer).filter(Customer.company_name == "Acme Corp").first()
    customer_b = customer_b_setup["customer"]
    product = db_session.query(Product).first()

    sub_b = Subscription(
        customer_id=customer_b.id,
        product_id=product.id,
        name="Customer B Secret Subscription",
        status=SubscriptionStatus.ACTIVE,
        duration_mode="LIFETIME",
        billing_frequency="NONE",
    )
    db_session.add(sub_b)
    db_session.commit()

    # Customer A lists subscriptions
    resp_a = client.get(
        "/api/portal/subscriptions",
        headers={"Authorization": f"Bearer {auth_tokens['customer_a']}"},
    )
    assert resp_a.status_code == 200
    a_subs = resp_a.json()
    assert not any(s["id"] == sub_b.id for s in a_subs)
    assert not any(s["customer_id"] != customer_a.id for s in a_subs)

    # Customer B lists subscriptions
    resp_b = client.get(
        "/api/portal/subscriptions",
        headers={"Authorization": f"Bearer {customer_b_setup['token']}"},
    )
    assert resp_b.status_code == 200
    b_subs = resp_b.json()
    assert any(s["id"] == sub_b.id for s in b_subs)
    assert all(s["customer_id"] == customer_b.id for s in b_subs)


def test_9_customer_isolation_billing_history_forbidden(client: TestClient, db_session: Session, auth_tokens, customer_b_setup):
    customer_b = customer_b_setup["customer"]
    product = db_session.query(Product).first()

    sub_b = Subscription(
        customer_id=customer_b.id,
        product_id=product.id,
        name="Customer B Private Sub",
        status=SubscriptionStatus.ACTIVE,
        duration_mode="LIFETIME",
        billing_frequency="NONE",
    )
    db_session.add(sub_b)
    db_session.commit()

    # Customer A attempts to access Customer B's billing history via portal endpoint
    resp = client.get(
        f"/api/portal/subscriptions/{sub_b.id}/billing-history",
        headers={"Authorization": f"Bearer {auth_tokens['customer_a']}"},
    )
    assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}"

    # Customer A attempts to access Customer B's billing history via subscriptions endpoint
    resp2 = client.get(
        f"/api/subscriptions/{sub_b.id}/billing-history",
        headers={"Authorization": f"Bearer {auth_tokens['customer_a']}"},
    )
    assert resp2.status_code == 403, f"Expected 403 Forbidden, got {resp2.status_code}"


def test_10_get_endpoints_strictly_read_only(client: TestClient, db_session: Session, auth_tokens):
    sub_count_before = db_session.query(Subscription).count()
    inv_count_before = db_session.query(Invoice).count()

    # Call GET subscriptions
    client.get(
        "/api/portal/subscriptions",
        headers={"Authorization": f"Bearer {auth_tokens['customer_a']}"},
    )

    first_sub = db_session.query(Subscription).first()
    if first_sub:
        client.get(
            f"/api/portal/subscriptions/{first_sub.id}/billing-history",
            headers={"Authorization": f"Bearer {auth_tokens['customer_a']}"},
        )

    client.get(
        "/api/portal/invoices",
        headers={"Authorization": f"Bearer {auth_tokens['customer_a']}"},
    )

    sub_count_after = db_session.query(Subscription).count()
    inv_count_after = db_session.query(Invoice).count()

    assert sub_count_before == sub_count_after, "GET endpoints must not create subscriptions!"
    assert inv_count_before == inv_count_after, "GET endpoints must not create invoices!"
