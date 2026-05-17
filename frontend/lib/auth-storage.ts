/**
 * Token storage. `localStorage` for an MVP; switch to httpOnly cookies
 * once we have a same-origin proxy that can set them. SSR-safe — every
 * accessor checks for `window`.
 */

const ACCESS_KEY = "ip.access_token";
const REFRESH_KEY = "ip.refresh_token";
const ORG_KEY = "ip.active_org_id";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export const tokenStorage = {
  getAccess(): string | null {
    if (!isBrowser()) return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  getRefresh(): string | null {
    if (!isBrowser()) return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  setTokens(access: string, refresh: string): void {
    if (!isBrowser()) return;
    window.localStorage.setItem(ACCESS_KEY, access);
    window.localStorage.setItem(REFRESH_KEY, refresh);
  },
  clearTokens(): void {
    if (!isBrowser()) return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

export const orgStorage = {
  get(): number | null {
    if (!isBrowser()) return null;
    const raw = window.localStorage.getItem(ORG_KEY);
    return raw ? Number(raw) : null;
  },
  set(orgId: number): void {
    if (!isBrowser()) return;
    window.localStorage.setItem(ORG_KEY, String(orgId));
  },
  clear(): void {
    if (!isBrowser()) return;
    window.localStorage.removeItem(ORG_KEY);
  },
};
