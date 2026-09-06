# DealFlow360

> **Unified Enterprise Deal Lifecycle, Multi-Warehouse Fulfillment & Recurring Subscription Billing Engine**

DealFlow360 is an enterprise-grade CPQ (Configure, Price, Quote) and Order-to-Cash fulfillment platform designed for modern multi-channel commerce. It bridges the gap between sales quoting, automated discount governance, customer counter-negotiations, multi-warehouse inventory allocation, and recurring subscription lifecycle management.

---

## Problem Statement

Modern enterprise sales operations suffer from fragmented toolchains:
1. **Siloed Quoting & Pricing**: Sales reps often quote discounts without real-time risk scoring, resulting in margin erosion or protracted, untracked approval delays.
2. **Disconnected Customer Negotiations**: Customers receive static PDFs with no collaborative counter-offer mechanism, driving communication into unrecorded email chains.
3. **Fulfillment & Backorder Chaos**: Orders lack automated inventory checking across multiple warehouses, creating unfulfilled commitments and manual stock tracking.
4. **Subscription Lifecycle & Invoicing Disconnect**: Hybrid sales combining one-time hardware and recurring software/support subscriptions frequently lead to inaccurate billing cycles, lost recurring revenue, and missing historical subscription records upon repurchases.

---

## Solution

**DealFlow360** consolidates the complete order lifecycle into a unified, audit-compliant platform:
- **Intelligent CPQ Engine**: Dynamic discount ceiling calculation, line-level margins, and real-time risk scoring.
- **Hierarchical Multi-Level Approvals**: Automatic approval routing to Sales Managers and Finance based on discount tiers and deal value thresholds, complete with customer-visible governance feedback.
- **Collaborative Customer Portal**: Self-service portal where customers review quotes, propose structured counter-offers with business rationale, accept terms, track multi-warehouse shipments, and manage subscriptions.
- **Intelligent Multi-Warehouse Fulfillment**: Automatic order splitting, stock allocation, and backorder status tracking across independent physical warehouses.
- **Flexible Billing & Subscription Engine**: First-class handling of one-time hardware sales, bundled service entitlements, limited-duration subscriptions (with automated start/end dates and billing cycles), and lifetime licenses.
- **Immutable Subscription & Audit History**: Historical subscription periods are preserved without corruption upon customer renewal or re-purchase.

---

## Key Features

- **Granular Role-Based Access Control (RBAC)**: Distinct permissions for `CUSTOMER`, `SALES_REP`, `SALES_MANAGER`, `FINANCE`, `OPERATIONS`, and `ADMIN`.
- **Real-Time Discount Governance**: Automated tier checks against Customer Tier discount ceilings with automatic escalation flags.
- **Customer Negotiation Workflow**: Two-way structured negotiation allowing customers to request custom prices and quantities, triggering manager re-evaluations while maintaining audit trails.
- **Customer-Facing Approval Notes**: Persisted manager and finance review comments displayed directly on customer quote views.
- **Warehouse & Stock Management**: Real-time inventory tracking by product category (Hardware, Software, Professional Services, Maintenance & Support) with manual restocking and multi-location fulfillment.
- **Backorder Tracking**: Transparent backorder indicators when demand exceeds on-hand stock.
- **Dual Billing Architecture**: Instant generation of one-time invoices alongside recurring subscription billing schedules.
- **Document Generation**: Instant export of professional commercial invoices in both **PDF** and **Excel (XLSX)** formats.
- **Enterprise UI Design**: Clean, high-contrast, accessible enterprise theme built with responsive layouts, fluid modals, and zero external CSS bloat.

---

## Architecture

DealFlow360 follows a decoupled client-server architecture with an asynchronous REST API backend and a responsive component-driven single-page application frontend.

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React 19 / Vite)               │
│  - Unified Role Navigation    - Customer Self-Service Portal│
│  - CPQ Quoting Engine         - Multi-Warehouse Dashboard   │
│  - Financial Approval Center  - Invoicing & Subscriptions   │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / JSON REST API
┌──────────────────────────────▼──────────────────────────────┐
│                    Backend (FastAPI / Python)               │
│  - JWT Authentication & RBAC  - CPQ & Pricing Calculation   │
│  - Risk Scoring & Governance  - Multi-Warehouse Fulfillment │
│  - Negotiation Engine         - Subscription Lifecycle Engine│
│  - ReportLab PDF Generation   - OpenPyXL Spreadsheet Engine │
└──────────────────────────────┬──────────────────────────────┘
                               │ SQLAlchemy 2.0 ORM
┌──────────────────────────────▼──────────────────────────────┐
│           Database (PostgreSQL / SQLite fallback)           │
│  - Alembic Versioned Schema   - Deterministic Seed Engine   │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

- **Frontend**:
  - React 19 (`^19.2.8`)
  - Vite (`^8.2.2`)
  - Lucide React (`^1.41.0`)
  - Vanilla Enterprise CSS Design System (clean white/neutral palette, zero framework lock-in)
  - Oxlint for high-performance static analysis
