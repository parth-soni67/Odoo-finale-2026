import React, { useState, useEffect } from "react";
import { api, getStoredToken } from "./api";
import { CustomerPortal } from "./components/CustomerPortal";
import { DealHealthDashboard } from "./components/DealHealthDashboard";
import { NegotiationsReview } from "./components/NegotiationsReview";
import { ProductManagement } from "./components/ProductManagement";
import { CustomerManagement } from "./components/CustomerManagement";
import { SalesReports } from "./components/SalesReports";
import {
  Activity,
  MessageSquare,
  Package,
  Users,
  BarChart3,
  Building2,
  LogOut,
  UserCheck,
} from "lucide-react";

const DEMO_PERSONAS = [
  { label: "Customer (Acme)", email: "customer@acmecorp.com", role: "CUSTOMER" },
  { label: "Sales Rep", email: "salesrep@dealflow360.internal", role: "SALES_REP" },
  { label: "Sales Manager", email: "salesmgr@dealflow360.internal", role: "SALES_MANAGER" },
  { label: "Admin", email: "admin@dealflow360.internal", role: "ADMIN" },
];

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState("deal-health");
  const [toasts, setToasts] = useState([]);
  const [authLoading, setAuthLoading] = useState(true);

  // Manual Login state
  const [loginEmail, setLoginEmail] = useState("customer@acmecorp.com");
  const [loginPassword, setLoginPassword] = useState("Demo1234!");

  useEffect(() => {
    initAuth();
  }, []);

  async function initAuth() {
    setAuthLoading(true);
    const token = getStoredToken();
    if (token) {
      try {
        const me = await api.getMe();
        setCurrentUser(me);
        if (me.role === "CUSTOMER") setActiveTab("portal");
        else setActiveTab("deal-health");
      } catch {
        api.logout();
        // Default login as customer for immediate demo readiness
        loginAs("customer@acmecorp.com");
      }
    } else {
      // Auto login as demo customer
      loginAs("customer@acmecorp.com");
    }
    setAuthLoading(false);
  }

  async function loginAs(email) {
    try {
      const res = await api.login(email, "Demo1234!");
      setCurrentUser(res.user);
      if (res.user.role === "CUSTOMER") {
        setActiveTab("portal");
      } else {
        setActiveTab("deal-health");
      }
      notify(`Logged in as ${res.user.full_name} (${res.user.role})`, "success");
    } catch (err) {
      notify("Login failed: " + err.message, "error");
    }
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
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg-main)", color: "#fff" }}>
        Loading DealFlow360...
      </div>
    );
  }

  const isCustomer = currentUser?.role === "CUSTOMER";

  return (
    <div className="app-container">
      {/* Global Header */}
      <header className="header">
        <div className="header-inner">
          <div className="brand" onClick={() => setActiveTab(isCustomer ? "portal" : "deal-health")}>
            <Activity size={24} color="var(--primary)" />
            <span>DealFlow<span style={{ color: "var(--primary)" }}>360</span></span>
            <span className="brand-badge">Intelligent Ops</span>
          </div>

          {/* Navigation Links for Internal Roles */}
          {!isCustomer && currentUser && (
            <nav className="nav-links">
              <button
                className={`nav-item ${activeTab === "deal-health" ? "active" : ""}`}
                onClick={() => setActiveTab("deal-health")}
              >
                <Activity size={16} /> Deal Health
              </button>
              <button
                className={`nav-item ${activeTab === "negotiations" ? "active" : ""}`}
                onClick={() => setActiveTab("negotiations")}
              >
                <MessageSquare size={16} /> Negotiations
              </button>
              <button
                className={`nav-item ${activeTab === "products" ? "active" : ""}`}
                onClick={() => setActiveTab("products")}
              >
                <Package size={16} /> Products
              </button>
              <button
                className={`nav-item ${activeTab === "customers" ? "active" : ""}`}
                onClick={() => setActiveTab("customers")}
              >
                <Users size={16} /> Customers
              </button>
              <button
                className={`nav-item ${activeTab === "reports" ? "active" : ""}`}
                onClick={() => setActiveTab("reports")}
              >
                <BarChart3 size={16} /> Reports
              </button>
            </nav>
          )}

          {/* Demo Persona Switcher & User Status */}
          <div className="user-controls">
            <div className="persona-switcher" title="Instantly switch authentication persona for judge demo">
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 700, paddingLeft: "0.2rem" }}>
                DEMO PERSONA:
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
            <h2 style={{ fontSize: "1.3rem", fontWeight: 800, marginBottom: "0.5rem" }}>Sign In to DealFlow360</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.5rem" }}>
              Select a persona from the top right bar or enter credentials below.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                api
                  .login(loginEmail, loginPassword)
                  .then((res) => {
                    setCurrentUser(res.user);
                    if (res.user.role === "CUSTOMER") setActiveTab("portal");
                    else setActiveTab("deal-health");
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
              <button type="submit" className="btn btn-primary" style={{ width: "100%", marginTop: "0.5rem" }}>
                Sign In
              </button>
            </form>
          </div>
        ) : isCustomer ? (
          <CustomerPortal user={currentUser} onNotify={notify} />
        ) : (
          <div>
            {activeTab === "deal-health" && (
              <DealHealthDashboard
                onInspectNegotiation={() => setActiveTab("negotiations")}
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
