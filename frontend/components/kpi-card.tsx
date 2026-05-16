import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  delta?: { value: string; positive: boolean };
}

export function KpiCard({ label, value, delta }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-line bg-panel p-6">
      <div className="font-heading text-xs font-medium uppercase tracking-wide text-fade">
        {label}
      </div>
      <div className="mt-2 font-heading text-3xl font-semibold tracking-tight text-ink">
        {value}
      </div>
      {delta && (
        <div
          className={cn(
            "mt-1 font-heading text-xs font-medium",
            delta.positive ? "text-accent" : "text-mute"
          )}
        >
          {delta.value}
        </div>
      )}
    </div>
  );
}
