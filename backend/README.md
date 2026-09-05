# DealFlow360 — Backend Engine

Intelligent, Self-Governing Sales Operations Platform Backend built with FastAPI, SQLAlchemy, PostgreSQL, Alembic, and JWT Authentication.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+ (tested on Python 3.13)
- PostgreSQL (or local SQLite fallback)

### 2. Setup Environment
```bash
# Create and activate virtual environment (optional if using global)
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` in repository root or set environment variables:
```bash
cp .env.example .env
```
Default configuration connects to SQLite (`sqlite:///./dealflow360.db`) if `DATABASE_URL` is omitted, or connects to PostgreSQL when configured:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/dealflow360
```

### 4. Database Migrations
Apply schema migrations with Alembic:
```bash
alembic upgrade head
```

### 5. Seed Demo Data
Populate deterministic demo users, catalog, customers, warehouses, and discount rules:
```bash
python -m seed.seed_data
```

### 6. Run Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive API docs are available at:
- **Swagger UI**: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- **ReDoc**: [http://127.0.0.1:8000/api/redoc](http://127.0.0.1:8000/api/redoc)
- **Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 🧪 Testing

Run test suite with pytest:
```bash
pytest -v
```

---

## 👥 Demo User Credentials (Development / Demo Only)

All seeded accounts use password: `Demo1234!`

| Role | Email | Use Case |
| :--- | :--- | :--- |
| **Admin** | `admin@dealflow360.internal` | Full administrative configuration |
| **Sales Rep** | `salesrep@dealflow360.internal` | Create quotes, view catalog |
| **Sales Manager** | `salesmgr@dealflow360.internal` | Approve quotes & discounts |
| **Finance** | `finance@dealflow360.internal` | Commercial approval, billing & invoices |
| **Operations** | `ops@dealflow360.internal` | Warehouse split & fulfillment |
| **Customer** | `customer@acmecorp.com` | Customer negotiation portal |

---

## 📂 Project Structure

```text
backend/
├── alembic/              # Database migration configurations and revisions
├── app/
│   ├── api/routes/       # API route controllers (health, auth)
│   ├── core/             # Configuration, DB connection, Security, RBAC dependencies
│   ├── models/           # SQLAlchemy database entities
│   ├── schemas/          # Pydantic validation and serialization models
│   ├── services/         # Business logic layer (AuthService, etc.)
│   └── main.py           # FastAPI application entrypoint and exception handlers
├── seed/                 # Deterministic seed script for demo data
├── tests/                # Pytest automated test suite
├── alembic.ini           # Alembic migration configuration
├── requirements.txt      # Python dependencies
└── README.md
```
