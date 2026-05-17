"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth-context";
import { Sidebar } from "@/components/sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading } = useAuth();

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
      <Sidebar />
      <main className="ml-64">{children}</main>
    </div>
  );
}
