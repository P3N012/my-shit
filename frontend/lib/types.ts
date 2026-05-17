/**
 * Mirrors the FastAPI response shapes. Keep in sync with `app/schemas/*.py`.
 * Field names match the backend exactly so JSON parses without remapping.
 */

export interface Membership {
  organization_id: number;
  organization_name: string;
  role: "owner" | "admin" | "member";
}

export interface User {
  id: number;
  email: string;
  username: string;
  is_admin: boolean;
  status: string;
  subscription_tier: string;
  subscription_status: string;
  created_at: string;
  memberships: Membership[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Organization {
  id: number;
  name: string;
  created_at: string;
}

export type ConnectionStatus = "active" | "disconnected" | "error";

export interface Connection {
  id: number;
  platform: string;
  account_id: string;
  account_name: string | null;
  account_metadata: Record<string, unknown> | null;
  status: ConnectionStatus;
  last_synced_at: string | null;
  last_sync_status: string | null;
  error_message: string | null;
  created_at: string;
}

export interface ConnectionListResponse {
  connections: Connection[];
  total: number;
}

export interface SyncTriggerResponse {
  sync_log_id: number;
  status: string;
}

export interface SyncLog {
  id: number;
  connection_id: number;
  status: "running" | "success" | "failed";
  started_at: string;
  finished_at: string | null;
  stats: { customers?: number; subscriptions?: number; charges?: number } | null;
  error: string | null;
}

export interface StripeCustomerSummary {
  id: number;
  stripe_customer_id: string;
  email: string | null;
  name: string | null;
  currency: string | null;
  balance: number;
  delinquent: boolean;
  stripe_created_at: string;
}

export interface SubscriptionSummary {
  id: number;
  stripe_subscription_id: string;
  stripe_customer_id: string;
  status: string;
  currency: string | null;
  amount_per_period: number;
  interval: string | null;
  interval_count: number;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export interface ChargeSummary {
  id: number;
  stripe_charge_id: string;
  stripe_customer_id: string | null;
  amount: number;
  amount_refunded: number;
  currency: string;
  status: string;
  paid: boolean;
  refunded: boolean;
  stripe_created_at: string;
}

export interface AIMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AIMessagesResponse {
  text: string;
  model: string;
  stop_reason: string | null;
  usage: {
    input_tokens: number;
    output_tokens: number;
    cache_creation_input_tokens: number;
    cache_read_input_tokens: number;
  };
  cost_usd: string;
}

export interface AIUsageSummary {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cost_usd: string;
}

export interface OAuthInitResponse {
  authorization_url: string;
  state: string;
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export interface KpiDelta {
  value_pct: number;
  positive: boolean;
}

export interface DashboardOverview {
  mrr_cents: number;
  arr_cents: number;
  active_customers: number;
  churn_rate: number;
  mrr_delta: KpiDelta | null;
  arr_delta: KpiDelta | null;
  customers_delta: KpiDelta | null;
  churn_delta: KpiDelta | null;
  period_days: number;
}

export interface DashboardTrendPoint {
  date: string;
  mrr_cents: number;
}

export interface DashboardTrends {
  points: DashboardTrendPoint[];
}

export interface DashboardTopCustomer {
  stripe_customer_id: string;
  name: string | null;
  email: string | null;
  total_revenue_cents: number;
}

export interface DashboardTopCustomers {
  customers: DashboardTopCustomer[];
}

// ---------------------------------------------------------------------------
// AI review
// ---------------------------------------------------------------------------

export interface AIReview {
  id: number;
  period_start: string;
  period_end: string;
  model: string;
  content: string;
  metrics_snapshot: Record<string, unknown> | null;
  created_at: string;
}
