/**
 * Bare-metal bar chart matching the prototype's "trading terminal" look.
 * Renders a CSS grid background under accent bars; no chart library
 * needed yet (Recharts will land when the data goes real).
 */
export function MrrChart({ values }: { values: number[] }) {
  const max = Math.max(...values);
  return (
    <div
      className="relative flex h-60 items-end gap-2 rounded-md border border-line/60 p-5"
      style={{
        backgroundImage:
          "repeating-linear-gradient(0deg, transparent, transparent 39px, #1a1a1a 39px, #1a1a1a 40px)",
      }}
    >
      {values.map((v, i) => (
        <div
          key={i}
          className="flex-1 rounded-t-[2px] bg-accent"
          style={{ height: `${(v / max) * 100}%`, opacity: 0.9 }}
        />
      ))}
    </div>
  );
}
