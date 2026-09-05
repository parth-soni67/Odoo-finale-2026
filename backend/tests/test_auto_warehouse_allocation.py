import pytest
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.user import User, Role
from app.models.customer import Customer, CustomerTier
from app.models.product import Product, ProductCategory
from app.models.warehouse import Warehouse, Inventory
from app.models.order import Order, OrderLine, OrderStatus, FulfillmentSplit, FulfillmentSplitStatus
from app.models.quote import Quote, QuoteLine, QuoteStatus, LineType
from app.models.billing import Subscription, SubscriptionStatus, Invoice, BillingType
from app.schemas.quote import QuoteCreate, QuoteLineCreate
from app.services.quote_service import quote_service
from app.services.portal_service import portal_service
from app.services.order_service import order_service
from app.services.fulfillment_service import fulfillment_service


@pytest.fixture
def alloc_env(db_session: Session):
    """Fixture providing isolated setup for auto warehouse allocation tests."""
    unique_suffix = datetime.now().strftime("%Y%m%d%H%M%S%f")

    # Category
    cat = ProductCategory(name=f"Alloc Cat {unique_suffix}", description="Test Category")
    db_session.add(cat)
    db_session.flush()

    # Users
    sales_rep = User(
        email=f"rep_{unique_suffix}@example.com",
        full_name="Sales Rep",
        role=Role.SALES_REP,
        is_active=True,
        hashed_password=get_password_hash("Demo1234!"),
    )
    db_session.add(sales_rep)

    admin = User(
        email=f"admin_{unique_suffix}@example.com",
        full_name="Admin User",
        role=Role.ADMIN,
        is_active=True,
        hashed_password=get_password_hash("Demo1234!"),
    )
    db_session.add(admin)

    cust_user = User(
        email=f"cust_{unique_suffix}@example.com",
        full_name="Customer User",
        role=Role.CUSTOMER,
        is_active=True,
        hashed_password=get_password_hash("Demo1234!"),
    )
    db_session.add(cust_user)
    db_session.flush()

    # Customer
    customer = Customer(
        company_name=f"Test Enterprise {unique_suffix}",
        contact_name="Customer User",
        email=cust_user.email,
        phone="555-0199",
        tier=CustomerTier.STANDARD,
        discount_ceiling=15.0,
    )
    db_session.add(customer)
    db_session.flush()

    # Warehouses
    wh_a = Warehouse(name=f"Warehouse A - East {unique_suffix}", location="New York", is_active=True)
    wh_b = Warehouse(name=f"Warehouse B - West {unique_suffix}", location="California", is_active=True)
    db_session.add(wh_a)
    db_session.add(wh_b)
    db_session.flush()

    # Physical Product
    prod_physical = Product(
        name=f"Edge Gateway {unique_suffix}",
        sku=f"PHYS-{unique_suffix}",
        category_id=cat.id,
        unit_price=1000.0,
        cost_price=600.0,
        allowed_discount_percent=20.0,
        subscription_enabled=False,
    )
    db_session.add(prod_physical)

    # Lifetime Subscription Product
    prod_lifetime = Product(
        name=f"Lifetime Laptop {unique_suffix}",
        sku=f"LIFE-{unique_suffix}",
        category_id=cat.id,
        unit_price=2000.0,
        cost_price=1400.0,
        allowed_discount_percent=15.0,
        subscription_enabled=True,
        subscription_name="Lifetime Care Package",
        duration_mode="LIFETIME",
        validity_value=0,
        validity_unit="YEARS",
        billing_frequency="NONE",
        subscription_start_trigger="ORDER_ACTIVATION",
    )
    db_session.add(prod_lifetime)

    # Till-Validity Recurring Product
    prod_recurring = Product(
        name=f"Cloud Monitoring {unique_suffix}",
        sku=f"REC-{unique_suffix}",
        category_id=cat.id,
        unit_price=200.0,
        cost_price=50.0,
        allowed_discount_percent=10.0,
        subscription_enabled=True,
        subscription_name="Cloud Monitoring Pro",
        duration_mode="TILL_VALIDITY",
        validity_value=3,
        validity_unit="MONTHS",
        billing_frequency="MONTHLY",
        subscription_start_trigger="ORDER_ACTIVATION",
    )
    db_session.add(prod_recurring)
    db_session.commit()

    return {
        "db": db_session,
        "cat": cat,
        "sales_rep": sales_rep,
        "admin": admin,
        "cust_user": cust_user,
        "customer": customer,
        "wh_a": wh_a,
        "wh_b": wh_b,
        "prod_physical": prod_physical,
        "prod_lifetime": prod_lifetime,
        "prod_recurring": prod_recurring,
    }


