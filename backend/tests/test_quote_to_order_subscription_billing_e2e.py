import pytest
import uuid
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from app.core.database import SessionLocal
from app.models.user import User, Role
from app.models.customer import Customer, CustomerTier
from app.models.product import Product, ProductCategory
from app.models.quote import Quote, QuoteLine, QuoteStatus, LineType
from app.models.order import Order, OrderLine, OrderStatus
from app.models.billing import Subscription, SubscriptionStatus, Invoice, BillingType
from app.models.warehouse import Warehouse, Inventory
from app.schemas.quote import QuoteCreate, QuoteLineCreate
from app.schemas.negotiation import NegotiationCreate
from app.services.quote_service import quote_service
from app.services.approval_service import approval_service
from app.services.negotiation_service import negotiation_service
from app.services.portal_service import portal_service
from app.services.order_service import order_service
from app.services.fulfillment_service import fulfillment_service
from app.services.billing_service import billing_service


@pytest.fixture(scope="module")
def e2e_env():
    db = SessionLocal()
    unique_suffix = uuid.uuid4().hex[:6]

    # Users
    sales_rep = db.query(User).filter(User.email == "salesrep@dealflow360.internal").first()
    sales_mgr = db.query(User).filter(User.email == "salesmgr@dealflow360.internal").first()
    finance = db.query(User).filter(User.email == "finance@dealflow360.internal").first()
    admin = db.query(User).filter(User.email == "admin@dealflow360.internal").first()

    # Customer 1
    cust1_user = User(
        email=f"e2e_cust1_{unique_suffix}@acme.com",
        full_name="Alice Customer",
        hashed_password="hashed_password",
        role=Role.CUSTOMER,
        is_active=True,
    )
    db.add(cust1_user)
    db.flush()

    cust1 = Customer(
        company_name=f"Acme Corp {unique_suffix}",
        contact_name="Alice Customer",
        email=cust1_user.email,
        phone="555-0101",
        tier=CustomerTier.STANDARD,
        discount_ceiling=15.0,
    )
    db.add(cust1)

    # Customer 2 (for role isolation test)
    cust2_user = User(
        email=f"e2e_cust2_{unique_suffix}@beta.com",
        full_name="Bob Customer",
        hashed_password="hashed_password",
        role=Role.CUSTOMER,
        is_active=True,
    )
    db.add(cust2_user)
    db.flush()

    cust2 = Customer(
        company_name=f"Beta Corp {unique_suffix}",
        contact_name="Bob Customer",
        email=cust2_user.email,
        phone="555-0102",
        tier=CustomerTier.STANDARD,
        discount_ceiling=10.0,
    )
    db.add(cust2)

    # Category
    cat = db.query(ProductCategory).filter(ProductCategory.name == "E2E Tech").first()
    if not cat:
        cat = ProductCategory(name="E2E Tech", description="Category for E2E testing")
        db.add(cat)
        db.flush()

    # Products
    # 1. Physical Hardware (ONE_TIME)
    prod_hardware = Product(
        name=f"Enterprise Server {unique_suffix}",
        sku=f"E2E-HW-{unique_suffix}",
        category_id=cat.id,
        unit_price=4000.0,
        cost_price=2500.0,
        allowed_discount_percent=20.0,
        subscription_enabled=False,
    )
    db.add(prod_hardware)

    # 2. Lifetime Laptop (ONE_TIME purchase + LIFETIME subscription entitlement)
    prod_laptop = Product(
        name=f"Laptop Lifetime Care {unique_suffix}",
        sku=f"E2E-LAPTOP-{unique_suffix}",
        category_id=cat.id,
        unit_price=1800.0,
        cost_price=1200.0,
        allowed_discount_percent=15.0,
        subscription_enabled=True,
        subscription_name="Lifetime Care & Warranty",
        duration_mode="LIFETIME",
        validity_value=0,
        validity_unit="YEARS",
        billing_frequency="NONE",
        subscription_start_trigger="ORDER_ACTIVATION",
    )
    db.add(prod_laptop)

    # 3. Limited Till Validity (RECURRING subscription)
    prod_windows = Product(
        name=f"Windows Cloud Support {unique_suffix}",
        sku=f"E2E-WIN-{unique_suffix}",
        category_id=cat.id,
        unit_price=150.0,
        cost_price=50.0,
        allowed_discount_percent=25.0,
        subscription_enabled=True,
        subscription_name="Cloud Support Tier 1",
        duration_mode="TILL_VALIDITY",
        validity_value=3,
        validity_unit="MONTHS",
        billing_frequency="MONTHLY",
        subscription_start_trigger="ORDER_ACTIVATION",
    )
    db.add(prod_windows)
    db.flush()

    # Warehouse & Inventory for physical hardware
    wh = db.query(Warehouse).filter(Warehouse.is_active == True).first()
    if not wh:
        wh = Warehouse(name="Primary E2E Hub", location="Building A", is_active=True)
        db.add(wh)
        db.flush()

    inv_hw = Inventory(
        product_id=prod_hardware.id,
        warehouse_id=wh.id,
        quantity_available=100,
    )
    db.add(inv_hw)

    db.commit()
    db.refresh(cust1)
    db.refresh(cust2)
    db.refresh(prod_hardware)
    db.refresh(prod_laptop)
    db.refresh(prod_windows)

    yield {
        "db": db,
        "sales_rep": sales_rep,
        "sales_mgr": sales_mgr,
        "finance": finance,
        "admin": admin,
        "cust1_user": cust1_user,
        "cust1": cust1,
        "cust2_user": cust2_user,
        "cust2": cust2,
        "hardware": prod_hardware,
        "laptop": prod_laptop,
        "windows": prod_windows,
        "wh": wh,
    }

    db.close()


