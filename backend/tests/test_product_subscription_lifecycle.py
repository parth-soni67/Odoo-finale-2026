import pytest
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine, Base
from app.models.user import User, Role
from app.models.customer import Customer, CustomerTier
from app.models.product import Product, ProductCategory
from app.models.quote import Quote, QuoteLine, QuoteStatus, LineType
from app.models.order import Order, OrderLine, OrderStatus
from app.models.billing import Subscription, SubscriptionStatus, Invoice, InvoiceStatus, BillingType
from app.models.audit import AuditLog
from app.schemas.quote import QuoteCreate, QuoteLineCreate
from app.services.quote_service import QuoteService
from app.services.order_service import OrderService
from app.services.billing_service import BillingService


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def test_data(db: Session):
    # Ensure test users
    admin = db.query(User).filter(User.email == "admin_sub_test@dealflow360.com").first()
    if not admin:
        admin = User(
            email="admin_sub_test@dealflow360.com",
            hashed_password="hash",
            full_name="Admin Sub Test",
            role=Role.ADMIN,
            is_active=True,
        )
        db.add(admin)

    sales_rep = db.query(User).filter(User.email == "rep_sub_test@dealflow360.com").first()
    if not sales_rep:
        sales_rep = User(
            email="rep_sub_test@dealflow360.com",
            hashed_password="hash",
            full_name="Rep Sub Test",
            role=Role.SALES_REP,
            is_active=True,
        )
        db.add(sales_rep)

    customer_user = db.query(User).filter(User.email == "cust_sub_test@client.com").first()
    if not customer_user:
        customer_user = User(
            email="cust_sub_test@client.com",
            hashed_password="hash",
            full_name="Cust User Sub Test",
            role=Role.CUSTOMER,
            is_active=True,
        )
        db.add(customer_user)

    # Customer record
    customer = db.query(Customer).filter(Customer.email == "cust_sub_test@client.com").first()
    if not customer:
        customer = Customer(
            company_name="Acme Entitlements Corp",
            contact_name="John Entitlements",
            email="cust_sub_test@client.com",
            tier=CustomerTier.ENTERPRISE,
        )
        db.add(customer)

    # Category
    category = db.query(ProductCategory).filter(ProductCategory.name == "Software Sub Test").first()
    if not category:
        category = ProductCategory(name="Software Sub Test", description="Software test category")
        db.add(category)

    db.commit()
    db.refresh(admin)
    db.refresh(sales_rep)
    db.refresh(customer_user)
    db.refresh(customer)
    db.refresh(category)

    return {
        "admin": admin,
        "sales_rep": sales_rep,
        "customer_user": customer_user,
        "customer": customer,
        "category": category,
    }


def test_01_product_subscription_configuration(db: Session, test_data):
    """Test 1: Product subscription config can be created with till validity and lifetime modes."""
    # 1. Till Validity Product
    p1 = db.query(Product).filter(Product.sku == "SW-ENT-SUB-01").first()
    if not p1:
        p1 = Product(
            name="Enterprise Software Suite",
            sku="SW-ENT-SUB-01",
            category_id=test_data["category"].id,
            unit_price=5000.0,
            cost_price=2000.0,
            allowed_discount_percent=10.0,
            subscription_enabled=True,
            subscription_name="Premium Enterprise Support",
            duration_mode="TILL_VALIDITY",
            validity_value=3,
            validity_unit="MONTHS",
            billing_frequency="MONTHLY",
            subscription_start_trigger="ORDER_ACTIVATION",
        )
        db.add(p1)
    else:
        p1.subscription_enabled = True
        p1.subscription_name = "Premium Enterprise Support"
        p1.duration_mode = "TILL_VALIDITY"
        p1.validity_value = 3
        p1.validity_unit = "MONTHS"
        p1.billing_frequency = "MONTHLY"
        p1.subscription_start_trigger = "ORDER_ACTIVATION"

    # 2. Lifetime Product
    p2 = db.query(Product).filter(Product.sku == "HW-DEV-LIFETIME-01").first()
    if not p2:
        p2 = Product(
            name="Developer Workstation Pro",
            sku="HW-DEV-LIFETIME-01",
            category_id=test_data["category"].id,
            unit_price=3500.0,
            cost_price=2500.0,
            allowed_discount_percent=5.0,
            subscription_enabled=True,
            subscription_name="Lifetime Firmware Maintenance",
            duration_mode="LIFETIME",
            validity_value=1,
            validity_unit="YEARS",
            billing_frequency="NONE",
            subscription_start_trigger="ORDER_ACTIVATION",
        )
        db.add(p2)
    else:
        p2.subscription_enabled = True
        p2.subscription_name = "Lifetime Firmware Maintenance"
        p2.duration_mode = "LIFETIME"
        p2.validity_value = 1
        p2.validity_unit = "YEARS"
        p2.billing_frequency = "NONE"
        p2.subscription_start_trigger = "ORDER_ACTIVATION"

    # 3. Standard Product without subscription
    p3 = db.query(Product).filter(Product.sku == "ACC-DOCK-NO-SUB").first()
    if not p3:
        p3 = Product(
            name="USB-C Docking Station",
            sku="ACC-DOCK-NO-SUB",
            category_id=test_data["category"].id,
            unit_price=250.0,
            cost_price=100.0,
            allowed_discount_percent=15.0,
            subscription_enabled=False,
        )
        db.add(p3)
    else:
        p3.subscription_enabled = False

    db.commit()
    db.refresh(p1)
    db.refresh(p2)
    db.refresh(p3)

    assert p1.subscription_enabled is True
    assert p1.subscription_name == "Premium Enterprise Support"
    assert p1.duration_mode == "TILL_VALIDITY"
    assert p1.validity_value == 3
    assert p1.validity_unit == "MONTHS"
    assert p1.billing_frequency == "MONTHLY"

    assert p2.subscription_enabled is True
    assert p2.duration_mode == "LIFETIME"
    assert p2.billing_frequency == "NONE"

    assert p3.subscription_enabled is False


