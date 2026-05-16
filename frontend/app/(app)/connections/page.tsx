"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { Connection } from "@/lib/types";

export default function ConnectionsPage() {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);

  const connectionsQuery = useQuery({
    queryKey: ["connections"],
    queryFn: () => api.listConnections(),
  });

  const beginConnect = useMutation({
    mutationFn: () => api.beginStripeConnect(),
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const syncOne = useMutation({
    mutationFn: (id: number) => api.triggerSync(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["connections"] }),
    onError: (err: Error) => setActionError(err.message),
  });

  const deleteOne = useMutation({
    mutationFn: (id: number) => api.deleteConnection(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["connections"] }),
    onError: (err: Error) => setActionError(err.message),
  });

  const connections = connectionsQuery.data?.connections ?? [];

  return (
    <div className="px-10 py-10">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight text-ink">
            Connections
          </h1>
          <p className="mt-1 text-sm text-fade">
            Manage your payment platform integrations.
          </p>
        </div>
        <Button onClick={() => beginConnect.mutate()} disabled={beginConnect.isPending}>
          {beginConnect.isPending ? "Redirecting…" : "Connect Stripe"}
        </Button>
      </header>

      {actionError && (
        <div className="mb-6 rounded-md border border-line bg-elev px-4 py-3 text-sm text-mute">
          {actionError}
        </div>
      )}

      {connectionsQuery.isLoading ? (
        <div className="rounded-lg border border-line bg-panel p-12 text-center font-heading text-sm text-mute">
          Loading…
        </div>
      ) : connectionsQuery.isError ? (
        <div className="rounded-lg border border-line bg-panel p-12 text-center text-sm text-mute">
          Couldn&apos;t load connections.{" "}
          <button
            type="button"
            onClick={() => connectionsQuery.refetch()}
            className="text-accent hover:underline"
          >
            Try again
          </button>
        </div>
      ) : connections.length === 0 ? (
        <EmptyState onConnect={() => beginConnect.mutate()} loading={beginConnect.isPending} />
      ) : (
        <div className="grid gap-5">
          {connections.map((c) => (
            <ConnectionCard
              key={c.id}
              conn={c}
              onSync={() => syncOne.mutate(c.id)}
              onDelete={() => deleteOne.mutate(c.id)}
              syncing={syncOne.isPending && syncOne.variables === c.id}
              deleting={deleteOne.isPending && deleteOne.variables === c.id}
            />
          ))}
          <button
            type="button"
            onClick={() => beginConnect.mutate()}
            disabled={beginConnect.isPending}
            className="rounded-lg border border-dashed border-line bg-panel p-12 text-center transition-colors hover:border-accent/40"
          >
            <div className="font-heading text-base font-semibold text-ink">
              Connect another account
            </div>
            <div className="mt-1 text-sm text-fade">
              Link a second Stripe account from a different business.
            </div>
          </button>
        </div>
      )}
    </div>
  );
}

function ConnectionCard({
  conn,
  onSync,
  onDelete,
  syncing,
  deleting,
}: {
  conn: Connection;
  onSync: () => void;
  onDelete: () => void;
  syncing: boolean;
  deleting: boolean;
}) {
  const badgeVariant =
    conn.status === "active" ? "active" : conn.status === "error" ? "error" : "idle";

  return (
    <div className="flex items-center justify-between rounded-lg border border-line bg-panel p-6">
      <div className="flex items-center gap-5">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-stripe font-heading text-xl font-semibold text-white">
          S
        </div>
        <div>
          <div className="font-heading text-base font-semibold text-ink">
            {conn.account_name || conn.account_id}
          </div>
          <div className="mt-0.5 text-sm text-fade">
            <span className="capitalize">{conn.platform}</span> · Last synced{" "}
            {timeAgo(conn.last_synced_at)}
            {conn.error_message ? ` · ${conn.error_message}` : ""}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Badge variant={badgeVariant} size="md">
          {conn.status}
        </Badge>
        <Button variant="secondary" size="sm" onClick={onSync} disabled={syncing}>
          {syncing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          <span>Sync now</span>
        </Button>
        <Button variant="destructive" size="icon" onClick={onDelete} disabled={deleting}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function EmptyState({ onConnect, loading }: { onConnect: () => void; loading: boolean }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-panel p-16 text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-lg bg-stripe font-heading text-2xl font-semibold text-white">
        S
      </div>
      <div className="font-heading text-lg font-semibold text-ink">
        Connect your first account
      </div>
      <div className="mx-auto mt-2 max-w-sm text-sm text-fade">
        Link your Stripe account to pull customers, subscriptions, and charges. Read-only by
        default.
      </div>
      <Button onClick={onConnect} disabled={loading} className="mt-6">
        {loading ? "Redirecting…" : "Connect Stripe"}
      </Button>
    </div>
  );
}
