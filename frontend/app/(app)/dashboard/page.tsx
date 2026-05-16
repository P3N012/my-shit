"use client";

import { Sparkles } from "lucide-react";

import { KpiCard } from "@/components/kpi-card";
import { MrrChart } from "@/components/mrr-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// TODO(PR-C): wire these to `GET /dashboard/overview` and
// `GET /dashboard/trends` once the aggregate endpoints land. Placeholder
// data matches the prototype so the screen reads as a working account.
const KPIS = [
  { label: "MRR", value: "$24,128", delta: { value: "+12.3%", positive: true } },
  { label: "ARR", value: "$289,536", delta: { value: "+12.3%", positive: true } },
  { label: "Active Customers", value: "147", delta: { value: "+8", positive: true } },
  { label: "Churn Rate", value: "2.1%", delta: { value: "-0.4%", positive: true } },
];

const MRR_TREND = [16400, 17100, 18200, 17600, 18900, 19700, 20800, 21500, 22200, 23000, 23700, 24128];

const TOP_CUSTOMERS = [
  { name: "Acme Corp", mrr: "$1,249", ltv: "$14,988" },
  { name: "TechStart Inc", mrr: "$899", ltv: "$10,788" },
  { name: "Digital Solutions", mrr: "$749", ltv: "$8,988" },
  { name: "CloudBase Systems", mrr: "$649", ltv: "$7,788" },
  { name: "DataFlow Ltd", mrr: "$549", ltv: "$6,588" },
];

export default function DashboardPage() {
  return (
    <div className="px-10 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight text-ink">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-fade">Last 30 days · all connected accounts</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
        {KPIS.map((k) => (
          <KpiCard key={k.label} {...k} />
        ))}
      </div>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Monthly Recurring Revenue</CardTitle>
          <span className="font-heading text-xs text-fade">12 mo trailing</span>
        </CardHeader>
        <CardContent>
          <MrrChart values={MRR_TREND} />
        </CardContent>
      </Card>

      <div className="mt-8 grid gap-8 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Top customers</CardTitle>
            <span className="font-heading text-xs text-fade">by recurring revenue</span>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-3 text-left font-heading text-xs font-medium uppercase tracking-wide text-fade">
                    Customer
                  </th>
                  <th className="py-3 text-right font-heading text-xs font-medium uppercase tracking-wide text-fade">
                    MRR
                  </th>
                  <th className="py-3 text-right font-heading text-xs font-medium uppercase tracking-wide text-fade">
                    LTV
                  </th>
                </tr>
              </thead>
              <tbody>
                {TOP_CUSTOMERS.map((c) => (
                  <tr key={c.name} className="border-b border-line/60 last:border-0">
                    <td className="py-4 text-ink">{c.name}</td>
                    <td className="py-4 text-right font-heading text-ink">{c.mrr}</td>
                    <td className="py-4 text-right font-heading text-ink">{c.ltv}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              <span className="inline-flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-accent" />
                AI weekly review
              </span>
            </CardTitle>
            <span className="font-heading text-xs text-fade">generated this morning</span>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-mute">
            <p>
              Strong growth this week. MRR increased 3.2% driven by 5 new enterprise
              subscriptions.
            </p>
            <p>Acme Corp upgraded to annual, adding $8.4K to committed revenue.</p>
            <p className="text-ink">
              <span className="font-heading text-xs uppercase tracking-wide text-accent">
                Watch
              </span>{" "}
              — 2 customers flagged for churn risk based on usage patterns.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