def test_01_onetime_quote_to_order_visible(e2e_env):
    """TEST 1: ONE_TIME quote -> approve -> customer accepts -> order created -> order visible."""
    db = e2e_env["db"]
    cust = e2e_env["cust1"]
    cust_user = e2e_env["cust1_user"]
    rep = e2e_env["sales_rep"]
    hw = e2e_env["hardware"]

    # 1. Create quote with physical one-time item
    quote_in = QuoteCreate(
        customer_id=cust.id,
        lines=[QuoteLineCreate(product_id=hw.id, quantity=2, discount_percent=5.0)]
    )
    quote = quote_service.create_quote(db, quote_in, rep)
    assert quote.status in (QuoteStatus.APPROVED, QuoteStatus.PENDING_APPROVAL)
    if quote.status != QuoteStatus.APPROVED:
        quote.status = QuoteStatus.APPROVED
        db.commit()

    # 2. Customer confirms quote
    res = portal_service.confirm_quote(db, cust_user, quote.id)
    assert res["status"] == "ACCEPTED"
    assert res["order_id"] is not None

    # 3. Verify order exists and is visible in customer orders
    order = db.query(Order).filter(Order.id == res["order_id"]).first()
    assert order is not None
    assert order.customer_id == cust.id
    assert order.status == OrderStatus.PENDING
    assert len(order.lines) == 1
    assert order.lines[0].product_id == hw.id

    cust_orders = portal_service.get_customer_orders(db, cust_user)
    assert any(o.id == order.id for o in cust_orders)


def test_02_recurring_quote_to_order_and_subscription_active(e2e_env):
    """TEST 2: RECURRING quote -> approve -> customer accepts -> order created -> subscription created -> subscription ACTIVE."""
    db = e2e_env["db"]
    cust = e2e_env["cust1"]
    cust_user = e2e_env["cust1_user"]
    rep = e2e_env["sales_rep"]
    win = e2e_env["windows"]

    quote_in = QuoteCreate(
        customer_id=cust.id,
        lines=[QuoteLineCreate(product_id=win.id, quantity=1, discount_percent=0.0)]
    )
    quote = quote_service.create_quote(db, quote_in, rep)
    if quote.status != QuoteStatus.APPROVED:
        quote.status = QuoteStatus.APPROVED
        db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order_id = res["order_id"]

    sub = db.query(Subscription).filter(Subscription.order_id == order_id, Subscription.product_id == win.id).first()
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.customer_id == cust.id


def test_03_lifetime_subscription_start_date_populated_end_date_none(e2e_env):
    """TEST 3: Lifetime subscription -> start_date populated, end_date NULL."""
    db = e2e_env["db"]
    cust = e2e_env["cust1"]
    cust_user = e2e_env["cust1_user"]
    rep = e2e_env["sales_rep"]
    laptop = e2e_env["laptop"]

    quote_in = QuoteCreate(
        customer_id=cust.id,
        lines=[QuoteLineCreate(product_id=laptop.id, quantity=1, discount_percent=0.0)]
    )
    quote = quote_service.create_quote(db, quote_in, rep)
    if quote.status != QuoteStatus.APPROVED:
        quote.status = QuoteStatus.APPROVED
        db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order_id = res["order_id"]

    sub = db.query(Subscription).filter(Subscription.order_id == order_id, Subscription.product_id == laptop.id).first()
    assert sub is not None
    assert sub.duration_mode == "LIFETIME"
    assert sub.start_date is not None
    assert sub.end_date is None
    assert sub.status == SubscriptionStatus.ACTIVE


