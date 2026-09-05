import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  FileText,
  MessageSquare,
  CheckCircle2,
  Clock,
  Building2,
  Package,
  Receipt,
  ArrowRight,
  Send,
  AlertCircle,
} from "lucide-react";

export function CustomerPortal({ user, onNotify }) {
  const [profile, setProfile] = useState(null);
  const [quotes, setQuotes] = useState([]);
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [activeTab, setActiveTab] = useState("quotes"); // quotes, orders, billing, profile
  const [loading, setLoading] = useState(true);

  // Negotiation Modal
  const [isNegModalOpen, setIsNegModalOpen] = useState(false);
  const [requestedChange, setRequestedChange] = useState("discount_percent");
  const [proposedValue, setProposedValue] = useState("");
  const [negLoading, setNegLoading] = useState(false);

  useEffect(() => {
    loadPortalData();
  }, []);

  async function loadPortalData() {
    setLoading(true);
    try {
      const [profData, quotesData] = await Promise.all([
        api.getPortalProfile().catch(() => null),
        api.getPortalQuotes().catch(() => []),
      ]);
      setProfile(profData);
      setQuotes(quotesData);
      if (quotesData.length > 0) {
        loadQuoteDetail(quotesData[0].id);
      }
    } catch (err) {
      onNotify("Failed to load portal data: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function loadQuoteDetail(quoteId) {
    try {
      const detail = await api.getPortalQuoteDetail(quoteId);
      setSelectedQuote(detail);
    } catch (err) {
      onNotify("Error fetching quote: " + err.message, "error");
    }
  }

  async function handleConfirmQuote(quoteId) {
    try {
      const res = await api.confirmQuote(quoteId);
      onNotify(res.message || "Quote accepted successfully!", "success");
      loadPortalData();
      if (selectedQuote?.id === quoteId) {
        loadQuoteDetail(quoteId);
      }
    } catch (err) {
      onNotify("Confirmation failed: " + err.message, "error");
    }
  }

  async function handleSubmitNegotiation(e) {
    e.preventDefault();
    if (!proposedValue) {
      onNotify("Please enter a proposed value", "error");
      return;
    }

    setNegLoading(true);
    try {
      await api.submitNegotiation(selectedQuote.id, {
        requested_change: requestedChange,
        proposed_value: proposedValue,
      });
      onNotify("Negotiation request submitted to sales team!", "success");
      setIsNegModalOpen(false);
      setProposedValue("");
      loadQuoteDetail(selectedQuote.id);
      loadPortalData();
    } catch (err) {
      onNotify("Failed to submit request: " + err.message, "error");
    } finally {
      setNegLoading(false);
    }
  }

  if (loading) {
    return <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>Loading Customer Portal...</div>;
  }

  return (
    <div>
      {/* Customer Header Banner */}
      <div className="card" style={{ marginBottom: "1.5rem", background: "linear-gradient(135deg, #111827 0%, #1e1b4b 100%)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.25rem" }}>
              <Building2 size={24} color="var(--primary)" />
              <h1 style={{ fontSize: "1.5rem", fontWeight: 800 }}>{profile?.company_name || "Customer Workspace"}</h1>
              <span className="badge badge-info">{profile?.tier || "STANDARD"} TIER</span>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
              Authorized Contact: <strong>{profile?.contact_name}</strong> ({profile?.email})
            </p>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>Discount Ceiling</div>
            <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--status-healthy)" }}>
              {profile?.discount_ceiling || 10}%
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.5rem" }}>
        <button
          className={`nav-item ${activeTab === "quotes" ? "active" : ""}`}
          onClick={() => setActiveTab("quotes")}
        >
          <FileText size={16} /> My Quotes ({quotes.length})
        </button>
        <button
          className={`nav-item ${activeTab === "orders" ? "active" : ""}`}
          onClick={() => setActiveTab("orders")}
        >
          <Package size={16} /> Orders & Fulfillment
        </button>
        <button
          className={`nav-item ${activeTab === "billing" ? "active" : ""}`}
          onClick={() => setActiveTab("billing")}
        >
          <Receipt size={16} /> Billing & Invoices
        </button>
        <button
          className={`nav-item ${activeTab === "profile" ? "active" : ""}`}
          onClick={() => setActiveTab("profile")}
        >
          <Building2 size={16} /> Company Account
        </button>
      </div>

      {/* Tab: Quotes */}
      {activeTab === "quotes" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: "1.5rem", alignItems: "start" }}>
          {/* Quotes List */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <FileText size={18} /> Active Quotations
              </div>
            </div>
            {quotes.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No quotes available.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {quotes.map((q) => {
                  const isSelected = selectedQuote?.id === q.id;
                  let badgeClass = "badge-neutral";
                  if (q.status === "APPROVED" || q.status === "ACCEPTED") badgeClass = "badge-healthy";
                  else if (q.status === "PENDING_APPROVAL") badgeClass = "badge-medium";
                  else if (q.status === "REJECTED") badgeClass = "badge-high";

                  return (
                    <div
                      key={q.id}
                      onClick={() => loadQuoteDetail(q.id)}
                      style={{
                        padding: "1rem",
                        borderRadius: "var(--radius-md)",
                        background: isSelected ? "var(--bg-surface-elevated)" : "var(--bg-surface)",
                        border: isSelected ? "1px solid var(--primary)" : "1px solid var(--border-subtle)",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                        <span style={{ fontWeight: 700, color: "#fff" }}>{q.quote_number}</span>
                        <span className={`badge ${badgeClass}`}>{q.status}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                        <span>{q.item_count} items</span>
                        <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>${q.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Selected Quote Inspector */}
          {selectedQuote ? (
            <div className="card">
              <div className="card-header">
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>Quotation Details</div>
                  <h2 style={{ fontSize: "1.3rem", fontWeight: 800, color: "#fff" }}>{selectedQuote.quote_number}</h2>
                </div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      setProposedValue("");
                      setIsNegModalOpen(true);
                    }}
                  >
                    <MessageSquare size={14} /> Request Change
                  </button>
                  {selectedQuote.status === "APPROVED" && (
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => handleConfirmQuote(selectedQuote.id)}
                    >
                      <CheckCircle2 size={14} /> Confirm Quote
                    </button>
                  )}
                </div>
              </div>

              {/* Line Items Table */}
              <div className="table-container" style={{ marginBottom: "1.25rem" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>SKU</th>
                      <th>Qty</th>
                      <th>Unit Price</th>
                      <th>Discount</th>
                      <th>Line Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedQuote.lines.map((line) => (
                      <tr key={line.id}>
                        <td>
                          <strong>{line.product_name}</strong>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{line.line_type}</div>
                        </td>
                        <td><code>{line.product_sku}</code></td>
                        <td>{line.quantity}</td>
                        <td>${line.unit_price.toFixed(2)}</td>
                        <td>
                          <span style={{ color: line.discount_percent > 0 ? "var(--status-healthy)" : "inherit" }}>
                            {line.discount_percent}% (${line.discount_amount.toFixed(2)})
                          </span>
                        </td>
                        <td><strong>${line.line_total.toFixed(2)}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Financial Summary */}
              <div style={{ background: "var(--bg-surface-elevated)", padding: "1rem", borderRadius: "var(--radius-md)", marginBottom: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                  <span>Subtotal:</span>
                  <span>${selectedQuote.subtotal.toFixed(2)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem", fontSize: "0.9rem", color: "var(--status-healthy)" }}>
                  <span>Total Discount:</span>
                  <span>-${selectedQuote.total_discount.toFixed(2)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "1.15rem", fontWeight: 800, color: "#fff", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.6rem" }}>
                  <span>Total Payable:</span>
                  <span>${selectedQuote.total_amount.toFixed(2)}</span>
                </div>
              </div>

              {/* Negotiation Thread */}
              <div>
                <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <MessageSquare size={16} /> Negotiation & Revision History
                </h3>
                {selectedQuote.negotiations.length === 0 ? (
                  <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>No change requests submitted yet.</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {selectedQuote.negotiations.map((neg) => {
                      let statusBadge = "badge-medium";
                      if (neg.status === "APPROVED" || neg.status === "ACCEPTED") statusBadge = "badge-healthy";
                      if (neg.status === "REJECTED") statusBadge = "badge-high";

                      return (
                        <div
                          key={neg.id}
                          style={{
                            padding: "0.85rem",
                            background: "var(--bg-surface-elevated)",
                            borderRadius: "var(--radius-sm)",
                            borderLeft: "3px solid var(--primary)",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.3rem" }}>
                            <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>
                              Requested: <strong>{neg.requested_change}</strong> from <code>{neg.previous_value}%</code> to <code>{neg.proposed_value}%</code>
                            </span>
                            <span className={`badge ${statusBadge}`}>{neg.status}</span>
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            Submitted on {new Date(neg.created_at).toLocaleString()}
                            {neg.resolved_at && ` • Resolved on ${new Date(neg.resolved_at).toLocaleString()}`}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
              Select a quote from the list to view items and pricing.
            </div>
          )}
        </div>
      )}

      {/* Tab: Orders Placeholder */}
      {activeTab === "orders" && (
        <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
          <Package size={42} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "0.5rem" }}>Order Fulfillment & Tracking</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: "500px", margin: "0 auto 1.5rem auto", fontSize: "0.9rem" }}>
            Warehouse allocations, tracking IDs, and fulfillment split shipments will populate here once orders are confirmed and released by Operations.
          </p>
          <span className="badge badge-info">Person 3 Integration Ready</span>
        </div>
      )}

      {/* Tab: Billing Placeholder */}
      {activeTab === "billing" && (
        <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
          <Receipt size={42} color="var(--status-healthy)" style={{ marginBottom: "1rem" }} />
          <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "0.5rem" }}>Billing & Invoices</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: "500px", margin: "0 auto 1.5rem auto", fontSize: "0.9rem" }}>
            Hybrid billing invoices (one-time license hardware + recurring subscriptions) and simulated payment receipts will be accessible here.
          </p>
          <span className="badge badge-info">Person 3 Integration Ready</span>
        </div>
      )}

      {/* Tab: Profile */}
      {activeTab === "profile" && profile && (
        <div className="card" style={{ maxWidth: "600px" }}>
          <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "1rem" }}>Company Account Details</h3>
          <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: "0.75rem", fontSize: "0.9rem" }}>
            <span style={{ color: "var(--text-secondary)" }}>Company Name:</span>
            <strong>{profile.company_name}</strong>
            <span style={{ color: "var(--text-secondary)" }}>Customer Tier:</span>
            <span><span className="badge badge-info">{profile.tier}</span></span>
            <span style={{ color: "var(--text-secondary)" }}>Discount Ceiling:</span>
            <strong style={{ color: "var(--status-healthy)" }}>{profile.discount_ceiling}%</strong>
            <span style={{ color: "var(--text-secondary)" }}>Contact Name:</span>
            <span>{profile.contact_name}</span>
            <span style={{ color: "var(--text-secondary)" }}>Official Email:</span>
            <span>{profile.email}</span>
            <span style={{ color: "var(--text-secondary)" }}>Phone:</span>
            <span>{profile.phone || "N/A"}</span>
          </div>
        </div>
      )}

      {/* Request Change Negotiation Modal */}
      {isNegModalOpen && (
        <div className="modal-overlay" onClick={() => setIsNegModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h2 className="card-title">
                <MessageSquare size={20} color="var(--primary)" /> Request Quote Adjustment
              </h2>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>
              Submit a formal counter-proposal for Quote <strong>{selectedQuote?.quote_number}</strong>. This will be routed to your account manager for review.
            </p>

            <form onSubmit={handleSubmitNegotiation}>
              <div className="form-group">
                <label className="form-label">Requested Parameter</label>
                <select
                  className="form-select"
                  value={requestedChange}
                  onChange={(e) => setRequestedChange(e.target.value)}
                >
                  <option value="discount_percent">Discount Percentage (%)</option>
                  <option value="total_amount">Total Target Price ($)</option>
                  <option value="payment_terms">Payment Terms / Scope</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Proposed Value {requestedChange === "discount_percent" ? "(e.g., 12 for 12%)" : "(e.g., 2800)"}
                </label>
                <input
                  type="text"
                  className="form-input"
                  placeholder={requestedChange === "discount_percent" ? "12.0" : "2800.00"}
                  value={proposedValue}
                  onChange={(e) => setProposedValue(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsNegModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={negLoading}>
                  <Send size={14} /> {negLoading ? "Submitting..." : "Submit Proposal"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
