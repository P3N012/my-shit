import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  delta?: { value: string; positive: boolean };
}

export function KpiCard({ label, value, delta }: KpiCardProps) {
  return (
    <div className="stripe-ember relative overflow-hidden rounded-lg border border-line bg-panel p-7">
      <div className="font-heading text-xs font-semibold uppercase tracking-wide text-mute">
        {label}
      </div>
      <div className="mt-3 font-heading text-3xl font-bold tracking-tight text-ink">
        {value}
      </div>
      {delta && (
        <div
          className={cn(
            "mt-1.5 text-xs font-semibold",
            delta.positive ? "text-accent" : "text-mute"
          )}
        >
          {delta.value}
        </div>
      )}
    </div>
  );
}
