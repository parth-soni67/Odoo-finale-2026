import React, { useState, useEffect } from "react";
import { api } from "../api";
import { Receipt, DollarSign, Clock, RotateCcw, CheckCircle2, AlertCircle } from "lucide-react";

export function FinanceBilling({ onNotify }) {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadInvoices();
  }, []);

  async function loadInvoices() {
    setLoading(true);
    try {
      const data = await api.getPortalInvoices();
      setInvoices(data || []);
    } catch (err) {
      onNotify("Error loading billing invoices: " + err.message, "error");
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
        <button className="btn btn-secondary" onClick={loadInvoices}>
          <RotateCcw size={14} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>
          <Clock size={32} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <div>Loading Invoices...</div>
        </div>
      ) : invoices.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "3.5rem 1.5rem" }}>
          <Receipt size={48} color="var(--status-healthy)" style={{ marginBottom: "1rem" }} />
          <h3 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "0.5rem" }}>
            No Active Invoices
          </h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: "460px", margin: "0 auto" }}>
            Invoices are generated upon customer quotation confirmation and order fulfillment release.
          </p>
        </div>
      ) : (
        <div className="card">
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice #</th>
                  <th>Order #</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td><strong>{inv.invoice_number || `INV-${inv.id}`}</strong></td>
                    <td>{inv.order_id ? `ORD-${inv.order_id}` : "N/A"}</td>
                    <td style={{ fontWeight: 700 }}>${(inv.amount || 0).toFixed(2)}</td>
                    <td>
                      <span className={`badge ${inv.status === "PAID" ? "badge-healthy" : "badge-medium"}`}>
                        {inv.status || "ISSUED"}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                      {inv.created_at ? new Date(inv.created_at).toLocaleDateString() : "Recent"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
