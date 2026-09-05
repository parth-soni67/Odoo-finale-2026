import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  Users,
  Package,
  AlertTriangle,
  CheckCircle2,
  Clock,
} from "lucide-react";

export function SalesReports({ onNotify }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSummary();
  }, []);

  async function loadSummary() {
    setLoading(true);
    try {
      const summary = await api.getSalesSummary();
      setData(summary);
    } catch (err) {
      onNotify("Failed to load reports: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>Generating analytics summary...</div>;
  }

  const approvalRate = data?.total_quotes
    ? Math.round((data.approved_quotes / data.total_quotes) * 100)
    : 0;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: 800, color: "#fff", display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <BarChart3 color="var(--primary)" size={24} /> Sales Operations & Governance Analytics
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Real-time pipeline valuation, approval throughput, and deal health risk telemetry.
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadSummary}>
          Refresh Analytics
        </button>
      </div>

      {/* Top Level Metric Cards */}
      <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
        <div className="kpi-card primary">
          <span className="kpi-label">Total Pipeline Value</span>
          <span className="kpi-value">${data?.total_quote_value?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          <span className="kpi-sub">Across {data?.total_quotes} active quotes</span>
        </div>

        <div className="kpi-card healthy">
          <span className="kpi-label">Approved Revenue Value</span>
          <span className="kpi-value" style={{ color: "var(--status-healthy)" }}>
            ${data?.approved_quote_value?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </span>
          <span className="kpi-sub">{data?.approved_quotes} approved quotes ({approvalRate}% approval rate)</span>
        </div>

        <div className="kpi-card medium">
          <span className="kpi-label">Pending Governance Sign-off</span>
          <span className="kpi-value" style={{ color: "var(--status-medium)" }}>
            {data?.pending_approvals}
          </span>
          <span className="kpi-sub">Awaiting Sales Manager / Finance review</span>
        </div>

        <div className="kpi-card high">
          <span className="kpi-label">High Risk Exposure</span>
          <span className="kpi-value" style={{ color: "var(--status-high)" }}>
            {data?.high_risk_deals}
          </span>
          <span className="kpi-sub">Deals exceeding policy thresholds</span>
        </div>
      </div>

      {/* Breakdown Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: "1rem" }}>
            <TrendingUp size={18} color="var(--primary)" /> Quote Conversion & Velocity
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem", fontSize: "0.9rem" }}>
                <span>Approved & Accepted Deals</span>
                <strong>{data?.approved_quotes} / {data?.total_quotes}</strong>
              </div>
              <div className="risk-bar-bg" style={{ height: "10px" }}>
                <div
                  className="risk-bar-fill healthy"
                  style={{ width: `${approvalRate}%` }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "0.5rem" }}>
              <div style={{ background: "var(--bg-surface-elevated)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Active Negotiations</div>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--primary)" }}>{data?.active_negotiations}</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Customer counter-offers</div>
              </div>

              <div style={{ background: "var(--bg-surface-elevated)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Rejected Quotes</div>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--status-high)" }}>{data?.rejected_quotes}</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Unresolved proposals</div>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="card-title" style={{ marginBottom: "1rem" }}>
            <Users size={18} color="var(--status-info)" /> Catalog & Customer Footprint
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div style={{ background: "var(--bg-surface-elevated)", padding: "1.25rem", borderRadius: "var(--radius-md)" }}>
                <Users size={24} color="var(--status-info)" style={{ marginBottom: "0.5rem" }} />
                <div style={{ fontSize: "1.6rem", fontWeight: 800 }}>{data?.customer_count}</div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Client Accounts Managed</div>
              </div>

              <div style={{ background: "var(--bg-surface-elevated)", padding: "1.25rem", borderRadius: "var(--radius-md)" }}>
                <Package size={24} color="var(--accent-purple)" style={{ marginBottom: "0.5rem" }} />
                <div style={{ fontSize: "1.6rem", fontWeight: 800 }}>{data?.product_count}</div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Active Catalog Products</div>
              </div>
            </div>

            <div style={{ background: "rgba(99, 102, 241, 0.08)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "var(--radius-md)", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              All metrics are computed deterministically from persistent PostgreSQL/SQLite storage across quote lines and customer tier guardrails.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