def test_01_single_warehouse_full_allocation(alloc_env):
    """TEST 1: 1 physical product, inventory available -> auto allocation creates split and deducts inventory."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    prod = alloc_env["prod_physical"]
    wh_a = alloc_env["wh_a"]

    # Seed 10 units in Warehouse A
    inv = Inventory(product_id=prod.id, warehouse_id=wh_a.id, quantity_available=10)
    db.add(inv)
    db.commit()

    # Create & approve quote for 1 unit
    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=prod.id, quantity=1, line_type=LineType.ONE_TIME)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    # Customer accepts quote
    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order_id = res["order_id"]
    order = db.query(Order).filter(Order.id == order_id).first()

    assert order is not None
    assert order.status == OrderStatus.PROCESSING
    assert len(order.lines) == 1

    line = order.lines[0]
    splits = line.fulfillment_splits
    assert len(splits) == 1
    assert splits[0].warehouse_id == wh_a.id
    assert splits[0].quantity_allocated == 1
    assert splits[0].status == FulfillmentSplitStatus.ALLOCATED

    # Verify inventory deducted
    db.refresh(inv)
    assert inv.quantity_available == 9

    # Backorder & progress
    total_physical = line.quantity
    total_allocated = sum(s.quantity_allocated for s in splits)
    backorder = max(0, total_physical - total_allocated)
    progress = round((total_allocated / total_physical) * 100)
    assert backorder == 0
    assert progress == 100


def test_02_zero_inventory_backorder(alloc_env):
    """TEST 2: 1 physical product, 0 inventory -> backorder equals quantity requested, progress 0%."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    prod = alloc_env["prod_physical"]

    # No inventory seeded (0 units)
    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=prod.id, quantity=5, line_type=LineType.ONE_TIME)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order = db.query(Order).filter(Order.id == res["order_id"]).first()

    assert order is not None
    assert order.status == OrderStatus.PENDING
    line = order.lines[0]
    assert len(line.fulfillment_splits) == 0

    total_allocated = sum(s.quantity_allocated for s in line.fulfillment_splits)
    backorder = line.quantity - total_allocated
    progress = round((total_allocated / line.quantity) * 100)

    assert backorder == 5
    assert progress == 0


def test_03_multi_warehouse_split_full_allocation(alloc_env):
    """TEST 3: Multi-warehouse split: 10 qty with Wh A = 6, Wh B = 4 -> allocations 6 + 4, backorder 0, progress 100%."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    prod = alloc_env["prod_physical"]
    wh_a = alloc_env["wh_a"]
    wh_b = alloc_env["wh_b"]

    # Seed Wh A = 6, Wh B = 4
    inv_a = Inventory(product_id=prod.id, warehouse_id=wh_a.id, quantity_available=6)
    inv_b = Inventory(product_id=prod.id, warehouse_id=wh_b.id, quantity_available=4)
    db.add_all([inv_a, inv_b])
    db.commit()

    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=prod.id, quantity=10, line_type=LineType.ONE_TIME)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order = db.query(Order).filter(Order.id == res["order_id"]).first()

    assert order.status == OrderStatus.PROCESSING
    line = order.lines[0]
    splits = line.fulfillment_splits
    assert len(splits) == 2

    # Verify allocations across both warehouses
    split_a = next(s for s in splits if s.warehouse_id == wh_a.id)
    split_b = next(s for s in splits if s.warehouse_id == wh_b.id)
    assert split_a.quantity_allocated == 6
    assert split_b.quantity_allocated == 4

    # Verify inventories depleted to 0
    db.refresh(inv_a)
    db.refresh(inv_b)
    assert inv_a.quantity_available == 0
    assert inv_b.quantity_available == 0

    total_allocated = sum(s.quantity_allocated for s in splits)
    backorder = line.quantity - total_allocated
    progress = round((total_allocated / line.quantity) * 100)
    assert backorder == 0
    assert progress == 100


def test_04_partial_allocation_with_backorder(alloc_env):
    """TEST 4: Partial multi-warehouse: 10 qty with Wh A = 6, Wh B = 2 -> allocations 6 + 2, backorder 2, progress 80%."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    prod = alloc_env["prod_physical"]
    wh_a = alloc_env["wh_a"]
    wh_b = alloc_env["wh_b"]

    inv_a = Inventory(product_id=prod.id, warehouse_id=wh_a.id, quantity_available=6)
    inv_b = Inventory(product_id=prod.id, warehouse_id=wh_b.id, quantity_available=2)
    db.add_all([inv_a, inv_b])
    db.commit()

    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=prod.id, quantity=10, line_type=LineType.ONE_TIME)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order = db.query(Order).filter(Order.id == res["order_id"]).first()

    assert order.status == OrderStatus.PROCESSING
    line = order.lines[0]
    splits = line.fulfillment_splits
    assert len(splits) == 2

    total_allocated = sum(s.quantity_allocated for s in splits)
    assert total_allocated == 8
    backorder = line.quantity - total_allocated
    assert backorder == 2
    progress = round((total_allocated / line.quantity) * 100)
    assert progress == 80


