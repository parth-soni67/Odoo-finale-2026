# DealFlow360 — Shared API Contract Specification

This document defines the unified API contract for DealFlow360. All frontend components and backend modules developed by Person 1, Person 2, Person 3, and Person 4 adhere to these schemas and conventions.

---

## 1. Global Conventions

### Base URL & Versioning
- All API routes are prefixed with `/api`.
- OpenAPI interactive documentation: `/api/docs`
- ReDoc documentation: `/api/redoc`

### Standard Error Response Format
All error responses (4xx and 5xx) conform to this schema:

```json
{
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human readable description of the error",
    "details": null
  }
}
```

Common Error Codes:
- `AUTHENTICATION_REQUIRED` (401)
- `INVALID_CREDENTIALS` (401)
- `INVALID_TOKEN` (401)
- `FORBIDDEN` (403)
- `NOT_FOUND` (404)
- `VALIDATION_ERROR` (422)
- `INTERNAL_SERVER_ERROR` (500)

### Authentication Header
Protected endpoints require a Bearer token:
```http
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

---

## 2. Implemented Foundation APIs

### 2.1 Health Check
- **Endpoint**: `GET /api/health`
- **Access**: Public
- **Description**: Verifies service status and live database connectivity.
- **Response 200 OK**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "connected"
}
```

### 2.2 User Login
- **Endpoint**: `POST /api/auth/login`
- **Access**: Public
- **Request Body**:
```json
{
  "email": "salesrep@dealflow360.internal",
  "password": "Demo1234!"
}
```
- **Response 200 OK**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 2,
    "email": "salesrep@dealflow360.internal",
    "full_name": "Sam Representative",
    "role": "SALES_REP",
    "is_active": true,
    "created_at": "2026-09-05T10:30:00Z",
    "updated_at": null
  }
}
```

### 2.3 Current User Profile
- **Endpoint**: `GET /api/auth/me`
- **Access**: Authenticated (Any active user)
- **Response 200 OK**:
```json
{
  "id": 2,
  "email": "salesrep@dealflow360.internal",
  "full_name": "Sam Representative",
  "role": "SALES_REP",
  "is_active": true,
  "created_at": "2026-09-05T10:30:00Z",
  "updated_at": null
}
```

---

## 3. Module Contracts

### 3.1 Catalog & Customers [IMPLEMENTED - Person 2 & Person 4]
- **`GET /api/products`** `[IMPLEMENTED]`
  - Access: Authenticated (Active items enforced for `CUSTOMER`)
  - Query: `search`, `category_id`, `is_active`, `skip`, `limit`
  - Response 200: Array of `ProductResponse` (`id`, `name`, `sku`, `category`, `unit_price`, `cost_price`, `allowed_discount_percent`, `is_active`)
- **`GET /api/products/categories`** `[IMPLEMENTED]`
  - Access: Authenticated
  - Response 200: Array of `ProductCategoryResponse` (`id`, `name`, `description`)
- **`POST /api/products`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`
  - Request: `ProductCreate`
  - Response 201: `ProductResponse`
- **`PUT /api/products/{id}`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`
  - Request: `ProductUpdate`
  - Response 200: `ProductResponse`
- **`DELETE /api/products/{id}`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`
  - Query: `hard_delete=false`
  - Response 200: `ProductResponse`
- **`GET /api/customers`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`, `SALES_REP`, `FINANCE`
  - Query: `search`, `tier`, `skip`, `limit`
  - Response 200: Array of `CustomerResponse` (`id`, `company_name`, `contact_name`, `email`, `phone`, `tier`, `discount_ceiling`, `created_at`)
- **`GET /api/customers/{id}`** `[IMPLEMENTED]`
  - Access: Authenticated (Strict isolation: `CUSTOMER` role restricted to own customer id)
  - Response 200: `CustomerResponse`
- **`POST /api/customers`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`
  - Request: `CustomerCreate`
  - Response 201: `CustomerResponse`