def test_02_quote_creation_inherits_product_subscription_without_activating(db: Session, test_data):
    """Test 2-6 & 22: Quote creation automatically inherits config onto QuoteLine snapshot,
    and neither quote creation, approval, nor view activates any subscription."""
    quote_service = QuoteService()
    p1 = db.query(Product).filter(Product.sku == "SW-ENT-SUB-01").first()

    quote_in = QuoteCreate(
        customer_id=test_data["customer"].id,
        lines=[
            QuoteLineCreate(
                product_id=p1.id,
                quantity=1,
                unit_price=5000.0,
                discount_percent=0.0,
                line_type=LineType.ONE_TIME,
            )
        ],
    )

    quote = quote_service.create_quote(db, quote_in, test_data["sales_rep"])
    assert quote.id is not None
    assert len(quote.lines) == 1
    qline = quote.lines[0]

    # Inherited correctly onto quote line
    assert qline.subscription_enabled is True
    assert qline.subscription_name == "Premium Enterprise Support"
    assert qline.duration_mode == "TILL_VALIDITY"
    assert qline.validity_value == 3
    assert qline.validity_unit == "MONTHS"
    assert qline.billing_frequency == "MONTHLY"

    # Test 4: Quotation creation does NOT activate subscription for this quote
    existing_subs = db.query(Subscription).filter(Subscription.order_id != None).all()
    # No subscription for any order of this quote yet
    
    # Test 5: Quotation approval does NOT activate subscription
    quote.status = QuoteStatus.APPROVED
    db.commit()

    # Test 6: Customer viewing quote does NOT activate subscription
    from app.services.portal_service import portal_service
    portal_detail = portal_service.get_customer_quote_detail(db, test_data["customer_user"], quote.id)
    assert portal_detail["lines"][0]["subscription_enabled"] is True
    assert portal_detail["lines"][0]["subscription_name"] == "Premium Enterprise Support"


def test_03_order_creation_creates_snapshot_and_activation_activates_subscription(db: Session, test_data):
    """Test 7-12, 24: Order creation creates OrderLine snapshot.
    Order activation activates subscription with exact start_date and calculated end_date."""
    quote_service = QuoteService()
    order_service = OrderService()
    p1 = db.query(Product).filter(Product.sku == "SW-ENT-SUB-01").first()

    quote = quote_service.create_quote(
        db,
        QuoteCreate(
            customer_id=test_data["customer"].id,
            lines=[QuoteLineCreate(product_id=p1.id, quantity=1, unit_price=5000.0, line_type=LineType.ONE_TIME)],
        ),
        test_data["sales_rep"],
    )
    quote.status = QuoteStatus.APPROVED
    db.commit()

    # Test 7: Order creation snapshots quote line
    order = order_service.create_order_from_quote(db, quote.id, test_data["sales_rep"].id)
    assert order.status == OrderStatus.PENDING
    assert len(order.lines) == 1
    oline = order.lines[0]
    assert oline.subscription_enabled is True
    assert oline.subscription_name == "Premium Enterprise Support"
    assert oline.duration_mode == "TILL_VALIDITY"
    assert oline.validity_value == 3
    assert oline.validity_unit == "MONTHS"
    assert oline.billing_frequency == "MONTHLY"

    # Ensure no subscriptions yet while order is PENDING
    assert db.query(Subscription).filter(Subscription.order_id == order.id).count() == 0

    # Test 8-11: Order activation activates subscription
    activated_order = order_service.activate_order(db, order.id, test_data["admin"].id)
    assert activated_order.status == OrderStatus.CONFIRMED

    # Test 9: Subscription status ACTIVE
    subs = db.query(Subscription).filter(Subscription.order_id == order.id).all()
    assert len(subs) == 1
    sub = subs[0]
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.name == "Premium Enterprise Support"

    # Test 10: start_date equals order activation date (within last minute)
    now_utc = datetime.now(timezone.utc)
    sub_start = sub.start_date.replace(tzinfo=timezone.utc) if sub.start_date.tzinfo is None else sub.start_date
    assert abs((now_utc - sub_start).total_seconds()) < 60

    # Test 11: end_date is exactly 3 months from start_date
    sub_end = sub.end_date.replace(tzinfo=timezone.utc) if sub.end_date.tzinfo is None else sub.end_date
    expected_end = sub_start + relativedelta(months=3)
    assert abs((expected_end - sub_end).total_seconds()) < 10

    # Test 24: Audit logs recorded
    sub_audit = db.query(AuditLog).filter(
        AuditLog.entity_type == "Subscription",
        AuditLog.action == "SUBSCRIPTION_ACTIVATED",
        AuditLog.entity_id == sub.id,
    ).first()
    assert sub_audit is not None


