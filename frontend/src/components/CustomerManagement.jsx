import React, { useState, useEffect } from "react";
import { api } from "../api";
import {
  Users,
  Plus,
  Search,
  Edit2,
  Building2,
  ShieldAlert,
} from "lucide-react";

export function CustomerManagement({ user, onNotify }) {
  const [customers, setCustomers] = useState([]);
  const [tierFilter, setTierFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [formData, setFormData] = useState({
    company_name: "",
    contact_name: "",
    email: "",
    phone: "",
    tier: "STANDARD",
    discount_ceiling: 10.0,
  });

  const canManage = user?.role === "ADMIN" || user?.role === "SALES_MANAGER";

  useEffect(() => {
    loadCustomers();
  }, [tierFilter]);

  async function loadCustomers() {
    setLoading(true);
    try {
      const params = {};
      if (tierFilter) params.tier = tierFilter;
      const data = await api.getCustomers(params);
      setCustomers(data);
    } catch (err) {
      onNotify("Error loading customers: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function handleOpenCreate() {
    setEditingCustomer(null);
    setFormData({
      company_name: "",
      contact_name: "",
      email: "",
      phone: "",
      tier: "STANDARD",
      discount_ceiling: 10.0,
    });
    setIsModalOpen(true);
  }

  function handleOpenEdit(cust) {
    setEditingCustomer(cust);
    setFormData({
      company_name: cust.company_name,
      contact_name: cust.contact_name,
      email: cust.email,
      phone: cust.phone || "",
      tier: cust.tier,
      discount_ceiling: cust.discount_ceiling,
    });
    setIsModalOpen(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        discount_ceiling: parseFloat(formData.discount_ceiling),
      };

      if (editingCustomer) {
        await api.updateCustomer(editingCustomer.id, payload);
        onNotify("Customer updated successfully!", "success");
      } else {
        await api.createCustomer(payload);
        onNotify("Customer created successfully!", "success");
      }
      setIsModalOpen(false);
      loadCustomers();
    } catch (err) {
      onNotify("Failed to save customer: " + err.message, "error");
    }
  }

  const filteredCustomers = customers.filter(
    (c) =>
      c.company_name.toLowerCase().includes(search.toLowerCase()) ||
      c.contact_name.toLowerCase().includes(search.toLowerCase()) ||
      c.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <Users color="var(--primary)" size={24} /> Customer Accounts & Tier Governance
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Configure client tiers, contact profiles, and contractual discount guardrails.
          </p>
        </div>
        {canManage && (
          <button className="btn btn-primary" onClick={handleOpenCreate}>
            <Plus size={16} /> Add Customer
          </button>
        )}
      </div>

      {/* Filter & Search */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "1rem" }}>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <select
            className="form-select"
            style={{ width: "180px" }}
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
          >
            <option value="">All Tiers</option>
            <option value="STANDARD">Standard</option>
            <option value="GROWTH">Growth</option>
            <option value="ENTERPRISE">Enterprise</option>
          </select>
        </div>

        <div style={{ position: "relative" }}>
          <Search size={16} color="var(--text-muted)" style={{ position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)" }} />
          <input
            type="text"
            className="form-input"
            style={{ paddingLeft: "2.2rem", width: "260px" }}
            placeholder="Search company or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Customers Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Company Name</th>
                <th>Contact</th>
                <th>Email</th>
                <th>Tier</th>
                <th>Discount Ceiling</th>
                <th>Created</th>
                {canManage && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>Loading customers...</td>
                </tr>
              ) : filteredCustomers.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>No customers found.</td>
                </tr>
              ) : (
                filteredCustomers.map((c) => (
                  <tr key={c.id}>
                    <td><strong style={{ color: "var(--text-primary)" }}>{c.company_name}</strong></td>
                    <td>{c.contact_name}</td>
                    <td><code>{c.email}</code></td>
                    <td>
                      <span className="badge badge-info">{c.tier}</span>
                    </td>
                    <td>
                      <span style={{ color: "var(--status-healthy)", fontWeight: 700 }}>
                        {c.discount_ceiling}%
                      </span>
                    </td>
                    <td style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                    {canManage && (
                      <td>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleOpenEdit(c)}
                        >
                          <Edit2 size={12} /> Edit
                        </button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add / Edit Customer Modal */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h2 className="card-title">
                <Building2 size={20} color="var(--primary)" />
                {editingCustomer ? "Edit Customer Account" : "Create Customer Account"}
              </h2>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Company Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.company_name}
                  onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                  required
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label className="form-label">Contact Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.contact_name}
                    onChange={(e) => setFormData({ ...formData, contact_name: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Email</label>
                  <input
                    type="email"
                    className="form-input"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label className="form-label">Phone</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Customer Tier</label>
                  <select
                    className="form-select"
                    value={formData.tier}
                    onChange={(e) => {
                      const newTier = e.target.value;
                      let ceiling = 10.0;
                      if (newTier === "GROWTH") ceiling = 20.0;
                      if (newTier === "ENTERPRISE") ceiling = 35.0;
                      setFormData({ ...formData, tier: newTier, discount_ceiling: ceiling });
                    }}
                  >
                    <option value="STANDARD">Standard</option>
                    <option value="GROWTH">Growth</option>
                    <option value="ENTERPRISE">Enterprise</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Discount Ceiling (%)</label>
                  <input
                    type="number"
                    step="0.5"
                    className="form-input"
                    value={formData.discount_ceiling}
                    onChange={(e) => setFormData({ ...formData, discount_ceiling: e.target.value })}
                    required
                  />
                </div>
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
                  {editingCustomer ? "Save Changes" : "Create Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
