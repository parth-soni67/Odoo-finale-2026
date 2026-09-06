import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  ShieldAlert,
  UserCheck,
  Building2,
  DollarSign,
  AlertTriangle,
} from "lucide-react";

export function ApprovalQueue({ user, onNotify }) {
  const [pendingQuotes, setPendingQuotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [decisionModal, setDecisionModal] = useState({ open: false, quote: null, action: null, comments: "" });
  const [decisionLoading, setDecisionLoading] = useState(false);

  useEffect(() => {
    loadApprovalQueue();
  }, [user]);

  async function loadApprovalQueue() {
    setLoading(true);
    try {
      const allQuotes = await api.getQuotes();
      // Filter quotes that require approval or have status PENDING_APPROVAL
      const queue = (allQuotes || []).filter(
        (q) => q.status === "PENDING_APPROVAL" || q.requires_approval
      );
      setPendingQuotes(queue);
    } catch (err) {
      onNotify("Error loading approval queue: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleDecisionSubmit(e) {
    e.preventDefault();
    const { quote, action, comments } = decisionModal;
    if (!quote || !action) return;

    setDecisionLoading(true);
    try {
      if (action === "APPROVE") {
        await api.approveQuote(quote.id, comments);
        onNotify(`Quote ${quote.quote_number} approved successfully!`, "success");
      } else {
        await api.rejectQuote(quote.id, comments);
        onNotify(`Quote ${quote.quote_number} rejected.`, "info");
      }
      setDecisionModal({ open: false, quote: null, action: null, comments: "" });
      loadApprovalQueue();
    } catch (err) {
      onNotify(`Decision failed: ` + err.message, "error");
    } finally {
      setDecisionLoading(false);
    }
  }

  const roleTitle =
    user?.role === "FINANCE"
      ? "Finance Escalation Queue"
      : user?.role === "SALES_MANAGER"
      ? "Sales Manager Approval Queue"
      : "Executive Approval Queue";

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
            {roleTitle}
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Review deal terms, discount ceiling exceptions, and governance risk before customer authorization.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={loadApprovalQueue}>
          <RotateCcw size={14} /> Refresh Queue
        </button>
      </div>

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>
          <Clock size={32} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <div>Loading Approval Queue...</div>
        </div>
      ) : pendingQuotes.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "3.5rem 1.5rem" }}>
          <CheckCircle2 size={48} color="var(--status-healthy)" style={{ marginBottom: "1rem" }} />
          <h3 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "0.5rem" }}>
            Approval Queue Clean
          </h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: "460px", margin: "0 auto" }}>
            No quotations are currently pending approval. All active deals comply with discount guardrails.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {pendingQuotes.map((quote) => {
            const custName = quote.customer?.company_name || `Customer #${quote.customer_id}`;
            return (
              <div
                key={quote.id}
                className="card"
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "1.25rem",
                  borderLeft: "4px solid var(--status-medium)",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.35rem" }}>
                    <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                      {quote.quote_number}
                    </h3>
                    <span className="badge badge-medium">{quote.status}</span>
                    <span
                      className={`badge ${
                        quote.risk_score > 60
                          ? "badge-high"
                          : quote.risk_score > 30
                          ? "badge-medium"
                          : "badge-healthy"
                      }`}
                    >
                      Risk: {quote.risk_score}
                    </span>
                  </div>

                  <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "0.35rem" }}>
                    Customer: <strong>{custName}</strong> • Items: <strong>{(quote.lines || []).length}</strong>
                  </div>

                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", display: "flex", gap: "1.25rem" }}>
                    <span>Subtotal: ${(quote.subtotal || 0).toFixed(2)}</span>
                    <span>Discount: -${(quote.total_discount || 0).toFixed(2)}</span>
                    <span>
                      Target Total: <strong>${(quote.total_amount || 0).toFixed(2)}</strong>
                    </span>
                  </div>
                </div>

                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    className="btn btn-success"
                    onClick={() => setDecisionModal({ open: true, quote, action: "APPROVE", comments: "" })}
                  >
                    <CheckCircle2 size={15} /> Approve Deal
                  </button>
                  <button
                    className="btn btn-secondary"
                    style={{ color: "var(--status-high)" }}
                    onClick={() => setDecisionModal({ open: true, quote, action: "REJECT", comments: "" })}
                  >
                    <XCircle size={15} /> Reject
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Decision Modal */}
      {decisionModal.open && (
        <div className="modal-overlay" onClick={() => setDecisionModal({ open: false, quote: null, action: null, comments: "" })}>
          <div className="modal-card" style={{ maxWidth: "480px" }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h2 className="card-title">
                {decisionModal.action === "APPROVE" ? (
                  <>
                    <CheckCircle2 size={20} color="var(--status-healthy)" /> Confirm Approval
                  </>
                ) : (
                  <>
                    <XCircle size={20} color="var(--status-high)" /> Reject Quotation
                  </>
                )}
              </h2>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "1rem" }}>
              Action for Quote <strong>{decisionModal.quote?.quote_number}</strong>.
            </p>
            <form onSubmit={handleDecisionSubmit}>
              <div className="form-group">
                <label className="form-label">Review Comments (Optional)</label>
                <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "-0.25rem", marginBottom: "0.4rem" }}>
                  These comments will be visible to the customer in the quotation details.
                </p>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="e.g. Approved exception based on volume commitments..."
                  value={decisionModal.comments}
                  onChange={(e) => setDecisionModal((prev) => ({ ...prev, comments: e.target.value }))}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setDecisionModal({ open: false, quote: null, action: null, comments: "" })}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`btn ${decisionModal.action === "APPROVE" ? "btn-success" : "btn-secondary"}`}
                  style={decisionModal.action === "REJECT" ? { color: "var(--status-high)" } : {}}
                  disabled={decisionLoading}
                >
                  {decisionLoading ? "Submitting..." : decisionModal.action === "APPROVE" ? "Confirm Approval" : "Confirm Rejection"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