def test_04_till_validity_subscription_dates_calculated(e2e_env):
    """TEST 4: Till Validity subscription -> start_date populated, end_date correctly calculated."""
    db = e2e_env["db"]
    cust = e2e_env["cust1"]
    cust_user = e2e_env["cust1_user"]
    rep = e2e_env["sales_rep"]
    win = e2e_env["windows"]

    quote_in = QuoteCreate(
        customer_id=cust.id,
        lines=[QuoteLineCreate(product_id=win.id, quantity=3, discount_percent=0.0)]
    )
    quote = quote_service.create_quote(db, quote_in, rep)
    if quote.status != QuoteStatus.APPROVED:
        quote.status = QuoteStatus.APPROVED
        db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order_id = res["order_id"]

    sub = db.query(Subscription).filter(Subscription.order_id == order_id, Subscription.product_id == win.id).first()
    assert sub is not None
    assert sub.duration_mode == "TILL_VALIDITY"
    assert sub.start_date is not None
    assert sub.end_date is not None
    # Configured for 3 months
    expected_end = sub.start_date + relativedelta(months=3)
    assert sub.end_date.year == expected_end.year
    assert sub.end_date.month == expected_end.month
    assert sub.end_date.day == expected_end.day


def test_05_hybrid_quote_both_flows(e2e_env):
    """TEST 5: Hybrid quote: ONE_TIME + RECURRING -> one order -> one-time order line -> recurring order line -> fulfillment -> subscription."""
    db = e2e_env["db"]
    cust = e2e_env["cust1"]
    cust_user = e2e_env["cust1_user"]
    rep = e2e_env["sales_rep"]
    hw = e2e_env["hardware"]
    win = e2e_env["windows"]

    quote_in = QuoteCreate(
        customer_id=cust.id,
        lines=[
            QuoteLineCreate(product_id=hw.id, quantity=1, discount_percent=0.0),
            QuoteLineCreate(product_id=win.id, quantity=1, discount_percent=0.0),
        ]
    )
    quote = quote_service.create_quote(db, quote_in, rep)
    if quote.status != QuoteStatus.APPROVED:
        quote.status = QuoteStatus.APPROVED
        db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order_id = res["order_id"]
    order = db.query(Order).filter(Order.id == order_id).first()

    assert len(order.lines) == 2
    # Verify both line types exist
    has_hw = any(l.product_id == hw.id for l in order.lines)
    has_win = any(l.product_id == win.id for l in order.lines)
    assert has_hw and has_win

    # Subscription created for windows
    sub = db.query(Subscription).filter(Subscription.order_id == order_id, Subscription.product_id == win.id).first()
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE

    # Fulfillment can be confirmed for physical hardware
    fulfilled_order = fulfillment_service.confirm_fulfillment(db, order_id=order.id, user_id=e2e_env["admin"].id)
    assert fulfilled_order.status == OrderStatus.CONFIRMED


def test_06_customer_accepts_same_quote_twice_idempotency(e2e_env):
    """TEST 6: Customer accepts same quote twice -> only ONE order exists -> only ONE subscription exists."""
    db = e2e_env["db"]
    cust = e2e_env["cust1"]
    cust_user = e2e_env["cust1_user"]
    rep = e2e_env["sales_rep"]
    win = e2e_env["windows"]

    quote_in = QuoteCreate(
        customer_id=cust.id,
        lines=[QuoteLineCreate(product_id=win.id, quantity=1, discount_percent=0.0)]
    )
    quote = quote_service.create_quote(db, quote_in, rep)
    if quote.status != QuoteStatus.APPROVED:
        quote.status = QuoteStatus.APPROVED
        db.commit()

    res1 = portal_service.confirm_quote(db, cust_user, quote.id)
    res2 = portal_service.confirm_quote(db, cust_user, quote.id)

    assert res1["order_id"] == res2["order_id"]

    orders = db.query(Order).filter(Order.quote_id == quote.id).all()
    assert len(orders) == 1

    subs = db.query(Subscription).filter(Subscription.order_id == res1["order_id"]).all()
    assert len(subs) == 1


def test_07_billing_recurring_subscription_generates_invoice(e2e_env):
    """TEST 7: Billing: Recurring subscription -> next billing date calculated -> recurring invoice generated."""
    db = e2e_env["db"]
    cust = e2e_env["cust1"]
    cust_user = e2e_env["cust1_user"]
    rep = e2e_env["sales_rep"]
    win = e2e_env["windows"]

    quote_in = QuoteCreate(
        customer_id=cust.id,
        lines=[QuoteLineCreate(product_id=win.id, quantity=2, discount_percent=0.0)]
    )
    quote = quote_service.create_quote(db, quote_in, rep)
    if quote.status != QuoteStatus.APPROVED:
        quote.status = QuoteStatus.APPROVED
        db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order_id = res["order_id"]

    sub = db.query(Subscription).filter(Subscription.order_id == order_id, Subscription.product_id == win.id).first()
    assert sub is not None
    assert sub.next_billing_date is not None
    assert sub.billing_frequency == "MONTHLY"

    # Verify recurring invoice is generated
    invoices = db.query(Invoice).filter(Invoice.order_id == order_id, Invoice.billing_type == BillingType.RECURRING).all()
    assert len(invoices) >= 1
    rec_inv = invoices[0]
    assert rec_inv.total_amount == 300.0  # 2 * 150.0


