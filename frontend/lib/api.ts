/**
 * Single fetch wrapper used by every page and hook.
 *
 * - Attaches `Authorization: Bearer <access_token>` if present.
 * - Attaches `X-Organization-Id` when the caller is in an org-scoped flow.
 * - On 401, transparently rotates via /auth/refresh and replays once.
 *   If the rotation also 401s, clears tokens and signals the caller via
 *   an `AuthRequiredError` so the UI can redirect to /login.
 */

import { orgStorage, tokenStorage } from "./auth-storage";
import type {
  AIMessagesResponse,
  AIUsageSummary,
  ChargeSummary,
  Connection,
  ConnectionListResponse,
  Organization,
  OAuthInitResponse,
  StripeCustomerSummary,
  SubscriptionSummary,
  SyncLog,
  SyncTriggerResponse,
  TokenResponse,
  User,
} from "./types";

// Paths are relative; Next.js rewrites /api/v1/* to the backend.
const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

export class AuthRequiredError extends ApiError {
  constructor(detail = "Authentication required") {
    super(401, detail);
    this.name = "AuthRequiredError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "DELETE" | "PUT" | "PATCH";
  body?: unknown;
  /** Pass `true` to attach the active-org header. Defaults to `true` for org-scoped endpoints, `false` for /auth/*. */
  orgScoped?: boolean;
  /** Pass `false` to skip the auth header (used by login / register / refresh themselves). */
  authed?: boolean;
}

async function rawRequest<T>(
  path: string,
  { method = "GET", body, orgScoped = true, authed = true }: RequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  if (authed) {
    const token = tokenStorage.getAccess();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  if (orgScoped) {
    const orgId = orgStorage.get();
    if (orgId) headers["X-Organization-Id"] = String(orgId);
  }

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "omit",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const data = text ? safeJson(text) : null;

  if (!response.ok) {
    const detail =
      (data && typeof data === "object" && "detail" in data
        ? String((data as Record<string, unknown>).detail)
        : null) || response.statusText;
    if (response.status === 401) {
      throw new AuthRequiredError(detail);
    }
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

let refreshInFlight: Promise<void> | null = null;

async function rotateRefreshToken(): Promise<void> {
  if (refreshInFlight) return refreshInFlight;
  const refresh = tokenStorage.getRefresh();
  if (!refresh) throw new AuthRequiredError("No refresh token");

  refreshInFlight = (async () => {
    try {
      const tokens = await rawRequest<TokenResponse>("/auth/refresh", {
        method: "POST",
        body: { refresh_token: refresh },
        authed: false,
        orgScoped: false,
      });
      tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
    } catch (err) {
      tokenStorage.clearTokens();
      throw err;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

/** Wrapper that handles transparent refresh on 401. */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  try {
    return await rawRequest<T>(path, options);
  } catch (err) {
    if (!(err instanceof AuthRequiredError)) throw err;
    if (options.authed === false) throw err;
    // Try one refresh + replay. If that fails, propagate so the UI logs out.
    await rotateRefreshToken();
    return rawRequest<T>(path, options);
  }
}

// -----------------------------------------------------------------------------
// Auth
// -----------------------------------------------------------------------------

export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      authed: false,
      orgScoped: false,
    }),

  register: (email: string, username: string, password: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: { email, username, password },
      authed: false,
      orgScoped: false,
    }),

  me: () => request<User>("/auth/me", { orgScoped: false }),

  logout: (refresh_token: string) =>
    request<void>("/auth/logout", {
      method: "POST",
      body: { refresh_token },
      orgScoped: false,
    }),

  // ---------------------------------------------------------------------------
  // Organizations
  // ---------------------------------------------------------------------------

  listOrgs: () =>
    request<{ organizations: Organization[]; total: number }>("/orgs", {
      orgScoped: false,
    }),

  createOrg: (name: string) =>
    request<Organization>("/orgs", { method: "POST", body: { name }, orgScoped: false }),

  // ---------------------------------------------------------------------------
  // Connections + Stripe data
  // ---------------------------------------------------------------------------

  listConnections: () => request<ConnectionListResponse>("/connections"),

  getConnection: (id: number) => request<Connection>(`/connections/${id}`),

  deleteConnection: (id: number) =>
    request<{ message: string }>(`/connections/${id}`, { method: "DELETE" }),

  beginStripeConnect: () =>
    request<OAuthInitResponse>("/connections/stripe/connect", { method: "POST" }),

  triggerSync: (id: number) =>
    request<SyncTriggerResponse>(`/connections/${id}/sync`, { method: "POST" }),

  listSyncLogs: (id: number) => request<SyncLog[]>(`/connections/${id}/sync-logs`),

  listCustomers: (id: number, limit = 50) =>
    request<StripeCustomerSummary[]>(`/connections/${id}/customers?limit=${limit}`),

  listSubscriptions: (id: number, status?: string, limit = 100) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (status) q.set("status", status);
    return request<SubscriptionSummary[]>(`/connections/${id}/subscriptions?${q}`);
  },

  listCharges: (id: number, limit = 50) =>
    request<ChargeSummary[]>(`/connections/${id}/charges?limit=${limit}`),

  // ---------------------------------------------------------------------------
  // AI
  // ---------------------------------------------------------------------------

  aiMessage: (messages: Array<{ role: "user" | "assistant"; content: string }>, system?: string) =>
    request<AIMessagesResponse>("/ai/messages", {
      method: "POST",
      body: { messages, system },
    }),

  aiUsage: () => request<AIUsageSummary>("/ai/usage"),
};
