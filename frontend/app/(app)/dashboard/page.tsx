"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import { KpiCard } from "@/components/kpi-card";
import { MrrChart } from "@/components/mrr-chart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatMoney, timeAgo } from "@/lib/format";
import type { DashboardOverview, DashboardTopCustomer } from "@/lib/types";

export default function DashboardPage() {
  const overview = useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: () => api.dashboardOverview(),
  });
  const trends = useQuery({
    queryKey: ["dashboard", "trends"],
    queryFn: () => api.dashboardTrends(12),
  });
  const topCustomers = useQuery({
    queryKey: ["dashboard", "top-customers"],
    queryFn: () => api.dashboardTopCustomers(5),
  });

  return (
    <div className="px-10 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight text-ink">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-fade">
            Last {overview.data?.period_days ?? 30} days · all connected accounts
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
        <KpiCard
          label="MRR"
          value={overview.data ? formatMoney(overview.data.mrr_cents) : "—"}
          delta={kpiDelta(overview.data?.mrr_delta)}
        />
        <KpiCard
          label="ARR"
          value={overview.data ? formatMoney(overview.data.arr_cents) : "—"}
          delta={kpiDelta(overview.data?.arr_delta)}
        />
        <KpiCard
          label="Active Customers"
          value={overview.data ? String(overview.data.active_customers) : "—"}
          delta={kpiDelta(overview.data?.customers_delta)}
        />
        <KpiCard
          label="Churn Rate"
          value={overview.data ? formatChurn(overview.data.churn_rate) : "—"}
          delta={kpiDelta(overview.data?.churn_delta)}
        />
      </div>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Monthly Recurring Revenue</CardTitle>
          <span className="font-heading text-xs text-fade">12 mo trailing</span>
        </CardHeader>
        <CardContent>
          {trends.isLoading ? (
            <ChartPlaceholder text="Loading…" />
          ) : (
            <MrrChart points={trends.data?.points ?? []} />
          )}
        </CardContent>
      </Card>

      <div className="mt-8 grid gap-8 lg:grid-cols-[2fr_1fr]">
        <TopCustomersCard
          rows={topCustomers.data?.customers ?? []}
          loading={topCustomers.isLoading}
        />
        <AIReviewCard />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI review card — its own component because it has a regenerate flow.
// ---------------------------------------------------------------------------

function AIReviewCard() {
  const queryClient = useQueryClient();
  const review = useQuery({
    queryKey: ["ai-review", "latest"],
    queryFn: () => api.aiReviewLatest(),
  });
  const generate = useMutation({
    mutationFn: () => api.aiReviewGenerate(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-review", "latest"] }),
  });

  const r = review.data;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <div className="flex flex-col gap-1.5">
          <CardTitle>
            <span className="inline-flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-accent" />
              AI weekly review
            </span>
          </CardTitle>
          <span className="font-heading text-xs text-fade">
            {r ? `generated ${timeAgo(r.created_at)}` : "not generated yet"}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
        >
          {generate.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
          <span>{r ? "Regenerate" : "Generate"}</span>
        </Button>
      </CardHeader>
      <CardContent>
        {generate.isError && (
          <div className="mb-3 rounded-md border border-line bg-elev px-3 py-2 text-xs text-mute">
            {(generate.error as Error).message}
          </div>
        )}
        {r ? (
          <div className="space-y-3 whitespace-pre-line text-sm leading-relaxed text-mute">
            {r.content}
          </div>
        ) : review.isLoading ? (
          <div className="font-heading text-sm text-fade">Loading…</div>
        ) : (
          <div className="text-sm leading-relaxed text-fade">
            Click <strong className="text-ink">Generate</strong> to have Claude
            summarize the past week against your synced numbers.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Top customers table
// ---------------------------------------------------------------------------

function TopCustomersCard({
  rows,
  loading,
}: {
  rows: DashboardTopCustomer[];
  loading: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Top customers</CardTitle>
        <span className="font-heading text-xs text-fade">
          last 90 days, by revenue
        </span>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="font-heading text-sm text-fade">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="text-sm text-fade">
            No charge data yet — sync a connection or run the demo seed.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className="py-3 text-left font-heading text-xs font-medium uppercase tracking-wide text-fade">
                  Customer
                </th>
                <th className="py-3 text-right font-heading text-xs font-medium uppercase tracking-wide text-fade">
                  Revenue
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.stripe_customer_id} className="border-b border-line/60 last:border-0">
                  <td className="py-4 text-ink">
                    <div className="font-medium">{c.name ?? c.stripe_customer_id}</div>
                    {c.email && (
                      <div className="text-xs text-fade">{c.email}</div>
                    )}
                  </td>
                  <td className="py-4 text-right font-heading text-ink">
                    {formatMoney(c.total_revenue_cents)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function kpiDelta(d: DashboardOverview["mrr_delta"] | undefined) {
  if (!d) return undefined;
  const sign = d.value_pct >= 0 ? "+" : "";
  return { value: `${sign}${d.value_pct}%`, positive: d.positive };
}

function formatChurn(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

function ChartPlaceholder({ text }: { text: string }) {
  return (
    <div className="flex h-60 items-center justify-center rounded-md border border-line/60 font-heading text-sm text-fade">
      {text}
    </div>
  );
}
