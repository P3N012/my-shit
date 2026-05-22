"use client";

import { useAuth } from "@/components/auth-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  const { user, activeOrg } = useAuth();

  return (
    <div className="px-5 py-7 lg:px-10 lg:py-10">
      <header className="mb-8">
        <h1 className="font-heading text-3xl font-semibold tracking-tight text-ink">
          Settings
        </h1>
        <p className="mt-1 text-sm text-fade">Account and workspace.</p>
      </header>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Email" value={user?.email} />
            <Row label="Username" value={user?.username} />
            <Row label="Plan" value={user?.subscription_tier ?? "—"} />
            <Row label="Status" value={user?.subscription_status ?? "—"} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Workspace</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Name" value={activeOrg?.organization_name ?? "—"} />
            <Row label="Role" value={activeOrg?.role ?? "—"} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | undefined | null }) {
  return (
    <div className="flex items-center justify-between border-b border-line/60 py-2 last:border-0">
      <span className="font-heading text-xs uppercase tracking-wide text-fade">
        {label}
      </span>
      <span className="text-ink">{value ?? "—"}</span>
    </div>
  );
}
