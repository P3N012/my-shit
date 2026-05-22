import {
  ArrowLeft,
  CreditCard,
  Eye,
  KeyRound,
  Lock,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Security — InsightPlus",
  description:
    "How InsightPlus handles your Stripe data: read-only access, encryption at rest, and data you can delete any time.",
};

const CHIPS = [
  { icon: Eye, label: "Read-only" },
  { icon: Lock, label: "Encrypted at rest" },
  { icon: CreditCard, label: "No card data" },
  { icon: Trash2, label: "Disconnect deletes all" },
];

const GUARANTEES = [
  {
    icon: Eye,
    title: "Read-only access",
    body: (
      <>
        You connect with a <strong className="text-ink">read-only restricted key</strong> you
        create in your own Stripe dashboard. InsightPlus can read your customers,
        subscriptions, and charges — it can <strong className="text-ink">never</strong> create
        charges, issue refunds, or change anything. Full secret keys are rejected outright.
      </>
    ),
  },
  {
    icon: KeyRound,
    title: "You stay in control",
    body: (
      <>
        You authorize inside Stripe — we never see your password. Revoke access any time from{" "}
        <strong className="text-ink">your</strong> Stripe dashboard; you don&apos;t need us to
        do it.
      </>
    ),
  },
  {
    icon: CreditCard,
    title: "We never touch card data",
    body: (
      <>
        Card numbers live with Stripe, a PCI-certified processor — they never reach our
        servers. We mirror only metadata: amounts, statuses, plan names, and customer
        names/emails.
      </>
    ),
  },
  {
    icon: Lock,
    title: "Encrypted at rest",
    body: (
      <>
        The credential for your connected account is{" "}
        <strong className="text-ink">encrypted at rest</strong> (AES, via Fernet). Even our own
        API never returns it — a leaked database row is useless without the key.
      </>
    ),
  },
  {
    icon: Trash2,
    title: "Disconnect deletes everything",
    body: (
      <>
        Disconnect an account and we <strong className="text-ink">cascade-delete</strong> all
        of its synced customers, subscriptions, and charges. No leftovers.
      </>
    ),
  },
  {
    icon: Sparkles,
    title: "Try before you connect",
    body: (
      <>
        A one-click demo runs on fully synthetic data, so you can evaluate the entire product
        before connecting anything real.
      </>
    ),
  },
];

export default function SecurityPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-base text-mute">
      {/* Ambient glows so the page isn't a flat black slab. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[36rem] w-[36rem] -translate-x-1/2 rounded-full opacity-25 blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(255,107,53,0.45), transparent)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-48 -right-40 h-[34rem] w-[34rem] rounded-full opacity-20 blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(255,134,89,0.4), transparent)",
        }}
      />

      {/* Top bar */}
      <header className="relative flex items-center justify-between px-6 py-5 lg:px-12">
        <Link
          href="/"
          className="text-ember font-heading text-lg font-bold tracking-tight"
        >
          InsightPlus
        </Link>
        <Link href="/login" className="text-sm font-semibold text-mute hover:text-ink">
          Sign in
        </Link>
      </header>

      <main className="relative mx-auto max-w-4xl px-6 pb-24">
        <Link
          href="/login"
          className="inline-flex items-center gap-2 text-sm font-semibold text-mute hover:text-ink"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>

        {/* Hero */}
        <section className="mx-auto mt-10 max-w-2xl text-center lg:mt-14">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/15">
            <ShieldCheck className="h-7 w-7 text-accent" />
          </span>
          <h1 className="mt-6 font-heading text-4xl font-bold tracking-tight text-ink lg:text-5xl">
            Your revenue data, <span className="text-ember">handled with care</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed lg:text-lg">
            Connecting financial data to a product you don&apos;t know is a big ask. So
            here&apos;s exactly how InsightPlus handles it — in plain English, nothing hidden.
          </p>

          {/* Quick-scan chips */}
          <div className="mt-7 flex flex-wrap items-center justify-center gap-2.5">
            {CHIPS.map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="inline-flex items-center gap-1.5 rounded-full border border-line bg-panel px-3 py-1.5 text-xs font-semibold text-mute"
              >
                <Icon className="h-3.5 w-3.5 text-accent" />
                {label}
              </span>
            ))}
          </div>
        </section>

        {/* Guarantees */}
        <section className="mt-14 grid gap-4 sm:grid-cols-2">
          {GUARANTEES.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-xl border border-line bg-panel p-6 transition-colors hover:border-accent/30"
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/15">
                <Icon className="h-5 w-5 text-accent" />
              </span>
              <h2 className="mt-4 font-heading text-lg font-semibold text-ink">
                {title}
              </h2>
              <p className="mt-2 text-sm leading-relaxed">{body}</p>
            </div>
          ))}
        </section>

        {/* CTA */}
        <section className="mt-6 rounded-xl border border-line bg-panel p-8 text-center">
          <h2 className="font-heading text-xl font-semibold text-ink">
            See it before you trust it
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed">
            Explore a fully populated demo account — no signup, no connection, nothing to lose.
          </p>
          <Link
            href="/login"
            className="mt-5 inline-flex items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-accent-fg transition-opacity hover:opacity-90"
          >
            <Sparkles className="h-4 w-4" />
            Try the live demo
          </Link>
        </section>

        {/* Contact / footer */}
        <footer className="mt-10 border-t border-line pt-6 text-sm">
          <p>
            Built by <span className="font-semibold text-ink">P3N012</span>. Security questions
            or disclosures:{" "}
            <a
              className="font-semibold text-accent hover:underline"
              href="mailto:p3n012@gmail.com"
            >
              p3n012@gmail.com
            </a>
            .
          </p>
        </footer>
      </main>
    </div>
  );
}
