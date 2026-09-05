import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  Package,
  Plus,
  Search,
  Edit2,
  Trash2,
  Check,
  X,
  Tag,
} from "lucide-react";

export function ProductManagement({ user, onNotify }) {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [loading, setLoading] = useState(true);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    sku: "",
    category_id: "",
    unit_price: "",
    cost_price: "",
    allowed_discount_percent: 15.0,
    description: "",
    is_active: true,
  });

  const canManage = user?.role === "ADMIN" || user?.role === "SALES_MANAGER";

  useEffect(() => {
    loadData();
  }, [selectedCategory]);

  async function loadData() {
    setLoading(true);
    try {
      const params = {};
      if (selectedCategory) params.category_id = selectedCategory;
      const [prods, cats] = await Promise.all([
        api.getProducts(params),
        api.getCategories().catch(() => []),
      ]);
      setProducts(prods);
      setCategories(cats);
    } catch (err) {
      onNotify("Error loading products: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function handleOpenCreate() {
    setEditingProduct(null);
    setFormData({
      name: "",
      sku: "",
      category_id: categories[0]?.id || "",
      unit_price: "",
      cost_price: "",
      allowed_discount_percent: 15.0,
      description: "",
      is_active: true,
    });
    setIsModalOpen(true);
  }

  function handleOpenEdit(prod) {
    setEditingProduct(prod);
    setFormData({
      name: prod.name,
      sku: prod.sku,
      category_id: prod.category_id || "",
      unit_price: prod.unit_price,
      cost_price: prod.cost_price,
      allowed_discount_percent: prod.allowed_discount_percent,
      description: prod.description || "",
      is_active: prod.is_active,
    });
    setIsModalOpen(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        category_id: formData.category_id ? parseInt(formData.category_id) : null,
        unit_price: parseFloat(formData.unit_price),
        cost_price: parseFloat(formData.cost_price),
        allowed_discount_percent: parseFloat(formData.allowed_discount_percent),
      };

      if (editingProduct) {
        await api.updateProduct(editingProduct.id, payload);
        onNotify("Product updated successfully!", "success");
      } else {
        await api.createProduct(payload);
        onNotify("Product created successfully!", "success");
      }
      setIsModalOpen(false);
      loadData();
    } catch (err) {
      onNotify("Failed to save product: " + err.message, "error");
    }
  }

  async function handleToggleActive(prod) {
    try {
      await api.updateProduct(prod.id, { is_active: !prod.is_active });
      onNotify(`Product ${!prod.is_active ? "activated" : "deactivated"}`, "info");
      loadData();
    } catch (err) {
      onNotify("Error: " + err.message, "error");
    }
  }

  const filteredProducts = products.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.sku.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <Package color="var(--primary)" size={24} /> Product Catalog Management
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Configure price floors, discount ceilings, and multi-category hardware & license offerings.
          </p>
        </div>
        {canManage && (
          <button className="btn btn-primary" onClick={handleOpenCreate}>
            <Plus size={16} /> Add Product
          </button>
        )}
      </div>

      {/* Filter & Search Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "1rem" }}>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <select
            className="form-select"
            style={{ width: "200px" }}
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
          >
            <option value="">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div style={{ position: "relative" }}>
          <Search size={16} color="var(--text-muted)" style={{ position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)" }} />
          <input
            type="text"
            className="form-input"
            style={{ paddingLeft: "2.2rem", width: "260px" }}
            placeholder="Search by name or SKU..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Products Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Product Name</th>
                <th>SKU</th>
                <th>Category</th>
                <th>Unit Price</th>
                <th>Cost Price</th>
                <th>Max Discount</th>
                <th>Status</th>
                {canManage && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>Loading products...</td>
                </tr>
              ) : filteredProducts.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>No products found.</td>
                </tr>
              ) : (
                filteredProducts.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong style={{ color: "var(--text-primary)" }}>{p.name}</strong>
                      {p.description && (
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", maxWidth: "280px" }}>
                          {p.description}
                        </div>
                      )}
                    </td>
                    <td><code>{p.sku}</code></td>
                    <td>
                      <span className="badge badge-neutral">
                        {p.category?.name || "Uncategorized"}
                      </span>
                    </td>
                    <td><strong>${p.unit_price.toFixed(2)}</strong></td>
                    <td style={{ color: "var(--text-secondary)" }}>${p.cost_price.toFixed(2)}</td>
                    <td>
                      <span style={{ color: "var(--status-healthy)", fontWeight: 600 }}>
                        {p.allowed_discount_percent}%
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${p.is_active ? "badge-healthy" : "badge-high"}`}>
                        {p.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    {canManage && (
                      <td>
                        <div style={{ display: "flex", gap: "0.4rem" }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleOpenEdit(p)}
                          >
                            <Edit2 size={12} />
                          </button>
                          <button
                            className={`btn ${p.is_active ? "btn-danger" : "btn-success"} btn-sm`}
                            onClick={() => handleToggleActive(p)}
                            title={p.is_active ? "Deactivate" : "Activate"}
                          >
                            {p.is_active ? <X size={12} /> : <Check size={12} />}
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add / Edit Product Modal */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h2 className="card-title">
                <Package size={20} color="var(--primary)" />
                {editingProduct ? "Edit Product" : "Create New Product"}
              </h2>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Product Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label className="form-label">SKU</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.sku}
                    onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                    required
                    disabled={!!editingProduct}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Category</label>
                  <select
                    className="form-select"
                    value={formData.category_id}
                    onChange={(e) => setFormData({ ...formData, category_id: e.target.value })}
                  >
                    <option value="">Select Category</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label className="form-label">Unit Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    className="form-input"
                    value={formData.unit_price}
                    onChange={(e) => setFormData({ ...formData, unit_price: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Cost Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    className="form-input"
                    value={formData.cost_price}
                    onChange={(e) => setFormData({ ...formData, cost_price: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Max Discount (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    className="form-input"
                    value={formData.allowed_discount_percent}
                    onChange={(e) => setFormData({ ...formData, allowed_discount_percent: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingProduct ? "Save Changes" : "Create Product"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