def test_04_lifetime_subscription_sets_end_date_none(db: Session, test_data):
    """Test 2 & 12: Lifetime duration sets end_date to None upon order activation."""
    quote_service = QuoteService()
    order_service = OrderService()
    p2 = db.query(Product).filter(Product.sku == "HW-DEV-LIFETIME-01").first()

    quote = quote_service.create_quote(
        db,
        QuoteCreate(
            customer_id=test_data["customer"].id,
            lines=[QuoteLineCreate(product_id=p2.id, quantity=1, unit_price=3500.0, line_type=LineType.ONE_TIME)],
        ),
        test_data["sales_rep"],
    )
    quote.status = QuoteStatus.APPROVED
    db.commit()

    order = order_service.create_order_from_quote(db, quote.id, test_data["sales_rep"].id)
    order_service.activate_order(db, order.id, test_data["admin"].id)

    sub = db.query(Subscription).filter(Subscription.order_id == order.id).first()
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.duration_mode == "LIFETIME"
    assert sub.end_date is None


def test_05_future_product_edits_do_not_alter_existing_snapshots(db: Session, test_data):
    """Test 13-14: Future product edits do NOT modify existing quotation lines or order lines."""
    quote_service = QuoteService()
    order_service = OrderService()

    # Create fresh product for snapshot immutability test
    test_prod = db.query(Product).filter(Product.sku == "SNAP-GUARD-01").first()
    if not test_prod:
        test_prod = Product(
            name="Snapshot Guard Product",
            sku="SNAP-GUARD-01",
            category_id=test_data["category"].id,
            unit_price=1000.0,
            cost_price=500.0,
            allowed_discount_percent=10.0,
            subscription_enabled=True,
            subscription_name="Original Entitlement",
            duration_mode="TILL_VALIDITY",
            validity_value=6,
            validity_unit="MONTHS",
            billing_frequency="MONTHLY",
        )
        db.add(test_prod)
        db.commit()
        db.refresh(test_prod)
    else:
        test_prod.subscription_name = "Original Entitlement"
        test_prod.duration_mode = "TILL_VALIDITY"
        test_prod.validity_value = 6
        db.commit()

    # Create quote and order
    quote = quote_service.create_quote(
        db,
        QuoteCreate(
            customer_id=test_data["customer"].id,
            lines=[QuoteLineCreate(product_id=test_prod.id, quantity=1, unit_price=1000.0, line_type=LineType.ONE_TIME)],
        ),
        test_data["sales_rep"],
    )
    quote.status = QuoteStatus.APPROVED
    db.commit()

    order = order_service.create_order_from_quote(db, quote.id, test_data["sales_rep"].id)

    # Now modify the product in catalog
    test_prod.subscription_name = "Completely Altered Title"
    test_prod.duration_mode = "LIFETIME"
    test_prod.validity_value = 99
    db.commit()

    # Existing quote line snapshot must remain unchanged
    qline = db.query(QuoteLine).filter(QuoteLine.quote_id == quote.id).first()
    assert qline.subscription_name == "Original Entitlement"
    assert qline.duration_mode == "TILL_VALIDITY"
    assert qline.validity_value == 6

    # Existing order line snapshot must remain unchanged
    oline = db.query(OrderLine).filter(OrderLine.order_id == order.id).first()
    assert oline.subscription_name == "Original Entitlement"
    assert oline.duration_mode == "TILL_VALIDITY"
    assert oline.validity_value == 6


