/**
 * Money + date formatters used across the app. Amounts are passed in
 * cents (Stripe's native unit) — never convert at the storage layer.
 */

export function formatMoney(cents: number, currency: string = "usd"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

export function formatMoneyPrecise(cents: number, currency: string = "usd"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
    minimumFractionDigits: 2,
  }).format(cents / 100);
}

const RELATIVE_THRESHOLDS: Array<[number, Intl.RelativeTimeFormatUnit]> = [
  [60, "second"],
  [60, "minute"],
  [24, "hour"],
  [7, "day"],
  [4.34524, "week"],
  [12, "month"],
  [Number.POSITIVE_INFINITY, "year"],
];

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "never";
  const date = new Date(iso);
  const seconds = (Date.now() - date.getTime()) / 1000;
  if (seconds < 5) return "just now";

  const rtf = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });
  let duration = seconds;
  for (const [divisor, unit] of RELATIVE_THRESHOLDS) {
    if (duration < divisor) {
      return rtf.format(-Math.round(duration), unit);
    }
    duration /= divisor;
  }
  return rtf.format(-Math.round(duration), "year");
}

/** "Mar 14, 2026" — the deterministic short form, no relative drift. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
