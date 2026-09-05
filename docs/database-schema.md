# DealFlow360 — Database Schema Reference

This document outlines the shared SQLAlchemy database models, relationships, foreign keys, and enumeration types established for DealFlow360.

---

## 1. Core Enumerations

| Enum Name | Allowed Values | Usage |
| :--- | :--- | :--- |
| **`Role`** | `ADMIN`, `SALES_REP`, `SALES_MANAGER`, `FINANCE`, `OPERATIONS`, `CUSTOMER` | User role-based authorization |
| **`CustomerTier`** | `STANDARD`, `GROWTH`, `ENTERPRISE` | Customer tier & discount rules |
| **`LineType`** | `ONE_TIME`, `RECURRING` | Hybrid quoting and billing split |
| **`QuoteStatus`** | `DRAFT`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `ACCEPTED`, `CANCELLED` | Quotation lifecycle |
| **`ApprovalStatus`** | `PENDING`, `APPROVED`, `REJECTED` | Governance approval workflow |
| **`ApprovalType`** | `MANAGER`, `FINANCE` | Tiered approval levels |
| **`OrderStatus`** | `PENDING`, `CONFIRMED`, `PROCESSING`, `FULFILLED`, `CANCELLED` | Order lifecycle |
| **`FulfillmentSplitStatus`** | `ALLOCATED`, `PICKED`, `SHIPPED`, `BACKORDERED` | Multi-warehouse routing status |
| **`BillingType`** | `ONE_TIME`, `RECURRING` | Invoicing breakdown |
| **`InvoiceStatus`** | `DRAFT`, `ISSUED`, `PAID`, `OVERDUE`, `VOID` | Invoicing state |
| **`PaymentStatus`** | `PENDING`, `SUCCESSFUL`, `FAILED`, `REFUNDED` | Simulated payment processing |
| **`SubscriptionStatus`** | `ACTIVE`, `PAUSED`, `CANCELLED`, `EXPIRED` | Recurring subscription contract |
| **`NegotiationStatus`** | `PENDING`, `APPROVED`, `REJECTED`, `ACCEPTED` | Customer negotiation requests |

---

## 2. Entity Specifications & Relationships

### 2.1 Identity & Access
- **`users`**
  - `id` (PK, Integer)
  - `email` (String(255), Unique, Indexed)
  - `hashed_password` (String(255))
  - `full_name` (String(255))
  - `role` (Enum: `Role`)
  - `is_active` (Boolean, default: True)
  - `created_at` (DateTime, default: now)
  - `updated_at` (DateTime, onupdate: now)
  - *Relations*: `quotes_created`, `approvals_given`, `audit_logs`

- **`audit_logs`**
  - `id` (PK, Integer)
  - `user_id` (FK -> `users.id`, nullable)
  - `entity_type` (String(100), Indexed)
  - `entity_id` (Integer, Indexed)
  - `action` (String(50))
  - `old_value` (Text, nullable)
  - `new_value` (Text, nullable)
  - `timestamp` (DateTime, default: now)

### 2.2 Customer & Catalog
- **`customers`**
  - `id` (PK, Integer)
  - `company_name` (String(255), Indexed)
  - `contact_name` (String(255))
  - `email` (String(255), Indexed)
  - `phone` (String(50), nullable)
  - `tier` (Enum: `CustomerTier`, default: `STANDARD`)
  - `discount_ceiling` (Float, default: 10.0)
  - `created_at` (DateTime, default: now)
  - *Relations*: `quotes`, `orders`, `subscriptions`, `invoices`, `negotiations`

- **`product_categories`**
  - `id` (PK, Integer)
  - `name` (String(100), Unique, Indexed)
  - `description` (Text, nullable)
  - *Relations*: `products`, `discount_rules`

- **`products`**
  - `id` (PK, Integer)
  - `name` (String(255), Indexed)
  - `sku` (String(100), Unique, Indexed)
  - `category_id` (FK -> `product_categories.id`, nullable)
  - `description` (Text, nullable)
  - `unit_price` (Float, default: 0.0)
  - `cost_price` (Float, default: 0.0)
  - `allowed_discount_percent` (Float, default: 0.0)
  - `is_active` (Boolean, default: True)
  - *Relations*: `category`, `inventory_items`, `quote_lines`, `order_lines`, `recommendations`

- **`discount_rules`**
  - `id` (PK, Integer)
  - `name` (String(255))
  - `customer_tier` (Enum: `CustomerTier`, nullable)
  - `category_id` (FK -> `product_categories.id`, nullable)
  - `min_quantity` (Integer, default: 1)
  - `max_discount_percent` (Float)
  - `is_active` (Boolean, default: True)
  - `created_at` (DateTime, default: now)

### 2.3 Warehousing & Inventory
- **`warehouses`**
  - `id` (PK, Integer)
  - `name` (String(255))
  - `location` (String(255))
  - `is_active` (Boolean, default: True)
  - *Relations*: `inventory_items`, `fulfillment_splits`

- **`inventories`**
  - `id` (PK, Integer)
  - `warehouse_id` (FK -> `warehouses.id`)
  - `product_id` (FK -> `products.id`)
  - `quantity_available` (Integer, default: 0)

