"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  XAxis,
  YAxis,
} from "recharts";

import type { DashboardTrendPoint } from "@/lib/types";

const ACCENT = "oklch(0.65 0.24 142)";
const GRID = "#1a1a1a";
const AXIS = "#666";
const TICK_FONT = {
  fontFamily: "var(--font-mono)",
  fontSize: 11,
};

interface RowData {
  label: string;
  fullDate: string;
  mrr: number;     // dollars
  isCurrent: boolean;
}

export function MrrChart({ points }: { points: DashboardTrendPoint[] }) {
  if (!points || points.length === 0) {
    return (
      <div className="flex h-60 items-center justify-center rounded-md border border-line/60 font-heading text-sm text-fade">
        No data yet — connect Stripe or seed demo data.
      </div>
    );
  }

  const data: RowData[] = points.map((p, i) => ({
    label: new Date(p.date).toLocaleDateString("en-US", { month: "short" }),
    fullDate: new Date(p.date).toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
    }),
    mrr: p.mrr_cents / 100,
    isCurrent: i === points.length - 1,
  }));

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 10, right: 8, left: 0, bottom: 0 }}
          barCategoryGap="20%"
        >
          <CartesianGrid stroke={GRID} strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="label"
            stroke={AXIS}
            tickLine={false}
            axisLine={{ stroke: GRID }}
            tick={TICK_FONT}
          />
          <YAxis
            stroke={AXIS}
            tickLine={false}
            axisLine={false}
            tick={TICK_FONT}
            width={56}
            tickFormatter={formatYTick}
          />
          <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<MrrTooltip />} />
          <Bar
            dataKey="mrr"
            fill={ACCENT}
            radius={[3, 3, 0, 0]}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function formatYTick(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${value}`;
}

function MrrTooltip(props: TooltipProps<number, string>) {
  const item = props.payload?.[0]?.payload as RowData | undefined;
  if (!props.active || !item) return null;

  return (
    <div className="rounded-md border border-line bg-panel px-3 py-2 shadow-xl">
      <div className="font-heading text-xs uppercase tracking-wide text-fade">
        {item.fullDate}
      </div>
      <div className="mt-1 font-heading text-base font-semibold text-ink">
        ${item.mrr.toLocaleString("en-US", { maximumFractionDigits: 0 })}
      </div>
      {item.isCurrent && (
        <div className="mt-0.5 font-heading text-[10px] uppercase tracking-wide text-accent">
          current
        </div>
      )}
    </div>
  );
}
