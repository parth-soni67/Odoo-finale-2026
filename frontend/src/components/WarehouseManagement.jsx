import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  Warehouse as WarehouseIcon,
  Plus,
  RotateCcw,
  Edit2,
  CheckCircle2,
  XCircle,
  Clock,
  Boxes,
  MapPin,
  Search,
} from "lucide-react";

export function WarehouseManagement({ user, onNotify }) {
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState("create"); // "create" or "edit"
  const [selectedWh, setSelectedWh] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Form State
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [isActive, setIsActive] = useState(true);

  const canManage = ["ADMIN", "SALES_MANAGER"].includes(user?.role);

  useEffect(() => {
    loadWarehouses();
  }, []);

  async function loadWarehouses() {
    setLoading(true);
    try {
      const data = await api.getWarehouses();
      setWarehouses(data || []);
    } catch (err) {
      onNotify("Failed to load warehouses: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function handleOpenCreate() {
    setSelectedWh(null);
    setName("");
    setLocation("");
    setIsActive(true);
    setModalMode("create");
    setIsModalOpen(true);
  }

  function handleOpenEdit(wh) {
    setSelectedWh(wh);
    setName(wh.name);
    setLocation(wh.location);
    setIsActive(wh.is_active);
    setModalMode("edit");
    setIsModalOpen(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim() || !location.trim()) {
      onNotify("Please provide both warehouse name and location", "error");
      return;
    }

    setSubmitting(true);
    try {
      if (modalMode === "create") {
        await api.createWarehouse({
          name: name.trim(),
          location: location.trim(),
          is_active: isActive,
        });
        onNotify(`Warehouse "${name.trim()}" created successfully!`, "success");
      } else {
        await api.updateWarehouse(selectedWh.id, {
          name: name.trim(),
          location: location.trim(),
          is_active: isActive,
        });
        onNotify(`Warehouse "${name.trim()}" updated successfully!`, "success");
      }
      setIsModalOpen(false);
      await loadWarehouses();
    } catch (err) {
      onNotify(`Failed to ${modalMode} warehouse: ` + err.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleStatus(wh) {
    try {
      const newStatus = !wh.is_active;
      await api.updateWarehouse(wh.id, { is_active: newStatus });
      onNotify(`Warehouse "${wh.name}" marked as ${newStatus ? "ACTIVE" : "INACTIVE"}.`, "info");
      await loadWarehouses();
    } catch (err) {
      onNotify("Failed to toggle warehouse status: " + err.message, "error");
    }
  }

  const filteredWarehouses = warehouses.filter((wh) => {
    if (!search) return true;
    const term = search.toLowerCase();
    return (
      (wh.name || "").toLowerCase().includes(term) ||
      (wh.location || "").toLowerCase().includes(term)
    );
  });

  const totalStock = warehouses.reduce((sum, w) => sum + (w.available_stock || 0), 0);
  const activeCount = warehouses.filter((w) => w.is_active).length;

  return (
    <div>
      {/* Header */}
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
            Warehouse Management
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Configure fulfillment distribution centers, regional hubs, and operational inventory facilities.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button className="btn btn-secondary" onClick={loadWarehouses}>
            <RotateCcw size={14} /> Refresh
          </button>
          {canManage && (
            <button className="btn btn-primary" onClick={handleOpenCreate}>
              <Plus size={15} /> Add Warehouse
            </button>
          )}
        </div>
      </div>

      {/* KPI Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
        <div className="card" style={{ padding: "1.1rem" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
            Total Facilities
          </div>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--text-primary)", marginTop: "0.3rem" }}>
            {warehouses.length}
          </div>
        </div>
        <div className="card" style={{ padding: "1.1rem" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
            Active Warehouses
          </div>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--status-healthy-text)", marginTop: "0.3rem" }}>
            {activeCount}
          </div>
        </div>
        <div className="card" style={{ padding: "1.1rem" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
            Available Physical Units
          </div>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--primary)", marginTop: "0.3rem" }}>
            {totalStock.toLocaleString()}
          </div>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="card" style={{ padding: "0.85rem 1rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <Search size={16} color="var(--text-muted)" />
        <input
          type="text"
          className="form-control"
          placeholder="Search warehouses by name or location..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ border: "none", boxShadow: "none", padding: "0.2rem", fontSize: "0.9rem" }}
        />
      </div>

      {/* Warehouses Table */}
      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>
          <Clock size={32} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <div>Loading Warehouses...</div>
        </div>
      ) : filteredWarehouses.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "3.5rem 1.5rem" }}>
          <WarehouseIcon size={48} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <h3 style={{ fontSize: "1.25rem", fontWeight: 700, marginBottom: "0.4rem" }}>No Warehouses Found</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: "420px", margin: "0 auto 1.25rem" }}>
            {search ? "No warehouses matched your search query." : "No warehouse facilities configured yet."}
          </p>
          {canManage && !search && (
            <button className="btn btn-primary" onClick={handleOpenCreate}>
              <Plus size={15} /> Create First Warehouse
            </button>
          )}
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Warehouse</th>
                  <th>Location</th>
                  <th style={{ textAlign: "center", width: "120px" }}>Status</th>
                  <th style={{ textAlign: "right", width: "150px" }}>Available Stock</th>
                  {canManage && <th style={{ textAlign: "right", width: "180px" }}>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {filteredWarehouses.map((wh) => (
                  <tr key={wh.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                        <div
                          style={{
                            width: "32px",
                            height: "32px",
                            borderRadius: "var(--radius-sm)",
                            background: "var(--bg-surface-elevated)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "var(--primary)",
                          }}
                        >
                          <WarehouseIcon size={16} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>{wh.name}</div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>ID: #{wh.id}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", color: "var(--text-secondary)", fontSize: "0.88rem" }}>
                        <MapPin size={13} color="var(--text-muted)" />
                        {wh.location}
                      </div>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`badge ${wh.is_active ? "badge-healthy" : "badge-neutral"}`}>
                        {wh.is_active ? "ACTIVE" : "INACTIVE"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right", fontWeight: 700, fontSize: "0.95rem" }}>
                      <span style={{ color: (wh.available_stock || 0) > 0 ? "var(--text-primary)" : "var(--status-high-text)" }}>
                        {(wh.available_stock || 0).toLocaleString()} units
                      </span>
                    </td>
                    {canManage && (
                      <td style={{ textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: "0.4rem" }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleOpenEdit(wh)}
                            title="Edit Warehouse"
                          >
                            <Edit2 size={13} /> Edit
                          </button>
                          <button
                            className={`btn btn-sm ${wh.is_active ? "btn-secondary" : "btn-primary"}`}
                            onClick={() => handleToggleStatus(wh)}
                            title={wh.is_active ? "Deactivate Facility" : "Activate Facility"}
                          >
                            {wh.is_active ? "Deactivate" : "Activate"}
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal: Add / Edit Warehouse */}
      {isModalOpen && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                {modalMode === "create" ? "Add New Warehouse" : `Edit Warehouse #${selectedWh?.id}`}
              </h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsModalOpen(false)}>
                ✕
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Warehouse Name *</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. Mumbai Central Hub"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Location / City *</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. Mumbai, Maharashtra"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    required
                  />
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginTop: "0.25rem" }}>
                  <input
                    type="checkbox"
                    id="wh-active-check"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                    style={{ width: "16px", height: "16px" }}
                  />
                  <label htmlFor="wh-active-check" style={{ fontSize: "0.9rem", fontWeight: 600, cursor: "pointer" }}>
                    Warehouse Active (Available for Inventory Allocation)
                  </label>
                </div>
              </div>
              <div className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={submitting}
                  onClick={() => setIsModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Saving..." : modalMode === "create" ? "Create Warehouse" : "Update Warehouse"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
