"use client";

import { AlertCircle, ArrowDownRight, ArrowUpRight } from "lucide-react";

import { formatMoney, timeAgo } from "@/lib/format";
import type { ActivityEvent, ActivityEventKind } from "@/lib/types";
import { cn } from "@/lib/utils";

interface KindMeta {
  Icon: React.ComponentType<{ className?: string }>;
  iconBg: string;
  iconColor: string;
  amountSign: "+" | "-" | "";
}

const KIND_META: Record<ActivityEventKind, KindMeta> = {
  subscription_started: {
    Icon: ArrowUpRight,
    iconBg: "bg-accent/15",
    iconColor: "text-accent",
    amountSign: "+",
  },
  subscription_canceled: {
    Icon: ArrowDownRight,
    iconBg: "bg-mute/15",
    iconColor: "text-mute",
    amountSign: "-",
  },
  charge_failed: {
    Icon: AlertCircle,
    iconBg: "bg-line",
    iconColor: "text-ink",
    amountSign: "",
  },
};

export function ActivityFeed({
  events,
  loading,
}: {
  events: ActivityEvent[];
  loading: boolean;
}) {
  if (loading) {
    return <div className="font-heading text-sm text-fade">Loading…</div>;
  }
  if (events.length === 0) {
    return (
      <div className="text-sm text-fade">
        No activity in the last 30 days — sync a connection or seed demo data.
      </div>
    );
  }

  return (
    <ol className="space-y-3">
      {events.map((e, i) => (
        <ActivityRow key={i} event={e} />
      ))}
    </ol>
  );
}

function ActivityRow({ event }: { event: ActivityEvent }) {
  const meta = KIND_META[event.kind] ?? KIND_META.subscription_started;
  const displayName = event.customer_name || event.customer_email || "Unknown customer";

  return (
    <li className="flex items-start gap-3">
      <span
        className={cn(
          "mt-0.5 flex h-7 w-7 flex-none items-center justify-center rounded-full",
          meta.iconBg
        )}
      >
        <meta.Icon className={cn("h-3.5 w-3.5", meta.iconColor)} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <div className="truncate text-sm font-semibold text-ink">{displayName}</div>
          {event.amount_cents > 0 && (
            <span className={cn("font-heading text-xs font-bold", meta.iconColor)}>
              {meta.amountSign}
              {formatMoney(event.amount_cents)}
            </span>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-fade">
          <span className="truncate">{event.description}</span>
          <span aria-hidden>·</span>
          <span className="flex-none">{timeAgo(event.timestamp)}</span>
        </div>
      </div>
    </li>
  );
}
