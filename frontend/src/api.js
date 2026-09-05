const API_BASE = "/api";

export function getStoredToken() {
  return localStorage.getItem("dealflow_token");
}

export function setStoredToken(token) {
  if (token) {
    localStorage.setItem("dealflow_token", token);
  } else {
    localStorage.removeItem("dealflow_token");
  }
}

async function request(path, options = {}) {
  const token = getStoredToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    let errorMsg = `HTTP ${res.status}: ${res.statusText}`;
    if (data?.error?.message) {
      errorMsg = data.error.message;
    } else if (typeof data?.detail === "string") {
      errorMsg = data.detail;
    } else if (data?.detail?.message) {
      errorMsg = data.detail.message;
    } else if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
      errorMsg = data.detail[0].msg;
    }
    throw new Error(errorMsg);
  }

  return data;
}

export const api = {
  // Auth
  async login(email, password) {
    const res = await request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setStoredToken(res.access_token);
    return res;
  },

  async signup(fullName, email, password) {
    return request("/auth/signup", {
      method: "POST",
      body: JSON.stringify({
        full_name: fullName,
        email: email,
        password: password,
      }),
    });
  },

  async getMe() {
    return request("/auth/me");
  },

  logout() {
    setStoredToken(null);
  },

  // Products
  async getProducts(params = {}) {
    const query = new URLSearchParams(params).toString();
    return request(`/products${query ? `?${query}` : ""}`);
  },

  async getCategories() {
    return request("/products/categories");
  },

  async createProduct(payload) {
    return request("/products", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateProduct(id, payload) {
    return request(`/products/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  async deleteProduct(id) {
    return request(`/products/${id}`, {
      method: "DELETE",
    });
  },

  // Customers
  async getCustomers(params = {}) {
    const query = new URLSearchParams(params).toString();
    return request(`/customers${query ? `?${query}` : ""}`);
  },

  async createCustomer(payload) {
    return request("/customers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateCustomer(id, payload) {
    return request(`/customers/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  // Customer Portal
  async getPortalProfile() {
    return request("/portal/profile");
  },

  async getPortalQuotes() {
    return request("/portal/quotes");
  },

  async getPortalQuoteDetail(id) {
    return request(`/portal/quotes/${id}`);
  },

  async submitNegotiation(quoteId, payload) {
    return request(`/portal/quotes/${quoteId}/negotiate`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async confirmQuote(quoteId) {
    return request(`/portal/quotes/${quoteId}/confirm`, {
      method: "POST",
    });
  },

  async getPortalOrders() {
    return request("/portal/orders");
  },

  async getPortalOrderDetail(id) {
    return request(`/portal/orders/${id}`);
  },

  async getOrders() {
    return request("/orders");
  },

  async getOrder(id) {
    return request(`/orders/${id}`);
  },

  async activateOrder(id) {
    return request(`/orders/${id}/activate`, {
      method: "POST",
    });
  },

  async getOrderSubscriptions(id) {
    return request(`/orders/${id}/subscriptions`);
  },

  async expireSubscription(subscriptionId) {
    return request(`/orders/subscriptions/${subscriptionId}/expire`, {
      method: "POST",
    });
  },

  async getPortalInvoices() {
    return request("/portal/invoices");
  },

  async getPortalSubscriptions() {
    return request("/portal/subscriptions");
  },

  // Deal Health
  async getDealHealth() {
    return request("/deal-health");
  },

  async getQuoteDealHealth(id) {
    return request(`/deal-health/${id}`);
  },

  // Negotiations (Internal)
  async getNegotiations(status = null) {
    const query = status ? `?status=${status}` : "";
    return request(`/negotiations${query}`);
  },

  async approveNegotiation(id, comments = null) {
    return request(`/negotiations/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ comments }),
    });
  },

  async rejectNegotiation(id, comments = null) {
    return request(`/negotiations/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ comments }),
    });
  },

  // Reports
  async getSalesSummary() {
    return request("/reports/sales-summary");
  },

  // Quotations & Approvals
  async getQuotes(params = {}) {
    const query = new URLSearchParams(params).toString();
    return request(`/quotes${query ? `?${query}` : ""}`);
  },

  async getQuote(id) {
    return request(`/quotes/${id}`);
  },

  async createQuote(payload) {
    return request("/quotes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateQuote(id, payload) {
    return request(`/quotes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async evaluateQuoteRisk(id) {
    return request(`/quotes/${id}/risk`, {
      method: "POST",
    });
  },

  async getQuoteRecommendations(id) {
    return request(`/quotes/${id}/recommendations`);
  },

  async getQuoteApprovals(id) {
    return request(`/quotes/${id}/approvals`);
  },

  async approveQuote(id, comments = null) {
    return request(`/quotes/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ comments }),
    });
  },

  async rejectQuote(id, comments = null) {
    return request(`/quotes/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ comments }),
    });
  },

  // Warehouses
  async getWarehouses() {
    return request("/warehouses");
  },

  async getWarehouse(id) {
    return request(`/warehouses/${id}`);
  },

  async createWarehouse(payload) {
    return request("/warehouses", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateWarehouse(id, payload) {
    return request(`/warehouses/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async getWarehouseInventory(warehouseId) {
    return request(`/warehouses/${warehouseId}/inventory`);
  },

  // Inventory
  async getInventory(params = {}) {
    const query = new URLSearchParams(params).toString();
    return request(`/inventory${query ? `?${query}` : ""}`);
  },

  async getInventoryItem(id) {
    return request(`/inventory/${id}`);
  },

  async addInventoryStock(payload) {
    return request("/inventory/stock", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async restockInventory(inventoryId, payload) {
    return request(`/inventory/restock?inventory_id=${inventoryId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Fulfillment Execution
  async getFulfillmentSuggestion(orderId) {
    return request(`/orders/${orderId}/fulfillment/suggest`, {
      method: "POST",
    });
  },

  async confirmFulfillment(orderId, allocations = null) {
    return request(`/orders/${orderId}/fulfillment/confirm`, {
      method: "POST",
      body: allocations ? JSON.stringify({ allocations }) : JSON.stringify({}),
    });
  },
};
