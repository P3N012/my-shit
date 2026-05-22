"use client";

import {
  ArrowRightLeft,
  BarChart3,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";

import { useAuth } from "./auth-context";
import { Button } from "./ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/connections", label: "Connections", icon: ArrowRightLeft },
  { href: "/ai-assistant", label: "AI Assistant", icon: MessageSquare },
  { href: "/usage", label: "Usage", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

interface SidebarProps {
  /** Whether the mobile drawer is open. Ignored on lg+ where the sidebar is always shown. */
  mobileOpen?: boolean;
  /** Called when the drawer should close (backdrop click or nav). */
  onClose?: () => void;
}

export function Sidebar({ mobileOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, activeOrg, setActiveOrgId, logout } = useAuth();
  const [orgMenuOpen, setOrgMenuOpen] = useState(false);

  const initials = useMemo(() => {
    if (!user) return "";
    const source = user.username || user.email;
    return source.slice(0, 2).toUpperCase();
  }, [user]);

  return (
    <>
      {/* Backdrop — mobile only, only when the drawer is open. Tap to close. */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-panel",
          "transition-transform duration-200 ease-out",
          // Always on-screen at lg+. On mobile, slide in/out.
          "lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
      <div className="flex flex-col gap-1 px-6 pt-7 pb-5">
        <span className="text-ember font-heading text-xl font-bold tracking-tight">
          InsightPlus
        </span>
      </div>

      {user && user.memberships.length > 0 && (
        <div className="relative px-4 pb-4">
          <button
            type="button"
            onClick={() => setOrgMenuOpen((v) => !v)}
            className={cn(
              "flex w-full items-center justify-between rounded-md border border-line px-3 py-2.5",
              "text-left text-sm font-semibold text-ink",
              "hover:border-accent/40 hover:bg-elev"
            )}
          >
            <span className="truncate">
              {activeOrg?.organization_name ?? "Choose workspace"}
            </span>
            <span className="text-[10px] font-bold uppercase text-accent">
              {activeOrg?.role ?? "—"}
            </span>
          </button>
          {orgMenuOpen && (
            <div className="absolute left-4 right-4 top-full z-50 mt-1 overflow-hidden rounded-md border border-line bg-panel shadow-2xl">
              {user.memberships.map((m) => (
                <button
                  key={m.organization_id}
                  type="button"
                  onClick={() => {
                    setActiveOrgId(m.organization_id);
                    setOrgMenuOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-center justify-between px-3 py-2.5 text-left text-sm hover:bg-elev",
                    m.organization_id === activeOrg?.organization_id
                      ? "text-ink"
                      : "text-mute"
                  )}
                >
                  <span className="truncate">{m.organization_name}</span>
                  <span className="text-[10px] font-bold uppercase text-fade">
                    {m.role}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <nav className="flex-1 px-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className={cn(
                "mb-1 flex items-center gap-3 rounded-md py-2.5 pl-3 pr-3 text-sm font-semibold transition-colors",
                // Active items get a 3px accent strip on the left and a
                // soft 15% accent background — the Ember Glow "live
                // indicator" pattern.
                "border-l-[3px] border-transparent",
                active
                  ? "border-accent bg-accent/15 text-ink"
                  : "text-mute hover:bg-elev/80 hover:text-ink"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-line px-3 py-3">
        <div className="flex items-center gap-3 px-2 py-2">
          {/* Gradient avatar — orange to lighter orange, white initials. */}
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-muted text-xs font-bold text-white">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-ink">
              {user?.username}
            </div>
            <div className="truncate text-xs text-fade">{user?.email}</div>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="mt-2 w-full justify-center"
          onClick={() => void logout()}
        >
          <LogOut className="h-3.5 w-3.5" />
          <span>Sign out</span>
        </Button>
      </div>
      </aside>
    </>
  );
}
