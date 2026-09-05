import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  Warehouse as WarehouseIcon,
  Plus,
  RotateCcw,
  Edit2,
  Clock,
  Boxes,
  MapPin,
  Search,
  ArrowLeft,
  Tag,
  Package,
  Trash2,
} from "lucide-react";

export function WarehouseManagement({ user, onNotify, initialWarehouseId = null }) {
  // Warehouse List State
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  
  // Warehouse Detail State
  const [activeWarehouseId, setActiveWarehouseId] = useState(initialWarehouseId);
  const [warehouseDetail, setWarehouseDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [productSearch, setProductSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [stockStatusFilter, setStockStatusFilter] = useState("ALL");

  useEffect(() => {
    if (initialWarehouseId) {
      setActiveWarehouseId(initialWarehouseId);
    }
  }, [initialWarehouseId]);

  // All Products for dropdowns
  const [allProducts, setAllProducts] = useState([]);

  // Modals State
  const [isWhModalOpen, setIsWhModalOpen] = useState(false);
  const [whModalMode, setWhModalMode] = useState("create"); // "create" or "edit"
  const [selectedWh, setSelectedWh] = useState(null);

  const [isRestockModalOpen, setIsRestockModalOpen] = useState(false);
  const [restockProduct, setRestockProduct] = useState(null);
  const [restockQty, setRestockQty] = useState(10);
  const [restockReason, setRestockReason] = useState("Regular restock");

  const [isAddStockModalOpen, setIsAddStockModalOpen] = useState(false);
  const [addStockProdId, setAddStockProdId] = useState("");
  const [addStockQty, setAddStockQty] = useState(10);

  const [submitting, setSubmitting] = useState(false);

  // Warehouse Form State
  const [whName, setWhName] = useState("");
  const [whLocation, setWhLocation] = useState("");
  const [whIsActive, setWhIsActive] = useState(true);
  const [whInitialProdId, setWhInitialProdId] = useState("");
  const [whInitialQty, setWhInitialQty] = useState(0);

  const canManage = ["ADMIN", "SALES_MANAGER"].includes(user?.role);

  useEffect(() => {
    loadWarehouses();
    loadCatalog();
  }, []);

  useEffect(() => {
    if (activeWarehouseId) {
      loadWarehouseDetail(activeWarehouseId);
    } else {
      setWarehouseDetail(null);
    }
  }, [activeWarehouseId]);

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

  async function loadCatalog() {
    try {
      const [prods, cats] = await Promise.all([
        api.getProducts().catch(() => []),
        api.getCategories().catch(() => []),
      ]);
      setAllProducts(prods || []);
      setAllCategories(cats || []);
    } catch (err) {
      console.warn("Could not load products/categories catalog", err);
    }
  }

  async function loadWarehouseDetail(whId) {
    setLoadingDetail(true);
    try {
      const data = await api.getWarehouseInventorySummary(whId);
      setWarehouseDetail(data);
    } catch (err) {
      onNotify("Failed to load warehouse inventory: " + err.message, "error");
    } finally {
      setLoadingDetail(false);
    }
  }

  // Open Create Modal
  function handleOpenCreate() {
    setSelectedWh(null);
    setWhName("");
    setWhLocation("");
    setWhIsActive(true);
    setWhInitialProdId("");
    setWhInitialQty(0);
    setWhModalMode("create");
    setIsWhModalOpen(true);
  }

  // Open Edit Modal
  function handleOpenEdit(wh) {
    setSelectedWh(wh);
    setWhName(wh.name);
    setWhLocation(wh.location);
    setWhIsActive(wh.is_active);
    setWhInitialProdId("");
    setWhInitialQty(0);
    setWhModalMode("edit");
    setIsWhModalOpen(true);
  }

  // Submit Create / Edit Warehouse
  async function handleWhSubmit(e) {
    e.preventDefault();
    if (!whName.trim() || !whLocation.trim()) {
      onNotify("Please provide both warehouse name and location", "error");
      return;
    }

    setSubmitting(true);
    try {
      if (whModalMode === "create") {
        const newWh = await api.createWarehouse({
          name: whName.trim(),
          location: whLocation.trim(),
          is_active: whIsActive,
        });

        // Add initial stock if specified
        if (whInitialProdId && parseInt(whInitialQty, 10) > 0) {
          try {
            await api.addStock({
              warehouse_id: newWh.id,
              product_id: parseInt(whInitialProdId, 10),
              quantity: parseInt(whInitialQty, 10),
            });
          } catch (stkErr) {
            console.warn("Initial stock addition notice:", stkErr);
          }
        }

        onNotify(`Warehouse "${whName.trim()}" created successfully!`, "success");
      } else {
        await api.updateWarehouse(selectedWh.id, {
          name: whName.trim(),
          location: whLocation.trim(),
          is_active: whIsActive,
        });
        onNotify(`Warehouse "${whName.trim()}" updated successfully!`, "success");
      }
      setIsWhModalOpen(false);
      await loadWarehouses();
      if (activeWarehouseId) {
        await loadWarehouseDetail(activeWarehouseId);
      }
    } catch (err) {
      onNotify(`Failed to ${whModalMode} warehouse: ` + err.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  // Activate / Deactivate
  async function handleToggleStatus(wh) {
    try {
      if (wh.is_active) {
        await api.deactivateWarehouse(wh.id);
        onNotify(`Warehouse "${wh.name}" deactivated.`, "info");
      } else {
        await api.activateWarehouse(wh.id);
        onNotify(`Warehouse "${wh.name}" activated!`, "success");
      }
      await loadWarehouses();
      if (activeWarehouseId === wh.id) {
        await loadWarehouseDetail(wh.id);
      }
    } catch (err) {
      onNotify("Failed to toggle status: " + err.message, "error");
    }
  }

  // Open Restock Modal
  function handleOpenRestock(product) {
    setRestockProduct(product);
    setRestockQty(10);
    setRestockReason("Inventory restock");
    setIsRestockModalOpen(true);
  }

  // Submit Restock
  async function handleRestockSubmit(e) {
    e.preventDefault();
    const qty = parseInt(restockQty, 10);
    if (!qty || qty <= 0) {
      onNotify("Restock quantity must be greater than zero", "error");
      return;
    }
    const whId = activeWarehouseId || selectedWh?.id;
    if (!whId || !restockProduct) {
      onNotify("Missing warehouse or product target", "error");
      return;
    }

    setSubmitting(true);
    try {
      await api.restockWarehouseProduct(whId, {
        product_id: restockProduct.product_id,
        quantity: qty,
        reason: restockReason || "Inventory restock",
      });
      onNotify(
        `Successfully added ${qty} units of ${restockProduct.product_name}!`,
        "success"
      );
      setIsRestockModalOpen(false);
      await loadWarehouseDetail(whId);
      await loadWarehouses();
    } catch (err) {
      onNotify("Restock failed: " + err.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  // Open Add Stock Modal
  function handleOpenAddStock() {
    if (allProducts.length > 0) {
      setAddStockProdId(allProducts[0].id);
    }
    setAddStockQty(10);
    setIsAddStockModalOpen(true);
  }

  // Submit Add Stock
  async function handleAddStockSubmit(e) {
    e.preventDefault();
    const qty = parseInt(addStockQty, 10);
    if (!qty || qty <= 0) {
      onNotify("Quantity must be greater than zero", "error");
      return;
    }
    const whId = activeWarehouseId;
    if (!whId || !addStockProdId) {
      onNotify("Please select a product", "error");
      return;
    }

    setSubmitting(true);
    try {
      await api.addStock({
        warehouse_id: whId,
        product_id: parseInt(addStockProdId, 10),
        quantity: qty,
      });
      onNotify(`Added ${qty} units to warehouse inventory!`, "success");
      setIsAddStockModalOpen(false);
      await loadWarehouseDetail(whId);
      await loadWarehouses();
    } catch (err) {
      onNotify("Failed to add stock: " + err.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  // Safe Delete Warehouse
  async function handleDeleteWarehouse(wh) {
    if (!window.confirm(`Are you sure you want to delete warehouse "${wh.name}"? This action cannot be undone.`)) {
      return;
    }
    try {
      await api.deleteWarehouse(wh.id);
      onNotify(`Warehouse "${wh.name}" deleted successfully.`, "info");
      if (activeWarehouseId === wh.id) {
        setActiveWarehouseId(null);
      }
      await loadWarehouses();
    } catch (err) {
      onNotify("Cannot delete warehouse: " + err.message, "error");
    }
  }

  // =========================================================================
  // VIEW: WAREHOUSE DETAIL VIEW (/warehouses/:id)
  // =========================================================================
  if (activeWarehouseId) {
    const wh = warehouseDetail || warehouses.find((w) => w.id === activeWarehouseId);
    const categories = warehouseDetail?.categories || [];

    // Filter categories and products
    const filteredCategories = categories.map((cat) => {
      const filteredProds = (cat.products || []).filter((p) => {
        // Product name or SKU search
        if (productSearch) {
          const term = productSearch.toLowerCase();
          const matchName = (p.product_name || "").toLowerCase().includes(term);
          const matchSku = (p.sku || "").toLowerCase().includes(term);
          if (!matchName && !matchSku) return false;
        }
        // Category filter
        if (categoryFilter !== "ALL" && cat.category_name !== categoryFilter) {
          return false;
        }
        // Stock status filter
        if (stockStatusFilter === "LOW_STOCK" && (p.quantity_available > 5 || p.quantity_available === 0)) {
          return false;
        }
        if (stockStatusFilter === "OUT_OF_STOCK" && p.quantity_available > 0) {
          return false;
        }
        if (stockStatusFilter === "IN_STOCK" && p.quantity_available === 0) {
          return false;
        }
        return true;
      });

      // Recalculate filtered category total
      const categoryFilteredTotal = filteredProds.reduce(
        (sum, p) => sum + (p.quantity_available || 0),
        0
      );

      return {
        ...cat,
        products: filteredProds,
        filtered_total: categoryFilteredTotal,
      };
    }).filter((cat) => {
      if (categoryFilter !== "ALL" && cat.category_name !== categoryFilter) return false;
      return cat.products.length > 0 || !productSearch;
    });

    // Compute metrics
    const totalProductsCount = categories.reduce((sum, c) => sum + (c.products?.length || 0), 0);
    const lowStockCount = categories.reduce(
      (sum, c) =>
        sum +
        (c.products?.filter(
          (p) => p.quantity_available > 0 && p.quantity_available <= 5
        ).length || 0),
      0
    );
    const outOfStockCount = categories.reduce(
      (sum, c) => sum + (c.products?.filter((p) => p.quantity_available === 0).length || 0),
      0
    );
    const totalWarehouseUnits = warehouseDetail?.total_units || 0;

    return (
      <div>
        {/* Navigation Breadcrumb & Back */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.25rem" }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setActiveWarehouseId(null)}
            style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}
          >
            <ArrowLeft size={14} /> Back to Warehouses
          </button>
          <span style={{ color: "var(--border-prominent)" }}>/</span>
          <span style={{ fontWeight: 600, color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            {wh?.warehouse_name || wh?.name || `Warehouse #${activeWarehouseId}`}
          </span>
        </div>

        {/* WAREHOUSE HEADER */}
        <div
          className="card"
          style={{
            padding: "1.5rem",
            marginBottom: "1.5rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "1rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "var(--radius-md)",
                background: "var(--primary-light)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--primary)",
              }}
            >
              <WarehouseIcon size={24} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <h1 style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
                  {wh?.warehouse_name || wh?.name || "Warehouse"}
                </h1>
                <span
                  className={`badge ${
                    (wh?.status || (wh?.is_active ? "ACTIVE" : "INACTIVE")) === "ACTIVE"
                      ? "badge-healthy"
                      : "badge-neutral"
                  }`}
                >
                  {wh?.status || (wh?.is_active ? "ACTIVE" : "INACTIVE")}
                </span>
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  color: "var(--text-secondary)",
                  fontSize: "0.9rem",
                  marginTop: "0.25rem",
                }}
              >
                <MapPin size={14} color="var(--text-muted)" />
                {wh?.location || "Unknown Location"}
                <span style={{ color: "var(--border-prominent)", margin: "0 0.3rem" }}>•</span>
                <span>ID: #{activeWarehouseId}</span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => loadWarehouseDetail(activeWarehouseId)}
              disabled={loadingDetail}
            >
              <RotateCcw size={13} /> Refresh
            </button>
            {canManage && (
              <>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleOpenEdit(wh)}
                >
                  <Edit2 size={13} /> Edit
                </button>
                <button
                  className={`btn btn-sm ${wh?.is_active ? "btn-secondary" : "btn-primary"}`}
                  onClick={() => handleToggleStatus(wh)}
                >
                  {wh?.is_active ? "Deactivate" : "Activate"}
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleOpenAddStock}
                  disabled={!wh?.is_active}
                  title={!wh?.is_active ? "Warehouse is inactive" : "+ Add Stock to Warehouse"}
                >
                  <Plus size={14} /> Add Stock
                </button>
              </>
            )}
          </div>
        </div>

        {/* SUMMARY KPI CARDS */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
            gap: "1rem",
            marginBottom: "1.5rem",
          }}
        >
          <div className="card" style={{ padding: "1.2rem" }}>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
              Total Units
            </div>
            <div style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--primary)", marginTop: "0.3rem" }}>
              {totalWarehouseUnits.toLocaleString()}
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
              Available physical stock
            </div>
          </div>

          <div className="card" style={{ padding: "1.2rem" }}>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
              Total Products
            </div>
            <div style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--text-primary)", marginTop: "0.3rem" }}>
              {totalProductsCount}
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
              Active SKU inventory lines
            </div>
          </div>

          <div className="card" style={{ padding: "1.2rem" }}>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
              Categories
            </div>
            <div style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--text-primary)", marginTop: "0.3rem" }}>
              {categories.length}
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
              Catalog product groupings
            </div>
          </div>

          <div className="card" style={{ padding: "1.2rem" }}>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
              Low Stock Items
            </div>
            <div
              style={{
                fontSize: "1.85rem",
                fontWeight: 800,
                color: lowStockCount > 0 ? "var(--status-medium-text)" : "var(--status-healthy-text)",
                marginTop: "0.3rem",
              }}
            >
              {lowStockCount}
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
              ≤ 5 units threshold ({outOfStockCount} out of stock)
            </div>
          </div>
        </div>

        {/* SEARCH & FILTERS BAR */}
        <div
          className="card"
          style={{
            padding: "0.85rem 1.15rem",
            marginBottom: "1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "0.75rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flex: 1, minWidth: "220px" }}>
            <Search size={16} color="var(--text-muted)" />
            <input
              type="text"
              className="form-control"
              placeholder="Search product by name or SKU..."
              value={productSearch}
              onChange={(e) => setProductSearch(e.target.value)}
              style={{ border: "none", boxShadow: "none", padding: "0.2rem", fontSize: "0.9rem" }}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
            {/* Category Filter */}
            <select
              className="form-control"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              style={{ fontSize: "0.85rem", padding: "0.35rem 0.6rem", minWidth: "140px" }}
            >
              <option value="ALL">All Categories</option>
              {categories.map((c) => (
                <option key={c.category_id} value={c.category_name}>
                  {c.category_name}
                </option>
              ))}
            </select>

            {/* Status Filter */}
            <select
              className="form-control"
              value={stockStatusFilter}
              onChange={(e) => setStockStatusFilter(e.target.value)}
              style={{ fontSize: "0.85rem", padding: "0.35rem 0.6rem", minWidth: "130px" }}
            >
              <option value="ALL">All Stock Statuses</option>
              <option value="IN_STOCK">In Stock (&gt;0)</option>
              <option value="LOW_STOCK">Low Stock (≤5)</option>
              <option value="OUT_OF_STOCK">Out of Stock (0)</option>
            </select>
          </div>
        </div>

        {/* INVENTORY BY CATEGORY */}
        {loadingDetail ? (
          <div className="card" style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>
            <Clock size={32} color="var(--primary)" style={{ marginBottom: "1rem" }} />
            <div>Calculating real-time warehouse inventory...</div>
          </div>
        ) : filteredCategories.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: "3.5rem 1.5rem" }}>
            <Boxes size={44} color="var(--primary)" style={{ marginBottom: "0.75rem" }} />
            <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "0.4rem" }}>
              No Inventory Items Match Filter
            </h3>
            <p style={{ color: "var(--text-secondary)", maxWidth: "420px", margin: "0 auto 1.25rem" }}>
              {productSearch || categoryFilter !== "ALL" || stockStatusFilter !== "ALL"
                ? "Try clearing your search or filters to view all products."
                : "This warehouse currently has no inventory recorded."}
            </p>
            {canManage && (
              <button className="btn btn-primary" onClick={handleOpenAddStock} disabled={!wh?.is_active}>
                <Plus size={15} /> Add Initial Stock
              </button>
            )}
          </div>
        ) : (
          <div>
            {filteredCategories.map((cat) => {
              const categoryTotal = cat.total_units || 0;
              const isServiceCategory =
                cat.category_name.toLowerCase().includes("service") ||
                cat.category_name.toLowerCase().includes("support");

              return (
                <div key={cat.category_id} className="category-card">
                  {/* Category Header */}
                  <div className="category-header">
                    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                      <Tag size={16} color="var(--primary)" />
                      <span style={{ fontWeight: 700, fontSize: "1rem", color: "var(--text-primary)" }}>
                        {cat.category_name}
                      </span>
                      <span className="badge badge-neutral" style={{ fontSize: "0.72rem" }}>
                        {cat.products.length} {cat.products.length === 1 ? "Product" : "Products"}
                      </span>
                    </div>
                    <div style={{ fontSize: "0.88rem", fontWeight: 700, color: "var(--text-secondary)" }}>
                      Subtotal: <span style={{ color: "var(--primary)" }}>{categoryTotal.toLocaleString()} units</span>
                    </div>
                  </div>

                  {/* Products Table */}
                  {cat.products.length === 0 ? (
                    <div style={{ padding: "1.5rem", textAlign: "center", color: "var(--text-muted)", fontSize: "0.9rem" }}>
                      {isServiceCategory
                        ? "Services — No physical stock required (entitlements handled via subscriptions)"
                        : "No products in this category currently stocked"}
                    </div>
                  ) : (
                    <div className="table-container">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Product</th>
                            <th>SKU</th>
                            <th style={{ width: "110px" }}>Type</th>
                            <th style={{ textAlign: "right", width: "120px" }}>Available</th>
                            <th style={{ textAlign: "right", width: "110px" }}>Reserved</th>
                            <th style={{ textAlign: "center", width: "130px" }}>Status</th>
                            {canManage && <th style={{ textAlign: "right", width: "120px" }}>Actions</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {cat.products.map((prod) => {
                            const isLow = prod.quantity_available > 0 && prod.quantity_available <= 5;
                            const isOut = prod.quantity_available === 0;
                            const statusLabel = isOut ? "OUT OF STOCK" : isLow ? "LOW STOCK" : "IN STOCK";
                            const statusBadgeClass = isOut
                              ? "badge-high"
                              : isLow
                              ? "badge-medium"
                              : "badge-healthy";

                            return (
                              <tr key={prod.product_id}>
                                <td>
                                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                    <Package size={16} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                                    <div>
                                      <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                                        {prod.product_name}
                                      </span>
                                      {!prod.is_active && (
                                        <span
                                          className="badge badge-neutral"
                                          style={{ marginLeft: "0.4rem", fontSize: "0.68rem" }}
                                        >
                                          Archived
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </td>
                                <td>
                                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                                    {prod.sku}
                                  </span>
                                </td>
                                <td>
                                  <span
                                    className={`badge ${
                                      prod.product_type === "PHYSICAL"
                                        ? "badge-info"
                                        : prod.product_type === "DIGITAL"
                                        ? "badge-neutral"
                                        : "badge-neutral"
                                    }`}
                                    style={{ fontSize: "0.72rem" }}
                                  >
                                    {prod.product_type}
                                  </span>
                                </td>
                                <td style={{ textAlign: "right", fontWeight: 700, fontSize: "0.95rem" }}>
                                  <span style={{ color: isOut ? "var(--status-high-text)" : "var(--text-primary)" }}>
                                    {prod.quantity_available.toLocaleString()}
                                  </span>
                                </td>
                                <td style={{ textAlign: "right", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                                  {prod.quantity_reserved || 0}
                                </td>
                                <td style={{ textAlign: "center" }}>
                                  <span className={`badge ${statusBadgeClass}`}>
                                    {statusLabel}
                                  </span>
                                </td>
                                {canManage && (
                                  <td style={{ textAlign: "right" }}>
                                    <button
                                      className="btn btn-secondary btn-sm"
                                      onClick={() => handleOpenRestock(prod, activeWarehouseId)}
                                      disabled={!wh?.is_active}
                                      title={!wh?.is_active ? "Warehouse inactive" : "Restock Inventory"}
                                      style={{ padding: "0.25rem 0.55rem" }}
                                    >
                                      <RotateCcw size={12} /> Restock
                                    </button>
                                  </td>
                                )}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Category Total Footer */}
                  <div className="category-footer-total">
                    <span>
                      {cat.category_name} Total:{" "}
                      <span style={{ color: "var(--primary)", marginLeft: "0.3rem" }}>
                        {categoryTotal.toLocaleString()} units
                      </span>
                    </span>
                  </div>
                </div>
              );
            })}

            {/* Warehouse Total Footer Bar */}
            <div className="warehouse-grand-total">
              <div>
                <div style={{ fontSize: "0.8rem", textTransform: "uppercase", fontWeight: 700, color: "var(--text-secondary)" }}>
                  Facility Stock Summary
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
                  Aggregated from live inventory records across {categories.length} product categories
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "0.8rem", textTransform: "uppercase", fontWeight: 700, color: "var(--primary)" }}>
                  TOTAL AVAILABLE
                </div>
                <div style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--primary)" }}>
                  {totalWarehouseUnits.toLocaleString()} units
                </div>
              </div>
            </div>
          </div>
        )}

        {/* RESTOCK MODAL */}
        {isRestockModalOpen && restockProduct && (
          <div className="modal-backdrop">
            <div className="modal" style={{ maxWidth: "460px" }}>
              <div className="modal-header">
                <h3 style={{ fontSize: "1.15rem", fontWeight: 700 }}>Restock Inventory</h3>
                <button className="btn btn-secondary btn-sm" onClick={() => setIsRestockModalOpen(false)}>
                  ✕
                </button>
              </div>
              <form onSubmit={handleRestockSubmit}>
                <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div style={{ padding: "0.75rem", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                      Warehouse
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--text-primary)" }}>
                      {wh?.warehouse_name || wh?.name} ({wh?.location})
                    </div>
                  </div>

                  <div style={{ padding: "0.75rem", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                      Product Details
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--text-primary)" }}>
                      {restockProduct.product_name}
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
                      SKU: {restockProduct.sku} • Current Stock:{" "}
                      <strong>{restockProduct.quantity_available} units</strong>
                    </div>
                  </div>

                  <div>
                    <label className="form-label" style={{ fontWeight: 600 }}>Quantity to Add *</label>
                    <input
                      type="number"
                      min="1"
                      className="form-control"
                      value={restockQty}
                      onChange={(e) => setRestockQty(e.target.value)}
                      required
                      autoFocus
                    />
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>
                      New Stock will be:{" "}
                      <strong style={{ color: "var(--primary)" }}>
                        {restockProduct.quantity_available + (parseInt(restockQty, 10) || 0)} units
                      </strong>
                    </div>
                  </div>

                  <div>
                    <label className="form-label" style={{ fontWeight: 600 }}>Reason / Audit Reference</label>
                    <input
                      type="text"
                      className="form-control"
                      value={restockReason}
                      onChange={(e) => setRestockReason(e.target.value)}
                      placeholder="e.g. Purchase order PO-2026-081"
                    />
                  </div>
                </div>

                <div className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={submitting}
                    onClick={() => setIsRestockModalOpen(false)}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={submitting}>
                    {submitting ? "Restocking..." : "Restock"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ADD STOCK MODAL */}
        {isAddStockModalOpen && (
          <div className="modal-backdrop">
            <div className="modal" style={{ maxWidth: "480px" }}>
              <div className="modal-header">
                <h3 style={{ fontSize: "1.15rem", fontWeight: 700 }}>+ Add Stock to {wh?.warehouse_name || wh?.name}</h3>
                <button className="btn btn-secondary btn-sm" onClick={() => setIsAddStockModalOpen(false)}>
                  ✕
                </button>
              </div>
              <form onSubmit={handleAddStockSubmit}>
                <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                    <label className="form-label" style={{ fontWeight: 600 }}>Select Product *</label>
                    <select
                      className="form-control"
                      value={addStockProdId}
                      onChange={(e) => setAddStockProdId(e.target.value)}
                      required
                    >
                      {allProducts.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.sku}) — {p.category?.name || "Uncategorized"}
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
                      value={addStockQty}
                      onChange={(e) => setAddStockQty(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={submitting}
                    onClick={() => setIsAddStockModalOpen(false)}
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

        {/* MODAL: ADD / EDIT WAREHOUSE */}
        {isWhModalOpen && (
          <div className="modal-backdrop">
            <div className="modal" style={{ maxWidth: "480px" }}>
              <div className="modal-header">
                <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                  {whModalMode === "create" ? "Add New Warehouse" : `Edit Warehouse #${selectedWh?.id}`}
                </h3>
                <button className="btn btn-secondary btn-sm" onClick={() => setIsWhModalOpen(false)}>
                  ✕
                </button>
              </div>
              <form onSubmit={handleWhSubmit}>
                <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                    <label className="form-label" style={{ fontWeight: 600 }}>Warehouse Name *</label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="e.g. Mumbai Central Warehouse"
                      value={whName}
                      onChange={(e) => setWhName(e.target.value)}
                      required
                      autoFocus
                    />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontWeight: 600 }}>Location / City *</label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="e.g. Mumbai, India"
                      value={whLocation}
                      onChange={(e) => setWhLocation(e.target.value)}
                      required
                    />
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginTop: "0.25rem" }}>
                    <input
                      type="checkbox"
                      id="wh-active-check"
                      checked={whIsActive}
                      onChange={(e) => setWhIsActive(e.target.checked)}
                      style={{ width: "16px", height: "16px" }}
                    />
                    <label htmlFor="wh-active-check" style={{ fontSize: "0.9rem", fontWeight: 600, cursor: "pointer" }}>
                      Active Status (Available for Fulfillment Allocation)
                    </label>
                  </div>
                </div>
                <div className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={submitting}
                    onClick={() => setIsWhModalOpen(false)}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={submitting}>
                    {submitting ? "Saving..." : whModalMode === "create" ? "Create Warehouse" : "Update Warehouse"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    );
  }

  // =========================================================================
  // VIEW: WAREHOUSES LIST
  // =========================================================================
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
              <Plus size={15} /> + Create Warehouse
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
                  <th style={{ textAlign: "center", width: "110px" }}>Status</th>
                  <th style={{ textAlign: "right", width: "140px" }}>Total Units</th>
                  {canManage && <th style={{ textAlign: "right", width: "230px" }}>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {filteredWarehouses.map((wh) => (
                  <tr
                    key={wh.id}
                    style={{ cursor: "pointer" }}
                    onClick={() => setActiveWarehouseId(wh.id)}
                  >
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
                      <td style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: "inline-flex", gap: "0.4rem" }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => setActiveWarehouseId(wh.id)}
                            title="View Detailed Inventory"
                          >
                            View
                          </button>
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
                          {user?.role === "ADMIN" && (
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleDeleteWarehouse(wh)}
                              title="Delete Facility"
                            >
                              <Trash2 size={13} color="var(--status-high)" />
                            </button>
                          )}
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
      {isWhModalOpen && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                {whModalMode === "create" ? "Create Warehouse" : `Edit Warehouse #${selectedWh?.id}`}
              </h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsWhModalOpen(false)}>
                ✕
              </button>
            </div>
            <form onSubmit={handleWhSubmit}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Warehouse Name *</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. Mumbai Central Warehouse"
                    value={whName}
                    onChange={(e) => setWhName(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Location / City *</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. Mumbai, India"
                    value={whLocation}
                    onChange={(e) => setWhLocation(e.target.value)}
                    required
                  />
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginTop: "0.25rem" }}>
                  <input
                    type="checkbox"
                    id="wh-active-check"
                    checked={whIsActive}
                    onChange={(e) => setWhIsActive(e.target.checked)}
                    style={{ width: "16px", height: "16px" }}
                  />
                  <label htmlFor="wh-active-check" style={{ fontSize: "0.9rem", fontWeight: 600, cursor: "pointer" }}>
                    Warehouse Active (Available for Inventory Allocation)
                  </label>
                </div>

                {whModalMode === "create" && allProducts.length > 0 && (
                  <div style={{ marginTop: "0.5rem", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.75rem" }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.5rem", color: "var(--text-primary)" }}>
                      Initial Stock (Optional)
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 100px", gap: "0.5rem" }}>
                      <select
                        className="form-control"
                        value={whInitialProdId}
                        onChange={(e) => setWhInitialProdId(e.target.value)}
                      >
                        <option value="">No initial stock</option>
                        {allProducts.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name} ({p.sku})
                          </option>
                        ))}
                      </select>
                      <input
                        type="number"
                        min="0"
                        placeholder="Qty"
                        className="form-control"
                        value={whInitialQty}
                        onChange={(e) => setWhInitialQty(e.target.value)}
                        disabled={!whInitialProdId}
                      />
                    </div>
                  </div>
                )}
              </div>
              <div className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={submitting}
                  onClick={() => setIsWhModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Saving..." : whModalMode === "create" ? "Create Warehouse" : "Update Warehouse"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