def test_05_deterministic_warehouse_ordering(alloc_env):
    """TEST 5: Deterministic warehouse ordering by warehouse ID."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    prod = alloc_env["prod_physical"]
    wh_a = alloc_env["wh_a"]
    wh_b = alloc_env["wh_b"]

    # Determine which warehouse has smaller ID
    first_wh, second_wh = (wh_a, wh_b) if wh_a.id < wh_b.id else (wh_b, wh_a)

    inv_first = Inventory(product_id=prod.id, warehouse_id=first_wh.id, quantity_available=3)
    inv_second = Inventory(product_id=prod.id, warehouse_id=second_wh.id, quantity_available=5)
    db.add_all([inv_first, inv_second])
    db.commit()

    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=prod.id, quantity=5, line_type=LineType.ONE_TIME)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order = db.query(Order).filter(Order.id == res["order_id"]).first()

    line = order.lines[0]
    splits = line.fulfillment_splits
    assert len(splits) == 2

    # First warehouse should be fully allocated (3 units), second gets remainder (2 units)
    assert splits[0].warehouse_id == first_wh.id
    assert splits[0].quantity_allocated == 3
    assert splits[1].warehouse_id == second_wh.id
    assert splits[1].quantity_allocated == 2


def test_06_customer_accepts_quote_twice_idempotency(alloc_env):
    """TEST 6: Customer accepts quote twice -> idempotency: 1 order, 1 set of splits, inventory not deducted twice."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    prod = alloc_env["prod_physical"]
    wh_a = alloc_env["wh_a"]

    inv = Inventory(product_id=prod.id, warehouse_id=wh_a.id, quantity_available=10)
    db.add(inv)
    db.commit()

    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=prod.id, quantity=2, line_type=LineType.ONE_TIME)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    # First acceptance
    res1 = portal_service.confirm_quote(db, cust_user, quote.id)
    order1_id = res1["order_id"]

    db.refresh(inv)
    assert inv.quantity_available == 8

    # Second acceptance
    res2 = portal_service.confirm_quote(db, cust_user, quote.id)
    order2_id = res2["order_id"]

    assert order1_id == order2_id

    # Inventory must still be 8, not deducted again
    db.refresh(inv)
    assert inv.quantity_available == 8

    # Verify only 1 order exists for this quote and only 1 split
    orders = db.query(Order).filter(Order.quote_id == quote.id).all()
    assert len(orders) == 1
    splits = db.query(FulfillmentSplit).filter(FulfillmentSplit.order_line_id == orders[0].lines[0].id).all()
    assert len(splits) == 1
    assert splits[0].quantity_allocated == 2


def test_07_recurring_product_no_warehouse_allocation(alloc_env):
    """TEST 7: Recurring product -> subscription ACTIVE, 0 fulfillment splits, inventory untouched."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    prod_rec = alloc_env["prod_recurring"]

    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=prod_rec.id, quantity=1, line_type=LineType.RECURRING)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order = db.query(Order).filter(Order.id == res["order_id"]).first()

    assert order is not None
    # No fulfillment splits for recurring items
    for line in order.lines:
        assert len(line.fulfillment_splits) == 0

    # Subscription is active
    sub = db.query(Subscription).filter(Subscription.order_id == order.id).first()
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE


def test_08_lifetime_subscription_dates(alloc_env):
    """TEST 8: Lifetime subscription -> status ACTIVE, start_date set, end_date None."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    laptop = alloc_env["prod_lifetime"]

    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=laptop.id, quantity=1, line_type=LineType.ONE_TIME)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order = db.query(Order).filter(Order.id == res["order_id"]).first()

    sub = db.query(Subscription).filter(Subscription.order_id == order.id).first()
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.duration_mode == "LIFETIME"
    assert sub.start_date is not None
    assert sub.end_date is None


