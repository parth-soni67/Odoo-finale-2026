import React from "react";
import {
  Activity,
  MessageSquare,
  Package,
  Users,
  BarChart3,
  Building2,
  FileText,
  CheckCircle2,
  Receipt,
  Truck,
  Warehouse,
  Boxes,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

export const NAVIGATION_BY_ROLE = {
  CUSTOMER: {
    sectionTitle: "CUSTOMER",
    items: [
      { id: "portal", label: "Customer Portal", icon: Building2 },
      { id: "my-quotes", label: "My Quotes", icon: FileText },
      { id: "orders", label: "Orders & Fulfillment", icon: Package },
      { id: "billing", label: "Billing & Invoices", icon: Receipt },
      { id: "company", label: "Company Account", icon: Users },
    ],
  },
  SALES_REP: {
    sectionTitle: "SALES",
    items: [
      { id: "quotations", label: "Quotations", icon: FileText },
      { id: "products", label: "Products", icon: Package },
      { id: "customers", label: "Customers", icon: Users },
      { id: "negotiations", label: "Negotiations", icon: MessageSquare },
    ],
  },
  SALES_MANAGER: {
    sectionTitle: "SALES MANAGEMENT",
    items: [
      { id: "quotations", label: "Quotations", icon: FileText },
      { id: "products", label: "Products", icon: Package },
      { id: "customers", label: "Customers", icon: Users },
      { id: "negotiations", label: "Negotiations", icon: MessageSquare },
      { id: "approvals", label: "Approvals", icon: CheckCircle2 },
      { id: "deal-health", label: "Deal Health", icon: Activity },
      { id: "reports", label: "Reports", icon: BarChart3 },
      { id: "warehouses", label: "Warehouses", icon: Warehouse },
      { id: "inventory", label: "Inventory", icon: Boxes },
    ],
  },
  FINANCE: {
    sectionTitle: "FINANCE",
    items: [
      { id: "billing", label: "Billing & Invoices", icon: Receipt },
      { id: "approvals", label: "Approvals", icon: CheckCircle2 },
      { id: "quotations", label: "Quotations", icon: FileText },
    ],
  },
  OPERATIONS: {
    sectionTitle: "OPERATIONS",
    items: [
      { id: "orders", label: "Orders & Fulfillment", icon: Truck },
      { id: "warehouses", label: "Warehouses", icon: Warehouse },
      { id: "inventory", label: "Inventory", icon: Boxes },
    ],
  },
  ADMIN: {
    sectionTitle: "ADMINISTRATION",
    items: [
      { id: "deal-health", label: "Deal Health", icon: Activity },
      { id: "quotations", label: "Quotations", icon: FileText },
      { id: "approvals", label: "Approvals", icon: CheckCircle2 },
      { id: "negotiations", label: "Negotiations", icon: MessageSquare },
      { id: "products", label: "Products", icon: Package },
      { id: "customers", label: "Customers", icon: Users },
      { id: "warehouses", label: "Warehouses", icon: Warehouse },
      { id: "inventory", label: "Inventory", icon: Boxes },
      { id: "orders", label: "Fulfillment", icon: Truck },
      { id: "billing", label: "Billing & Invoices", icon: Receipt },
      { id: "reports", label: "Reports", icon: BarChart3 },
    ],
  },
};

export function isItemActive(itemId, activeTab) {
  if (activeTab === itemId) return true;
  // Customer route aliases:
  if (itemId === "portal" && (activeTab === "portal" || !activeTab)) return true;
  if (itemId === "my-quotes" && (activeTab === "my-quotes" || activeTab === "quotes")) return true;
  if (itemId === "company" && (activeTab === "company" || activeTab === "account")) return true;
  // Internal aliases:
  if (itemId === "warehouses" && activeTab.startsWith("warehouses/")) return true;
  if (itemId === "orders" && activeTab === "fulfillment") return true;
  return false;
}

export function RoleSidebar({
  role,
  activeTab,
  onNavigate,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}) {
  const config = NAVIGATION_BY_ROLE[role] || {
    sectionTitle: (role || "WORKSPACE").replace("_", " "),
    items: [],
  };

  return (
    <aside
      className={`internal-sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}
      aria-label="Sidebar Navigation"
      id="role-sidebar"
    >
      <div className="sidebar-header">
        <span className="sidebar-role-label">{config.sectionTitle}</span>
        <button
          type="button"
          className="sidebar-toggle-btn desktop-only-toggle"
          onClick={onToggleCollapse}
          title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          aria-label={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      <div className="sidebar-section-heading">{config.sectionTitle}</div>

      <nav className="sidebar-nav">
        {config.items.map((item) => {
          const Icon = item.icon;
          const active = isItemActive(item.id, activeTab);
          return (
            <button
              key={`${role}-${item.id}`}
              type="button"
              className={`sidebar-link ${active ? "active" : ""}`}
              onClick={() => {
                onNavigate(item.id);
                if (onCloseMobile) onCloseMobile();
              }}
              title={item.label}
              id={`sidebar-item-${item.id}`}
              aria-current={active ? "page" : undefined}
            >
              <Icon size={17} className="sidebar-icon" />
              <span className="sidebar-text">{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
