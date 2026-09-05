import React, { useState, useEffect } from "react";
import { api } from "../api";
import { Receipt, Clock, RotateCcw, Sparkles, Play, Download, FileSpreadsheet, CreditCard } from "lucide-react";

export function FinanceBilling({ onNotify }) {
  const [invoices, setInvoices] = useState([]);
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningBilling, setRunningBilling] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState(null);

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

  async function handleRunBilling() {
    setRunningBilling(true);
    try {
      const res = await api.runBilling();
      onNotify(res.message || `Billing run executed: ${res.invoices_generated} invoice(s) generated.`, "success");
      await loadBilling();
    } catch (err) {
      onNotify("Billing run failed: " + err.message, "error");
    } finally {
      setRunningBilling(false);
    }
  }

  async function handleDownloadPdf(inv) {
    try {
      setActionLoadingId(`pdf-${inv.id}`);
      await api.downloadInvoicePdf(inv.id, inv.invoice_number);
      onNotify(`Downloaded PDF for ${inv.invoice_number}`, "success");
    } catch (err) {
      onNotify("PDF download failed: " + err.message, "error");
    } finally {
      setActionLoadingId(null);
    }
  }

  async function handleDownloadXlsx(inv) {
    try {
      setActionLoadingId(`xlsx-${inv.id}`);
      await api.downloadInvoiceXlsx(inv.id, inv.invoice_number);
      onNotify(`Downloaded XLS for ${inv.invoice_number}`, "success");
    } catch (err) {
      onNotify("XLS download failed: " + err.message, "error");
    } finally {
      setActionLoadingId(null);
    }
  }

  async function handleProcessPayment(inv) {
    try {
      setActionLoadingId(`pay-${inv.id}`);
      const amt = inv.total_amount !== undefined ? inv.total_amount : inv.amount;
      await api.payInvoice(inv.id, { amount: amt, payment_method: "SIMULATED_CARD" });
      onNotify(`Payment recorded for ${inv.invoice_number}. Status updated to PAID.`, "success");
      await loadBilling();
    } catch (err) {
      onNotify("Payment processing failed: " + err.message, "error");
    } finally {
      setActionLoadingId(null);
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
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className="btn btn-primary"
            onClick={handleRunBilling}
            disabled={runningBilling}
            style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}
          >
            <Play size={14} /> {runningBilling ? "Running Billing Engine..." : "Run Recurring Billing"}
          </button>
          <button className="btn btn-secondary" onClick={loadBilling}>
            <RotateCcw size={14} /> Refresh
          </button>
        </div>
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
                      <th style={{ textAlign: "center" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((inv) => {
                      const amt = inv.total_amount !== undefined ? inv.total_amount : inv.amount || 0;
                      const isPaid = inv.status === "PAID";
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
                          <td style={{ textAlign: "center" }}>
                            <div style={{ display: "flex", gap: "0.35rem", justifyContent: "center" }}>
                              <button
                                className="btn btn-secondary btn-sm"
                                title="Download PDF"
                                onClick={() => handleDownloadPdf(inv)}
                                disabled={actionLoadingId === `pdf-${inv.id}`}
                                style={{ padding: "0.2rem 0.45rem", fontSize: "0.75rem" }}
                              >
                                <Download size={13} /> PDF
                              </button>
                              <button
                                className="btn btn-secondary btn-sm"
                                title="Download Excel"
                                onClick={() => handleDownloadXlsx(inv)}
                                disabled={actionLoadingId === `xlsx-${inv.id}`}
                                style={{ padding: "0.2rem 0.45rem", fontSize: "0.75rem" }}
                              >
                                <FileSpreadsheet size={13} /> XLS
                              </button>
                              {!isPaid && (
                                <button
                                  className="btn btn-primary btn-sm"
                                  title="Mark Paid"
                                  onClick={() => handleProcessPayment(inv)}
                                  disabled={actionLoadingId === `pay-${inv.id}`}
                                  style={{ padding: "0.2rem 0.5rem", fontSize: "0.75rem" }}
                                >
                                  <CreditCard size={13} /> Pay
                                </button>
                              )}
                            </div>
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
