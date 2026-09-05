# DealFlow360 — Shared API Contract Specification

This document defines the unified API contract for DealFlow360. All frontend components and backend modules developed by Person 1, Person 2, Person 3, and Person 4 must adhere to these schemas and conventions.

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

## 3. Planned Module Contracts

The following endpoints represent agreed data contracts for Person 2, Person 3, and Person 4.
> **Status Note**: Marked as `[PLANNED / NOT IMPLEMENTED]` in the foundation stage.

### 3.1 Catalog & Customers [IMPLEMENTED - Person 4]
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

### 3.2 Quotations & Risk Assessment [PLANNED]
- **`POST /api/quotes`** `[PLANNED / NOT IMPLEMENTED]`
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
          "discount_percent": 15.0,
          "line_type": "ONE_TIME"
        },
        {
          "product_id": 4,
          "quantity": 1,
          "unit_price": 800.0,
          "discount_percent": 10.0,
          "line_type": "RECURRING"
        }
      ]
    }
    ```
  - Response 201: `QuoteResponse` with calculated `subtotal`, `total_discount`, `total_amount`, `risk_score`, and `requires_approval`.
- **`GET /api/quotes/{quote_id}`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: Authenticated
  - Response 200: Complete `QuoteResponse` including lines, customer info, and approval status.
- **`POST /api/quotes/{quote_id}/risk`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: Authenticated
  - Response 200: `QuoteRiskResponse` (`risk_score`, `requires_approval`, `reasons: ["Discount exceeds customer ceiling 10%", "Margin below floor"]`)

### 3.3 Approval Workflow [PLANNED]
- **`GET /api/quotes/{quote_id}/approvals`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `SALES_REP`, `SALES_MANAGER`, `FINANCE`, `ADMIN`
  - Response 200: Array of `ApprovalResponse` (`id`, `approval_type`, `status`, `reason`, `comments`)
- **`POST /api/quotes/{quote_id}/approve`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `SALES_MANAGER`, `FINANCE`, `ADMIN`
  - Request: `{"comments": "Approved after margin review"}`
  - Response 200: Updated `ApprovalResponse`
- **`POST /api/quotes/{quote_id}/reject`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `SALES_MANAGER`, `FINANCE`, `ADMIN`
  - Request: `{"comments": "Discount too high, renegotiate"}`
  - Response 200: Updated `ApprovalResponse`

### 3.4 Recommendations & Advisory [PLANNED]
- **`GET /api/quotes/{quote_id}/recommendations`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `SALES_REP`, `SALES_MANAGER`
  - Response 200: List of recommendations (`product_id`, `recommendation_type: "UPSELL"|"CROSS_SELL"`, `reason`, `score`)

### 3.5 Order Fulfillment & Warehousing [PLANNED]
- **`POST /api/orders/{order_id}/fulfillment/suggest`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `OPERATIONS`, `ADMIN`
  - Response 200: Suggested multi-warehouse fulfillment split based on live inventory.
- **`POST /api/orders/{order_id}/fulfillment/confirm`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `OPERATIONS`, `ADMIN`
  - Request: Confirmed warehouse allocations
  - Response 200: Updated order status and fulfillment splits.

### 3.6 Billing & Payments [PLANNED]
- **`GET /api/orders/{order_id}/billing`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `FINANCE`, `ADMIN`
  - Response 200: Split invoices showing one-time vs recurring subscription breakdown.
- **`POST /api/orders/{order_id}/payment`** `[PLANNED / NOT IMPLEMENTED]`
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
  - Response 200: Customer fulfillment tracking (empty array awaiting Person 3 fulfillment).
- **`GET /api/portal/invoices`** `[IMPLEMENTED]`
  - Access: `CUSTOMER`, `ADMIN`
  - Response 200: Customer billing invoices (empty array awaiting Person 3 billing).

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
