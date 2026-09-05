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
  RotateCcw,
  Sparkles,
} from "lucide-react";

function formatNegotiationDisplay(neg) {
  const req = (neg.requested_change || "").toLowerCase();
  const isPercent = neg.field_type === "PERCENTAGE" || req.includes("discount") || req.includes("percent");
  const isCurrency = neg.field_type === "CURRENCY" || req.includes("amount") || req.includes("price") || req.includes("total");

  function fmt(val) {
    if (val === null || val === undefined || val === "" || val === "N/A") return "N/A";
    const num = parseFloat(val);
    if (isNaN(num)) return val;
    if (isPercent) return `${num.toFixed(1)}%`;
    if (isCurrency) return `$${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return num.toString();
  }

  const label = (req === "overall_discount_percent" || req === "discount_percent" || req.includes("discount"))
    ? "Overall Quote Discount"
    : req === "quantity"
    ? "Order Quantity"
    : neg.requested_change;
  return {
    label,
    prev: fmt(neg.previous_value),
    prop: fmt(neg.proposed_value),
  };
}

function getCustomerOrderStatus(order) {
  if (!order) return "CONFIRMED";
  const status = (order.status || "").toUpperCase();
  const physicalLines = (order.lines || []).filter(
    (l) => (l.line_type || "ONE_TIME").toUpperCase() === "ONE_TIME" &&
           (l.fulfillment_type || "PHYSICAL").toUpperCase() === "PHYSICAL"
  );
  const totalPhysicalQty = physicalLines.reduce((sum, l) => sum + (l.quantity || 0), 0);
  const totalAllocatedQty = (order.lines || []).reduce((sum, l) => {
    return sum + (l.fulfillment_splits || []).reduce((sSum, sp) => sSum + (sp.quantity_allocated || 0), 0);
  }, 0);

  if (totalPhysicalQty === 0) {
    return status === "PENDING" ? "ACTIVE" : (status || "ACTIVE");
  }

  if (status === "FULFILLED") return "FULFILLED";
  if (status === "CANCELLED") return "CANCELLED";
  if (totalPhysicalQty > 0 && totalAllocatedQty > 0 && totalAllocatedQty < totalPhysicalQty) {
    return "PARTIALLY FULFILLED";
  }
  if (totalPhysicalQty > 0 && totalAllocatedQty >= totalPhysicalQty) {
    return (status === "CONFIRMED" || status === "FULFILLED") ? "FULFILLED" : (status || "PROCESSING");
  }
  return status || "CONFIRMED";
}

function getStatusBadgeClass(status) {
  switch (status) {
    case "FULFILLED":
      return "badge-healthy";
    case "CONFIRMED":
    case "PROCESSING":
      return "badge-info";
    case "PARTIALLY FULFILLED":
      return "badge-medium";
    case "CANCELLED":
      return "badge-high";
    default:
      return "badge-neutral";
  }
}

function _formatAsciiProgress(percent) {
  const totalBlocks = 15;
  const filled = Math.min(totalBlocks, Math.max(0, Math.round((percent / 100) * totalBlocks)));
  const empty = totalBlocks - filled;
  return "█".repeat(filled) + "░".repeat(empty);
}

function getSplitStatusLabel(splitStatus) {
  const s = (splitStatus || "").toUpperCase();
  switch (s) {
    case "ALLOCATED":
      return "Allocated";
    case "PICKED":
      return "Picked";
    case "SHIPPED":
      return "Fulfilled";
    case "BACKORDERED":
      return "Backordered";
    default:
      return splitStatus || "Allocated";
  }
}

function getItemStatus(line, orderStatus) {
  const ft = (line.fulfillment_type || "PHYSICAL").toUpperCase();
  if (ft === "DIGITAL") {
    return { label: "Digital Fulfillment", badge: "badge-healthy" };
  }
  if (ft === "SERVICE") {
    return { label: "Service Active", badge: "badge-healthy" };
  }
  const isRecurring = (line.line_type || "").toUpperCase() === "RECURRING";
  if (isRecurring) {
    return { label: "Active", badge: "badge-healthy" };
  }
  const allocated = (line.fulfillment_splits || []).reduce(
    (sum, sp) => sum + (sp.quantity_allocated || 0),
    0
  );
  if (orderStatus === "FULFILLED") {
    return { label: "Fulfilled", badge: "badge-healthy" };
  }
  if (allocated >= line.quantity && line.quantity > 0) {
    return { label: "Allocated", badge: "badge-info" };
  }
  if (allocated > 0) {
    return { label: `Partially Fulfilled (${allocated}/${line.quantity})`, badge: "badge-medium" };
  }
  if (orderStatus === "CONFIRMED") {
    return { label: "Confirmed", badge: "badge-info" };
  }
  return { label: "Processing", badge: "badge-info" };
}

export function CustomerPortal({ user, onNotify, activeSubTab = "quotes", onTabChange = null }) {
  const [profile, setProfile] = useState(null);
  const [quotes, setQuotes] = useState([]);
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [activeTab, setActiveTab] = useState(activeSubTab || "quotes"); // quotes, orders, billing, profile
  const [loading, setLoading] = useState(true);

  // Orders & Fulfillment State
  const [orders, setOrders] = useState([]);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState(null);

  // Negotiation Modal
  const [isNegModalOpen, setIsNegModalOpen] = useState(false);
  const [requestedChange, setRequestedChange] = useState("overall_discount_percent");
  const [proposedValue, setProposedValue] = useState("");
  const [negLoading, setNegLoading] = useState(false);

  // Billing & Subscriptions State
  const [portalInvoices, setPortalInvoices] = useState([]);
  const [portalSubscriptions, setPortalSubscriptions] = useState([]);
  const [billingLoading, setBillingLoading] = useState(false);

  useEffect(() => {
    if (activeSubTab && activeSubTab !== activeTab) {
      setActiveTab(activeSubTab);
      if (activeSubTab === "orders" && orders.length === 0 && !ordersLoading) {
        loadOrders();
      }
    }
  }, [activeSubTab]);

  function handleTabSelect(tab) {
    setActiveTab(tab);
    if (onTabChange) {
      onTabChange(tab);
    }
  }

  useEffect(() => {
    loadPortalData();
    loadOrders();
    loadBillingData();
  }, []);

  async function loadBillingData() {
    setBillingLoading(true);
    try {
      const [invs, subs] = await Promise.all([
        api.getPortalInvoices().catch(() => []),
        api.getPortalSubscriptions().catch(() => []),
      ]);
      setPortalInvoices(invs || []);
      setPortalSubscriptions(subs || []);
    } catch {
      // ignore
    } finally {
      setBillingLoading(false);
    }
  }

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

  async function loadOrders() {
    setOrdersLoading(true);
    setOrdersError(null);
    try {
      const ordersData = await api.getPortalOrders();
      const list = ordersData || [];
      setOrders(list);
      if (list.length > 0) {
        // Auto-select first order if none selected or if selection changed
        setSelectedOrder((prev) => {
          const currentId = prev?.id;
          const matching = list.find((o) => o.id === currentId);
          const toSelect = matching || list[0];
          loadOrderDetail(toSelect.id);
          return toSelect;
        });
      } else {
        setSelectedOrder(null);
      }
    } catch (err) {
      setOrdersError("Unable to load your order information.");
    } finally {
      setOrdersLoading(false);
    }
  }

  async function loadOrderDetail(orderId) {
    try {
      const detail = await api.getPortalOrderDetail(orderId);
      if (detail) {
        setSelectedOrder(detail);
      }
    } catch (err) {
      setOrders((currentOrders) => {
        const found = currentOrders.find((o) => o.id === orderId);
        if (found) setSelectedOrder(found);
        return currentOrders;
      });
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
      loadOrders();
      loadBillingData();
      if (selectedQuote?.id === quoteId) {
        loadQuoteDetail(quoteId);
      }
    } catch (err) {
      onNotify("Confirmation failed: " + err.message, "error");
    }
  }

  async function handleSubmitNegotiation(e) {
    e.preventDefault();
    const val = proposedValue.trim();
    if (!val) {
      onNotify("Please enter a proposed discount percentage.", "error");
      return;
    }

    const numVal = parseFloat(val);
    if (isNaN(numVal) || numVal < 0 || numVal > 100) {
      onNotify("Proposed discount must be a valid number between 0.0% and 100.0%.", "error");
      return;
    }

    setNegLoading(true);
    try {
      await api.submitNegotiation(selectedQuote.id, {
        requested_change: requestedChange || "overall_discount_percent",
        proposed_value: val,
      });
      onNotify("Discount proposal submitted successfully!", "success");
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
      <div className="card" style={{ marginBottom: "1.5rem", borderLeft: "4px solid var(--primary)", background: "var(--bg-surface)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.25rem" }}>
              <Building2 size={22} color="var(--primary)" />
              <h1 style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--text-primary)" }}>{profile?.company_name || "Customer Workspace"}</h1>
              <span className="badge badge-info">{profile?.tier || "STANDARD"} TIER</span>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem" }}>
              Authorized Contact: <strong style={{ color: "var(--text-primary)" }}>{profile?.contact_name}</strong> ({profile?.email})
            </p>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.04em" }}>Discount Ceiling</div>
            <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--status-healthy)" }}>
              {profile?.discount_ceiling || 10}%
            </div>
          </div>
        </div>
      </div>

      {/* Tab: Customer Portal Dashboard (Route: /portal) */}
      {activeTab === "portal" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* KPI Cards Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
            <div className="card" style={{ padding: "1.25rem", cursor: "pointer" }} onClick={() => handleTabSelect("quotes")}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <span style={{ fontSize: "0.82rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.04em" }}>
                  Active Quotes
                </span>
                <FileText size={20} color="var(--primary)" />
              </div>
              <div style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--text-primary)" }}>
                {quotes.length}
              </div>
              <div style={{ fontSize: "0.82rem", color: "var(--primary)", marginTop: "0.5rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.25rem" }}>
                View Quotes <ArrowRight size={13} />
              </div>
            </div>

            <div className="card" style={{ padding: "1.25rem", cursor: "pointer" }} onClick={() => handleTabSelect("orders")}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <span style={{ fontSize: "0.82rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.04em" }}>
                  Orders & Fulfillment
                </span>
                <Package size={20} color="var(--primary)" />
              </div>
              <div style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--text-primary)" }}>
                {orders.length}
              </div>
              <div style={{ fontSize: "0.82rem", color: "var(--primary)", marginTop: "0.5rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.25rem" }}>
                Track Fulfillment <ArrowRight size={13} />
              </div>
            </div>

            <div className="card" style={{ padding: "1.25rem", cursor: "pointer" }} onClick={() => handleTabSelect("billing")}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <span style={{ fontSize: "0.82rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.04em" }}>
                  Active Subscriptions
                </span>
                <Sparkles size={20} color="var(--primary)" />
              </div>
              <div style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--text-primary)" }}>
                {portalSubscriptions.length}
              </div>
              <div style={{ fontSize: "0.82rem", color: "var(--primary)", marginTop: "0.5rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.25rem" }}>
                Manage Subscriptions <ArrowRight size={13} />
              </div>
            </div>

            <div className="card" style={{ padding: "1.25rem", cursor: "pointer" }} onClick={() => handleTabSelect("billing")}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <span style={{ fontSize: "0.82rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.04em" }}>
                  Invoices & Statements
                </span>
                <Receipt size={20} color="var(--primary)" />
              </div>
              <div style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--text-primary)" }}>
                {portalInvoices.length}
              </div>
              <div style={{ fontSize: "0.82rem", color: "var(--primary)", marginTop: "0.5rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.25rem" }}>
                View Invoices <ArrowRight size={13} />
              </div>
            </div>
          </div>

          {/* Recent Activity Panels */}
          <div className="two-column-layout">
            {/* Recent Quotations Quick View */}
            <div className="card">
              <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div className="card-title">
                  <FileText size={18} /> Recent Quotations
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleTabSelect("quotes")}
                >
                  View All ({quotes.length})
                </button>
              </div>
              {quotes.length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No active quotations.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                  {quotes.slice(0, 4).map((q) => (
                    <div
                      key={q.id}
                      onClick={() => {
                        loadQuoteDetail(q.id);
                        handleTabSelect("quotes");
                      }}
                      style={{
                        padding: "0.85rem 1rem",
                        borderRadius: "var(--radius-md)",
                        background: "var(--bg-surface)",
                        border: "1px solid var(--border-subtle)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        cursor: "pointer",
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>{q.quote_number}</div>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{q.item_count} items</div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <span className={`badge ${q.status === "APPROVED" || q.status === "ACCEPTED" ? "badge-healthy" : "badge-neutral"}`}>
                          {q.status}
                        </span>
                        <div style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: "0.88rem", marginTop: "0.2rem" }}>
                          ${q.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Recent Orders Quick View */}
            <div className="card">
              <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div className="card-title">
                  <Package size={18} /> Recent Orders & Fulfillment
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleTabSelect("orders")}
                >
                  View All ({orders.length})
                </button>
              </div>
              {orders.length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No orders placed yet.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                  {orders.slice(0, 4).map((o) => {
                    const st = getCustomerOrderStatus(o);
                    return (
                      <div
                        key={o.id}
                        onClick={() => {
                          loadOrderDetail(o.id);
                          handleTabSelect("orders");
                        }}
                        style={{
                          padding: "0.85rem 1rem",
                          borderRadius: "var(--radius-md)",
                          background: "var(--bg-surface)",
                          border: "1px solid var(--border-subtle)",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          cursor: "pointer",
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>{o.order_number || `ORD-${o.id}`}</div>
                          <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{(o.lines || []).length} items</div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <span className={`badge ${getStatusBadgeClass(st)}`}>{st}</span>
                          <div style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: "0.88rem", marginTop: "0.2rem" }}>
                            ${(o.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Quotes */}
      {activeTab === "quotes" && (
        <div className="two-column-layout">
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
                        background: isSelected ? "var(--primary-light)" : "var(--bg-surface)",
                        border: isSelected ? "1px solid var(--primary)" : "1px solid var(--border-subtle)",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                        <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>{q.quote_number}</span>
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
                  <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.04em" }}>Quotation Details</div>
                  <h2 style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--text-primary)" }}>{selectedQuote.quote_number}</h2>
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
                          {line.subscription_enabled && (
                            <div style={{ marginTop: "0.25rem" }}>
                              <span
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "0.25rem",
                                  fontSize: "0.72rem",
                                  fontWeight: 600,
                                  padding: "0.15rem 0.45rem",
                                  borderRadius: "4px",
                                  backgroundColor: "#EFF6FF",
                                  color: "#1D4ED8",
                                  border: "1px solid #BFDBFE",
                                }}
                              >
                                <Sparkles size={11} /> Included Entitlement: {line.subscription_name || "Service Pass"} (
                                {line.duration_mode === "LIFETIME" ? "Lifetime Access" : `${line.validity_value || 1} ${line.validity_unit || "MONTHS"}`}
                                ) • Activates on Order
                              </span>
                            </div>
                          )}
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
              <div style={{ background: "var(--bg-surface-elevated)", border: "1px solid var(--border-subtle)", padding: "1.1rem", borderRadius: "var(--radius-md)", marginBottom: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem", fontSize: "0.88rem", color: "var(--text-secondary)" }}>
                  <span>Subtotal:</span>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>${selectedQuote.subtotal.toFixed(2)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem", fontSize: "0.88rem", color: "var(--status-healthy)" }}>
                  <span>Total Discount:</span>
                  <span style={{ fontWeight: 600 }}>-${selectedQuote.total_discount.toFixed(2)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "1.15rem", fontWeight: 800, color: "var(--text-primary)", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.6rem" }}>
                  <span>Total Payable:</span>
                  <span>${selectedQuote.total_amount.toFixed(2)}</span>
                </div>
              </div>

              {/* Negotiation Thread */}
              <div>
                <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <MessageSquare size={16} color="var(--primary)" /> Negotiation & Revision History
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
                            padding: "0.85rem 1rem",
                            background: "var(--bg-surface-elevated)",
                            border: "1px solid var(--border-subtle)",
                            borderRadius: "var(--radius-sm)",
                            borderLeft: "4px solid var(--primary)",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.3rem" }}>
                            <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>
                              {(() => {
                                const d = formatNegotiationDisplay(neg);
                                return (
                                  <>
                                    Requested: <strong>{d.label}</strong> from <code>{d.prev}</code> to <code>{d.prop}</code>
                                  </>
                                );
                              })()}
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

      {/* Tab: Orders & Fulfillment */}
      {activeTab === "orders" && (
        <div>
          {ordersLoading ? (
            <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
              <Clock size={36} color="var(--primary)" style={{ marginBottom: "1rem" }} />
              <h3 style={{ fontSize: "1.15rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                Loading your orders...
              </h3>
            </div>
          ) : ordersError ? (
            <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
              <AlertCircle size={40} color="var(--status-high)" style={{ marginBottom: "1rem" }} />
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "0.5rem", color: "var(--text-primary)" }}>
                Unable to load your order information.
              </h3>
              <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
                Please check your network connection or try again.
              </p>
              <button className="btn btn-secondary" onClick={loadOrders}>
                <RotateCcw size={14} /> Retry
              </button>
            </div>
          ) : orders.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "3.5rem 1.5rem" }}>
              <Package size={48} color="var(--primary)" style={{ marginBottom: "1rem" }} />
              <h3 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "0.5rem" }}>
                Order Fulfillment & Tracking
              </h3>
              <p style={{ color: "var(--text-secondary)", maxWidth: "520px", margin: "0 auto 0.5rem auto", fontSize: "0.95rem" }}>
                Your confirmed orders and fulfillment updates will appear here.
              </p>
              <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", margin: 0 }}>
                No active orders yet.
              </p>
            </div>
          ) : (
            <div className="two-column-layout">
              {/* Orders List / Cards */}
              <div className="card">
                <div className="card-header">
                  <div className="card-title">
                    <Package size={18} /> My Orders ({orders.length})
                  </div>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={loadOrders}
                    title="Refresh Orders"
                  >
                    <RotateCcw size={13} />
                  </button>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {orders.map((ord) => {
                    const isSelected = selectedOrder?.id === ord.id;
                    const dispStatus = getCustomerOrderStatus(ord);
                    const badgeClass = getStatusBadgeClass(dispStatus);
                    const itemCount = (ord.lines || []).length;
                    return (
                      <div
                        key={ord.id}
                        onClick={() => loadOrderDetail(ord.id)}
                        style={{
                          padding: "1rem",
                          borderRadius: "var(--radius-md)",
                          background: isSelected ? "var(--primary-light)" : "var(--bg-surface)",
                          border: isSelected ? "1px solid var(--primary)" : "1px solid var(--border-subtle)",
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                          <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>Order #{ord.order_number}</span>
                          <span className={`badge ${badgeClass}`}>{dispStatus}</span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                          <span>{itemCount} {itemCount === 1 ? "item" : "items"}</span>
                          <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                            ${(ord.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", color: "var(--primary)", fontSize: "0.8rem", fontWeight: 600 }}>
                          View Details <ArrowRight size={13} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Selected Order Fulfillment & Tracking View */}
              {selectedOrder ? (
                (() => {
                  const currentStatus = getCustomerOrderStatus(selectedOrder);
                  const statusBadge = getStatusBadgeClass(currentStatus);
                  const lines = selectedOrder.lines || [];
                  const physicalLines = lines.filter(
                    (l) => (l.line_type || "ONE_TIME").toUpperCase() === "ONE_TIME" &&
                           (l.fulfillment_type || "PHYSICAL").toUpperCase() === "PHYSICAL"
                  );
                  const totalPhysicalQty = physicalLines.reduce((sum, l) => sum + (l.quantity || 0), 0);

                  // Real splits aggregation
                  const allSplits = [];
                  lines.forEach((line) => {
                    (line.fulfillment_splits || []).forEach((split) => {
                      allSplits.push({
                        ...split,
                        product_name: line.product_name || `Product #${line.product_id}`,
                      });
                    });
                  });

                  const totalAllocatedQty = allSplits.reduce((sum, sp) => sum + (sp.quantity_allocated || 0), 0);
                  const backorderedQty = Math.max(0, totalPhysicalQty - totalAllocatedQty);
                  const fulfillmentPercent = totalPhysicalQty > 0
                    ? Math.min(100, Math.round((totalAllocatedQty / totalPhysicalQty) * 100))
                    : (selectedOrder.status === "FULFILLED" || selectedOrder.status === "CONFIRMED" ? 100 : 0);

                  const lastUpdated = selectedOrder.updated_at
                    ? new Date(selectedOrder.updated_at).toLocaleString()
                    : selectedOrder.created_at
                    ? new Date(selectedOrder.created_at).toLocaleString()
                    : "Not available";

                  return (
                    <div className="card">
                      <div className="card-header" style={{ marginBottom: "1.25rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "1rem" }}>
                        <div>
                          <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.04em" }}>
                            Order Fulfillment & Tracking
                          </div>
                          <h2 style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.75rem", marginTop: "0.25rem" }}>
                            Order #{selectedOrder.order_number}
                            <span className={`badge ${statusBadge}`} style={{ fontSize: "0.8rem", padding: "0.25rem 0.6rem" }}>
                              {currentStatus}
                            </span>
                          </h2>
                        </div>
                      </div>

                      {/* Items Section */}
                      <div style={{ marginBottom: "1.75rem" }}>
                        <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                          Items
                        </h4>
                        <div className="table-container" style={{ border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)" }}>
                          <table className="data-table">
                            <thead>
                              <tr>
                                <th>Product</th>
                                <th style={{ textAlign: "center", width: "80px" }}>Qty</th>
                                <th style={{ textAlign: "right", width: "160px" }}>Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {lines.length === 0 ? (
                                <tr>
                                  <td colSpan={3} style={{ textAlign: "center", color: "var(--text-muted)", padding: "1.5rem" }}>
                                    No items found for this order.
                                  </td>
                                </tr>
                              ) : (
                                lines.map((line) => {
                                  const itemStat = getItemStatus(line, selectedOrder.status);
                                  return (
                                    <tr key={line.id}>
                                      <td>
                                        <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                                          {line.product_name || `Product #${line.product_id}`}
                                        </div>
                                        {line.product_sku && (
                                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                            SKU: {line.product_sku}
                                          </div>
                                        )}
                                        {line.subscription_enabled && (
                                          <div style={{ marginTop: "0.25rem" }}>
                                            <span
                                              style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                gap: "0.25rem",
                                                fontSize: "0.72rem",
                                                fontWeight: 600,
                                                padding: "0.15rem 0.45rem",
                                                borderRadius: "4px",
                                                backgroundColor: "#EFF6FF",
                                                color: "#1D4ED8",
                                                border: "1px solid #BFDBFE",
                                              }}
                                            >
                                              <Sparkles size={11} /> Entitlement: {line.subscription_name || "Included Service"} (
                                              {line.duration_mode === "LIFETIME" ? "Lifetime" : `${line.validity_value || 1} ${line.validity_unit || "MONTHS"}`}
                                              )
                                            </span>
                                          </div>
                                        )}
                                      </td>
                                      <td style={{ textAlign: "center", fontWeight: 700 }}>
                                        {line.quantity}
                                      </td>
                                      <td style={{ textAlign: "right" }}>
                                        <span className={`badge ${itemStat.badge}`}>
                                          {itemStat.label}
                                        </span>
                                      </td>
                                    </tr>
                                  );
                                })
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Warehouse Allocation Section */}
                      <div style={{ marginBottom: "1.75rem" }}>
                        <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                          Warehouse Allocation
                        </h4>
                        {totalPhysicalQty === 0 ? (
                          <div style={{ padding: "1rem", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-sm)", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                            Digital fulfillment & service activation — Warehouse allocation not required.
                          </div>
                        ) : allSplits.length === 0 ? (
                          <div style={{ padding: "1rem", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-sm)", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                            Awaiting warehouse allocation.
                          </div>
                        ) : (
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.85rem", marginBottom: "1rem" }}>
                            {allSplits.map((split, idx) => (
                              <div
                                key={split.id || idx}
                                style={{
                                  padding: "1rem",
                                  background: "var(--bg-surface-elevated)",
                                  borderRadius: "var(--radius-md)",
                                  border: "1px solid var(--border-subtle)",
                                }}
                              >
                                <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--text-primary)", marginBottom: "0.35rem" }}>
                                  {split.warehouse_name || `Warehouse #${split.warehouse_id}`}
                                </div>
                                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                                  <strong style={{ color: "var(--text-primary)" }}>{split.quantity_allocated} units</strong> allocated
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem" }}>
                                  <span style={{ color: "var(--text-muted)" }}>Status:</span>
                                  <span className="badge badge-info">{getSplitStatusLabel(split.status)}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Backorder */}
                        {totalPhysicalQty > 0 && (
                          <div
                            style={{
                              marginTop: "0.75rem",
                              padding: "0.85rem 1rem",
                              borderRadius: "var(--radius-md)",
                              background: backorderedQty > 0 ? "var(--status-high-bg)" : "var(--bg-surface-elevated)",
                              border: backorderedQty > 0 ? "1px solid var(--status-high-border)" : "1px solid var(--border-subtle)",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                          >
                            <span style={{ fontSize: "0.9rem", fontWeight: 600, color: backorderedQty > 0 ? "var(--status-high-text)" : "var(--text-secondary)" }}>
                              Backorder
                            </span>
                            <span style={{ fontSize: "0.9rem", fontWeight: 700, color: backorderedQty > 0 ? "var(--status-high-text)" : "var(--status-healthy-text)" }}>
                              {backorderedQty > 0 ? `${backorderedQty} units remaining` : "0 units remaining"}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Fulfillment Progress */}
                      <div
                        style={{
                          marginBottom: "1.5rem",
                          padding: "1.25rem",
                          background: "var(--bg-surface-elevated)",
                          borderRadius: "var(--radius-md)",
                          border: "1px solid var(--border-subtle)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                          <span style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-secondary)" }}>
                            Fulfillment Progress
                          </span>
                          <span style={{ fontSize: "1.1rem", fontWeight: 800, color: fulfillmentPercent === 100 ? "var(--status-healthy-text)" : "var(--primary)" }}>
                            {fulfillmentPercent}%
                          </span>
                        </div>
                        <div style={{ background: "#e2e8f0", borderRadius: "var(--radius-full)", height: "9px", overflow: "hidden", marginBottom: "0.5rem" }}>
                          <div
                            style={{
                              width: `${fulfillmentPercent}%`,
                              background: fulfillmentPercent === 100 ? "var(--status-healthy)" : "var(--primary)",
                              height: "100%",
                              borderRadius: "var(--radius-full)",
                              transition: "width 0.3s ease",
                            }}
                          />
                        </div>
                        <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", display: "flex", justifyContent: "space-between" }}>
                          <span>{totalAllocatedQty} of {totalPhysicalQty} physical units allocated</span>
                          <span>{fulfillmentPercent}% Completed</span>
                        </div>
                      </div>

                      {/* Activated Subscriptions & Entitlements Section */}
                      {((selectedOrder.subscriptions && selectedOrder.subscriptions.length > 0) ||
                        (selectedOrder.lines || []).some((l) => l.subscription_enabled)) && (
                        <div style={{ marginBottom: "1.5rem" }}>
                          <h4
                            style={{
                              fontSize: "0.95rem",
                              fontWeight: 700,
                              color: "var(--text-primary)",
                              marginBottom: "0.75rem",
                              textTransform: "uppercase",
                              letterSpacing: "0.03em",
                              display: "flex",
                              alignItems: "center",
                              gap: "0.4rem",
                            }}
                          >
                            <Sparkles size={16} color="var(--primary)" /> Activated Subscriptions & Entitlements
                          </h4>
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "0.85rem" }}>
                            {(selectedOrder.subscriptions && selectedOrder.subscriptions.length > 0
                              ? selectedOrder.subscriptions
                              : (selectedOrder.lines || []).filter((l) => l.subscription_enabled).map((l, i) => ({
                                  id: `line-${i}`,
                                  name: l.subscription_name || "Bundled Entitlement",
                                  status: selectedOrder.status === "CONFIRMED" || selectedOrder.status === "FULFILLED" ? "ACTIVE" : "PENDING_ACTIVATION",
                                  duration_mode: l.duration_mode || "TILL_VALIDITY",
                                  validity_value: l.validity_value || 1,
                                  validity_unit: l.validity_unit || "MONTHS",
                                  billing_frequency: l.billing_frequency || "NONE",
                                  start_date: selectedOrder.status === "CONFIRMED" ? selectedOrder.created_at : null,
                                  end_date: l.duration_mode === "LIFETIME" ? null : null,
                                }))
                            ).map((sub) => (
                              <div
                                key={sub.id}
                                style={{
                                  padding: "1rem",
                                  backgroundColor: "#F8FAFC",
                                  borderRadius: "8px",
                                  border: "1px solid #BFDBFE",
                                }}
                              >
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                                  <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--text-primary)" }}>{sub.name}</span>
                                  <span className={`badge ${sub.status === "ACTIVE" ? "badge-healthy" : "badge-medium"}`}>
                                    {sub.status}
                                  </span>
                                </div>
                                <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                                  <div>
                                    <strong>Duration:</strong> {sub.duration_mode === "LIFETIME" ? "Lifetime Access" : `${sub.validity_value || 1} ${sub.validity_unit || "MONTHS"}`}
                                  </div>
                                  <div>
                                    <strong>Billing Frequency:</strong> {sub.billing_frequency === "NONE" ? "Free / Included" : sub.billing_frequency}
                                  </div>
                                  <div>
                                    <strong>Start Date:</strong> {sub.start_date ? new Date(sub.start_date).toLocaleDateString() : "Upon Order Activation"}
                                  </div>
                                  <div>
                                    <strong>End Date:</strong> {sub.end_date ? new Date(sub.end_date).toLocaleDateString() : (sub.duration_mode === "LIFETIME" ? "Lifetime (No Expiration)" : "Calculated from activation")}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Last Updated */}
                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.75rem", display: "flex", justifyContent: "space-between" }}>
                        <span>Last updated: {lastUpdated}</span>
                        <span>Customer Account: <strong>{profile?.company_name || "Authorized Customer"}</strong></span>
                      </div>
                    </div>
                  );
                })()
              ) : (
                <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  Select an order from the list to view fulfillment details.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab: Billing */}
      {activeTab === "billing" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Active Subscriptions & Recurring Entitlements */}
          <div className="card">
            <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Sparkles size={18} color="var(--primary)" /> Active Subscriptions & Recurring Plans
              </div>
              <span className="badge badge-info">{portalSubscriptions.length} Plans</span>
            </div>

            {billingLoading ? (
              <div style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                Loading subscriptions and billing records...
              </div>
            ) : portalSubscriptions.length === 0 ? (
              <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-secondary)" }}>
                No active subscriptions yet. Subscriptions and service entitlements activate automatically upon quote acceptance.
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem" }}>
                {portalSubscriptions.map((sub) => (
                  <div
                    key={sub.id}
                    style={{
                      padding: "1.25rem",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--border-subtle)",
                      background: "var(--bg-surface)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.5rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <h4 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                          {sub.name || "Software Entitlement"}
                        </h4>
                        {sub.order_id && (
                          <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                            Order: ORD-{sub.order_id}
                          </div>
                        )}
                      </div>
                      <span className={`badge ${sub.status === "ACTIVE" ? "badge-healthy" : "badge-medium"}`}>
                        {sub.status}
                      </span>
                    </div>

                    <div style={{ fontSize: "0.84rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.25rem", marginTop: "0.25rem" }}>
                      <div>
                        <strong>Duration:</strong> {sub.duration_mode === "LIFETIME" ? "Lifetime Access" : `${sub.validity_value || 1} ${sub.validity_unit || "MONTHS"}`}
                      </div>
                      <div>
                        <strong>Billing Frequency:</strong> {sub.billing_frequency === "NONE" ? "Free / Included" : sub.billing_frequency}
                      </div>
                      <div>
                        <strong>Start Date:</strong> {sub.start_date ? new Date(sub.start_date).toLocaleDateString() : "Upon Finalization"}
                      </div>
                      <div>
                        <strong>End Date:</strong> {sub.end_date ? new Date(sub.end_date).toLocaleDateString() : (sub.duration_mode === "LIFETIME" ? "Lifetime (No Expiration)" : "Calculated from activation")}
                      </div>
                      {sub.next_billing_date && (
                        <div style={{ color: "var(--primary)", fontWeight: 600 }}>
                          <strong>Next Billing Date:</strong> {new Date(sub.next_billing_date).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Invoices & Commercial Statements */}
          <div className="card">
            <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Receipt size={18} color="var(--status-healthy)" /> Invoices & Billing Statements
              </div>
              <span className="badge badge-neutral">{portalInvoices.length} Invoices</span>
            </div>

            {billingLoading ? (
              <div style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                Loading invoices...
              </div>
            ) : portalInvoices.length === 0 ? (
              <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-secondary)" }}>
                No invoices issued yet.
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
                      <th>Due Date</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portalInvoices.map((inv) => {
                      const amt = inv.total_amount !== undefined ? inv.total_amount : inv.amount || 0;
                      return (
                        <tr key={inv.id}>
                          <td><strong>{inv.invoice_number}</strong></td>
                          <td>{inv.order_id ? `ORD-${inv.order_id}` : "N/A"}</td>
                          <td>
                            <span className={`badge ${inv.billing_type === "RECURRING" ? "badge-info" : "badge-neutral"}`}>
                              {inv.billing_type || "ONE_TIME"}
                            </span>
                          </td>
                          <td style={{ fontWeight: 700 }}>
                            ${Number(amt).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                            {inv.due_date ? new Date(inv.due_date).toLocaleDateString() : "30 Days"}
                          </td>
                          <td>
                            <span className={`badge ${inv.status === "PAID" ? "badge-healthy" : "badge-info"}`}>
                              {inv.status || "ISSUED"}
                            </span>
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
          <div className="modal-card" style={{ maxWidth: "480px" }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header" style={{ marginBottom: "1rem" }}>
              <h2 className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <MessageSquare size={20} color="var(--primary)" /> Request Quote Adjustment
              </h2>
            </div>

            {/* Quote details banner */}
            <div style={{ padding: "0.75rem 1rem", background: "var(--bg-surface-elevated)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", marginBottom: "1.25rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem", fontSize: "0.85rem" }}>
                <span style={{ color: "var(--text-secondary)" }}>Quote:</span>
                <strong style={{ color: "var(--text-primary)" }}>{selectedQuote?.quote_number}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                <span style={{ color: "var(--text-secondary)" }}>Quote Subtotal:</span>
                <strong>${Number(selectedQuote?.subtotal || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
              </div>
            </div>

            <form onSubmit={handleSubmitNegotiation}>
              <div className="form-group" style={{ marginBottom: "1rem" }}>
                <label className="form-label" style={{ fontWeight: 600, fontSize: "0.85rem" }}>Requested Adjustment</label>
                <select
                  className="form-select"
                  value={requestedChange}
                  onChange={(e) => setRequestedChange(e.target.value)}
                  style={{ width: "100%", padding: "0.5rem 0.75rem" }}
                >
                  <option value="overall_discount_percent">Overall Quote Discount (%)</option>
                </select>
              </div>

              {/* Current vs Maximum stats grid */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1.25rem" }}>
                <div style={{ padding: "0.6rem 0.75rem", background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.15rem" }}>Current Overall Discount</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    {selectedQuote?.current_overall_discount_percent !== undefined
                      ? `${selectedQuote.current_overall_discount_percent}%`
                      : (selectedQuote?.subtotal > 0 ? `${((selectedQuote.total_discount / selectedQuote.subtotal) * 100).toFixed(1)}%` : "0.0%")}
                  </div>
                </div>

                <div style={{ padding: "0.6rem 0.75rem", background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.15rem" }}>Maximum Available Discount</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--status-healthy)" }}>
                    {selectedQuote?.max_permissible_discount_percent !== undefined
                      ? `${selectedQuote.max_permissible_discount_percent}%`
                      : `${profile?.discount_ceiling || 10.0}%`}
                  </div>
                </div>
              </div>

              {/* Requested Input */}
              <div className="form-group" style={{ marginBottom: "1rem" }}>
                <label className="form-label" style={{ fontWeight: 600, fontSize: "0.85rem" }}>
                  Requested Overall Discount (%)
                </label>
                <div style={{ position: "relative" }}>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    className="form-input"
                    placeholder="e.g. 12"
                    value={proposedValue}
                    onChange={(e) => setProposedValue(e.target.value)}
                    required
                    style={{ width: "100%", paddingRight: "2rem" }}
                  />
                  <span style={{ position: "absolute", right: "0.75rem", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)", fontWeight: 600 }}>%</span>
                </div>
              </div>

              {/* Expected Total live preview */}
              {(() => {
                const num = parseFloat(proposedValue);
                if (!isNaN(num) && num >= 0 && num <= 100 && selectedQuote?.subtotal > 0) {
                  const discAmt = selectedQuote.subtotal * (num / 100.0);
                  const expTot = Math.max(0, selectedQuote.subtotal - discAmt);
                  return (
                    <div style={{ padding: "0.65rem 0.85rem", background: "rgba(16, 185, 129, 0.08)", border: "1px solid rgba(16, 185, 129, 0.3)", borderRadius: "var(--radius-sm)", marginBottom: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Expected Total Payable:</span>
                      <strong style={{ fontSize: "1.05rem", color: "var(--status-healthy)" }}>
                        ${expTot.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </strong>
                    </div>
                  );
                }
                return null;
              })()}

              {/* Small explanation */}
              <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", lineHeight: 1.45, marginBottom: "1.25rem" }}>
                Your requested discount will be evaluated across all products in this quotation according to product, category, customer and margin rules.
              </p>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsNegModalOpen(false)}
                  disabled={negLoading}
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