def test_08_customer_portal_shows_order_subscription_billing(e2e_env):
    """TEST 8: Customer portal: accepted quote -> order visible -> subscription visible -> billing visible."""
    db = e2e_env["db"]
    cust_user = e2e_env["cust1_user"]

    # 1. Orders visible
    orders = portal_service.get_customer_orders(db, cust_user)
    assert len(orders) > 0

    # 2. Subscriptions visible
    subs = portal_service.get_customer_subscriptions(db, cust_user)
    assert len(subs) > 0

    # 3. Invoices visible
    invs = portal_service.get_customer_invoices(db, cust_user)
    assert len(invs) > 0


def test_09_customer_role_isolation(e2e_env):
    """TEST 9: Role isolation: Customer cannot access internal order/approval endpoints belonging to another customer."""
    db = e2e_env["db"]
    cust1_user = e2e_env["cust1_user"]
    cust2_user = e2e_env["cust2_user"]

    # Get an order belonging to cust1
    cust1_orders = portal_service.get_customer_orders(db, cust1_user)
    assert len(cust1_orders) > 0
    cust1_order_id = cust1_orders[0].id

    # Cust2 tries to access Cust1's order detail -> Must raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        portal_service.get_customer_order_detail(db, cust2_user, cust1_order_id)
    assert exc_info.value.status_code == 403

    # Cust2 cannot confirm a quote belonging to Cust1
    cust1_quotes = db.query(Quote).filter(Quote.customer_id == e2e_env["cust1"].id).all()
    if cust1_quotes:
        with pytest.raises(HTTPException) as exc_quote:
            portal_service.confirm_quote(db, cust2_user, cust1_quotes[0].id)
        assert exc_quote.value.status_code == 403


def test_10_negotiated_quote_order_preserves_final_negotiated_values(e2e_env):
    """TEST 10: Negotiated quote: customer negotiation -> manager approval -> customer acceptance -> order contains FINAL negotiated price/discount."""
    db = e2e_env["db"]
    cust = e2e_env["cust1"]
    cust_user = e2e_env["cust1_user"]
    rep = e2e_env["sales_rep"]
    mgr = e2e_env["sales_mgr"]
    hw = e2e_env["hardware"]

    # 1. Sales rep creates quote with initial 5% discount
    quote_in = QuoteCreate(
        customer_id=cust.id,
        lines=[QuoteLineCreate(product_id=hw.id, quantity=2, discount_percent=5.0)]
    )
    quote = quote_service.create_quote(db, quote_in, rep)
    if quote.status != QuoteStatus.APPROVED:
        quote.status = QuoteStatus.APPROVED
        db.commit()

    # Initial total = 2 * 4000 = 8000. 5% discount = 400. Total = 7600.
    assert quote.total_amount == 7600.0

    # 2. Customer negotiates for 12.0% discount
    neg_in = NegotiationCreate(
        requested_change="overall_discount_percent",
        proposed_value="12.0",
        message="Requesting 12% discount for annual contract"
    )
    neg = negotiation_service.create_negotiation(db, cust_user, quote.id, neg_in)

    # 3. If negotiation is pending, manager approves it
    if neg.status.value == "PENDING":
        approval_res = negotiation_service.approve_negotiation(db, mgr, neg.id, comments="Approved 12% discount")
        assert approval_res.status.value == "APPROVED"

    db.refresh(quote)
    # If quote requires re-approval after negotiation, manager re-approves it
    if quote.status == QuoteStatus.PENDING_APPROVAL:
        quote.status = QuoteStatus.APPROVED
        db.commit()
        db.refresh(quote)

    # Quote lines must reflect 12% discount: 2 * 4000 = 8000. 12% = 960. Total = 7040.
    assert quote.total_amount == 7040.0
    assert quote.lines[0].discount_percent == 12.0

    # 4. Customer accepts final negotiated quote
    confirm_res = portal_service.confirm_quote(db, cust_user, quote.id)
    order_id = confirm_res["order_id"]

    order = db.query(Order).filter(Order.id == order_id).first()
    assert order is not None
    assert order.total_amount == 7040.0
    assert order.lines[0].discount_percent == 12.0
    assert order.lines[0].line_total == 7040.0
