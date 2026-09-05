import React, { useState, useEffect } from "react";
import { api, getStoredToken } from "./api";
import { CustomerPortal } from "./components/CustomerPortal";
import { DealHealthDashboard } from "./components/DealHealthDashboard";
import { NegotiationsReview } from "./components/NegotiationsReview";
import { ProductManagement } from "./components/ProductManagement";
import { CustomerManagement } from "./components/CustomerManagement";
import { SalesReports } from "./components/SalesReports";
import { QuotationWorkflow } from "./components/QuotationWorkflow";
import { ApprovalQueue } from "./components/ApprovalQueue";
import { OperationsFulfillment } from "./components/OperationsFulfillment";
import { FinanceBilling } from "./components/FinanceBilling";
import {
  Activity,
  MessageSquare,
  Package,
  Users,
  BarChart3,
  Building2,
  LogOut,
  UserCheck,
  FileText,
  CheckCircle2,
  Receipt,
  Truck,
  ShieldAlert,
} from "lucide-react";

const DEMO_PERSONAS = [
  { label: "Customer", email: "customer@acmecorp.com", role: "CUSTOMER" },
  { label: "Sales Rep", email: "salesrep@dealflow360.internal", role: "SALES_REP" },
  { label: "Sales Manager", email: "salesmgr@dealflow360.internal", role: "SALES_MANAGER" },
  { label: "Finance", email: "finance@dealflow360.internal", role: "FINANCE" },
  { label: "Operations", email: "ops@dealflow360.internal", role: "OPERATIONS" },
  { label: "Admin", email: "admin@dealflow360.internal", role: "ADMIN" },
];

const ROLE_NAVIGATION = {
  SALES_REP: [
    { id: "quotations", label: "Quotations", icon: FileText },
    { id: "products", label: "Products", icon: Package },
    { id: "customers", label: "Customers", icon: Users },
    { id: "negotiations", label: "Negotiations", icon: MessageSquare },
  ],
  SALES_MANAGER: [
    { id: "deal-health", label: "Deal Health", icon: Activity },
    { id: "quotations", label: "Quotations", icon: FileText },
    { id: "approvals", label: "Approvals", icon: CheckCircle2 },
    { id: "negotiations", label: "Negotiations", icon: MessageSquare },
    { id: "products", label: "Products", icon: Package },
    { id: "customers", label: "Customers", icon: Users },
    { id: "reports", label: "Reports", icon: BarChart3 },
  ],
  FINANCE: [
    { id: "approvals", label: "Approvals", icon: CheckCircle2 },
    { id: "billing", label: "Billing & Invoices", icon: Receipt },
    { id: "quotations", label: "Quotations", icon: FileText },
  ],
  OPERATIONS: [
    { id: "orders", label: "Orders & Fulfillment", icon: Truck },
  ],
  CUSTOMER: [
    { id: "portal", label: "Customer Portal", icon: Building2 },
  ],
  ADMIN: [
    { id: "deal-health", label: "Deal Health", icon: Activity },
    { id: "quotations", label: "Quotations", icon: FileText },
    { id: "approvals", label: "Approvals", icon: CheckCircle2 },
    { id: "negotiations", label: "Negotiations", icon: MessageSquare },
    { id: "products", label: "Products", icon: Package },
    { id: "customers", label: "Customers", icon: Users },
    { id: "orders", label: "Fulfillment", icon: Truck },
    { id: "billing", label: "Billing", icon: Receipt },
    { id: "reports", label: "Reports", icon: BarChart3 },
  ],
};

const ROLE_ALLOWED_TABS = {
  SALES_REP: ["quotations", "products", "customers", "negotiations"],
  SALES_MANAGER: ["deal-health", "quotations", "approvals", "negotiations", "products", "customers", "reports"],
  FINANCE: ["approvals", "billing", "quotations"],
  OPERATIONS: ["orders", "fulfillment"],
  CUSTOMER: ["portal"],
  ADMIN: [
    "deal-health",
    "quotations",
    "approvals",
    "negotiations",
    "products",
    "customers",
    "reports",
    "orders",
    "fulfillment",
    "billing",
  ],
};

const ROLE_DEFAULT_TAB = {
  SALES_REP: "quotations",
  SALES_MANAGER: "deal-health",
  FINANCE: "approvals",
  OPERATIONS: "orders",
  CUSTOMER: "portal",
  ADMIN: "deal-health",
};

