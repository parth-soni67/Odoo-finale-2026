import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  Activity,
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  Clock,
  MessageSquare,
  Sparkles,
  ArrowRight,
  Filter,
  Search,
  CheckCircle,
} from "lucide-react";

export function DealHealthDashboard({ onInspectNegotiation, onNotify }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedFilter, setSelectedFilter] = useState("ALL"); // ALL, HEALTHY, MEDIUM_RISK, HIGH_RISK
  const [searchTerm, setSearchTerm] = useState("");
  const [inspectDeal, setInspectDeal] = useState(null);

  useEffect(() => {
    loadHealthData();
  }, []);

  async function loadHealthData() {
    setLoading(true);
    try {
      const summary = await api.getDealHealth();
      setData(summary);
    } catch (err) {
      onNotify("Failed to load deal health: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>Loading Deal Health Matrix...</div>;
  }

  const filteredDeals = (data?.deals || []).filter((deal) => {
    const matchesFilter =
      selectedFilter === "ALL" || deal.risk_level === selectedFilter;
    const matchesSearch =
      deal.quote_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      deal.customer_name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  return (
    <div>
      {/* Top Banner */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: 800, color: "#fff", display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <Activity color="var(--primary)" size={24} /> Deal Health & Governance Engine
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Self-governing sales pipeline monitoring risk signals, discount compliance, and approval bottlenecks.
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadHealthData}>
          Refresh Diagnostics
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        <div className="kpi-card primary">
          <span className="kpi-label">Total Active Deals</span>
          <span className="kpi-value">{data?.total_active_deals || 0}</span>
          <span className="kpi-sub">In sales pipeline</span>
        </div>

        <div className="kpi-card healthy">
          <span className="kpi-label">Healthy Deals</span>
          <span className="kpi-value" style={{ color: "var(--status-healthy)" }}>
            {data?.healthy_count || 0}
          </span>
          <span className="kpi-sub">Low risk (0–30 pts)</span>
        </div>

        <div className="kpi-card medium">
          <span className="kpi-label">Medium Risk</span>
          <span className="kpi-value" style={{ color: "var(--status-medium)" }}>
            {data?.medium_risk_count || 0}
          </span>
          <span className="kpi-sub">Advisory (31–60 pts)</span>
        </div>

        <div className="kpi-card high">
          <span className="kpi-label">High Risk Deals</span>
          <span className="kpi-value" style={{ color: "var(--status-high)" }}>
            {data?.high_risk_count || 0}
          </span>
          <span className="kpi-sub">Critical review (&gt;60 pts)</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Pending Approval</span>
          <span className="kpi-value">{data?.pending_approval_count || 0}</span>
          <span className="kpi-sub">Awaiting manager/finance</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Active Negotiations</span>
          <span className="kpi-value">{data?.active_negotiations_count || 0}</span>
          <span className="kpi-sub">Customer counter-offers</span>
        </div>
      </div>

      {/* Filters & Search */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "1rem" }}>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className={`btn btn-sm ${selectedFilter === "ALL" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setSelectedFilter("ALL")}
          >
            All Deals
          </button>
          <button
            className={`btn btn-sm ${selectedFilter === "HIGH_RISK" ? "btn-danger" : "btn-secondary"}`}
            onClick={() => setSelectedFilter("HIGH_RISK")}
          >
            <AlertOctagon size={14} /> High Risk ({data?.high_risk_count || 0})
          </button>
          <button
            className={`btn btn-sm ${selectedFilter === "MEDIUM_RISK" ? "btn-secondary" : "btn-secondary"}`}
            onClick={() => setSelectedFilter("MEDIUM_RISK")}
            style={selectedFilter === "MEDIUM_RISK" ? { background: "var(--status-medium)", color: "#fff" } : {}}
          >
            <AlertTriangle size={14} /> Medium Risk ({data?.medium_risk_count || 0})
          </button>
          <button
            className={`btn btn-sm ${selectedFilter === "HEALTHY" ? "btn-success" : "btn-secondary"}`}
            onClick={() => setSelectedFilter("HEALTHY")}
          >
            <ShieldCheck size={14} /> Healthy ({data?.healthy_count || 0})
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div style={{ position: "relative" }}>
            <Search size={16} color="var(--text-muted)" style={{ position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)" }} />
            <input
              type="text"
              className="form-input"
              style={{ paddingLeft: "2.2rem", width: "240px" }}
              placeholder="Search quote or customer..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Deals Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Deal / Quote</th>
                <th>Customer</th>
                <th>Amount</th>
                <th>Health Score & Risk</th>
                <th>Approval</th>
                <th>Negotiation</th>
                <th>Next Action</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDeals.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                    No deals matching current filter.
                  </td>
                </tr>
              ) : (
                filteredDeals.map((deal) => {
                  let badgeClass = "badge-healthy";
                  let fillClass = "healthy";
                  if (deal.risk_level === "HIGH_RISK") {
                    badgeClass = "badge-high";
                    fillClass = "high";
                  } else if (deal.risk_level === "MEDIUM_RISK") {
                    badgeClass = "badge-medium";
                    fillClass = "medium";
                  }

                  return (
                    <tr key={deal.quote_id}>
                      <td>
                        <strong style={{ color: "#fff" }}>{deal.quote_number}</strong>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          {new Date(deal.created_at).toLocaleDateString()}
                        </div>
                      </td>
                      <td>
                        <strong>{deal.customer_name}</strong>
                        <div><span className="badge badge-neutral" style={{ fontSize: "0.7rem" }}>{deal.customer_tier}</span></div>
                      </td>
                      <td>
                        <strong>${deal.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                      </td>
                      <td>
                        <div className="risk-meter-container">
                          <div className="risk-bar-bg">
                            <div
                              className={`risk-bar-fill ${fillClass}`}
                              style={{ width: `${Math.max(8, deal.risk_score)}%` }}
                            />
                          </div>
                          <span className={`badge ${badgeClass}`}>{deal.risk_score.toFixed(0)} / 100</span>
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${deal.approval_status === "APPROVED" ? "badge-healthy" : deal.approval_status === "PENDING_APPROVAL" ? "badge-medium" : "badge-neutral"}`}>
                          {deal.approval_status}
                        </span>
                      </td>
                      <td>
                        {deal.negotiation_status ? (
                          <span className="badge badge-medium" style={{ display: "inline-flex", gap: "0.3rem" }}>
                            <MessageSquare size={12} /> Counter-Offer
                          </span>
                        ) : (
                          <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>None</span>
                        )}
                      </td>
                      <td style={{ maxWidth: "240px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                        {deal.next_action}
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => setInspectDeal(deal)}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Deal Health Inspection Drawer / Modal */}
      {inspectDeal && (
        <div className="modal-overlay" onClick={() => setInspectDeal(null)}>
          <div className="modal-card" style={{ maxWidth: "680px" }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <div>
                <span className="badge badge-neutral" style={{ marginBottom: "0.4rem" }}>
                  Deal Diagnostic
                </span>
                <h2 className="card-title" style={{ fontSize: "1.3rem" }}>
                  {inspectDeal.quote_number} — {inspectDeal.customer_name}
                </h2>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setInspectDeal(null)}
              >
                Close
              </button>
            </div>

            {/* Score Banner */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "var(--bg-surface-elevated)", padding: "1rem", borderRadius: "var(--radius-md)", marginBottom: "1.25rem" }}>
              <div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Calculated Deal Health Score</div>
                <div style={{ fontSize: "1.75rem", fontWeight: 800, color: inspectDeal.risk_level === "HIGH_RISK" ? "var(--status-high)" : inspectDeal.risk_level === "MEDIUM_RISK" ? "var(--status-medium)" : "var(--status-healthy)" }}>
                  {inspectDeal.risk_score.toFixed(1)} / 100
                </div>
              </div>
              <div>
                <span className={`badge ${inspectDeal.risk_level === "HIGH_RISK" ? "badge-high" : inspectDeal.risk_level === "MEDIUM_RISK" ? "badge-medium" : "badge-healthy"}`} style={{ fontSize: "0.9rem", padding: "0.4rem 0.8rem" }}>
                  {inspectDeal.risk_level.replace("_", " ")}
                </span>
              </div>
            </div>

            {/* Risk Signals Detected */}
            <div style={{ marginBottom: "1.25rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--text-primary)" }}>
                <AlertTriangle size={16} color="var(--status-high)" /> Detected Risk Signals ({inspectDeal.signals.length})
              </h3>
              {inspectDeal.signals.length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>No adverse risk signals found on this quotation.</p>
              ) : (
                inspectDeal.signals.map((signal, idx) => (
                  <div key={idx} className="signal-item">
                    <span>{signal}</span>
                  </div>
                ))
              )}
            </div>

            {/* Recommendations */}
            <div style={{ marginBottom: "1.5rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--text-primary)" }}>
                <Sparkles size={16} color="var(--primary)" /> Actionable Recommendations
              </h3>
              {inspectDeal.recommendations.map((rec, idx) => (
                <div key={idx} className="recommendation-item">
                  <span>{rec}</span>
                </div>
              ))}
            </div>

            {/* Next Action Box */}
            <div style={{ background: "rgba(14, 165, 233, 0.08)", border: "1px solid var(--status-info-border)", borderRadius: "var(--radius-md)", padding: "1rem", marginBottom: "1.25rem" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--status-info)", fontWeight: 700, textTransform: "uppercase", marginBottom: "0.25rem" }}>
                Next Recommended Step
              </div>
              <div style={{ fontWeight: 600, color: "#fff" }}>
                {inspectDeal.next_action}
              </div>
            </div>

            {/* If has negotiation, button to review */}
            {inspectDeal.negotiation_status && (
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setInspectDeal(null);
                    if (onInspectNegotiation) onInspectNegotiation();
                  }}
                >
                  <MessageSquare size={16} /> Open Negotiation Review
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
