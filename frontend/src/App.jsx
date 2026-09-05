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

  // Auth Mode: "login" or "signup"
  const [authMode, setAuthMode] = useState("login");
  const [authSubmitting, setAuthSubmitting] = useState(false);

  // Login Form State
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Signup Form State
  const [signupFullName, setSignupFullName] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [signupConfirmPassword, setSignupConfirmPassword] = useState("");

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
        setCurrentUser(null);
      }
    } else {
      setCurrentUser(null);
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
    setAuthMode("login");
    setLoginPassword("");
    notify("Logged out", "info");
  }

  function notify(message, type = "info") {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }

  function handleLoginSubmit(e) {
    e.preventDefault();
    if (!loginEmail.trim()) {
      notify("Email address is required.", "error");
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(loginEmail.trim())) {
      notify("Please enter a valid email address.", "error");
      return;
    }
    if (!loginPassword) {
      notify("Password is required.", "error");
      return;
    }

    setAuthSubmitting(true);
    api
      .login(loginEmail.trim(), loginPassword)
      .then((res) => {
        setCurrentUser(res.user);
        const def = ROLE_DEFAULT_TAB[res.user.role] || "portal";
        navigateTo(def);
        notify(`Signed in as ${res.user.full_name}`, "success");
      })
      .catch((err) => {
        let msg = err.message;
        if (msg.includes("INVALID_CREDENTIALS") || msg.toLowerCase().includes("invalid")) {
          msg = "Invalid email or password.";
        }
        notify(msg, "error");
      })
      .finally(() => setAuthSubmitting(false));
  }

  function handleSignupSubmit(e) {
    e.preventDefault();
    if (!signupFullName.trim()) {
      notify("Full Name is required.", "error");
      return;
    }
    if (!signupEmail.trim()) {
      notify("Email address is required.", "error");
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(signupEmail.trim())) {
      notify("Please enter a valid email address.", "error");
      return;
    }
    if (!signupPassword) {
      notify("Password is required.", "error");
      return;
    }
    if (signupPassword !== signupConfirmPassword) {
      notify("Passwords do not match.", "error");
      return;
    }

    setAuthSubmitting(true);
    api
      .signup(signupFullName.trim(), signupEmail.trim(), signupPassword)
      .then(() => {
        notify("Account created successfully.", "success");
        setLoginEmail(signupEmail.trim());
        setLoginPassword("");
        setAuthMode("login");
      })
      .catch((err) => {
        let msg = err.message;
        if (msg.includes("EMAIL_EXISTS") || msg.toLowerCase().includes("already exists")) {
          msg = "An account with this email already exists.";
        } else if (!msg || msg.includes("500") || msg.includes("Failed to fetch")) {
          msg = "Unable to create your account. Please try again.";
        }
        notify(msg, "error");
      })
      .finally(() => setAuthSubmitting(false));
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
            onClick={() => {
              if (currentUser) {
                navigateTo(ROLE_DEFAULT_TAB[currentUser.role] || "portal");
              }
            }}
            style={{ cursor: currentUser ? "pointer" : "default" }}
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
            <div className="persona-switcher" title="Quickly login using pre-seeded demo accounts">
              <span
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  fontWeight: 700,
                  paddingLeft: "0.2rem",
                }}
              >
                DEMO PERSONAS:
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
                  <UserCheck size={12} /> AUTHENTICATED: {currentUser.role}
                </span>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleLogout}
                  title="Logout"
                >
                  <LogOut size={13} /> Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="main-content">
        {!currentUser ? (
          authMode === "login" ? (
            /* Sign In Page */
            <div className="card" style={{ maxWidth: "440px", margin: "3.5rem auto", padding: "2.25rem 2rem" }}>
              <div style={{ textAlign: "center", marginBottom: "1.75rem" }}>
                <Activity size={36} color="var(--primary)" style={{ margin: "0 auto 0.5rem auto" }} />
                <h2 style={{ fontSize: "1.45rem", fontWeight: 800, color: "var(--text-primary)" }}>
                  Sign In to DealFlow360
                </h2>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: "0.35rem" }}>
                  Enter your email and password to access your authorized workspace.
                </p>
              </div>

              <form onSubmit={handleLoginSubmit}>
                <div className="form-group">
                  <label className="form-label">Email Address</label>
                  <input
                    type="email"
                    className="form-input"
                    placeholder="name@company.com"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    autoComplete="email"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Password</label>
                  <input
                    type="password"
                    className="form-input"
                    placeholder="••••••••"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    autoComplete="current-password"
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: "100%", marginTop: "0.75rem" }}
                  disabled={authSubmitting}
                >
                  {authSubmitting ? "Signing In..." : "Sign In"}
                </button>
              </form>

              <div
                style={{
                  marginTop: "1.75rem",
                  paddingTop: "1.25rem",
                  borderTop: "1px solid var(--border-subtle)",
                  textAlign: "center",
                  fontSize: "0.9rem",
                  color: "var(--text-secondary)",
                }}
              >
                Don't have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode("signup");
                    setSignupFullName("");
                    setSignupEmail("");
                    setSignupPassword("");
                    setSignupConfirmPassword("");
                  }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--primary)",
                    fontWeight: 700,
                    cursor: "pointer",
                    padding: 0,
                    textDecoration: "underline",
                  }}
                >
                  Create Account
                </button>
              </div>
            </div>
          ) : (
            /* Create Account Page */
            <div className="card" style={{ maxWidth: "440px", margin: "3.5rem auto", padding: "2.25rem 2rem" }}>
              <div style={{ textAlign: "center", marginBottom: "1.75rem" }}>
                <Building2 size={36} color="var(--primary)" style={{ margin: "0 auto 0.5rem auto" }} />
                <h2 style={{ fontSize: "1.45rem", fontWeight: 800, color: "var(--text-primary)" }}>
                  Create your DealFlow360 account
                </h2>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: "0.35rem" }}>
                  Register for a customer account to track quotations, orders, and fulfillment.
                </p>
              </div>

              <form onSubmit={handleSignupSubmit}>
                <div className="form-group">
                  <label className="form-label">Full Name</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Jane Doe"
                    value={signupFullName}
                    onChange={(e) => setSignupFullName(e.target.value)}
                    autoComplete="name"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Email Address</label>
                  <input
                    type="email"
                    className="form-input"
                    placeholder="name@company.com"
                    value={signupEmail}
                    onChange={(e) => setSignupEmail(e.target.value)}
                    autoComplete="email"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Password</label>
                  <input
                    type="password"
                    className="form-input"
                    placeholder="••••••••"
                    value={signupPassword}
                    onChange={(e) => setSignupPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Confirm Password</label>
                  <input
                    type="password"
                    className="form-input"
                    placeholder="••••••••"
                    value={signupConfirmPassword}
                    onChange={(e) => setSignupConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: "100%", marginTop: "0.75rem" }}
                  disabled={authSubmitting}
                >
                  {authSubmitting ? "Creating Account..." : "Create Account"}
                </button>
              </form>

              <div
                style={{
                  marginTop: "1.75rem",
                  paddingTop: "1.25rem",
                  borderTop: "1px solid var(--border-subtle)",
                  textAlign: "center",
                  fontSize: "0.9rem",
                  color: "var(--text-secondary)",
                }}
              >
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => setAuthMode("login")}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--primary)",
                    fontWeight: 700,
                    cursor: "pointer",
                    padding: 0,
                    textDecoration: "underline",
                  }}
                >
                  Sign In
                </button>
              </div>
            </div>
          )
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
