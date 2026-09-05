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
} from "lucide-react";

export function OperationsFulfillment({ onNotify }) {
  const [orders, setOrders] = useState([]);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

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
                  <h2 style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    Order #{selectedOrder.order_number}
                    <span className="badge badge-info">{selectedOrder.status}</span>
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
