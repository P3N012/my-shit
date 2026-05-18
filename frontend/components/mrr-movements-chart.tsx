"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  XAxis,
  YAxis,
} from "recharts";

import type { DashboardMovementPoint } from "@/lib/types";

const ACCENT = "#ff6b35";
const CHURN = "#5a3a3a";   // warm desaturated red — coherent with the accent family
const GRID = "#2a2a2a";
const AXIS = "#666";
const TICK_FONT = {
  fontFamily: "var(--font-sans)",
  fontSize: 11,
};

interface Row {
  label: string;
  fullDate: string;
  new: number;
  churn: number;   // negative so it stacks below zero
}

export function MrrMovementsChart({ points }: { points: DashboardMovementPoint[] }) {
  if (!points || points.length === 0) {
    return (
      <div className="flex h-60 items-center justify-center rounded-md border border-line/60 font-heading text-sm text-fade">
        No movement data yet.
      </div>
    );
  }

  const data: Row[] = points.map((p) => {
    const d = new Date(p.month_start);
    return {
      label: d.toLocaleDateString("en-US", { month: "short" }),
      fullDate: d.toLocaleDateString("en-US", { month: "long", year: "numeric" }),
      new: p.new_mrr_cents / 100,
      churn: -(p.churn_mrr_cents / 100),
    };
  });

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 16, right: 8, left: 0, bottom: 0 }}
          stackOffset="sign"
          barCategoryGap="12%"
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
          {/* Zero line so the diverging design reads clearly. */}
          <ReferenceLine y={0} stroke={AXIS} strokeWidth={1} />
          <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<MovementTooltip />} />
          <Bar dataKey="new" stackId="a" fill={ACCENT} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="churn" stackId="a" fill={CHURN} radius={[0, 0, 4, 4]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function formatYTick(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${Math.round(abs / 1_000)}K`;
  return `${sign}$${abs}`;
}

function MovementTooltip(props: TooltipProps<number, string>) {
  const item = props.payload?.[0]?.payload as Row | undefined;
  if (!props.active || !item) return null;

  const net = item.new + item.churn;   // churn is already negative
  return (
    <div className="rounded-md border border-line bg-panel px-3 py-2 shadow-xl">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-fade">
        {item.fullDate}
      </div>
      <div className="mt-2 space-y-0.5 text-xs">
        <Row label="New" value={`+$${item.new.toLocaleString()}`} color="text-accent" />
        <Row label="Churn" value={`-$${Math.abs(item.churn).toLocaleString()}`} color="text-mute" />
        <div className="mt-1.5 flex items-center justify-between border-t border-line/60 pt-1.5">
          <span className="font-semibold text-fade">Net</span>
          <span className={`font-heading font-bold ${net >= 0 ? "text-accent" : "text-mute"}`}>
            {net >= 0 ? "+" : "-"}${Math.abs(net).toLocaleString()}
          </span>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center justify-between gap-6">
      <span className="text-mute">{label}</span>
      <span className={`font-heading font-semibold ${color}`}>{value}</span>
    </div>
  );
}
