import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  FileText,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  TrendingUp,
  Sparkles,
  ShieldAlert,
  Clock,
  RotateCcw,
  DollarSign,
  Send,
  UserCheck,
} from "lucide-react";

export function QuotationWorkflow({ user, onNotify, onInspectDeal }) {
  const [quotes, setQuotes] = useState([]);
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Create Quote Modal
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [subscriptionPlans, setSubscriptionPlans] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [quoteLines, setQuoteLines] = useState([]);
  const [createLoading, setCreateLoading] = useState(false);

  // Recommendations State for selected quote
  const [recommendations, setRecommendations] = useState([]);
  const [recsLoading, setRecsLoading] = useState(false);

  // Approvals State for selected quote
  const [approvals, setApprovals] = useState([]);
  const [approvalsLoading, setApprovalsLoading] = useState(false);

  // Risk state for selected quote
  const [riskData, setRiskData] = useState(null);
  const [riskLoading, setRiskLoading] = useState(false);

  // Decision modal (for Manager / Finance / Admin)
  const [decisionModal, setDecisionModal] = useState({ open: false, action: null, comments: "" });
  const [decisionLoading, setDecisionLoading] = useState(false);

  const isSalesRep = user?.role === "SALES_REP";
  const canApprove = ["SALES_MANAGER", "FINANCE", "ADMIN"].includes(user?.role);

  useEffect(() => {
    loadQuotes();
    loadMetadata();
  }, [user]);

  async function loadMetadata() {
    try {
      const [custs, prods, plans] = await Promise.all([
        api.getCustomers().catch(() => []),
        api.getProducts().catch(() => []),
        api.getSubscriptionPlans().catch(() => []),
      ]);
      setCustomers(custs || []);
      setProducts(prods || []);
      setSubscriptionPlans(plans || []);
    } catch {
      // ignore
    }
  }

  async function loadQuotes() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getQuotes();
      const list = data || [];
      setQuotes(list);
      if (list.length > 0) {
        // Auto select first quote or keep current selection
        setSelectedQuote((prev) => {
          const matching = list.find((q) => q.id === prev?.id);
          const toSelect = matching || list[0];
          loadQuoteDetails(toSelect.id);
          return toSelect;
        });
      } else {
        setSelectedQuote(null);
      }
    } catch (err) {
      setError("Unable to load quotations: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadQuoteDetails(quoteId) {
    try {
      const quote = await api.getQuote(quoteId);
      setSelectedQuote(quote);

      // Load risk, recommendations, approvals in parallel
      setRecsLoading(true);
      setApprovalsLoading(true);
      setRiskLoading(true);

      api
        .getQuoteRecommendations(quoteId)
        .then((res) => setRecommendations(res.recommendations || []))
        .catch(() => setRecommendations([]))
        .finally(() => setRecsLoading(false));

      api
        .getQuoteApprovals(quoteId)
        .then((res) => setApprovals(res || []))
        .catch(() => setApprovals([]))
        .finally(() => setApprovalsLoading(false));

      api
        .evaluateQuoteRisk(quoteId)
        .then((res) => setRiskData(res))
        .catch(() => setRiskData(null))
        .finally(() => setRiskLoading(false));
    } catch (err) {
      onNotify("Error loading quote details: " + err.message, "error");
    }
  }

  // Create Quote Handlers
  function openCreateModal() {
    setSelectedCustomerId(customers.length > 0 ? String(customers[0].id) : "");
    const defaultProd = products[0];
    setQuoteLines([
      {
        product_id: defaultProd ? defaultProd.id : "",
        quantity: 1,
        unit_price: defaultProd ? defaultProd.unit_price : 0,
        discount_percent: 0,
        purchase_type: "ONE_TIME",
        subscription_plan_id: subscriptionPlans[0]?.id ? String(subscriptionPlans[0].id) : "",
        subscription_name: subscriptionPlans[0]?.name || (defaultProd ? `${defaultProd.name} Subscription` : "Subscription Service"),
        duration_mode: "TILL_VALIDITY",
        validity_preset: "3_MONTHS",
        validity_value: 3,
        validity_unit: "MONTHS",
        billing_frequency: "MONTHLY",
      },
    ]);
    setIsCreateModalOpen(true);
  }

  function addEmptyLine() {
    const defaultProd = products[0];
    setQuoteLines((prev) => [
      ...prev,
      {
        product_id: defaultProd ? defaultProd.id : "",
        quantity: 1,
        unit_price: defaultProd ? defaultProd.unit_price : 0,
        discount_percent: 0,
        purchase_type: "ONE_TIME",
        subscription_plan_id: subscriptionPlans[0]?.id ? String(subscriptionPlans[0].id) : "",
        subscription_name: subscriptionPlans[0]?.name || (defaultProd ? `${defaultProd.name} Subscription` : "Subscription Service"),
        duration_mode: "TILL_VALIDITY",
        validity_preset: "3_MONTHS",
        validity_value: 3,
        validity_unit: "MONTHS",
        billing_frequency: "MONTHLY",
      },
    ]);
  }

  function updateLine(index, field, value) {
    setQuoteLines((prev) => {
      const updated = [...prev];
      const line = { ...updated[index], [field]: value };

      if (field === "product_id") {
        const prod = products.find((p) => p.id === Number(value));
        if (prod) {
          line.unit_price = prod.unit_price;
          if (line.purchase_type === "SUBSCRIPTION" && (!line.subscription_name || line.subscription_name.endsWith("Subscription"))) {
            line.subscription_name = `${prod.name} Subscription`;
          }
        }
      }

      updated[index] = line;
      return updated;
    });
  }

  function removeLine(index) {
    setQuoteLines((prev) => prev.filter((_, idx) => idx !== index));
  }

  async function handleCreateQuote(e) {
    e.preventDefault();
    if (!selectedCustomerId) {
      onNotify("Please select a customer", "error");
      return;
    }
    if (quoteLines.length === 0) {
      onNotify("Please add at least one line item", "error");
      return;
    }

    setCreateLoading(true);
    try {
      const payload = {
        customer_id: Number(selectedCustomerId),
        lines: quoteLines.map((l) => {
          const isSub = l.purchase_type === "SUBSCRIPTION";
          const isLifetime = isSub && l.duration_mode === "LIFETIME";
          let planName = l.subscription_name;
          if (isSub && !planName) {
            const planObj = subscriptionPlans.find((p) => String(p.id) === String(l.subscription_plan_id));
            planName = planObj ? planObj.name : "Subscription Plan";
          }
          return {
            product_id: Number(l.product_id),
            quantity: Number(l.quantity) || 1,
            unit_price: Number(l.unit_price) || 0,
            discount_percent: Number(l.discount_percent) || 0,
            line_type: isSub && !isLifetime && l.billing_frequency !== "NONE" ? "RECURRING" : "ONE_TIME",
            subscription_enabled: isSub,
            subscription_name: isSub ? planName : null,
            duration_mode: isSub ? l.duration_mode : null,
            validity_value: isSub && !isLifetime ? (Number(l.validity_value) || 1) : null,
            validity_unit: isSub && !isLifetime ? (l.validity_unit || "MONTHS") : null,
            billing_frequency: isSub ? (isLifetime ? "NONE" : (l.billing_frequency || "MONTHLY")) : "NONE",
            subscription_start_trigger: "ORDER_ACTIVATION",
          };
        }),
      };

      const newQuote = await api.createQuote(payload);
      onNotify(`Quote ${newQuote.quote_number} created successfully!`, "success");
      setIsCreateModalOpen(false);
      await loadQuotes();
      loadQuoteDetails(newQuote.id);
    } catch (err) {
      onNotify("Failed to create quote: " + err.message, "error");
    } finally {
      setCreateLoading(false);
    }
  }

  // Add Recommended Item to Quote
  async function handleAddRecommendation(rec) {
    if (!selectedQuote) return;
    try {
      // Build updated lines payload appending the recommended product
      const currentLines = (selectedQuote.lines || []).map((l) => ({
        product_id: l.product_id,
        quantity: l.quantity,
        unit_price: l.unit_price,
        discount_percent: l.discount_percent,
        line_type: l.line_type || "ONE_TIME",
      }));

      currentLines.push({
        product_id: rec.product_id,
        quantity: rec.suggested_quantity || 1,
        unit_price: rec.unit_price,
        discount_percent: 0,
        line_type: rec.type === "UPSELL" ? "ONE_TIME" : "RECURRING",
      });

      const updated = await api.updateQuote(selectedQuote.id, { lines: currentLines });
      onNotify(`Added ${rec.product_name} to Quote ${updated.quote_number}!`, "success");
      loadQuoteDetails(updated.id);
      loadQuotes();
    } catch (err) {
      onNotify("Failed to add recommendation: " + err.message, "error");
    }
  }

  // Decision Handlers (for Manager / Finance / Admin)
  async function handleDecisionSubmit(e) {
    e.preventDefault();
    if (!selectedQuote || !decisionModal.action) return;

    setDecisionLoading(true);
    try {
      if (decisionModal.action === "APPROVE") {
        await api.approveQuote(selectedQuote.id, decisionModal.comments);
        onNotify(`Quote ${selectedQuote.quote_number} approved!`, "success");
      } else {
        await api.rejectQuote(selectedQuote.id, decisionModal.comments);
        onNotify(`Quote ${selectedQuote.quote_number} rejected.`, "info");
      }
      setDecisionModal({ open: false, action: null, comments: "" });
      loadQuoteDetails(selectedQuote.id);
      loadQuotes();
    } catch (err) {
      onNotify(`Failed to ${decisionModal.action.toLowerCase()} quote: ` + err.message, "error");
    } finally {
      setDecisionLoading(false);
    }
  }

  // Calculate live line totals in modal
  const modalSubtotal = quoteLines.reduce(
    (sum, l) => sum + (Number(l.quantity) || 0) * (Number(l.unit_price) || 0),
    0
  );
  const modalDiscount = quoteLines.reduce(
    (sum, l) =>
      sum +
      (Number(l.quantity) || 0) *
        (Number(l.unit_price) || 0) *
        ((Number(l.discount_percent) || 0) / 100),
    0
  );
  const modalTotal = modalSubtotal - modalDiscount;

  return (
    <div>
      {/* Action Header */}
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
            Quotation Management
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Create quotes, govern discount risk ceilings, and evaluate intelligent upsell recommendations.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <button className="btn btn-secondary" onClick={loadQuotes} title="Refresh Quotes">
            <RotateCcw size={15} /> Refresh
          </button>
          <button className="btn btn-primary" onClick={openCreateModal}>
            <Plus size={16} /> Create Quote
          </button>
        </div>
      </div>

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>
          <Clock size={32} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <div>Loading Quotations...</div>
        </div>
      ) : error ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--status-high)" }}>
          <AlertTriangle size={36} style={{ marginBottom: "1rem" }} />
          <h3>{error}</h3>
          <button className="btn btn-secondary" onClick={loadQuotes} style={{ marginTop: "1rem" }}>
            Retry
          </button>
        </div>
      ) : quotes.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "3.5rem 1.5rem" }}>
          <FileText size={48} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <h3 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "0.5rem" }}>No Quotations Found</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: "480px", margin: "0 auto 1.5rem auto" }}>
            Get started by creating your first sales quote with real-time discount risk governance.
          </p>
          <button className="btn btn-primary" onClick={openCreateModal}>
            <Plus size={16} /> Create First Quote
          </button>
        </div>
      ) : (
        <div className="two-column-layout">
          {/* Quotes List */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <FileText size={18} /> Quotations ({quotes.length})
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {quotes.map((q) => {
                const isSelected = selectedQuote?.id === q.id;
                let badgeClass = "badge-neutral";
                if (q.status === "APPROVED" || q.status === "ACCEPTED") badgeClass = "badge-healthy";
                else if (q.status === "PENDING_APPROVAL") badgeClass = "badge-medium";
                else if (q.status === "REJECTED") badgeClass = "badge-high";

                const custName = q.customer?.company_name || `Customer #${q.customer_id}`;

                return (
                  <div
                    key={q.id}
                    onClick={() => loadQuoteDetails(q.id)}
                    style={{
                      padding: "1rem",
                      borderRadius: "var(--radius-md)",
                      background: isSelected ? "var(--bg-surface-elevated)" : "var(--bg-surface)",
                      border: isSelected ? "1px solid var(--primary)" : "1px solid var(--border-subtle)",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "0.35rem",
                      }}
                    >
                      <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>{q.quote_number}</span>
                      <span className={`badge ${badgeClass}`}>{q.status}</span>
                    </div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>
                      {custName}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        fontSize: "0.85rem",
                      }}
                    >
                      <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                        ${(q.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span
                          className={`badge ${
                            q.risk_score > 60
                              ? "badge-high"
                              : q.risk_score > 30
                              ? "badge-medium"
                              : "badge-healthy"
                          }`}
                          style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }}
                        >
                          Risk: {q.risk_score}
                        </span>
                        <ArrowRight size={13} color="var(--primary)" />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Selected Quote Details Inspector */}
          {selectedQuote ? (
            <div className="card">
              {/* Header */}
              <div
                className="card-header"
                style={{
                  borderBottom: "1px solid var(--border-subtle)",
                  paddingBottom: "1rem",
                  marginBottom: "1.25rem",
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-muted)",
                      textTransform: "uppercase",
                      fontWeight: 600,
                    }}
                  >
                    Quote Overview
                  </div>
                  <h2
                    style={{
                      fontSize: "1.4rem",
                      fontWeight: 800,
                      color: "var(--text-primary)",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.75rem",
                    }}
                  >
                    {selectedQuote.quote_number}
                    <span
                      className={`badge ${
                        selectedQuote.status === "APPROVED" || selectedQuote.status === "ACCEPTED"
                          ? "badge-healthy"
                          : selectedQuote.status === "PENDING_APPROVAL"
                          ? "badge-medium"
                          : selectedQuote.status === "REJECTED"
                          ? "badge-high"
                          : "badge-neutral"
                      }`}
                    >
                      {selectedQuote.status}
                    </span>
                  </h2>
                  <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    Account: <strong>{selectedQuote.customer?.company_name || `Customer #${selectedQuote.customer_id}`}</strong>
                  </div>
                </div>

                {/* Manager / Finance / Admin Action Buttons */}
                {canApprove && selectedQuote.status === "PENDING_APPROVAL" && (
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => setDecisionModal({ open: true, action: "APPROVE", comments: "" })}
                    >
                      <CheckCircle2 size={14} /> Approve
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ color: "var(--status-high)" }}
                      onClick={() => setDecisionModal({ open: true, action: "REJECT", comments: "" })}
                    >
                      <XCircle size={14} /> Reject
                    </button>
                  </div>
                )}
              </div>

              {/* Financial Metrics Summary */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                  gap: "0.75rem",
                  marginBottom: "1.5rem",
                }}
              >
                <div
                  style={{
                    padding: "0.85rem",
                    background: "var(--bg-surface-elevated)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                    Subtotal
                  </div>
                  <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    ${(selectedQuote.subtotal || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </div>
                </div>
                <div
                  style={{
                    padding: "0.85rem",
                    background: "var(--bg-surface-elevated)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                    Total Discount
                  </div>
                  <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--status-medium)" }}>
                    -${(selectedQuote.total_discount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </div>
                </div>
                <div
                  style={{
                    padding: "0.85rem",
                    background: "var(--bg-surface-elevated)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--primary-border)",
                  }}
                >
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                    Net Amount
                  </div>
                  <div style={{ fontSize: "1.15rem", fontWeight: 800, color: "var(--primary)" }}>
                    ${(selectedQuote.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </div>
                </div>
              </div>

              {/* Line Items Table */}
              <div style={{ marginBottom: "1.5rem" }}>
                <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.6rem" }}>Quote Items</h4>
                <div className="table-container" style={{ border: "1px solid var(--border-subtle)" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th style={{ textAlign: "center" }}>Qty</th>
                        <th style={{ textAlign: "right" }}>Unit Price</th>
                        <th style={{ textAlign: "right" }}>Discount %</th>
                        <th style={{ textAlign: "right" }}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedQuote.lines || []).map((line) => {
                        const prod = products.find((p) => p.id === line.product_id);
                        const hasSub = line.subscription_enabled;
                        const subName = line.subscription_name;
                        const durationMode = line.duration_mode;
                        const validityVal = line.validity_value || 1;
                        const validityUnit = line.validity_unit || "MONTHS";
                        const billFreq = line.billing_frequency || "NONE";

                        return (
                          <tr key={line.id}>
                            <td>
                              <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                                {prod?.name || `Product #${line.product_id}`}
                              </div>
                              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                {prod?.sku ? `SKU: ${prod.sku} • ` : ""}{hasSub ? "Subscription Item" : "One-Time Item"}
                              </div>
                              {hasSub && (
                                <div style={{ marginTop: "0.25rem" }}>
                                  <span
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: "0.3rem",
                                      fontSize: "0.72rem",
                                      fontWeight: 600,
                                      padding: "0.15rem 0.45rem",
                                      borderRadius: "4px",
                                      backgroundColor: "#EFF6FF",
                                      color: "#1D4ED8",
                                      border: "1px solid #BFDBFE",
                                    }}
                                  >
                                    <Sparkles size={11} /> Subscription: {subName || "Plan"} (
                                    {durationMode === "LIFETIME"
                                      ? "Lifetime • Included / No recurring billing"
                                      : `${validityVal} ${validityUnit} • ${billFreq === "NONE" ? "Included / No recurring billing" : billFreq + " Billing"}`}
                                    )
                                  </span>
                                </div>
                              )}
                            </td>
                            <td style={{ textAlign: "center", fontWeight: 600 }}>{line.quantity}</td>
                            <td style={{ textAlign: "right" }}>${line.unit_price.toFixed(2)}</td>
                            <td style={{ textAlign: "right", color: line.discount_percent > 0 ? "var(--status-medium)" : "inherit" }}>
                              {line.discount_percent}%
                            </td>
                            <td style={{ textAlign: "right", fontWeight: 700 }}>${line.line_total.toFixed(2)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {(selectedQuote.lines || []).some((l) => l.subscription_enabled) && (
                  <div
                    style={{
                      marginTop: "0.75rem",
                      padding: "0.6rem 0.85rem",
                      borderRadius: "6px",
                      backgroundColor: "#F0FDF4",
                      border: "1px solid #BBF7D0",
                      fontSize: "0.8rem",
                      color: "#166534",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                    }}
                  >
                    <Sparkles size={14} color="#16A34A" />
                    <span>
                      <strong>Included Entitlements Snapshot:</strong> Bundled subscriptions do not activate at the quotation stage. They activate automatically upon customer <strong>Order Activation</strong>.
                    </span>
                  </div>
                )}
              </div>

              {/* Discount Governance & Risk Evaluation */}
              <div
                style={{
                  padding: "1.25rem",
                  background: "var(--bg-surface-elevated)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  marginBottom: "1.5rem",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <ShieldAlert size={18} color="var(--primary)" />
                    <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Discount Governance & Risk</span>
                  </div>
                  <span
                    className={`badge ${
                      selectedQuote.risk_score > 60
                        ? "badge-high"
                        : selectedQuote.risk_score > 30
                        ? "badge-medium"
                        : "badge-healthy"
                    }`}
                    style={{ fontSize: "0.85rem", padding: "0.25rem 0.6rem" }}
                  >
                    Risk Score: {selectedQuote.risk_score} / 100
                  </span>
                </div>

                {riskData && (
                  <div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                      {riskData.requires_approval
                        ? "⚠️ Quote exceeds discount ceilings and requires formal approval before acceptance."
                        : "✓ Quote falls within standard guardrails and does not require managerial escalation."}
                    </div>

                    {riskData.violations && riskData.violations.length > 0 && (
                      <div style={{ marginTop: "0.5rem" }}>
                        <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--status-high)", marginBottom: "0.3rem" }}>
                          Ceiling Violations:
                        </div>
                        {riskData.violations.map((v, i) => (
                          <div
                            key={i}
                            style={{
                              fontSize: "0.8rem",
                              color: "var(--text-secondary)",
                              padding: "0.4rem 0.6rem",
                              background: "rgba(220, 38, 38, 0.08)",
                              borderRadius: "var(--radius-xs)",
                              marginBottom: "0.25rem",
                            }}
                          >
                            <strong>{v.product}</strong>: Requested discount of {v.requested_discount}% exceeds maximum allowed ceiling of {v.allowed_discount}% (Excess: +{v.excess}%)
                          </div>
                        ))}
                      </div>
                    )}

                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
                      {riskData.requires_manager_approval && (
                        <span className="badge badge-medium">Requires Sales Manager Approval</span>
                      )}
                      {riskData.requires_finance_approval && (
                        <span className="badge badge-high">Requires Finance Escalation</span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* M6 Upsell & Cross-Sell Recommendations */}
              <div
                style={{
                  padding: "1.25rem",
                  background: "var(--bg-surface-elevated)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  marginBottom: "1.5rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <Sparkles size={18} color="var(--primary)" />
                  <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Recommended for this Deal (M6 Engine)</span>
                </div>

                {recsLoading ? (
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Evaluating recommendation algorithms...</div>
                ) : recommendations.length === 0 ? (
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    No additional cross-sell or upsell opportunities identified for current quote package.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    {recommendations.map((rec, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: "0.85rem",
                          background: "var(--bg-surface)",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border-subtle)",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: "1rem",
                          flexWrap: "wrap",
                        }}
                      >
                        <div style={{ flex: 1 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                            <span
                              className={`badge ${rec.type === "UPSELL" ? "badge-info" : "badge-healthy"}`}
                              style={{ fontSize: "0.7rem" }}
                            >
                              {rec.type}
                            </span>
                            <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>{rec.product_name}</strong>
                          </div>
                          <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.25rem" }}>
                            {rec.reason}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            Price: <strong>${rec.unit_price.toFixed(2)}</strong> • Margin Impact:{" "}
                            <strong style={{ color: "var(--status-healthy)" }}>+${rec.estimated_margin_impact.toFixed(2)}</strong>
                          </div>
                        </div>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleAddRecommendation(rec)}
                          style={{ whiteSpace: "nowrap" }}
                        >
                          <Plus size={13} /> Add to Quote
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Approval Tracking View */}
              <div
                style={{
                  padding: "1.25rem",
                  background: "var(--bg-surface-elevated)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <UserCheck size={18} color="var(--primary)" />
                  <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Approval Tracking</span>
                </div>

                {approvalsLoading ? (
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Checking approval chain...</div>
                ) : approvals.length === 0 ? (
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    No approvals required for this quotation.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {approvals.map((app) => {
                      let badge = "badge-medium";
                      if (app.status === "APPROVED") badge = "badge-healthy";
                      else if (app.status === "REJECTED") badge = "badge-high";

                      return (
                        <div
                          key={app.id}
                          style={{
                            padding: "0.75rem",
                            background: "var(--bg-surface)",
                            borderRadius: "var(--radius-sm)",
                            border: "1px solid var(--border-subtle)",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                          }}
                        >
                          <div>
                            <div style={{ fontWeight: 600, fontSize: "0.85rem" }}>
                              {app.approval_type} Level Approval
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                              {app.reason || "Policy compliance review"}
                              {app.comments && ` • "${app.comments}"`}
                            </div>
                          </div>
                          <span className={`badge ${badge}`}>{app.status}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
              Select a quote from the list to inspect details.
            </div>
          )}
        </div>
      )}

      {/* Create Quote Modal */}
      {isCreateModalOpen && (
        <div className="modal-overlay" onClick={() => setIsCreateModalOpen(false)}>
          <div className="modal-card" style={{ maxWidth: "820px", maxHeight: "90vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h2 className="card-title">
                <FileText size={20} color="var(--primary)" /> Create New Quotation
              </h2>
            </div>
            <form onSubmit={handleCreateQuote}>
              {/* Customer Selector */}
              <div className="form-group" style={{ marginBottom: "1.25rem" }}>
                <label className="form-label">Customer Account</label>
                <select
                  className="form-select"
                  value={selectedCustomerId}
                  onChange={(e) => setSelectedCustomerId(e.target.value)}
                  required
                >
                  <option value="">Select a customer...</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.company_name} ({c.tier} tier • {c.discount_ceiling}% ceiling)
                    </option>
                  ))}
                </select>
              </div>

              {/* Quote Lines Builder */}
              <div style={{ marginBottom: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <label className="form-label" style={{ margin: 0 }}>Quote Lines</label>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={addEmptyLine}>
                    <Plus size={13} /> Add Line
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxHeight: "420px", overflowY: "auto", paddingRight: "0.25rem" }}>
                  {quoteLines.map((line, idx) => {
                    return (
                      <div
                        key={idx}
                        style={{
                          padding: "0.85rem",
                          background: "var(--bg-surface-elevated)",
                          borderRadius: "var(--radius-md)",
                          border: line.purchase_type === "SUBSCRIPTION" ? "1px solid var(--primary)" : "1px solid var(--border-subtle)",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "2fr 70px 100px 90px 36px",
                            gap: "0.5rem",
                            alignItems: "center",
                          }}
                        >
                          <select
                            className="form-select"
                            value={line.product_id}
                            onChange={(e) => updateLine(idx, "product_id", e.target.value)}
                            required
                          >
                            {products.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.name} (${p.unit_price})
                              </option>
                            ))}
                          </select>
                          <input
                            type="number"
                            min="1"
                            className="form-input"
                            placeholder="Qty"
                            value={line.quantity}
                            onChange={(e) => updateLine(idx, "quantity", e.target.value)}
                            required
                          />
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            className="form-input"
                            placeholder="Unit Price"
                            value={line.unit_price}
                            onChange={(e) => updateLine(idx, "unit_price", e.target.value)}
                            required
                          />
                          <input
                            type="number"
                            step="0.1"
                            min="0"
                            max="100"
                            className="form-input"
                            placeholder="Disc %"
                            value={line.discount_percent}
                            onChange={(e) => updateLine(idx, "discount_percent", e.target.value)}
                          />
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            style={{ padding: "0.3rem", color: "var(--status-high)" }}
                            onClick={() => removeLine(idx)}
                            disabled={quoteLines.length === 1}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>

                        {/* Purchase Type & Subscription Configuration */}
                        <div style={{ marginTop: "0.75rem", paddingTop: "0.6rem", borderTop: "1px dashed var(--border-subtle)" }}>
                          <div style={{ marginBottom: "0.5rem" }}>
                            <label style={{ fontSize: "0.76rem", fontWeight: 700, color: "var(--text-secondary)", display: "block", marginBottom: "0.35rem" }}>
                              Purchase Type
                            </label>
                            <div style={{ display: "flex", gap: "1.25rem", alignItems: "center" }}>
                              <label style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", fontSize: "0.82rem", fontWeight: line.purchase_type === "ONE_TIME" ? 700 : 500, color: line.purchase_type === "ONE_TIME" ? "var(--text-primary)" : "var(--text-secondary)", cursor: "pointer" }}>
                                <input
                                  type="radio"
                                  name={`purchase_type_${idx}`}
                                  checked={line.purchase_type === "ONE_TIME"}
                                  onChange={() => updateLine(idx, "purchase_type", "ONE_TIME")}
                                />
                                One-Time Purchase
                              </label>
                              <label style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", fontSize: "0.82rem", fontWeight: line.purchase_type === "SUBSCRIPTION" ? 700 : 500, color: line.purchase_type === "SUBSCRIPTION" ? "var(--primary)" : "var(--text-secondary)", cursor: "pointer" }}>
                                <input
                                  type="radio"
                                  name={`purchase_type_${idx}`}
                                  checked={line.purchase_type === "SUBSCRIPTION"}
                                  onChange={() => {
                                    updateLine(idx, "purchase_type", "SUBSCRIPTION");
                                    if (!line.subscription_name) {
                                      const prod = products.find((p) => p.id === Number(line.product_id));
                                      updateLine(idx, "subscription_name", subscriptionPlans[0]?.name || (prod ? `${prod.name} Subscription` : "Subscription Plan"));
                                      if (subscriptionPlans[0]?.id) updateLine(idx, "subscription_plan_id", String(subscriptionPlans[0].id));
                                    }
                                  }}
                                />
                                With Subscription
                              </label>
                            </div>
                          </div>

                          {line.purchase_type === "SUBSCRIPTION" && (
                            <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid #BFDBFE", borderRadius: "6px", padding: "0.85rem", display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" }}>
                              <div style={{ fontSize: "0.82rem", fontWeight: 700, color: "#1D4ED8", display: "flex", alignItems: "center", gap: "0.35rem" }}>
                                <Sparkles size={14} /> Subscription Configuration
                              </div>

                              {/* Subscription Type / Plan */}
                              <div>
                                <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.25rem" }}>
                                  Subscription Type / Plan
                                </label>
                                <select
                                  className="form-select"
                                  style={{ fontSize: "0.8rem", padding: "0.3rem 0.5rem", height: "32px", width: "100%" }}
                                  value={line.subscription_plan_id || ""}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    updateLine(idx, "subscription_plan_id", val);
                                    if (val !== "custom") {
                                      const sel = subscriptionPlans.find((p) => String(p.id) === String(val));
                                      if (sel) updateLine(idx, "subscription_name", sel.name);
                                    }
                                  }}
                                >
                                  <option value="">Select Subscription Plan...</option>
                                  {subscriptionPlans.map((p) => (
                                    <option key={p.id} value={p.id}>{p.name}</option>
                                  ))}
                                  <option value="custom">+ Custom Plan Name</option>
                                </select>
                                {line.subscription_plan_id === "custom" && (
                                  <input
                                    type="text"
                                    className="form-input"
                                    style={{ fontSize: "0.78rem", padding: "0.25rem 0.5rem", height: "30px", marginTop: "0.3rem" }}
                                    placeholder="Enter custom plan name..."
                                    value={line.subscription_name || ""}
                                    onChange={(e) => updateLine(idx, "subscription_name", e.target.value)}
                                  />
                                )}
                              </div>

                              {/* Validity: Lifetime vs Till Validity */}
                              <div>
                                <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.25rem" }}>
                                  Validity
                                </label>
                                <div style={{ display: "flex", gap: "1.25rem", alignItems: "center" }}>
                                  <label style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", fontSize: "0.8rem", cursor: "pointer" }}>
                                    <input
                                      type="radio"
                                      name={`validity_${idx}`}
                                      checked={line.duration_mode === "LIFETIME"}
                                      onChange={() => {
                                        updateLine(idx, "duration_mode", "LIFETIME");
                                        updateLine(idx, "billing_frequency", "NONE");
                                      }}
                                    />
                                    Lifetime
                                  </label>
                                  <label style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", fontSize: "0.8rem", cursor: "pointer" }}>
                                    <input
                                      type="radio"
                                      name={`validity_${idx}`}
                                      checked={line.duration_mode !== "LIFETIME"}
                                      onChange={() => {
                                        updateLine(idx, "duration_mode", "TILL_VALIDITY");
                                        if (line.billing_frequency === "NONE") {
                                          updateLine(idx, "billing_frequency", "MONTHLY");
                                        }
                                      }}
                                    />
                                    Till Validity
                                  </label>
                                </div>
                              </div>

                              {/* If Till Validity: Duration & Billing Frequency */}
                              {line.duration_mode !== "LIFETIME" ? (
                                <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "0.75rem", alignItems: "flex-end" }}>
                                  <div>
                                    <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.25rem" }}>
                                      Duration
                                    </label>
                                    <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap", marginBottom: line.validity_preset === "CUSTOM" ? "0.3rem" : 0 }}>
                                      {[
                                        { label: "1 Month", value: 1, unit: "MONTHS", preset: "1_MONTH" },
                                        { label: "3 Months", value: 3, unit: "MONTHS", preset: "3_MONTHS" },
                                        { label: "6 Months", value: 6, unit: "MONTHS", preset: "6_MONTHS" },
                                        { label: "1 Year", value: 1, unit: "YEARS", preset: "1_YEAR" },
                                        { label: "Custom", preset: "CUSTOM" },
                                      ].map((d) => (
                                        <button
                                          key={d.preset}
                                          type="button"
                                          onClick={() => {
                                            updateLine(idx, "validity_preset", d.preset);
                                            if (d.preset !== "CUSTOM") {
                                              updateLine(idx, "validity_value", d.value);
                                              updateLine(idx, "validity_unit", d.unit);
                                            }
                                          }}
                                          style={{
                                            padding: "0.2rem 0.45rem",
                                            fontSize: "0.72rem",
                                            fontWeight: line.validity_preset === d.preset ? 700 : 500,
                                            borderRadius: "4px",
                                            border: line.validity_preset === d.preset ? "1px solid var(--primary)" : "1px solid var(--border-subtle)",
                                            background: line.validity_preset === d.preset ? "var(--primary-light, #EFF6FF)" : "var(--bg-surface)",
                                            color: line.validity_preset === d.preset ? "var(--primary)" : "var(--text-secondary)",
                                            cursor: "pointer",
                                          }}
                                        >
                                          {d.label}
                                        </button>
                                      ))}
                                    </div>
                                    {line.validity_preset === "CUSTOM" && (
                                      <div style={{ display: "flex", gap: "0.3rem", marginTop: "0.25rem" }}>
                                        <input
                                          type="number"
                                          min="1"
                                          className="form-input"
                                          style={{ width: "65px", fontSize: "0.75rem", padding: "0.2rem 0.4rem", height: "28px" }}
                                          value={line.validity_value || 1}
                                          onChange={(e) => updateLine(idx, "validity_value", Number(e.target.value) || 1)}
                                        />
                                        <select
                                          className="form-select"
                                          style={{ fontSize: "0.75rem", padding: "0.2rem 0.4rem", height: "28px" }}
                                          value={line.validity_unit || "MONTHS"}
                                          onChange={(e) => updateLine(idx, "validity_unit", e.target.value)}
                                        >
                                          <option value="MONTHS">Months</option>
                                          <option value="YEARS">Years</option>
                                        </select>
                                      </div>
                                    )}
                                  </div>

                                  <div>
                                    <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.25rem" }}>
                                      Billing Frequency
                                    </label>
                                    <select
                                      className="form-select"
                                      style={{ fontSize: "0.8rem", padding: "0.3rem 0.5rem", height: "32px" }}
                                      value={line.billing_frequency || "MONTHLY"}
                                      onChange={(e) => updateLine(idx, "billing_frequency", e.target.value)}
                                    >
                                      <option value="NONE">Included (No recurring billing)</option>
                                      <option value="MONTHLY">Monthly</option>
                                      <option value="QUARTERLY">Quarterly</option>
                                      <option value="YEARLY">Yearly</option>
                                    </select>
                                  </div>
                                </div>
                              ) : (
                                <div style={{ fontSize: "0.75rem", color: "#1E3A8A", background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: "4px", padding: "0.4rem 0.6rem" }}>
                                  ✓ <strong>End Date:</strong> Never • <strong>Billing:</strong> Included • No recurring billing
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Live Totals Bar */}
              <div
                style={{
                  padding: "0.85rem 1.25rem",
                  background: "var(--bg-surface-elevated)",
                  borderRadius: "var(--radius-md)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "1.5rem",
                }}
              >
                <div>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Subtotal: </span>
                  <strong>${modalSubtotal.toFixed(2)}</strong>
                </div>
                <div>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Discount: </span>
                  <strong style={{ color: "var(--status-medium)" }}>-${modalDiscount.toFixed(2)}</strong>
                </div>
                <div>
                  <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Total Price: </span>
                  <strong style={{ fontSize: "1.1rem", color: "var(--primary)" }}>${modalTotal.toFixed(2)}</strong>
                </div>
              </div>

              {/* Modal Actions */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsCreateModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={createLoading}>
                  {createLoading ? "Creating Quote..." : "Generate Quote"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Decision Modal (Approve / Reject) */}
      {decisionModal.open && (
        <div className="modal-overlay" onClick={() => setDecisionModal({ open: false, action: null, comments: "" })}>
          <div className="modal-card" style={{ maxWidth: "480px" }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h2 className="card-title">
                {decisionModal.action === "APPROVE" ? (
                  <>
                    <CheckCircle2 size={20} color="var(--status-healthy)" /> Approve Quotation
                  </>
                ) : (
                  <>
                    <XCircle size={20} color="var(--status-high)" /> Reject Quotation
                  </>
                )}
              </h2>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "1rem" }}>
              Provide approval governance notes for <strong>{selectedQuote?.quote_number}</strong>.
            </p>
            <form onSubmit={handleDecisionSubmit}>
              <div className="form-group">
                <label className="form-label">Review Comments (Optional)</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="e.g. Strategic account margin approved for Q3..."
                  value={decisionModal.comments}
                  onChange={(e) => setDecisionModal((prev) => ({ ...prev, comments: e.target.value }))}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setDecisionModal({ open: false, action: null, comments: "" })}
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
