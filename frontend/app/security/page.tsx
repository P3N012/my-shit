import {
  ArrowLeft,
  CreditCard,
  Eye,
  Github,
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
    "How InsightPlus handles your Stripe data: read-only access, encryption at rest, and an open-source codebase you can audit.",
};

const REPO = "https://github.com/P3N012/insightplus";

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
        You authorize inside Stripe — we never see your password. Revoke our access any time
        from <strong className="text-ink">your</strong> Stripe dashboard, and you don&apos;t
        need us to do it.
      </>
    ),
  },
  {
    icon: CreditCard,
    title: "We never touch card data",
    body: (
      <>
        Card numbers live with Stripe, a PCI-certified processor — they never reach our
        servers. We only mirror metadata: amounts, statuses, plan names, and customer
        names/emails.
      </>
    ),
  },
  {
    icon: Lock,
    title: "Encrypted at rest",
    body: (
      <>
        The credential for your connected account is <strong className="text-ink">encrypted
        at rest</strong> (AES, via Fernet) in our database. Even our own API never returns it.
        A leaked database row is useless without the key.
      </>
    ),
  },
  {
    icon: Trash2,
    title: "Disconnect deletes everything",
    body: (
      <>
        Disconnect an account and we <strong className="text-ink">cascade-delete</strong> all
        of its synced customers, subscriptions, and charges from our database. No leftovers.
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
    <div className="min-h-screen bg-base text-mute">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-5 lg:px-12">
        <Link
          href="/"
          className="text-ember font-heading text-lg font-bold tracking-tight"
        >
          InsightPlus
        </Link>
        <Link
          href="/login"
          className="text-sm font-semibold text-mute hover:text-ink"
        >
          Sign in
        </Link>
      </header>

      <main className="mx-auto max-w-3xl px-6 pb-24 pt-8 lg:pt-16">
        <Link
          href="/login"
          className="inline-flex items-center gap-2 text-sm font-semibold text-mute hover:text-ink"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>

        <div className="mt-8 flex items-center gap-3">
          <span className="flex h-11 w-11 flex-none items-center justify-center rounded-lg bg-accent/15">
            <ShieldCheck className="h-6 w-6 text-accent" />
          </span>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-ink lg:text-4xl">
            Security &amp; trust
          </h1>
        </div>

        <p className="mt-5 text-base leading-relaxed">
          Connecting your revenue data to a product you don&apos;t know is a big ask. So
          here&apos;s exactly how InsightPlus handles it — in plain English, with nothing
          hidden. InsightPlus is an independent product, not a large company; the difference is
          that the entire codebase is open, so you can verify every claim on this page yourself.
        </p>

        {/* Guarantees */}
        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {GUARANTEES.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-lg border border-line bg-panel p-5"
            >
              <div className="flex items-center gap-2.5">
                <Icon className="h-5 w-5 flex-none text-accent" />
                <h2 className="font-heading text-base font-semibold text-ink">
                  {title}
                </h2>
              </div>
              <p className="mt-3 text-sm leading-relaxed">{body}</p>
            </div>
          ))}
        </div>

        {/* Open source */}
        <div className="stripe-ember mt-10 overflow-hidden rounded-lg border border-line bg-panel p-6">
          <div className="flex items-center gap-2.5">
            <Github className="h-5 w-5 text-accent" />
            <h2 className="font-heading text-lg font-semibold text-ink">
              Don&apos;t take our word for it
            </h2>
          </div>
          <p className="mt-3 text-sm leading-relaxed">
            The entire codebase is public. You can read the exact code that touches your data:
          </p>
          <ul className="mt-4 space-y-2 text-sm">
            <li>
              <a
                className="font-semibold text-accent hover:underline"
                href={`${REPO}/blob/main/app/core/crypto.py`}
                target="_blank"
                rel="noreferrer"
              >
                app/core/crypto.py
              </a>{" "}
              — how credentials are encrypted at rest
            </li>
            <li>
              <a
                className="font-semibold text-accent hover:underline"
                href={`${REPO}/blob/main/app/services/stripe_apikey_service.py`}
                target="_blank"
                rel="noreferrer"
              >
                app/services/stripe_apikey_service.py
              </a>{" "}
              — read-only key handling (and why secret keys are rejected)
            </li>
          </ul>
          <a
            className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-ink hover:text-accent"
            href={REPO}
            target="_blank"
            rel="noreferrer"
          >
            <Github className="h-4 w-4" />
            View the full repository
          </a>
        </div>

        {/* Contact */}
        <div className="mt-10 border-t border-line pt-6 text-sm">
          <p>
            Built by{" "}
            <a
              className="font-semibold text-ink hover:text-accent"
              href="https://github.com/P3N012"
              target="_blank"
              rel="noreferrer"
            >
              @P3N012
            </a>
            . Security questions or disclosures:{" "}
            <a
              className="font-semibold text-accent hover:underline"
              href="mailto:p3n012@gmail.com"
            >
              p3n012@gmail.com
            </a>
            .
          </p>
        </div>
      </main>
    </div>
  );
}
