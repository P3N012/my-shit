"use client";

import { Menu } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-context";
import { Sidebar } from "@/components/sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-base">
        <div className="font-heading text-sm text-mute">Loading…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-base text-ink">
      <Sidebar mobileOpen={drawerOpen} onClose={() => setDrawerOpen(false)} />

      {/* Mobile-only top bar with a hamburger. Hidden on lg+ where the
          sidebar is always visible. */}
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-panel px-4 lg:hidden">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label="Open menu"
          className="flex h-9 w-9 items-center justify-center rounded-md border border-line text-mute hover:text-ink"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="text-ember font-heading text-lg font-bold tracking-tight">
          InsightPlus
        </span>
      </header>

      {/* Content takes the left margin only on lg+, where the sidebar
          occupies that space. On mobile it's full-width. */}
      <main className="lg:ml-64">{children}</main>
    </div>
  );
}
