import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  MessageSquare,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  Send,
  AlertCircle,
} from "lucide-react";

export function NegotiationsReview({ onNotify }) {
  const [negotiations, setNegotiations] = useState([]);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [loading, setLoading] = useState(true);

  // Review Modal
  const [activeNeg, setActiveNeg] = useState(null);
  const [actionType, setActionType] = useState("APPROVE"); // APPROVE or REJECT
  const [comments, setComments] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    loadNegotiations();
  }, [statusFilter]);

  async function loadNegotiations() {
    setLoading(true);
    try {
      const data = await api.getNegotiations(statusFilter === "ALL" ? null : statusFilter);
      setNegotiations(data);
    } catch (err) {
      onNotify("Failed to load negotiations: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function handleOpenReview(neg, type) {
    setActiveNeg(neg);
    setActionType(type);
    setComments(
      type === "APPROVE"
        ? `Approved counter-offer of ${neg.proposed_value} for ${neg.requested_change}.`
        : `Proposal exceeds margin threshold.`
    );
  }

  async function handleConfirmReview(e) {
    e.preventDefault();
    if (!activeNeg) return;

    setActionLoading(true);
    try {
      if (actionType === "APPROVE") {
        await api.approveNegotiation(activeNeg.id, comments);
        onNotify(
          `Negotiation #${activeNeg.id} approved! Quote updated and flagged for re-approval.`,
          "success"
        );
      } else {
        await api.rejectNegotiation(activeNeg.id, comments);
        onNotify(`Negotiation #${activeNeg.id} rejected.`, "info");
      }
      setActiveNeg(null);
      loadNegotiations();
    } catch (err) {
      onNotify("Action failed: " + err.message, "error");
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <MessageSquare color="var(--primary)" size={24} /> Customer Negotiation Review Queue
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Review incoming customer counter-proposals. Approvals trigger automatic quote updates and re-approval routing.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className={`btn btn-sm ${statusFilter === "PENDING" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setStatusFilter("PENDING")}
          >
            Pending Review
          </button>
          <button
            className={`btn btn-sm ${statusFilter === "APPROVED" ? "btn-success" : "btn-secondary"}`}
            onClick={() => setStatusFilter("APPROVED")}
          >
            Approved
          </button>
          <button
            className={`btn btn-sm ${statusFilter === "REJECTED" ? "btn-danger" : "btn-secondary"}`}
            onClick={() => setStatusFilter("REJECTED")}
          >
            Rejected
          </button>
          <button
            className={`btn btn-sm ${statusFilter === "ALL" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setStatusFilter("ALL")}
          >
            All
          </button>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Quote ID</th>
                <th>Requested Change</th>
                <th>Original</th>
                <th>Customer Proposal</th>
                <th>Status</th>
                <th>Submitted Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                    Loading negotiations...
                  </td>
                </tr>
              ) : negotiations.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                    No negotiations found in this status.
                  </td>
                </tr>
              ) : (
                negotiations.map((neg) => {
                  let statusBadge = "badge-medium";
                  if (neg.status === "APPROVED") statusBadge = "badge-healthy";
                  if (neg.status === "REJECTED") statusBadge = "badge-high";

                  return (
                    <tr key={neg.id}>
                      <td><strong>#{neg.id}</strong></td>
                      <td><code>Quote #{neg.quote_id}</code></td>
                      <td><strong>{neg.requested_change}</strong></td>
                      <td><code>{neg.previous_value || "N/A"}%</code></td>
                      <td>
                        <strong style={{ color: "var(--primary)" }}>{neg.proposed_value}%</strong>
                      </td>
                      <td>
                        <span className={`badge ${statusBadge}`}>{neg.status}</span>
                      </td>
                      <td style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                        {new Date(neg.created_at).toLocaleString()}
                      </td>
                      <td>
                        {neg.status === "PENDING" ? (
                          <div style={{ display: "flex", gap: "0.5rem" }}>
                            <button
                              className="btn btn-success btn-sm"
                              onClick={() => handleOpenReview(neg, "APPROVE")}
                            >
                              <CheckCircle2 size={13} /> Approve
                            </button>
                            <button
                              className="btn btn-danger btn-sm"
                              onClick={() => handleOpenReview(neg, "REJECT")}
                            >
                              <XCircle size={13} /> Reject
                            </button>
                          </div>
                        ) : (
                          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                            Resolved
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Review Action Modal */}
      {activeNeg && (
        <div className="modal-overlay" onClick={() => setActiveNeg(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h2 className="card-title">
                {actionType === "APPROVE" ? (
                  <CheckCircle2 size={20} color="var(--status-healthy)" />
                ) : (
                  <XCircle size={20} color="var(--status-high)" />
                )}
                {actionType === "APPROVE" ? "Approve Counter-Offer" : "Reject Counter-Offer"}
              </h2>
            </div>

            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>
              {actionType === "APPROVE"
                ? `Approving will update Quote #${activeNeg.quote_id} to ${activeNeg.proposed_value}% discount and flag the quote for re-approval (requires_approval = True).`
                : `Rejecting will retain existing terms on Quote #${activeNeg.quote_id}.`}
            </p>

            <form onSubmit={handleConfirmReview}>
              <div className="form-group">
                <label className="form-label">Reviewer Notes</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  value={comments}
                  onChange={(e) => setComments(e.target.value)}
                  placeholder="Add approval / rejection rationale..."
                  required
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setActiveNeg(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`btn ${actionType === "APPROVE" ? "btn-success" : "btn-danger"}`}
                  disabled={actionLoading}
                >
                  {actionLoading
                    ? "Processing..."
                    : actionType === "APPROVE"
                    ? "Confirm & Re-evaluate Approval"
                    : "Confirm Rejection"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
