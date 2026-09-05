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
    const errorMsg = data?.error?.message || `HTTP ${res.status}: ${res.statusText}`;
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

  async getPortalInvoices() {
    return request("/portal/invoices");
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
};
