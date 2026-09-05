# DealFlow360 — Architecture & Development Guidelines

This document outlines the layered architecture, module responsibilities, security/RBAC protocols, and coding rules for the DealFlow360 backend platform.

---

## 1. System Topology

The platform is designed around a strictly decoupled, layered architecture:

```text
React / Vite Web Portal (Person 4 & Frontend)
             │
             ▼ (HTTP / REST + JSON / JWT)
      FastAPI Gateway
             │
             ▼ (Pydantic Schema Validation)
     API Route Handlers (app/api/routes/)
             │
             ▼ (Business Logic & Workflow Rules)
       Service Layer (app/services/)
             │
             ▼ (ORM Query & Transactions)
     SQLAlchemy Models (app/models/)
             │
             ▼ (SQLAlchemy Engine / Connection Pool)
PostgreSQL Database (Local fallback: SQLite)
```

---

## 2. Where Business Logic Should Live

> **IMPORTANT ARCHITECTURAL RULE:**  
> **Route handlers must NOT contain core domain calculations, risk heuristics, or fulfillment routing logic.**

Follow this standard execution pattern:

1. **Route Handler (`app/api/routes/*.py`)**:
   - Parses HTTP parameters.
   - Triggers Pydantic input validation.
   - Enforces authentication & RBAC dependencies (`get_current_user`, `require_roles(...)`).
   - Delegates work to the appropriate Service function.
   - Serializes output to Pydantic Response schemas.

2. **Service Layer (`app/services/*.py`)**:
   - Executes all business calculations (e.g. margin checks, discount rule evaluations, approval determination).
   - Manages database transaction boundaries (`db.commit()`, `db.rollback()`).
   - Emits audit log entries (`AuditLog`) for auditable state changes.

3. **Data Model Layer (`app/models/*.py`)**:
   - Represents the persistent state schema.
   - Enforces column constraints, defaults, foreign keys, and cascading rules.

---

## 3. Authentication & RBAC Flow

### 3.1 Authentication
1. Client issues `POST /api/auth/login` with `email` and `password`.
2. `AuthService.authenticate_user()` validates credentials using `bcrypt` comparison against `User.hashed_password`.
3. If valid, a signed JWT bearer token is created containing claims:
   - `sub`: User ID (int as string)
   - `role`: Role enum value (`ADMIN`, `SALES_REP`, etc.)
   - `email`: User email
   - `exp`: Expiration timestamp (default: 60 minutes)
4. Client includes token in subsequent requests: `Authorization: Bearer <token>`.

### 3.2 Role-Based Access Control (RBAC)
FastAPI dependency injection enforces role restrictions cleanly:

```python
from fastapi import APIRouter, Depends
from app.core.dependencies import require_roles
from app.models.user import Role, User

router = APIRouter()

@router.post("/quotes/{id}/approve")
def approve_quote(
    quote_id: int,
    # Restrict to Sales Managers and Admins only
    current_user: User = Depends(require_roles(Role.SALES_MANAGER, Role.ADMIN))
):
    ...
```

If an unauthorized user attempts access, a standardized `403 Forbidden` response is automatically raised:
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Operation not permitted. Required roles: ['SALES_MANAGER', 'ADMIN'], your role: SALES_REP"
  }
}
```

---

## 4. Team Modular Responsibilities

| Teammate | Focus Area | Key Models & Services |
| :--- | :--- | :--- |
| **Person 1** | Backend Foundation, Database, Auth, Migrations, Core Data Contracts | `app/core/`, `app/models/`, `app/api/routes/auth.py`, `app/api/routes/health.py` |
| **Person 2** | Quotation Engine, Margin Calculation, Risk Assessment, Discount Governance & Approval Routing | `Quote`, `QuoteLine`, `Approval`, `DiscountRule`, `quote_service.py`, `approval_service.py` |
| **Person 3** | Multi-Warehouse Inventory Splitting, Order Fulfillment & Hybrid Billing (One-time + Subscription) | `Order`, `FulfillmentSplit`, `Warehouse`, `Inventory`, `Invoice`, `Subscription`, `fulfillment_service.py`, `billing_service.py` |
| **Person 4** | Customer Negotiation Portal, Deal Health Scoring, AI Recommendations & Frontend Integration | `Negotiation`, `Recommendation`, `DealHealthAlert`, `portal_service.py`, `recommendation_service.py` |

---

## 5. Development Guidelines

1. **Never commit `.env`**: Always use `.env.example` as reference.
2. **Deterministic Migrations**: Whenever database schema changes are required, use `alembic revision --autogenerate -m "<description>"` and apply via `alembic upgrade head`.
3. **Database Portability**: The foundation supports PostgreSQL in staging/production, and SQLite out-of-the-box for rapid local development and automated pytest runs without external daemon dependencies.
4. **Idempotent Seed Scripts**: Always ensure seed routines (`python -m seed.seed_data`) can be executed repeatedly without failing on duplicate constraints.
