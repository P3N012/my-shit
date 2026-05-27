"use client";

import { useQuery } from "@tanstack/react-query";

import { KpiCard } from "@/components/kpi-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

const compact = new Intl.NumberFormat("en-US", { notation: "compact" });

export default function UsagePage() {
  const usage = useQuery({
    queryKey: ["ai-usage"],
    queryFn: () => api.aiUsage(),
  });

  const data = usage.data;
  const cost = data ? Number(data.cost_usd) : 0;

  return (
    <div className="px-5 py-7 lg:px-10 lg:py-10">
      <header className="mb-8">
        <h1 className="font-heading text-3xl font-semibold tracking-tight text-ink">
          AI Usage
        </h1>
        <p className="mt-1 text-sm text-fade">
          Tokens and cost across every AI call this organization has made.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
        <KpiCard
          label="Calls"
          value={data ? compact.format(data.calls) : "—"}
        />
        <KpiCard
          label="Input tokens"
          value={data ? compact.format(data.input_tokens) : "—"}
        />
        <KpiCard
          label="Output tokens"
          value={data ? compact.format(data.output_tokens) : "—"}
        />
        <KpiCard
          label="Total cost"
          value={data ? `$${cost.toFixed(4)}` : "—"}
        />
      </div>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Cache hit rate</CardTitle>
          <span className="font-heading text-xs text-fade">prompt caching</span>
        </CardHeader>
        <CardContent>
          {data ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-mute">Cache-read input tokens</span>
                <span className="font-heading text-ink">
                  {compact.format(data.cache_read_input_tokens)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-mute">Uncached input tokens</span>
                <span className="font-heading text-ink">
                  {compact.format(data.input_tokens)}
                </span>
              </div>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-line">
                <div
                  className="h-full bg-accent"
                  style={{
                    width:
                      data.input_tokens + data.cache_read_input_tokens === 0
                        ? "0%"
                        : `${
                            (data.cache_read_input_tokens /
                              (data.input_tokens + data.cache_read_input_tokens)) *
                            100
                          }%`,
                  }}
                />
              </div>
            </div>
          ) : (
            <div className="font-heading text-sm text-fade">Loading…</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