- **Backend**:
  - Python 3.11+
  - FastAPI (`>=0.115.0`) & Uvicorn ASGI
  - Pydantic v2 (`>=2.10.0`) for strict schema validation
  - SQLAlchemy 2.0 (`>=2.0.36`) ORM
  - Alembic (`>=1.14.0`) for database schema migrations
  - PyJWT (`>=2.10.0`) & Passlib/Bcrypt for secure token-based authentication
  - ReportLab (`>=4.0.0`) for enterprise PDF invoice rendering
  - OpenPyXL (`>=3.1.0`) for dynamic Excel spreadsheet generation
  - Pytest (`>=8.3.0`) & HTTPX for integration test coverage
- **Database**:
  - SQLite (zero-config local development and testing)
  - PostgreSQL ready via standard SQLAlchemy connection string

---

## Core Workflow

```
1. Customer / Sales Setup
   └─ Sales Rep selects customer, reviews credit tier & discount ceilings.
2. CPQ Quotation Creation
   └─ Rep adds products, toggles [One-Time Purchase] or [With Subscription],
      specifies validity & billing cycles, and sets requested discounts.
3. Automated Governance & Risk Evaluation
   └─ System checks discount limits:
      • Standard approval (within threshold)
      • Manager approval required (exceeds rep authority)
      • Finance approval required (high deal size or deep discount)
4. Approval & Governance Notes
   └─ Sales Manager and/or Finance review the deal and append customer-facing review comments.
5. Customer Quote Review & Negotiation
   └─ Customer views quote with reviewer notes.
   └─ Customer either ACCEPTS or SUBMITS COUNTER-OFFER with requested pricing and rationale.
6. Order Conversion & Multi-Warehouse Fulfillment
   └─ Upon acceptance, an Order is automatically generated.
   └─ Inventory engine queries available stock across warehouses:
      • In-Stock: Allocates stock and creates warehouse fulfillment splits.
      • Out-of-Stock: Automatically marks line items as Backordered.
7. Subscription & Entitlement Activation
   └─ Recurring line items create active subscriptions with calculated start/end dates.
   └─ Repurchasing later establishes a distinct, clean historical subscription record.
8. Invoicing & Payment
   └─ Generates immediate one-time invoices and recurring subscription billing schedules.
   └─ Customer downloads commercial invoices in PDF or XLSX format and completes payment.
```

---

## User Roles & Permissions

| Role | Access Scope & Capabilities |
| :--- | :--- |
| **`CUSTOMER`** | View own quotes, propose counter-offers, accept quotes, view orders, track warehouse fulfillment, inspect billing, download PDF/XLS invoices, view historical subscriptions, update company profile. Strict multi-tenant data isolation. |
| **`SALES_REP`** | Create and manage quotations, select customers, configure product lines (one-time vs. subscription), view catalog prices and discount ceilings. No self-approval privileges. |
| **`SALES_MANAGER`** | Review and approve escalated quotations, evaluate deal risk scores, add customer-facing review notes, manage warehouses, view inventory across categories, and restock products. |
| **`FINANCE`** | Review high-value deals requiring financial authorization, approve margins, inspect global billing, monitor invoices, and track revenue health. |
| **`OPERATIONS`** | View confirmed orders, monitor multi-warehouse fulfillment splits, track backorders, and confirm warehouse dispatches. |
| **`ADMIN`** | Complete system configuration, user provisioning, global auditing, and administrative management. |

---

## Installation & Setup

### Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- Node.js 18+ and npm
- Git

### 1. Repository Setup
```bash
git clone https://github.com/parth-soni67/Odoo-finale-2026.git
cd Odoo-finale-2026
```

### 2. Backend Setup
```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### 3. Database Initialization & Deterministic Seeding
```bash
# Run database migrations (or auto-create via SQLAlchemy)
# Seed the database with customers, products, warehouses, and demo users:
python -m seed.seed_data
```

### 4. Run the Backend Server
```bash
# Start FastAPI development server on port 8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 5. Frontend Setup
```bash
# Open a new terminal in the repository root
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
The application will be accessible at `http://localhost:3000` (or `http://localhost:5173` depending on available ports).

---

## Demo Accounts

> **IMPORTANT**: The credentials below are provided strictly for hackathon evaluation and local demonstration. Do not use these in production environments.

| Role | Email | Password | Intended Demo Walkthrough |
| :--- | :--- | :--- | :--- |
| **Customer** | `customer@acmecorp.com` | `Demo1234!` | Portal review, counter-offers, accept quote, invoice download, subscription history |
| **Sales Rep** | `salesrep@dealflow360.internal` | `Demo1234!` | Create quotations, configure subscriptions, submit for approval |
| **Sales Manager** | `salesmgr@dealflow360.internal` | `Demo1234!` | Quotation approvals, review comments, warehouse stock management, restock |
| **Finance** | `finance@dealflow360.internal` | `Demo1234!` | Margin review, finance approval, invoice and payment oversight |
| **Operations** | `ops@dealflow360.internal` | `Demo1234!` | Warehouse allocation, fulfillment tracking, backorder resolution |
| **Admin** | `admin@dealflow360.internal` | `Demo1234!` | Full system administration and governance overview |

