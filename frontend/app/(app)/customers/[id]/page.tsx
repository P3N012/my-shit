"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { KpiCard } from "@/components/kpi-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatMoney, formatMoneyPrecise } from "@/lib/format";
import type {
  CustomerChargeDetail,
  CustomerSubscriptionDetail,
} from "@/lib/types";

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const customer = useQuery({
    queryKey: ["customer", id],
    queryFn: () => api.dashboardCustomerDetail(id),
    retry: false,
  });

  if (customer.isLoading) {
    return (
      <div className="px-5 py-7 lg:px-10 lg:py-10">
        <BackLink />
        <div className="mt-8 font-heading text-sm text-fade">Loading…</div>
      </div>
    );
  }

  if (customer.isError) {
    const notFound =
      customer.error instanceof ApiError && customer.error.status === 404;
    return (
      <div className="px-5 py-7 lg:px-10 lg:py-10">
        <BackLink />
        <div className="mt-8 rounded-lg border border-line bg-panel p-10 text-center text-sm text-mute">
          {notFound
            ? "That customer doesn't exist in this workspace."
            : "Couldn't load this customer."}
        </div>
      </div>
    );
  }

  const c = customer.data!;
  const monthlyInterval = (s: CustomerSubscriptionDetail) =>
    s.interval ? `/ ${s.interval_count > 1 ? `${s.interval_count} ` : ""}${s.interval}` : "";

  return (
    <div className="px-5 py-7 lg:px-10 lg:py-10">
      <BackLink />

      <header className="mt-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-ink">
            {c.name ?? c.stripe_customer_id}
          </h1>
          <p className="mt-1 text-sm text-fade">
            {c.email ?? "no email on file"} · customer since{" "}
            {formatDate(c.stripe_created_at)}
          </p>
        </div>
        {c.delinquent && (
          <Badge variant="error" size="md">
            Delinquent
          </Badge>
        )}
      </header>

      <div className="mt-8 grid grid-cols-2 gap-5 lg:grid-cols-3">
        <KpiCard label="Current MRR" value={formatMoney(c.current_mrr_cents)} />
        <KpiCard label="Lifetime Value" value={formatMoney(c.lifetime_value_cents)} />
        <KpiCard
          label="Active Subscriptions"
          value={String(
            c.subscriptions.filter((s) =>
              ["active", "trialing", "past_due"].includes(s.status)
            ).length
          )}
        />
      </div>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Subscriptions</CardTitle>
        </CardHeader>
        <CardContent>
          {c.subscriptions.length === 0 ? (
            <div className="text-sm text-fade">No subscriptions.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left">
                  <Th>Status</Th>
                  <Th>Amount</Th>
                  <Th className="text-right">Renews / ended</Th>
                </tr>
              </thead>
              <tbody>
                {c.subscriptions.map((s) => (
                  <tr
                    key={s.stripe_subscription_id}
                    className="border-b border-line/60 last:border-0"
                  >
                    <td className="py-3">
                      <SubStatusBadge status={s.status} />
                    </td>
                    <td className="py-3 font-heading text-ink">
                      {formatMoney(s.amount_per_period)}{" "}
                      <span className="text-xs text-fade">
                        {monthlyInterval(s)}
                      </span>
                    </td>
                    <td className="py-3 text-right text-mute">
                      {s.canceled_at
                        ? `canceled ${formatDate(s.canceled_at)}`
                        : formatDate(s.current_period_end)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Charges</CardTitle>
          <span className="font-heading text-xs text-fade">
            most recent {c.charges.length}
          </span>
        </CardHeader>
        <CardContent>
          {c.charges.length === 0 ? (
            <div className="text-sm text-fade">No charges.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left">
                  <Th>Date</Th>
                  <Th>Status</Th>
                  <Th className="text-right">Amount</Th>
                </tr>
              </thead>
              <tbody>
                {c.charges.map((ch) => (
                  <ChargeRow key={ch.stripe_charge_id} charge={ch} />
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/dashboard"
      className="inline-flex items-center gap-2 text-sm font-semibold text-mute hover:text-ink"
    >
      <ArrowLeft className="h-4 w-4" />
      Back to dashboard
    </Link>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      className={`py-3 font-heading text-xs font-bold uppercase tracking-wide text-fade ${className}`}
    >
      {children}
    </th>
  );
}

function SubStatusBadge({ status }: { status: string }) {
  const variant =
    status === "active" || status === "trialing"
      ? "active"
      : status === "canceled"
        ? "idle"
        : "error";
  return (
    <Badge variant={variant} size="sm">
      {status}
    </Badge>
  );
}

function ChargeRow({ charge }: { charge: CustomerChargeDetail }) {
  const ok = charge.status === "succeeded";
  return (
    <tr className="border-b border-line/60 last:border-0">
      <td className="py-3 text-mute">{formatDate(charge.stripe_created_at)}</td>
      <td className="py-3">
        <Badge variant={ok ? "active" : "error"} size="sm">
          {charge.status}
        </Badge>
      </td>
      <td className="py-3 text-right font-heading text-ink">
        {formatMoneyPrecise(charge.amount, charge.currency)}
        {charge.refunded && (
          <span className="ml-1 text-xs text-fade">(refunded)</span>
        )}
      </td>
    </tr>
  );
}
