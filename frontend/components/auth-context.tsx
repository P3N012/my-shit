"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api, AuthRequiredError } from "@/lib/api";
import { orgStorage, tokenStorage } from "@/lib/auth-storage";
import type { Membership, User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  activeOrg: Membership | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginDemo: () => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setActiveOrgId: (orgId: number) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [activeOrgId, _setActiveOrgId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: if we have an access token, hydrate the user.
  useEffect(() => {
    const access = tokenStorage.getAccess();
    if (!access) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((u) => {
        setUser(u);
        const stored = orgStorage.get();
        const fallback = u.memberships[0]?.organization_id ?? null;
        const chosen = stored && u.memberships.some((m) => m.organization_id === stored)
          ? stored
          : fallback;
        if (chosen) {
          _setActiveOrgId(chosen);
          orgStorage.set(chosen);
        }
      })
      .catch((err) => {
        if (err instanceof AuthRequiredError) {
          tokenStorage.clearTokens();
          orgStorage.clear();
        }
      })
      .finally(() => setLoading(false));
  }, []);

  // Shared tail of every sign-in path: persist tokens, hydrate the user,
  // select their first org, and land on the dashboard.
  const completeLogin = useCallback(
    async (tokens: { access_token: string; refresh_token: string }) => {
      tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
      const u = await api.me();
      setUser(u);
      const first = u.memberships[0]?.organization_id ?? null;
      if (first) {
        _setActiveOrgId(first);
        orgStorage.set(first);
      }
      router.push("/dashboard");
    },
    [router]
  );

  const login = useCallback(
    async (email: string, password: string) => {
      await completeLogin(await api.login(email, password));
    },
    [completeLogin]
  );

  const loginDemo = useCallback(async () => {
    await completeLogin(await api.demoLogin());
  }, [completeLogin]);

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      await api.register(email, username, password);
      // Registration doesn't auto-login server-side, so log in immediately.
      await login(email, password);
    },
    [login]
  );

  const logout = useCallback(async () => {
    const refresh = tokenStorage.getRefresh();
    if (refresh) {
      try {
        await api.logout(refresh);
      } catch {
        // Best-effort; tokens are cleared regardless.
      }
    }
    tokenStorage.clearTokens();
    orgStorage.clear();
    setUser(null);
    _setActiveOrgId(null);
    router.push("/login");
  }, [router]);

  const setActiveOrgId = useCallback((orgId: number) => {
    _setActiveOrgId(orgId);
    orgStorage.set(orgId);
  }, []);

  const activeOrg = useMemo(() => {
    if (!user || activeOrgId == null) return null;
    return user.memberships.find((m) => m.organization_id === activeOrgId) ?? null;
  }, [user, activeOrgId]);

  const value = useMemo(
    () => ({ user, activeOrg, loading, login, loginDemo, register, logout, setActiveOrgId }),
    [user, activeOrg, loading, login, loginDemo, register, logout, setActiveOrgId]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