- **`PUT /api/customers/{id}`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`
  - Request: `CustomerUpdate`
  - Response 200: `CustomerResponse`
- **`GET /api/approvals/pending`** `[IMPLEMENTED]`
  - Access: `SALES_MANAGER`, `FINANCE`, `ADMIN`
  - Description: Lists pending quote approvals awaiting action by the current reviewer.
  - Response 200: Array of `ApprovalResponse`

### 3.2 Quotations & Risk Assessment [IMPLEMENTED — PERSON 2]
- **`POST /api/quotes`**
  - Access: `SALES_REP`, `SALES_MANAGER`, `ADMIN`
  - Request:
    ```json
    {
      "customer_id": 1,
      "lines": [
        {
          "product_id": 1,
          "quantity": 10,
          "unit_price": 1200.0,
          "discount_percent": 8.0,
          "line_type": "ONE_TIME"
        },
        {
          "product_id": 3,
          "quantity": 1,
          "unit_price": 2500.0,
          "discount_percent": 18.0,
          "line_type": "ONE_TIME"
        }
      ]
    }
    ```
  - Response 201: `QuoteResponse` with calculated `subtotal`, `total_discount`, `total_amount`, `risk_score`, `requires_approval`, and `status`.
- **`GET /api/quotes`**
  - Access: Authenticated (scoping: Sales Rep sees own quotes; Managers/Finance/Admin see all quotes)
  - Response 200: Array of `QuoteResponse`
- **`GET /api/quotes/{quote_id}`**
  - Access: Authenticated
  - Response 200: Complete `QuoteResponse` including lines, customer info, and approval records.
- **`PATCH /api/quotes/{quote_id}`**
  - Access: `SALES_REP`, `SALES_MANAGER`, `ADMIN`
  - Request: `QuoteUpdate` (`lines`, `customer_id`, `status`)
  - Response 200: Updated `QuoteResponse` with recalculations and re-evaluated risk.
- **`POST /api/quotes/{quote_id}/risk`**
  - Access: Authenticated
  - Response 200: `QuoteRiskResponse` (`quote_id`, `risk_score`, `requires_approval`, `requires_manager_approval`, `requires_finance_approval`, `violations`, `reasons`)

### 3.3 Approval Workflow [IMPLEMENTED — PERSON 2]
- **`GET /api/quotes/{quote_id}/approvals`**
  - Access: Authenticated
  - Response 200: Array of `ApprovalResponse` (`id`, `approval_type`, `status`, `reason`, `comments`, `resolved_at`)
- **`POST /api/quotes/{quote_id}/approve`**
  - Access: `SALES_MANAGER`, `FINANCE`, `ADMIN`
  - Request (optional): `{"comments": "Approved after margin assessment"}`
  - Response 200: Updated `ApprovalResponse`
- **`POST /api/quotes/{quote_id}/reject`**
  - Access: `SALES_MANAGER`, `FINANCE`, `ADMIN`
  - Request (optional): `{"comments": "Discount excessive for standard tier"}`
  - Response 200: Updated `ApprovalResponse`

### 3.4 Recommendations & Advisory [IMPLEMENTED — PERSON 2]
- **`GET /api/quotes/{quote_id}/recommendations`**
  - Access: Authenticated (`SALES_REP`, `SALES_MANAGER`, `ADMIN`, etc.)
  - Description: Generates rule-based, deterministic UPSELL and CROSS_SELL product recommendations with estimated margin impact.
  - Response 200:
    ```json
    {
      "quote_id": 101,
      "recommendations": [
        {
          "product_id": 4,
          "product_name": "24/7 Mission-Critical SLA Support (Monthly)",
          "type": "CROSS_SELL",
          "reason": "Protect operational continuity and uptime with 24/7 Mission-Critical SLA Support (Monthly)",
          "suggested_quantity": 1,
          "unit_price": 800.0,
          "estimated_margin_impact": 600.0
        }
      ]
    }
    ```

### 3.5 Order Fulfillment & Warehousing [IMPLEMENTED - Person 3]
- **`POST /api/orders`** `[IMPLEMENTED]`
  - Access: Authenticated
  - Request: Create order from approved quote
  - Response 201: `OrderResponse`
- **`GET /api/orders/{order_id}`** `[IMPLEMENTED]`
  - Access: Authenticated
  - Response 200: Order details with order lines and fulfillment splits
- **`POST /api/orders/{order_id}/fulfillment/suggest`** `[IMPLEMENTED]`
  - Access: `OPERATIONS`, `ADMIN`
  - Response 200: Suggested multi-warehouse fulfillment split based on live inventory.
- **`POST /api/orders/{order_id}/fulfillment/confirm`** `[IMPLEMENTED]`
  - Access: `OPERATIONS`, `ADMIN`
  - Request: Confirmed warehouse allocations
  - Response 200: Updated order status and fulfillment splits.
- **`POST /api/orders/{order_id}/fulfillment/override`** `[IMPLEMENTED]`
  - Access: `OPERATIONS`, `ADMIN`
  - Response 200: Manual override of warehouse splits.

### 3.6 Billing & Payments [IMPLEMENTED - Person 3]
- **`GET /api/orders/{order_id}/billing`** `[IMPLEMENTED]`
  - Access: `FINANCE`, `ADMIN`
  - Response 200: Split invoices showing one-time vs recurring subscription breakdown.
- **`POST /api/orders/{order_id}/billing`** `[IMPLEMENTED]`
  - Access: `FINANCE`, `ADMIN`
  - Response 201: Generated invoices and active subscriptions.
- **`POST /api/orders/{order_id}/payment`** `[IMPLEMENTED]`
  - Access: `FINANCE`, `ADMIN`, `CUSTOMER`
  - Request: `{"invoice_id": 1, "amount": 11000.0, "payment_method": "SIMULATED_CARD"}`
  - Response 200: `PaymentResponse` (`payment_status: "SUCCESSFUL"`, `transaction_id`)

### 3.7 Customer Negotiation Portal [IMPLEMENTED - Person 4]
- **`GET /api/portal/profile`** `[IMPLEMENTED]`
  - Access: `CUSTOMER`, `ADMIN`
  - Response 200: Authenticated customer company details, tier, and discount ceiling.
- **`GET /api/portal/quotes`** `[IMPLEMENTED]`
  - Access: `CUSTOMER`, `ADMIN`
  - Response 200: Array of quotes owned by the authenticated customer.
- **`GET /api/portal/quotes/{quote_id}`** `[IMPLEMENTED]`
  - Access: `CUSTOMER`, `ADMIN` (Strict multi-tenant customer isolation enforced)
  - Response 200: Customer-facing quote details (lines, pricing, discounts, negotiation history, omitting internal risk/manager notes).
- **`POST /api/portal/quotes/{quote_id}/negotiate`** `[IMPLEMENTED]`
  - Access: `CUSTOMER`, `ADMIN`
  - Request: `{"requested_change": "discount_percent", "proposed_value": "12.0"}`
  - Response 201: Created `Negotiation` record with `status: "PENDING"`.
- **`POST /api/portal/quotes/{quote_id}/confirm`** `[IMPLEMENTED]`
  - Access: `CUSTOMER`, `ADMIN`
  - Response 200: Customer confirms/accepts approved quote.
- **`GET /api/portal/orders`** `[IMPLEMENTED]`
  - Access: `CUSTOMER`, `ADMIN`
  - Response 200: Customer fulfillment tracking.
- **`GET /api/portal/invoices`** `[IMPLEMENTED]`
  - Access: `CUSTOMER`, `ADMIN`
  - Response 200: Customer billing invoices.

### 3.8 Internal Negotiation Review & Re-approval [IMPLEMENTED - Person 4]
- **`GET /api/quotes/{quote_id}/negotiations`** `[IMPLEMENTED]`
  - Access: Authenticated (Owner customer or internal sales roles)
  - Response 200: Negotiation history thread for a quote.
- **`GET /api/negotiations`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`, `SALES_REP`
  - Query: `status` (PENDING, APPROVED, REJECTED)
  - Response 200: List of negotiations across quotes.
