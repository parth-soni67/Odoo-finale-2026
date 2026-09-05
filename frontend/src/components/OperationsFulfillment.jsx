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
  const [actionLoading, setActionLoading] = useState(false);

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
                <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.6rem" }}>Ordered Items & Warehouse Splits</h4>
                {(selectedOrder.lines || []).map((line) => (
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
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                      <div>
                        <strong>{line.product_name || `Product #${line.product_id}`}</strong>
                        {line.product_sku && (
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "0.5rem" }}>
                            ({line.product_sku})
                          </span>
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
                              <Sparkles size={11} /> Entitlement: {line.subscription_name} (
                              {line.duration_mode === "LIFETIME" ? "Lifetime" : `${line.validity_value || 1} ${line.validity_unit || "MONTHS"}`}
                              )
                            </span>
                          </div>
                        )}
                      </div>
                      <span className="badge badge-neutral">Qty: {line.quantity}</span>
                    </div>

                    {line.fulfillment_splits && line.fulfillment_splits.length > 0 ? (
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
                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        No inventory splits allocated yet.
                      </div>
                    )}
                  </div>
                ))}
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