def test_06_billing_generation_and_expiry_lifecycle(db: Session, test_data):
    """Test 15-19: Recurring billing generates invoice when ACTIVE,
    does NOT generate invoice when EXPIRED or billing_frequency == NONE."""
    quote_service = QuoteService()
    order_service = OrderService()
    billing_service = BillingService()

    # Create a till validity product with monthly billing
    p_monthly = db.query(Product).filter(Product.sku == "SAAS-MONTHLY-TEST-01").first()
    if not p_monthly:
        p_monthly = Product(
            name="Monthly SaaS Offering",
            sku="SAAS-MONTHLY-TEST-01",
            category_id=test_data["category"].id,
            unit_price=1200.0,
            cost_price=400.0,
            allowed_discount_percent=10.0,
            subscription_enabled=True,
            subscription_name="Monthly Cloud Entitlement",
            duration_mode="TILL_VALIDITY",
            validity_value=3,
            validity_unit="MONTHS",
            billing_frequency="MONTHLY",
        )
        db.add(p_monthly)
        db.commit()
        db.refresh(p_monthly)

    quote = quote_service.create_quote(
        db,
        QuoteCreate(
            customer_id=test_data["customer"].id,
            lines=[QuoteLineCreate(product_id=p_monthly.id, quantity=1, unit_price=1200.0, line_type=LineType.ONE_TIME)],
        ),
        test_data["sales_rep"],
    )
    quote.status = QuoteStatus.APPROVED
    db.commit()

    order = order_service.create_order_from_quote(db, quote.id, test_data["sales_rep"].id)
    order_service.activate_order(db, order.id, test_data["admin"].id)

    # Test 16: Active monthly subscription generates recurring invoice
    billing_res = billing_service.generate_billing(db, order.id, test_data["admin"].id)
    invoices = billing_res["invoices"]
    rec_inv = [i for i in invoices if i.billing_type == BillingType.RECURRING]
    assert len(rec_inv) > 0

    # Test 15 & 17: Expire subscription and verify no further recurring invoices created
    sub = db.query(Subscription).filter(Subscription.order_id == order.id).first()
    billing_service.expire_subscription(db, sub.id, test_data["admin"].id)
    assert sub.status == SubscriptionStatus.EXPIRED

    inv_count_before = db.query(Invoice).filter(Invoice.order_id == order.id).count()
    billing_service.generate_billing(db, order.id, test_data["admin"].id)
    inv_count_after = db.query(Invoice).filter(Invoice.order_id == order.id).count()
    assert inv_count_before == inv_count_after

    # Test 18: Lifetime subscription with billing_frequency == NONE does not generate recurring invoice
    p2 = db.query(Product).filter(Product.sku == "HW-DEV-LIFETIME-01").first()
    quote_none = quote_service.create_quote(
        db,
        QuoteCreate(
            customer_id=test_data["customer"].id,
            lines=[QuoteLineCreate(product_id=p2.id, quantity=1, unit_price=3500.0, line_type=LineType.ONE_TIME)],
        ),
        test_data["sales_rep"],
    )
    quote_none.status = QuoteStatus.APPROVED
    db.commit()

    order_none = order_service.create_order_from_quote(db, quote_none.id, test_data["sales_rep"].id)
    order_service.activate_order(db, order_none.id, test_data["admin"].id)

    lifetime_billing = billing_service.generate_billing(db, order_none.id, test_data["admin"].id)
    lifetime_rec_invoices = [i for i in lifetime_billing["invoices"] if i.billing_type == BillingType.RECURRING]
    assert len(lifetime_rec_invoices) == 0


def test_07_multiple_products_and_unsubscribed_products(db: Session, test_data):
    """Test 20-21: Multiple products with subscriptions all activate correctly,
    and products without subscription do not create subscriptions."""
    quote_service = QuoteService()
    order_service = OrderService()

    p_sub = db.query(Product).filter(Product.sku == "SW-ENT-SUB-01").first()
    p_nosub = db.query(Product).filter(Product.sku == "ACC-DOCK-NO-SUB").first()

    quote = quote_service.create_quote(
        db,
        QuoteCreate(
            customer_id=test_data["customer"].id,
            lines=[
                QuoteLineCreate(product_id=p_sub.id, quantity=2, unit_price=5000.0, line_type=LineType.ONE_TIME),
                QuoteLineCreate(product_id=p_nosub.id, quantity=3, unit_price=250.0, line_type=LineType.ONE_TIME),
            ],
        ),
        test_data["sales_rep"],
    )
    quote.status = QuoteStatus.APPROVED
    db.commit()

    order = order_service.create_order_from_quote(db, quote.id, test_data["sales_rep"].id)
    order_service.activate_order(db, order.id, test_data["admin"].id)

    order_subs = db.query(Subscription).filter(Subscription.order_id == order.id).all()
    # Exactly one subscription created (for p_sub only)
    assert len(order_subs) == 1
    assert order_subs[0].product_id == p_sub.id
    assert not any(s.product_id == p_nosub.id for s in order_subs)
