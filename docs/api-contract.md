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

### 3.1 Catalog & Customers [PLANNED]
- **`GET /api/products`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: Authenticated
  - Response 200: Array of `ProductResponse` (`id`, `name`, `sku`, `category_id`, `unit_price`, `allowed_discount_percent`, `is_active`)
- **`GET /api/customers`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: Authenticated
  - Response 200: Array of `CustomerResponse` (`id`, `company_name`, `contact_name`, `email`, `tier`, `discount_ceiling`)

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

### 3.7 Customer Negotiation Portal [PLANNED]
- **`GET /api/portal/quotes/{quote_id}`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `CUSTOMER`, `ADMIN`
  - Response 200: Customer-facing quote summary.
- **`POST /api/portal/quotes/{quote_id}/negotiate`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `CUSTOMER`
  - Request: `{"requested_change": "discount_percent", "proposed_value": "18.0"}`
  - Response 201: Created `Negotiation` record with `status: "PENDING"`.
- **`POST /api/portal/quotes/{quote_id}/confirm`** `[PLANNED / NOT IMPLEMENTED]`
  - Access: `CUSTOMER`
  - Response 200: Converts approved quote to confirmed `Order`.