function getRouteFromLocation() {
  const hash = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  if (hash) return hash;
  const path = window.location.pathname.replace(/^\//, "").split("?")[0];
  return path || "";
}

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState("quotations");
  const [toasts, setToasts] = useState([]);
  const [authLoading, setAuthLoading] = useState(true);

  // Manual Login state
  const [loginEmail, setLoginEmail] = useState("salesrep@dealflow360.internal");
  const [loginPassword, setLoginPassword] = useState("Demo1234!");

  useEffect(() => {
    initAuth();

    function handleUrlChange() {
      const route = getRouteFromLocation();
      if (route) {
        setActiveTab(route);
      }
    }
    window.addEventListener("hashchange", handleUrlChange);
    window.addEventListener("popstate", handleUrlChange);
    return () => {
      window.removeEventListener("hashchange", handleUrlChange);
      window.removeEventListener("popstate", handleUrlChange);
    };
  }, []);

  async function initAuth() {
    setAuthLoading(true);
    const token = getStoredToken();
    const route = getRouteFromLocation();

    if (token) {
      try {
        const me = await api.getMe();
        setCurrentUser(me);
        applyInitialRoute(me, route);
      } catch {
        api.logout();
        loginAs("salesrep@dealflow360.internal", route);
      }
    } else {
      // Default initial login as Sales Rep to highlight the primary new workflow
      loginAs("salesrep@dealflow360.internal", route);
    }
    setAuthLoading(false);
  }

  function applyInitialRoute(user, route) {
    if (route) {
      setActiveTab(route);
      window.location.hash = `#/${route}`;
    } else {
      const defaultTab = ROLE_DEFAULT_TAB[user.role] || "portal";
      setActiveTab(defaultTab);
      window.location.hash = `#/${defaultTab}`;
    }
  }

  async function loginAs(email, requestedRoute = null) {
    try {
      const res = await api.login(email, "Demo1234!");
      setCurrentUser(res.user);
      const targetRoute = requestedRoute || getRouteFromLocation();
      if (targetRoute) {
        setActiveTab(targetRoute);
        window.location.hash = `#/${targetRoute}`;
      } else {
        const def = ROLE_DEFAULT_TAB[res.user.role] || "portal";
        setActiveTab(def);
        window.location.hash = `#/${def}`;
      }
      notify(`Logged in as ${res.user.full_name} (${res.user.role})`, "success");
    } catch (err) {
      notify("Login failed: " + err.message, "error");
    }
  }

  function navigateTo(tab) {
    setActiveTab(tab);
    window.location.hash = `#/${tab}`;
  }

  function handleLogout() {
    api.logout();
    setCurrentUser(null);
    notify("Logged out", "info");
  }

  function notify(message, type = "info") {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }

  if (authLoading) {
    return (
      <div
        style={{
          display: "flex",
          height: "100vh",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg-main)",
          color: "var(--text-primary)",
          fontWeight: 600,
        }}
      >
        Loading DealFlow360...
      </div>
    );
  }

  const roleNavItems = currentUser ? ROLE_NAVIGATION[currentUser.role] || [] : [];
  const allowedTabs = currentUser ? ROLE_ALLOWED_TABS[currentUser.role] || [] : [];
  const isAuthorized = allowedTabs.includes(activeTab);

  return (
    <div className="app-container">
      {/* Global Header */}
      <header className="header">
        <div className="header-inner">
          <div
            className="brand"
            onClick={() => navigateTo(ROLE_DEFAULT_TAB[currentUser?.role] || "portal")}
            style={{ cursor: "pointer" }}
          >
            <Activity size={24} color="var(--primary)" />
            <span>
              DealFlow<span style={{ color: "var(--primary)" }}>360</span>
            </span>
            <span className="brand-badge">Intelligent Ops</span>
          </div>

          {/* Dynamic Role-Based Navigation */}
          {currentUser && (
            <nav className="nav-links">
              {roleNavItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    className={`nav-item ${isActive ? "active" : ""}`}
                    onClick={() => navigateTo(item.id)}
                  >
                    <Icon size={16} /> {item.label}
                  </button>
                );
              })}
            </nav>
          )}

          {/* Demo Persona Switcher & User Status */}
          <div className="user-controls">
            <div className="persona-switcher" title="Instantly switch authentication persona for judge demo">
              <span
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  fontWeight: 700,
                  paddingLeft: "0.2rem",
                }}
              >
                ROLE SWITCHER:
              </span>
              {DEMO_PERSONAS.map((p) => {
                const isActive = currentUser?.email === p.email;
                return (
                  <button
                    key={p.email}
                    className={`persona-btn ${isActive ? "active" : ""}`}
                    onClick={() => loginAs(p.email)}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>

            {currentUser && (
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span className="badge badge-neutral" style={{ fontSize: "0.75rem" }}>
                  <UserCheck size={12} /> {currentUser.role}
                </span>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleLogout}
                  title="Logout"
                >
                  <LogOut size={13} />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="main-content">
        {!currentUser ? (
          <div className="card" style={{ maxWidth: "420px", margin: "4rem auto" }}>
            <h2 style={{ fontSize: "1.3rem", fontWeight: 800, marginBottom: "0.5rem" }}>
              Sign In to DealFlow360
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.5rem" }}>
              Select a persona from the top bar or enter credentials below.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                api
                  .login(loginEmail, loginPassword)
                  .then((res) => {
                    setCurrentUser(res.user);
                    const def = ROLE_DEFAULT_TAB[res.user.role] || "portal";
                    navigateTo(def);
                    notify(`Signed in as ${res.user.full_name}`, "success");
                  })
                  .catch((err) => notify("Login failed: " + err.message, "error"));
              }}
            >
              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                  type="email"
                  className="form-input"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  required
                />
              </div>
              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: "100%", marginTop: "0.5rem" }}
              >
                Sign In
              </button>
            </form>
          </div>
        ) : !isAuthorized ? (
          /* Route Protection: Access Restricted View */
          <div
            className="card"
            style={{
              maxWidth: "560px",
              margin: "4rem auto",
              textAlign: "center",
              padding: "3.5rem 2rem",
            }}
          >
            <ShieldAlert size={52} color="var(--status-high)" style={{ marginBottom: "1rem" }} />
            <h2
              style={{
                fontSize: "1.5rem",
                fontWeight: 800,
                marginBottom: "0.5rem",
                color: "var(--text-primary)",
              }}
            >
              Access Restricted
            </h2>
            <p
              style={{
                color: "var(--text-secondary)",
                fontSize: "0.95rem",
                marginBottom: "1.75rem",
                lineHeight: 1.5,
              }}
            >
              You don't have permission to access this page. Your role (<strong>{currentUser.role}</strong>) is not authorized for <code>/{activeTab}</code>.
            </p>
            <button
              className="btn btn-primary"
              onClick={() => navigateTo(ROLE_DEFAULT_TAB[currentUser.role] || "portal")}
            >
              Back to Dashboard
            </button>
          </div>
        ) : (
          /* Authorized Component Rendering */
          <div>
            {activeTab === "portal" && (
              <CustomerPortal user={currentUser} onNotify={notify} />
            )}
            {activeTab === "quotations" && (
              <QuotationWorkflow
                user={currentUser}
                onNotify={notify}
                onInspectDeal={() => navigateTo("deal-health")}
              />
            )}
            {activeTab === "approvals" && (
              <ApprovalQueue user={currentUser} onNotify={notify} />
            )}
            {activeTab === "deal-health" && (
              <DealHealthDashboard
                onInspectNegotiation={() => navigateTo("negotiations")}
                onNotify={notify}
              />
            )}
            {activeTab === "negotiations" && (
              <NegotiationsReview onNotify={notify} />
            )}
            {activeTab === "products" && (
              <ProductManagement user={currentUser} onNotify={notify} />
            )}
            {activeTab === "customers" && (
              <CustomerManagement user={currentUser} onNotify={notify} />
            )}
            {activeTab === "reports" && (
              <SalesReports onNotify={notify} />
            )}
            {(activeTab === "orders" || activeTab === "fulfillment") && (
              <OperationsFulfillment onNotify={notify} />
            )}
            {activeTab === "billing" && (
              <FinanceBilling onNotify={notify} />
            )}
          </div>
        )}
      </main>

      {/* Floating Notifications Toast Container */}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.type}`}>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
