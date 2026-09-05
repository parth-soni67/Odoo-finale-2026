import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  Boxes,
  Plus,
  RotateCcw,
  Clock,
  Search,
  Warehouse as WarehouseIcon,
  Package,
  Layers,
  ArrowUpRight,
  Filter,
} from "lucide-react";

export function InventoryManagement({ user, onNotify }) {
  const [inventory, setInventory] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [selectedWhId, setSelectedWhId] = useState("");
  const [selectedCatId, setSelectedCatId] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  // Modals
  const [isAddStockOpen, setIsAddStockOpen] = useState(false);
  const [isRestockOpen, setIsRestockOpen] = useState(false);
  const [selectedInvForRestock, setSelectedInvForRestock] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Add Stock Form
  const [addWhId, setAddWhId] = useState("");
  const [addProdId, setAddProdId] = useState("");
  const [addQty, setAddQty] = useState(10);
  const [addReason, setAddReason] = useState("Initial Stock");

  // Restock Form
  const [restockQty, setRestockQty] = useState(10);
  const [restockReason, setRestockReason] = useState("Restock");

  const canManage = ["ADMIN", "SALES_MANAGER"].includes(user?.role);

  useEffect(() => {
    loadAllData();
  }, []);

  async function loadAllData() {
    setLoading(true);
    try {
      const [invData, whData, prodData, catData] = await Promise.all([
        api.getInventory(),
        api.getWarehouses(),
        api.getProducts(),
        api.getCategories(),
      ]);
      setInventory(invData || []);
      setWarehouses(whData || []);
      setProducts(prodData || []);
      setCategories(catData || []);
      if (whData && whData.length > 0 && !addWhId) {
        setAddWhId(whData[0].id);
      }
      if (prodData && prodData.length > 0 && !addProdId) {
        setAddProdId(prodData[0].id);
      }
    } catch (err) {
      onNotify("Failed to load inventory data: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function refreshInventory() {
    try {
      const invData = await api.getInventory({
        warehouse_id: selectedWhId || undefined,
        category_id: selectedCatId || undefined,
      });
      setInventory(invData || []);
    } catch (err) {
      onNotify("Failed to refresh inventory: " + err.message, "error");
    }
  }

  function handleOpenAddStock() {
    if (warehouses.length > 0) setAddWhId(warehouses[0].id);
    if (products.length > 0) setAddProdId(products[0].id);
    setAddQty(10);
    setAddReason("Initial Stock");
    setIsAddStockOpen(true);
  }

  function handleOpenRestock(invItem) {
    setSelectedInvForRestock(invItem);
    setRestockQty(10);
    setRestockReason("Restock");
    setIsRestockOpen(true);
  }

  async function handleAddStockSubmit(e) {
    e.preventDefault();
    if (!addWhId || !addProdId || !addQty || addQty <= 0) {
      onNotify("Please provide a valid warehouse, product, and positive quantity", "error");
      return;
    }

    setSubmitting(true);
    try {
      await api.addInventoryStock({
        warehouse_id: parseInt(addWhId, 10),
        product_id: parseInt(addProdId, 10),
        quantity: parseInt(addQty, 10),
        reason: addReason.trim() || "Initial Stock",
      });
      onNotify(`Added ${addQty} units of stock successfully!`, "success");
      setIsAddStockOpen(false);
      await loadAllData();
    } catch (err) {
      onNotify("Failed to add stock: " + err.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRestockSubmit(e) {
    e.preventDefault();
    if (!selectedInvForRestock || !restockQty || restockQty <= 0) {
      onNotify("Please provide a positive restock quantity", "error");
      return;
    }

    setSubmitting(true);
    try {
      await api.restockInventory(selectedInvForRestock.id, {
        quantity: parseInt(restockQty, 10),
        reason: restockReason.trim() || "Restock",
      });
      onNotify(`Restocked ${restockQty} units successfully!`, "success");
      setIsRestockOpen(false);
      await loadAllData();
    } catch (err) {
      onNotify("Failed to restock inventory: " + err.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  // Filter logic
  const filteredInventory = inventory.filter((item) => {
    if (selectedWhId && String(item.warehouse_id) !== String(selectedWhId)) return false;
    if (selectedStatus && (item.stock_status || "").toUpperCase() !== selectedStatus.toUpperCase()) return false;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const matchName = (item.product_name || "").toLowerCase().includes(term);
      const matchSku = (item.product_sku || "").toLowerCase().includes(term);
      const matchWh = (item.warehouse_name || "").toLowerCase().includes(term);
      if (!matchName && !matchSku && !matchWh) return false;
    }
    return true;
  });

  function getStatusBadgeClass(status) {
    switch ((status || "").toUpperCase()) {
      case "IN STOCK":
        return "badge-healthy";
      case "LOW STOCK":
        return "badge-medium";
      case "OUT OF STOCK":
        return "badge-high";
      case "DIGITAL":
        return "badge-info";
      case "SERVICE":
        return "badge-neutral";
      default:
        return "badge-neutral";
    }
  }

  const totalOnHand = inventory.reduce((sum, item) => sum + (item.quantity_on_hand || 0), 0);
  const totalAvailable = inventory.reduce((sum, item) => sum + (item.quantity_available || 0), 0);
  const totalAllocated = inventory.reduce((sum, item) => sum + (item.quantity_allocated || 0), 0);

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
            Inventory Management
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Track real-time multi-warehouse stock balances, available levels, allocated reserves, and restocking operations.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button className="btn btn-secondary" onClick={loadAllData}>
            <RotateCcw size={14} /> Refresh
          </button>
          {canManage && (
            <button className="btn btn-primary" onClick={handleOpenAddStock}>
              <Plus size={15} /> Add Stock
            </button>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
        <div className="card" style={{ padding: "1.1rem" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
            Total On Hand
          </div>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--text-primary)", marginTop: "0.3rem" }}>
            {totalOnHand.toLocaleString()}
          </div>
        </div>
        <div className="card" style={{ padding: "1.1rem" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
            Available for Sale
          </div>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--status-healthy-text)", marginTop: "0.3rem" }}>
            {totalAvailable.toLocaleString()}
          </div>
        </div>
        <div className="card" style={{ padding: "1.1rem" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
            Allocated Reserves
          </div>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--primary)", marginTop: "0.3rem" }}>
            {totalAllocated.toLocaleString()}
          </div>
        </div>
        <div className="card" style={{ padding: "1.1rem" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
            Active SKUs
          </div>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--text-secondary)", marginTop: "0.3rem" }}>
            {products.length}
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div
        className="card"
        style={{
          padding: "1rem",
          marginBottom: "1.25rem",
          display: "flex",
          gap: "0.85rem",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <div style={{ flex: "1 1 200px", minWidth: "180px", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Search size={16} color="var(--text-muted)" />
          <input
            type="text"
            className="form-control"
            placeholder="Search product, SKU, or warehouse..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ padding: "0.35rem 0.5rem", fontSize: "0.88rem" }}
          />
        </div>

        <div style={{ minWidth: "160px" }}>
          <select
            className="form-control"
            value={selectedWhId}
            onChange={(e) => setSelectedWhId(e.target.value)}
            style={{ padding: "0.35rem 0.5rem", fontSize: "0.88rem" }}
          >
            <option value="">All Warehouses</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </div>

        <div style={{ minWidth: "150px" }}>
          <select
            className="form-control"
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            style={{ padding: "0.35rem 0.5rem", fontSize: "0.88rem" }}
          >
            <option value="">All Statuses</option>
            <option value="IN STOCK">In Stock</option>
            <option value="LOW STOCK">Low Stock (&lt; 10)</option>
            <option value="OUT OF STOCK">Out of Stock</option>
            <option value="DIGITAL">Digital</option>
            <option value="SERVICE">Service</option>
          </select>
        </div>

        {(selectedWhId || selectedStatus || searchTerm) && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setSelectedWhId("");
              setSelectedStatus("");
              setSearchTerm("");
            }}
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Inventory Table */}
      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>
          <Clock size={32} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <div>Loading Inventory...</div>
        </div>
      ) : filteredInventory.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "3.5rem 1.5rem" }}>
          <Boxes size={48} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <h3 style={{ fontSize: "1.25rem", fontWeight: 700, marginBottom: "0.4rem" }}>No Inventory Records Found</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: "420px", margin: "0 auto 1.25rem" }}>
            {searchTerm || selectedWhId || selectedStatus
              ? "No inventory matches your active filter criteria."
              : "No stock records have been added yet."}
          </p>
          {canManage && (
            <button className="btn btn-primary" onClick={handleOpenAddStock}>
              <Plus size={15} /> Add Initial Stock
            </button>
          )}
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Warehouse</th>
                  <th style={{ textAlign: "center", width: "110px" }}>Fulfillment</th>
                  <th style={{ textAlign: "right", width: "100px" }}>On Hand</th>
                  <th style={{ textAlign: "right", width: "100px" }}>Available</th>
                  <th style={{ textAlign: "right", width: "100px" }}>Allocated</th>
                  <th style={{ textAlign: "center", width: "130px" }}>Status</th>
                  {canManage && <th style={{ textAlign: "right", width: "120px" }}>Action</th>}
                </tr>
              </thead>
              <tbody>
                {filteredInventory.map((item) => {
                  const isDigitalOrService =
                    (item.fulfillment_type || "").toUpperCase() === "DIGITAL" ||
                    (item.fulfillment_type || "").toUpperCase() === "SERVICE";

                  return (
                    <tr key={item.id}>
                      <td>
                        <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>{item.product_name}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          Category: {item.category_name}
                        </div>
                      </td>
                      <td style={{ fontFamily: "monospace", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                        {item.product_sku || "N/A"}
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.88rem" }}>
                          <WarehouseIcon size={14} color="var(--primary)" />
                          <span style={{ fontWeight: 600 }}>{item.warehouse_name}</span>
                        </div>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <span className="badge badge-neutral" style={{ fontSize: "0.72rem" }}>
                          {item.fulfillment_type || "PHYSICAL"}
                        </span>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 600 }}>
                        {isDigitalOrService ? "N/A" : (item.quantity_on_hand || 0).toLocaleString()}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 700 }}>
                        {isDigitalOrService ? "N/A" : (item.quantity_available || 0).toLocaleString()}
                      </td>
                      <td style={{ textAlign: "right", color: "var(--text-muted)" }}>
                        {isDigitalOrService ? "N/A" : (item.quantity_allocated || 0).toLocaleString()}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <span className={`badge ${getStatusBadgeClass(item.stock_status)}`}>
                          {item.stock_status}
                        </span>
                      </td>
                      {canManage && (
                        <td style={{ textAlign: "right" }}>
                          {!isDigitalOrService ? (
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleOpenRestock(item)}
                              title="Restock this SKU in this warehouse"
                            >
                              <ArrowUpRight size={13} /> Restock
                            </button>
                          ) : (
                            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Digital</span>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal: Add Stock */}
      {isAddStockOpen && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>Add Stock to Warehouse</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsAddStockOpen(false)}>
                ✕
              </button>
            </div>
            <form onSubmit={handleAddStockSubmit}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Warehouse *</label>
                  <select
                    className="form-control"
                    value={addWhId}
                    onChange={(e) => setAddWhId(e.target.value)}
                    required
                  >
                    {warehouses.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name} ({w.location})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Product *</label>
                  <select
                    className="form-control"
                    value={addProdId}
                    onChange={(e) => setAddProdId(e.target.value)}
                    required
                  >
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.sku}) — {p.fulfillment_type || "PHYSICAL"}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Quantity to Add *</label>
                  <input
                    type="number"
                    min="1"
                    className="form-control"
                    value={addQty}
                    onChange={(e) => setAddQty(parseInt(e.target.value, 10) || "")}
                    required
                  />
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                    Will be added to On Hand and Available quantities without overwriting previous stock.
                  </div>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Reason / Note</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. Initial Stock, Supplier Batch #8472"
                    value={addReason}
                    onChange={(e) => setAddReason(e.target.value)}
                  />
                </div>
              </div>
              <div className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={submitting}
                  onClick={() => setIsAddStockOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Adding..." : "Add Stock"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Restock Existing Inventory */}
      {isRestockOpen && selectedInvForRestock && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                Restock Inventory
              </h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsRestockOpen(false)}>
                ✕
              </button>
            </div>
            <form onSubmit={handleRestockSubmit}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div style={{ padding: "0.85rem", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                    {selectedInvForRestock.product_name} ({selectedInvForRestock.product_sku})
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    Warehouse: <strong>{selectedInvForRestock.warehouse_name}</strong>
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    Current Available: <strong style={{ color: "var(--primary)" }}>{selectedInvForRestock.quantity_available} units</strong>
                  </div>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Restock Quantity *</label>
                  <input
                    type="number"
                    min="1"
                    className="form-control"
                    value={restockQty}
                    onChange={(e) => setRestockQty(parseInt(e.target.value, 10) || "")}
                    required
                    autoFocus
                  />
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                    New Available will become: {((selectedInvForRestock.quantity_available || 0) + (parseInt(restockQty, 10) || 0))} units.
                  </div>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Restock Reason / PO #</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. Restock PO-9921, Factory Inbound"
                    value={restockReason}
                    onChange={(e) => setRestockReason(e.target.value)}
                  />
                </div>
              </div>
              <div className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={submitting}
                  onClick={() => setIsRestockOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Restocking..." : "Confirm Restock"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