def test_09_till_validity_subscription_dates(alloc_env):
    """TEST 9: Till Validity subscription -> status ACTIVE, end_date = start_date + 3 months, next billing set."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    rec = alloc_env["prod_recurring"]

    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=rec.id, quantity=1, line_type=LineType.RECURRING)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order = db.query(Order).filter(Order.id == res["order_id"]).first()

    sub = db.query(Subscription).filter(Subscription.order_id == order.id).first()
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.duration_mode == "TILL_VALIDITY"
    assert sub.validity_value == 3
    assert sub.validity_unit == "MONTHS"
    assert sub.end_date is not None
    # Verify ~3 months difference
    diff_days = (sub.end_date - sub.start_date).days
    assert 88 <= diff_days <= 93


def test_10_hybrid_order_physical_and_subscription_invoices(alloc_env):
    """TEST 10: Hybrid order -> physical fulfillment + subscription + one-time & recurring invoices."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    prod_phys = alloc_env["prod_physical"]
    prod_rec = alloc_env["prod_recurring"]
    wh_a = alloc_env["wh_a"]

    inv = Inventory(product_id=prod_phys.id, warehouse_id=wh_a.id, quantity_available=5)
    db.add(inv)
    db.commit()

    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[
            QuoteLineCreate(product_id=prod_phys.id, quantity=2, line_type=LineType.ONE_TIME),
            QuoteLineCreate(product_id=prod_rec.id, quantity=1, line_type=LineType.RECURRING),
        ],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order = db.query(Order).filter(Order.id == res["order_id"]).first()

    assert order is not None
    assert len(order.lines) == 2

    # Physical line has splits
    phys_line = next(l for l in order.lines if l.product_id == prod_phys.id)
    assert len(phys_line.fulfillment_splits) == 1
    assert phys_line.fulfillment_splits[0].quantity_allocated == 2

    # Subscription is active
    sub = db.query(Subscription).filter(Subscription.order_id == order.id).first()
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE

    # Invoices: 1 one-time invoice and 1 recurring invoice
    invoices = db.query(Invoice).filter(Invoice.order_id == order.id).all()
    one_time_inv = next((i for i in invoices if i.billing_type == BillingType.ONE_TIME), None)
    rec_inv = next((i for i in invoices if i.billing_type == BillingType.RECURRING), None)

    assert one_time_inv is not None
    assert rec_inv is not None
    assert one_time_inv.total_amount == 2000.0  # 2 * 1000
    assert rec_inv.total_amount == 200.0        # 1 * 200


def test_11_portal_orders_api_returns_fulfillment_splits(client: TestClient, alloc_env):
    """TEST 11: GET /api/portal/orders returns accurate fulfillment splits, warehouse names, and quantities."""
    db = alloc_env["db"]
    cust_user = alloc_env["cust_user"]
    rep = alloc_env["sales_rep"]
    prod = alloc_env["prod_physical"]
    wh_a = alloc_env["wh_a"]
    wh_b = alloc_env["wh_b"]

    inv_a = Inventory(product_id=prod.id, warehouse_id=wh_a.id, quantity_available=3)
    inv_b = Inventory(product_id=prod.id, warehouse_id=wh_b.id, quantity_available=4)
    db.add_all([inv_a, inv_b])
    db.commit()

    q_in = QuoteCreate(
        customer_id=alloc_env["customer"].id,
        lines=[QuoteLineCreate(product_id=prod.id, quantity=5, line_type=LineType.ONE_TIME)],
    )
    quote = quote_service.create_quote(db, q_in, rep)
    quote.status = QuoteStatus.APPROVED
    db.commit()

    # Customer accepts quote
    res = portal_service.confirm_quote(db, cust_user, quote.id)
    order_id = res["order_id"]

    # Login as customer
    login_resp = client.post("/api/auth/login", json={"email": cust_user.email, "password": "Demo1234!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Query portal orders
    orders_resp = client.get("/api/portal/orders", headers={"Authorization": f"Bearer {token}"})
    assert orders_resp.status_code == 200
    orders_data = orders_resp.json()

    portal_order = next((o for o in orders_data if o["id"] == order_id), None)
    assert portal_order is not None
    assert len(portal_order["lines"]) == 1

    line_data = portal_order["lines"][0]
    splits_data = line_data["fulfillment_splits"]
    assert len(splits_data) == 2

    # Verify splits have warehouse names, IDs, and correct quantities
    total_alloc = sum(s["quantity_allocated"] for s in splits_data)
    assert total_alloc == 5
    for s in splits_data:
        assert s["warehouse_name"] is not None
        assert s["status"] == "ALLOCATED"