### 2.4 Quotations, Governance & Negotiations
- **`quotes`**
  - `id` (PK, Integer)
  - `quote_number` (String(50), Unique, Indexed)
  - `customer_id` (FK -> `customers.id`)
  - `created_by` (FK -> `users.id`)
  - `status` (Enum: `QuoteStatus`, default: `DRAFT`)
  - `subtotal` (Float, default: 0.0)
  - `total_discount` (Float, default: 0.0)
  - `total_amount` (Float, default: 0.0)
  - `risk_score` (Float, default: 0.0)
  - `requires_approval` (Boolean, default: False)
  - `created_at` (DateTime, default: now)
  - `updated_at` (DateTime, onupdate: now)
  - *Relations*: `lines`, `approvals`, `orders`, `negotiations`, `recommendations`, `health_alerts`

- **`quote_lines`**
  - `id` (PK, Integer)
  - `quote_id` (FK -> `quotes.id`, ondelete: cascade)
  - `product_id` (FK -> `products.id`)
  - `quantity` (Integer, default: 1)
  - `unit_price` (Float)
  - `discount_percent` (Float, default: 0.0)
  - `discount_amount` (Float, default: 0.0)
  - `line_total` (Float)
  - `line_type` (Enum: `LineType`, default: `ONE_TIME`)

- **`approvals`**
  - `id` (PK, Integer)
  - `quote_id` (FK -> `quotes.id`, ondelete: cascade)
  - `approver_id` (FK -> `users.id`, nullable)
  - `approval_type` (Enum: `ApprovalType`)
  - `status` (Enum: `ApprovalStatus`, default: `PENDING`)
  - `reason` (Text, nullable)
  - `comments` (Text, nullable)
  - `created_at` (DateTime, default: now)
  - `resolved_at` (DateTime, nullable)

- **`negotiations`**
  - `id` (PK, Integer)
  - `quote_id` (FK -> `quotes.id`, ondelete: cascade)
  - `customer_id` (FK -> `customers.id`)
  - `requested_change` (String(255))
  - `previous_value` (String(255), nullable)
  - `proposed_value` (String(255))
  - `status` (Enum: `NegotiationStatus`, default: `PENDING`)
  - `created_at` (DateTime, default: now)
  - `resolved_at` (DateTime, nullable)

- **`recommendations`**
  - `id` (PK, Integer)
  - `quote_id` (FK -> `quotes.id`, ondelete: cascade)
  - `product_id` (FK -> `products.id`)
  - `recommendation_type` (String(50))
  - `reason` (Text, nullable)
  - `score` (Float, default: 1.0)
  - `created_at` (DateTime, default: now)

- **`deal_health_alerts`**
  - `id` (PK, Integer)
  - `quote_id` (FK -> `quotes.id`, ondelete: cascade)
  - `severity` (String(50), default: `MEDIUM`)
  - `alert_type` (String(100))
  - `message` (Text)
  - `created_at` (DateTime, default: now)

### 2.5 Orders, Fulfillment & Billing
- **`orders`**
  - `id` (PK, Integer)
  - `order_number` (String(50), Unique, Indexed)
  - `quote_id` (FK -> `quotes.id`, nullable)
  - `customer_id` (FK -> `customers.id`)
  - `status` (Enum: `OrderStatus`, default: `PENDING`)
  - `total_amount` (Float, default: 0.0)
  - `created_at` (DateTime, default: now)
  - `updated_at` (DateTime, onupdate: now)
  - *Relations*: `lines`, `invoices`, `subscriptions`

- **`order_lines`**
  - `id` (PK, Integer)
  - `order_id` (FK -> `orders.id`, ondelete: cascade)
  - `product_id` (FK -> `products.id`)
  - `quantity` (Integer, default: 1)
  - `unit_price` (Float)
  - `discount_percent` (Float, default: 0.0)
  - `line_total` (Float)
  - `line_type` (Enum: `LineType`, default: `ONE_TIME`)
  - *Relations*: `fulfillment_splits`

- **`fulfillment_splits`**
  - `id` (PK, Integer)
  - `order_line_id` (FK -> `order_lines.id`, ondelete: cascade)
  - `warehouse_id` (FK -> `warehouses.id`)
  - `quantity_allocated` (Integer)
  - `status` (Enum: `FulfillmentSplitStatus`, default: `ALLOCATED`)

- **`subscription_plans`**
  - `id` (PK, Integer)
  - `name` (String(255))
  - `billing_frequency` (String(50), default: "monthly")
  - `price` (Float)
  - `description` (Text, nullable)

- **`subscriptions`**
  - `id` (PK, Integer)
  - `customer_id` (FK -> `customers.id`)
  - `plan_id` (FK -> `subscription_plans.id`)
  - `order_id` (FK -> `orders.id`, nullable)
  - `status` (Enum: `SubscriptionStatus`, default: `ACTIVE`)
  - `current_period_start` (DateTime, nullable)
  - `current_period_end` (DateTime, nullable)
  - `renewal_date` (DateTime, nullable)

- **`invoices`**
  - `id` (PK, Integer)
  - `invoice_number` (String(50), Unique, Indexed)
  - `order_id` (FK -> `orders.id`, nullable)
  - `customer_id` (FK -> `customers.id`)
  - `total_amount` (Float)
  - `status` (Enum: `InvoiceStatus`, default: `DRAFT`)
  - `due_date` (DateTime, nullable)
  - `billing_type` (Enum: `BillingType`, default: `ONE_TIME`)
  - `created_at` (DateTime, default: now)
  - *Relations*: `payments`

- **`payments`**
  - `id` (PK, Integer)
  - `invoice_id` (FK -> `invoices.id`, ondelete: cascade)
  - `amount` (Float)
  - `payment_method` (String(50), default: `SIMULATED_CARD`)
  - `payment_status` (Enum: `PaymentStatus`, default: `PENDING`)
  - `transaction_id` (String(100), nullable)
  - `created_at` (DateTime, default: now)
