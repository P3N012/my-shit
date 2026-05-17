"use client";

import { Check, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";

const FEATURES = [
  "Live MRR, ARR, active customers, and 30-day churn.",
  "AI-written weekly review of your account, with citations.",
  "Top customers ranked by 90-day revenue.",
];

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [user, loading, router]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(email, username || email.split("@")[0], password);
      } else {
        await login(email, password);
      }
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Sign in failed";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[5fr_4fr]">
      <MarketingPanel />

      <div className="relative flex items-center justify-center bg-base px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <span className="text-ember font-heading text-2xl font-bold tracking-tight">
              InsightPlus
            </span>
          </div>

          <h1 className="font-heading text-3xl font-bold tracking-tight text-ink">
            {isRegister ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mt-2 text-sm text-mute">
            {isRegister
              ? "Start analyzing your Stripe revenue in two minutes."
              : "Sign in to continue to your dashboard."}
          </p>

          <form className="mt-8 space-y-5" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            {isRegister && (
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  type="text"
                  autoComplete="username"
                  placeholder="optional — derived from email if blank"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete={isRegister ? "new-password" : "current-password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>

            {error && (
              <div className="rounded-md border border-line bg-elev px-3 py-2 text-xs text-mute">
                {error}
              </div>
            )}

            <Button type="submit" className="h-11 w-full text-sm" disabled={submitting}>
              {submitting ? "Working…" : isRegister ? "Create account" : "Sign in"}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-mute">
            {isRegister ? "Already have an account? " : "Don't have an account? "}
            <button
              type="button"
              onClick={() => {
                setIsRegister((v) => !v);
                setError(null);
              }}
              className="font-semibold text-accent hover:underline"
            >
              {isRegister ? "Sign in" : "Sign up"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Marketing panel — only renders on lg+, hidden on mobile.
// ---------------------------------------------------------------------------

function MarketingPanel() {
  return (
    <div className="relative hidden overflow-hidden bg-panel lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
      {/* Soft radial glow so the panel doesn't read as a flat black slab.
          Positioned off-center so it draws the eye toward the wordmark. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -left-32 -top-32 h-[28rem] w-[28rem] rounded-full opacity-30 blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(255,107,53,0.45), transparent)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-40 -right-32 h-[32rem] w-[32rem] rounded-full opacity-20 blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(255,134,89,0.4), transparent)",
        }}
      />

      <div className="relative">
        <span className="text-ember font-heading text-2xl font-bold tracking-tight">
          InsightPlus
        </span>
      </div>

      <div className="relative max-w-md">
        <h2 className="font-heading text-4xl font-bold leading-tight tracking-tight text-ink xl:text-5xl">
          Stripe revenue,{" "}
          <span className="text-ember">summarized by AI</span> every week.
        </h2>
        <p className="mt-5 text-base leading-relaxed text-mute">
          Connect Stripe once. Get the four numbers founders actually care
          about on one page — plus an AI-written review that tells you what
          changed and why.
        </p>

        <ul className="mt-8 space-y-3.5">
          {FEATURES.map((f) => (
            <li key={f} className="flex items-start gap-3 text-sm text-ink">
              <span className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-accent/15">
                <Check className="h-3 w-3 text-accent" strokeWidth={3} />
              </span>
              <span>{f}</span>
            </li>
          ))}
        </ul>
      </div>

      <PreviewCard />
    </div>
  );
}

function PreviewCard() {
  return (
    <div className="stripe-ember relative overflow-hidden rounded-lg border border-line bg-base p-5">
      <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wide text-fade">
        <Sparkles className="h-3 w-3 text-accent" />
        AI weekly review · this morning
      </div>
      <p className="mt-3 text-sm leading-relaxed text-mute">
        <span className="text-ink">MRR up 3.2% to $24,128</span>, driven by 5
        new Pro subscriptions. <span className="text-ink">Acme Labs</span>{" "}
        upgraded to annual, adding $8.4K to committed revenue.{" "}
        <span className="text-accent">Watch:</span> 2 customers flagged for
        churn risk based on usage patterns.
      </p>
    </div>
  );
}
