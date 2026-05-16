"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * Public landing target for the Stripe Connect redirect.
 *
 * The backend's `STRIPE_OAUTH_SUCCESS_URL` / `FAILURE_URL` point here.
 * On success we forward into the authed connections page after a short
 * grace period so the user sees the outcome.
 */
export default function StripeCallbackPage() {
  return (
    <Suspense fallback={<Pending />}>
      <Inner />
    </Suspense>
  );
}

function Inner() {
  const router = useRouter();
  const params = useSearchParams();
  const status = params.get("stripe");
  const reason = params.get("reason");
  const connectionId = params.get("connection_id");
  const [seconds, setSeconds] = useState(3);

  useEffect(() => {
    if (status !== "ok") return;
    const t = window.setInterval(() => setSeconds((s) => Math.max(s - 1, 0)), 1000);
    const r = window.setTimeout(() => router.push("/connections"), 3000);
    return () => {
      window.clearInterval(t);
      window.clearTimeout(r);
    };
  }, [status, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-base px-6">
      <div className="w-full max-w-md rounded-lg border border-line bg-panel p-10 text-center">
        {status === "ok" ? (
          <>
            <h1 className="font-heading text-2xl font-semibold tracking-tight text-ink">
              Stripe connected
            </h1>
            <p className="mt-2 text-sm text-fade">
              Connection #{connectionId ?? "—"} is active. Redirecting in {seconds}s…
            </p>
            <Button className="mt-6 w-full" onClick={() => router.push("/connections")}>
              Continue
            </Button>
          </>
        ) : (
          <>
            <h1 className="font-heading text-2xl font-semibold tracking-tight text-ink">
              Couldn&apos;t connect
            </h1>
            <p className="mt-2 text-sm text-mute">
              {reason || "The OAuth flow did not complete."}
            </p>
            <Button
              variant="outline"
              className="mt-6 w-full"
              onClick={() => router.push("/connections")}
            >
              Back to connections
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

function Pending() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-base">
      <div className="font-heading text-sm text-mute">Finishing connection…</div>
    </div>
  );
}