- **`POST /api/negotiations/{id}/approve`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`
  - Request: `{"comments": "Approved 12% discount"}`
  - Behavior: Updates quote lines/total discount, triggers re-approval workflow (`status = PENDING_APPROVAL`, `requires_approval = True`), records AuditLog.
  - Response 200: Updated `NegotiationResponse`.
- **`POST /api/negotiations/{id}/reject`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`
  - Request: `{"comments": "Exceeds discount policy"}`
  - Response 200: Updated `NegotiationResponse`.

### 3.9 Deal Health & Reporting [IMPLEMENTED - Person 4]
- **`GET /api/deal-health`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`, `SALES_REP`, `FINANCE`
  - Response 200: `DealHealthSummaryResponse` with KPI cards (total active, healthy, medium, high risk, pending approval, active negotiations) and itemized deals table with deterministic scores (0-100), risk levels, detected signals, and next actions.
- **`GET /api/deal-health/{quote_id}`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`, `SALES_REP`, `FINANCE`
  - Response 200: Detailed deal health diagnosis, risk signals list, and actionable recommendations.
- **`GET /api/reports/sales-summary`** `[IMPLEMENTED]`
  - Access: `ADMIN`, `SALES_MANAGER`, `SALES_REP`, `FINANCE`
  - Response 200: Executive aggregate sales metrics (total pipeline value, approved value, conversion ratios, active counter-offers, customer/product counts).
