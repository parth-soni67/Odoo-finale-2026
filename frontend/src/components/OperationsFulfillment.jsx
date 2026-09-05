import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  Package,
  RotateCcw,
  Truck,
  CheckCircle2,
  Clock,
  Warehouse as WarehouseIcon,
  Layers,
  ArrowRight,
  Sparkles,
} from "lucide-react";

export function OperationsFulfillment({ onNotify }) {
  const [orders, setOrders] = useState([]);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [suggestion, setSuggestion] = useState(null);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);

  async function handleGetSuggestion(orderId) {
    setSuggestLoading(true);
    try {
      const res = await api.getFulfillmentSuggestion(orderId);
      setSuggestion(res);
      onNotify("Inventory suggestion generated from available warehouses", "info");
    } catch (err) {
      onNotify("Failed to get suggestions: " + err.message, "error");
    } finally {
      setSuggestLoading(false);
    }
  }

  async function handleConfirmFulfillment(orderId) {
    if (!suggestion || !suggestion.splits || suggestion.splits.length === 0) {
      onNotify("No splits available to confirm", "warning");
      return;
    }
    setConfirmLoading(true);
    try {
      await api.confirmFulfillment(orderId, {
        splits: suggestion.splits.map((s) => ({
          order_line_id: s.order_line_id,
          warehouse_id: s.warehouse_id,
          quantity: s.quantity,
        })),
      });
      onNotify("Warehouse allocations confirmed successfully!", "success");
      setSuggestion(null);
      await loadOrders();
      await loadOrderDetail(orderId);
    } catch (err) {
      onNotify("Failed to confirm fulfillment: " + err.message, "error");
    } finally {
      setConfirmLoading(false);
    }
  }

  async function handleActivateOrder(orderId) {
    setActionLoading(true);
    try {
      await api.activateOrder(orderId);
      onNotify("Order activated and subscriptions initialized successfully!", "success");
      await loadOrders();
      await loadOrderDetail(orderId);
    } catch (err) {
      onNotify("Failed to activate order: " + err.message, "error");
    } finally {
      setActionLoading(false);
    }
  }

  useEffect(() => {
    loadOrders();
  }, []);

  async function loadOrders() {
    setLoading(true);
    try {
      const data = await api.getOrders();
      setOrders(data || []);
      if (data && data.length > 0) {
        loadOrderDetail(data[0].id);
      }
    } catch (err) {
      onNotify("Failed to load operations orders: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function loadOrderDetail(id) {
    setSuggestion(null);
    try {
      const ord = await api.getOrder(id);
      setSelectedOrder(ord);
    } catch {
      const found = orders.find((o) => o.id === id);
      if (found) setSelectedOrder(found);
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
            Warehouse & Order Fulfillment
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Manage warehouse inventory allocations, split shipments, and backorders for confirmed deals.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={loadOrders}>
          <RotateCcw size={14} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>
          <Clock size={32} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <div>Loading Orders...</div>
        </div>
      ) : orders.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "3.5rem 1.5rem" }}>
          <Package size={48} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <h3 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "0.5rem" }}>No Orders to Fulfill</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: "460px", margin: "0 auto" }}>
            Orders confirmed from accepted quotations will populate here for inventory split allocation.
          </p>
        </div>
      ) : (
        <div className="two-column-layout">
          {/* Order List */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <Package size={18} /> Active Orders ({orders.length})
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {orders.map((ord) => {
                const isSelected = selectedOrder?.id === ord.id;
                return (
                  <div
                    key={ord.id}
                    onClick={() => loadOrderDetail(ord.id)}
                    style={{
                      padding: "1rem",
                      borderRadius: "var(--radius-md)",
                      background: isSelected ? "var(--bg-surface-elevated)" : "var(--bg-surface)",
                      border: isSelected ? "1px solid var(--primary)" : "1px solid var(--border-subtle)",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                      <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>Order #{ord.order_number}</span>
                      <span className="badge badge-info">{ord.status}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                      <span>{(ord.lines || []).length} lines</span>
                      <span style={{ fontWeight: 700 }}>${(ord.total_amount || 0).toFixed(2)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Fulfillment Details */}
          {selectedOrder ? (
            <div className="card">
              <div className="card-header" style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: "1rem", marginBottom: "1.25rem" }}>
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                    Fulfillment Execution
                  </div>
                  <h2 style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                    Order #{selectedOrder.order_number}
                    <span className="badge badge-info">{selectedOrder.status}</span>
                    {selectedOrder.status === "PENDING" && (
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={actionLoading}
                        onClick={() => handleActivateOrder(selectedOrder.id)}
                        style={{ marginLeft: "auto" }}
                      >
                        <CheckCircle2 size={13} /> {actionLoading ? "Activating..." : "Activate Order & Entitlements"}
                      </button>
                    )}
                  </h2>
                </div>
              </div>

              {/* Items & Splits */}
              <div style={{ marginBottom: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                  <h4 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0 }}>Ordered Items & Warehouse Splits</h4>
                  {(selectedOrder.lines || []).some((l) => (!l.fulfillment_type || l.fulfillment_type === "PHYSICAL") && (!l.fulfillment_splits || l.fulfillment_splits.length === 0)) && (
                    <button
                      className="btn btn-secondary btn-sm"
                      disabled={suggestLoading}
                      onClick={() => handleGetSuggestion(selectedOrder.id)}
                    >
                      <Layers size={13} /> {suggestLoading ? "Analyzing Inventory..." : "Suggest Warehouse Splits"}
                    </button>
                  )}
                </div>

                {(selectedOrder.lines || []).map((line) => {
                  const isPhysical = !line.fulfillment_type || line.fulfillment_type === "PHYSICAL";
                  const isDigital = line.fulfillment_type === "DIGITAL";
                  const isService = line.fulfillment_type === "SERVICE";

                  return (
                    <div
                      key={line.id}
                      style={{
                        padding: "0.85rem",
                        background: "var(--bg-surface-elevated)",
                        borderRadius: "var(--radius-md)",
                        marginBottom: "0.75rem",
                        border: "1px solid var(--border-subtle)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <strong>{line.product_name || `Product #${line.product_id}`}</strong>
                            {line.product_sku && (
                              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                ({line.product_sku})
                              </span>
                            )}
                            {isDigital && (
                              <span style={{ fontSize: "0.7rem", fontWeight: 700, padding: "0.15rem 0.45rem", borderRadius: "999px", background: "#F5F3FF", color: "#7C3AED", border: "1px solid #DDD6FE" }}>
                                DIGITAL LICENSE
                              </span>
                            )}
                            {isService && (
                              <span style={{ fontSize: "0.7rem", fontWeight: 700, padding: "0.15rem 0.45rem", borderRadius: "999px", background: "#ECFDF5", color: "#059669", border: "1px solid #A7F3D0" }}>
                                SERVICE ENTITLEMENT
                              </span>
                            )}
                            {isPhysical && (
                              <span style={{ fontSize: "0.7rem", fontWeight: 700, padding: "0.15rem 0.45rem", borderRadius: "999px", background: "#EFF6FF", color: "#2563EB", border: "1px solid #BFDBFE" }}>
                                PHYSICAL HARDWARE
                              </span>
                            )}
                          </div>

                          {line.subscription_enabled && (() => {
                            const sub = (selectedOrder.subscriptions || []).find((s) => s.product_id === line.product_id || s.name === line.subscription_name);
                            const isLifetime = line.duration_mode === "LIFETIME";
                            const startDateStr = sub?.start_date ? new Date(sub.start_date).toLocaleDateString() : (selectedOrder.status === "CONFIRMED" ? new Date(selectedOrder.created_at).toLocaleDateString() : "Pending Activation");
                            const endDateStr = isLifetime ? "Never" : (sub?.end_date ? new Date(sub.end_date).toLocaleDateString() : `${line.validity_value || 1} ${line.validity_unit || "MONTHS"} after activation`);
                            const billingStr = isLifetime || line.billing_frequency === "NONE" ? "Included" : (line.billing_frequency || "Monthly");

                            return (
                              <div style={{ marginTop: "0.45rem", padding: "0.5rem 0.75rem", background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: "6px" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.78rem", fontWeight: 700, color: "#1D4ED8", marginBottom: "0.25rem" }}>
                                  <Sparkles size={12} /> Subscription: {line.subscription_name || "Subscription Plan"}
                                </div>
                                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "0.35rem", fontSize: "0.74rem", color: "var(--text-secondary)" }}>
                                  <div><strong>Validity:</strong> {isLifetime ? "Lifetime" : `${line.validity_value || 1} ${line.validity_unit || "MONTHS"}`}</div>
                                  <div><strong>Status:</strong> <span className={`badge ${sub?.status === "ACTIVE" || selectedOrder.status === "CONFIRMED" ? "badge-healthy" : "badge-neutral"}`} style={{ fontSize: "0.68rem" }}>{sub?.status || (selectedOrder.status === "CONFIRMED" ? "ACTIVE" : "PENDING")}</span></div>
                                  <div><strong>Billing:</strong> {billingStr}</div>
                                  <div><strong>Start Date:</strong> {startDateStr}</div>
                                  <div><strong>End Date:</strong> {endDateStr}</div>
                                </div>
                              </div>
                            );
                          })()}
                        </div>
                        <span className="badge badge-neutral">Qty: {line.quantity}</span>
                      </div>

                      {/* Fulfillment Status / Splits */}
                      {!isPhysical ? (
                        <div style={{ fontSize: "0.8rem", color: "var(--status-healthy)", display: "flex", alignItems: "center", gap: "0.3rem", marginTop: "0.4rem" }}>
                          <CheckCircle2 size={13} />
                          Electronic delivery / license entitlement — no physical warehouse allocation required.
                        </div>
                      ) : line.fulfillment_splits && line.fulfillment_splits.length > 0 ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", marginTop: "0.5rem" }}>
                          {line.fulfillment_splits.map((sp) => (
                            <div
                              key={sp.id}
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                fontSize: "0.8rem",
                                padding: "0.35rem 0.6rem",
                                background: "var(--bg-surface)",
                                borderRadius: "var(--radius-xs)",
                                border: "1px solid var(--border-subtle)",
                              }}
                            >
                              <span>
                                <WarehouseIcon size={12} style={{ marginRight: "0.35rem", verticalAlign: "middle" }} />
                                {sp.warehouse_name || `Warehouse #${sp.warehouse_id}`}
                              </span>
                              <span>
                                <strong>{sp.quantity_allocated} units</strong> • <span className="badge badge-info" style={{ fontSize: "0.7rem" }}>{sp.status}</span>
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.3rem" }}>
                          Pending warehouse allocation.
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Suggestion Preview & Confirmation */}
                {suggestion && (
                  <div style={{ marginTop: "1rem", padding: "1rem", backgroundColor: "#F0FDF4", border: "1px solid #86EFAC", borderRadius: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                      <strong style={{ fontSize: "0.9rem", color: "#166534", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <WarehouseIcon size={15} /> Suggested Warehouse Allocation
                      </strong>
                      <span className="badge badge-healthy">
                        {suggestion.is_complete ? "Complete Stock Available" : "Partial / Backorder Required"}
                      </span>
                    </div>

                    {suggestion.splits && suggestion.splits.length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginBottom: "0.75rem" }}>
                        {suggestion.splits.map((s, idx) => (
                          <div key={idx} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", background: "#FFFFFF", padding: "0.5rem 0.75rem", borderRadius: "6px", border: "1px solid #DCFCE7" }}>
                            <span>Warehouse #{s.warehouse_id} (Line #{s.order_line_id})</span>
                            <strong>Allocate: {s.quantity} units</strong>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ fontSize: "0.85rem", color: "#B91C1C", marginBottom: "0.75rem" }}>
                        No warehouse has available stock for the requested physical quantities.
                      </div>
                    )}

                    {suggestion.backorders && suggestion.backorders.length > 0 && (
                      <div style={{ fontSize: "0.8rem", color: "#B45309", marginBottom: "0.75rem" }}>
                        Backorder: {suggestion.backorders.map((b) => `${b.quantity_backordered} units of Product #${b.product_id}`).join(", ")}
                      </div>
                    )}

                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => setSuggestion(null)}>
                        Cancel
                      </button>
                      {suggestion.splits && suggestion.splits.length > 0 && (
                        <button
                          className="btn btn-primary btn-sm"
                          disabled={confirmLoading}
                          onClick={() => handleConfirmFulfillment(selectedOrder.id)}
                        >
                          <CheckCircle2 size={13} /> {confirmLoading ? "Confirming..." : "Confirm Allocation"}
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Activated Subscriptions Card */}
              {((selectedOrder.subscriptions && selectedOrder.subscriptions.length > 0) ||
                (selectedOrder.lines || []).some((l) => l.subscription_enabled)) && (
                <div style={{ marginBottom: "1.5rem" }}>
                  <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.6rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <Sparkles size={16} color="var(--primary)" /> Activated Subscriptions & Entitlements
                  </h4>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "0.85rem" }}>
                    {(selectedOrder.subscriptions && selectedOrder.subscriptions.length > 0
                      ? selectedOrder.subscriptions
                      : (selectedOrder.lines || []).filter((l) => l.subscription_enabled).map((l, i) => ({
                          id: `sub-line-${i}`,
                          name: l.subscription_name || "Bundled Service",
                          status: selectedOrder.status === "CONFIRMED" || selectedOrder.status === "FULFILLED" ? "ACTIVE" : "PENDING_ACTIVATION",
                          duration_mode: l.duration_mode || "TILL_VALIDITY",
                          validity_value: l.validity_value || 1,
                          validity_unit: l.validity_unit || "MONTHS",
                          billing_frequency: l.billing_frequency || "NONE",
                          start_date: selectedOrder.status === "CONFIRMED" ? selectedOrder.created_at : null,
                          end_date: null,
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
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                          <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>{sub.name}</strong>
                          <span className={`badge ${sub.status === "ACTIVE" ? "badge-healthy" : "badge-medium"}`}>
                            {sub.status}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                          <div>Duration: <strong>{sub.duration_mode === "LIFETIME" ? "Lifetime Access" : `${sub.validity_value || 1} ${sub.validity_unit || "MONTHS"}`}</strong></div>
                          <div>Billing: <strong>{sub.billing_frequency === "NONE" ? "Free / Included" : sub.billing_frequency}</strong></div>
                          <div>Start Date: <strong>{sub.start_date ? new Date(sub.start_date).toLocaleDateString() : "Upon Order Activation"}</strong></div>
                          <div>End Date: <strong>{sub.end_date ? new Date(sub.end_date).toLocaleDateString() : (sub.duration_mode === "LIFETIME" ? "Lifetime (No Expiry)" : "Calculated on activation")}</strong></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
              Select an order to view fulfillment allocations.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
