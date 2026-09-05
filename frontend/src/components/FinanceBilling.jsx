import React, { useState, useEffect } from "react";
import { api } from "../api";
import { Receipt, Clock, RotateCcw, Sparkles } from "lucide-react";

export function FinanceBilling({ onNotify }) {
  const [invoices, setInvoices] = useState([]);
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadBilling();
  }, []);

  async function loadBilling() {
    setLoading(true);
    try {
      const [invData, subData] = await Promise.all([
        api.getPortalInvoices().catch(() => []),
        api.getPortalSubscriptions().catch(() => []),
      ]);
      setInvoices(invData || []);
      setSubscriptions(subData || []);
    } catch (err) {
      onNotify("Error loading billing data: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.5rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--text-primary)" }}>
            Financial Operations & Invoicing
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Reconcile one-time hardware payments, recurring SaaS subscriptions, and invoice statuses.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={loadBilling}>
          <RotateCcw size={14} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>
          <Clock size={32} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <div>Loading Invoices & Subscriptions...</div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Active Subscriptions */}
          <div className="card">
            <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Sparkles size={18} color="var(--primary)" /> Active Subscriptions & SaaS Entitlements
              </div>
              <span className="badge badge-info">{subscriptions.length} Subscriptions</span>
            </div>

            {subscriptions.length === 0 ? (
              <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-secondary)" }}>
                No active subscriptions found.
              </div>
            ) : (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Subscription Name</th>
                      <th>Order #</th>
                      <th>Duration Mode</th>
                      <th>Billing Cadence</th>
                      <th>Status</th>
                      <th>Start Date</th>
                      <th>End Date</th>
                      <th>Next Billing Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subscriptions.map((sub) => (
                      <tr key={sub.id}>
                        <td><strong>{sub.name || "Software Entitlement"}</strong></td>
                        <td>{sub.order_id ? `ORD-${sub.order_id}` : "N/A"}</td>
                        <td>{sub.duration_mode === "LIFETIME" ? "Lifetime" : `${sub.validity_value || 1} ${sub.validity_unit || "MONTHS"}`}</td>
                        <td>
                          <span className={`badge ${sub.billing_frequency !== "NONE" ? "badge-info" : "badge-neutral"}`}>
                            {sub.billing_frequency === "NONE" ? "Included / Free" : sub.billing_frequency}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${sub.status === "ACTIVE" ? "badge-healthy" : "badge-medium"}`}>
                            {sub.status}
                          </span>
                        </td>
                        <td style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                          {sub.start_date ? new Date(sub.start_date).toLocaleDateString() : "N/A"}
                        </td>
                        <td style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                          {sub.end_date ? new Date(sub.end_date).toLocaleDateString() : "Lifetime (No Expiry)"}
                        </td>
                        <td style={{ fontSize: "0.85rem", fontWeight: 600, color: sub.next_billing_date ? "var(--primary)" : "var(--text-muted)" }}>
                          {sub.next_billing_date ? new Date(sub.next_billing_date).toLocaleDateString() : "Non-recurring"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Invoices */}
          <div className="card">
            <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Receipt size={18} color="var(--status-healthy)" /> Billing Invoices
              </div>
              <span className="badge badge-neutral">{invoices.length} Invoices</span>
            </div>

            {invoices.length === 0 ? (
              <div style={{ padding: "2.5rem 1.5rem", textAlign: "center", color: "var(--text-secondary)" }}>
                No active invoices generated yet.
              </div>
            ) : (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Invoice #</th>
                      <th>Order #</th>
                      <th>Billing Type</th>
                      <th>Amount</th>
                      <th>Status</th>
                      <th>Due Date</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((inv) => {
                      const amt = inv.total_amount !== undefined ? inv.total_amount : inv.amount || 0;
                      return (
                        <tr key={inv.id}>
                          <td><strong>{inv.invoice_number || `INV-${inv.id}`}</strong></td>
                          <td>{inv.order_id ? `ORD-${inv.order_id}` : "N/A"}</td>
                          <td>
                            <span className={`badge ${inv.billing_type === "RECURRING" ? "badge-info" : "badge-neutral"}`}>
                              {inv.billing_type || "ONE_TIME"}
                            </span>
                          </td>
                          <td style={{ fontWeight: 700 }}>
                            ${Number(amt).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td>
                            <span className={`badge ${inv.status === "PAID" ? "badge-healthy" : "badge-info"}`}>
                              {inv.status || "ISSUED"}
                            </span>
                          </td>
                          <td style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                            {inv.due_date ? new Date(inv.due_date).toLocaleDateString() : "30 Days"}
                          </td>
                          <td style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                            {inv.created_at ? new Date(inv.created_at).toLocaleDateString() : "Recent"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