---

## API Documentation

FastAPI automatically generates interactive OpenAPI documentation:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc Interactive Reference**: `http://127.0.0.1:8000/redoc`

Key API Route Groups:
- `/api/auth` — Authentication, registration, current user profile (`/me`)
- `/api/quotes` — Quotation CRUD, line-item pricing, governance evaluation
- `/api/negotiations` — Customer counter-offers, manager re-evaluations, negotiation history
- `/api/approvals` — Manager/Finance review comments and approval decisions
- `/api/orders` — Order conversion, warehouse allocation, fulfillment status
- `/api/warehouses` — Warehouse directory, category-based stock levels, restocking
- `/api/billing` — Invoicing, PDF/XLS export, subscriptions, payment recording

---

## Verification & Test Results

DealFlow360 has undergone a rigorous release audit:

| Test Suite | Command | Result | Status |
| :--- | :--- | :--- | :--- |
| **Backend Unit & Integration Tests** | `cd backend && python -m pytest -q` | **193 passed** (0 failures, 0 skipped) |  PASS |
| **Frontend Production Build** | `cd frontend && npm run build` | **Built in 424ms** (0 build errors) |  PASS |
| **Frontend Static Code Analysis** | `cd frontend && npm run lint` | **0 errors** (warnings non-blocking) |  PASS |
| **End-to-End Regression Test Suite** | `node scratch/run_regression_suite.cjs` | **37 / 37 scenarios passed** |  PASS |
| **Deterministic Database Seeding** | `cd backend && python -m seed.seed_data` | **Idempotent** (zero duplicate errors) |  PASS |

---

## Project Structure

```
DealFlow360/
├── backend/
│   ├── alembic/              # Database migration definitions
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/       # FastAPI route controllers (auth, quotes, approvals, etc.)
│   │   ├── core/             # Configuration, JWT security, database engine
│   │   ├── models/           # SQLAlchemy data models (user, quote, order, warehouse, etc.)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── services/         # Business logic (pricing, governance, fulfillment, billing)
│   ├── seed/                 # Deterministic seed data generator
│   ├── tests/                # Pytest comprehensive test suite (193 tests)
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/       # Enterprise UI components (UnifiedSidebar, QuoteDetails, etc.)
│   │   ├── context/          # React AuthContext with real backend token validation
│   │   ├── App.jsx           # Master application router and role-based view orchestration
│   │   └── index.css         # Enterprise CSS design tokens and component styling
│   ├── package.json          # Node dependencies and scripts
│   └── vite.config.js        # Vite bundler configuration with API proxying
├── docs/                     # API contracts, architecture diagrams, and database schemas
├── .env.example              # Non-sensitive environment configuration template
└── README.md                 # Project documentation
```

---

## Hackathon Demo Flow (Golden Path)

To experience the complete platform capabilities in under 5 minutes:

1. **Log in as Sales Rep** (`salesrep@dealflow360.internal` / `Demo1234!`):
   - Click **Create Quotation**.
   - Select customer **Acme Corp**.
   - Add **Hardware Line**: Enterprise Server (Quantity: 2, Purchase Type: *One-Time Purchase*).
   - Add **Software Line**: Cloud Management Platform (Quantity: 5, Purchase Type: *With Subscription*, Duration: 12 Months, Billing: Quarterly).
   - Apply a 25% discount (exceeds standard ceiling to trigger governance).
   - Click **Submit for Approval**.
2. **Log in as Sales Manager** (`salesmgr@dealflow360.internal` / `Demo1234!`):
   - Open **Approvals**. View risk score and margin analysis.
   - Enter Review Comments: *"Approved based on enterprise annual commitment."*
   - Click **Confirm Approval**.
3. **Log in as Customer** (`customer@acmecorp.com` / `Demo1234!`):
   - Go to **My Quotes** → Select the quotation.
   - Review pricing, lines, and notice the **Sales Manager Review Comment**.
   - Click **Accept Quotation**.
4. **Inspect Multi-Warehouse Fulfillment & Operations** (`ops@dealflow360.internal` / `Demo1234!`):
   - Navigate to **Orders & Fulfillment**.
   - Verify order generation and view warehouse allocation across Central and Regional depots.
5. **Customer Invoicing & Subscription History** (`customer@acmecorp.com` / `Demo1234!`):
   - Navigate to **Billing & Invoices**.
   - Download the generated invoice in **PDF** or **XLSX**.
   - Switch to **Subscription History** tab: verify the active 12-month cloud platform subscription with correct start date, end date, and quarterly billing cycle.
