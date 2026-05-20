# InsightPlus — frontend

Next.js 14 (App Router) + TypeScript + Tailwind. Ports the **"Monochrome
Authority"** direction from the Claude Design handoff and wires it to
the FastAPI backend.

## Stack

- **Framework**: Next.js 14, App Router, TypeScript strict
- **Styling**: Tailwind CSS with theme tokens baked into `tailwind.config.ts`
- **Components**: shadcn-shaped primitives in `components/ui/*`
  (Radix Slot + class-variance-authority + Tailwind). No CLI install
  step — the components live in-tree.
- **Data**: TanStack Query against `/api/v1/*`
- **Fonts**: `next/font/google` → JetBrains Mono (heading) + IBM Plex Sans (body)

## Run

```bash
pnpm install
cp .env.example .env.local         # optional — defaults assume backend at localhost:8000
pnpm dev                           # http://localhost:3000
```

You'll need the backend running (`uvicorn main:app --reload` from the
repo root, or `docker compose up`). The Next.js dev server rewrites
`/api/v1/*` to the backend, so cookies/CORS are not a concern in dev.

## Project layout

```
frontend/
├── app/
│   ├── layout.tsx               root layout, fonts, providers
│   ├── page.tsx                 redirect to /login or /dashboard
│   ├── login/page.tsx           login + register
│   ├── oauth/stripe/page.tsx    public Stripe Connect callback landing
│   └── (app)/                   authed app shell
│       ├── layout.tsx           sidebar + auth guard
│       ├── dashboard/           KPI cards, MRR chart, MRR movements, activity feed, AI review
│       ├── connections/         list, sync, OAuth start, delete
│       ├── ai-assistant/        chat against /ai/messages
│       ├── usage/               wired to /ai/usage
│       └── settings/            account + workspace info
├── components/
│   ├── auth-context.tsx         token storage, /auth/me hydrate, login/logout
│   ├── providers.tsx            TanStack Query + AuthProvider
│   ├── sidebar.tsx              nav, org switcher, user dropdown
│   ├── kpi-card.tsx, mrr-chart.tsx
│   └── ui/                      button, card, input, label, badge
├── lib/
│   ├── api.ts                   single fetch wrapper with refresh-token rotation
│   ├── auth-storage.ts          localStorage tokens + active-org
│   ├── format.ts                money + relative-time
│   ├── types.ts                 mirrors backend pydantic shapes
│   └── utils.ts                 cn()
└── tailwind.config.ts           Direction 1 design tokens
```

## Design tokens (Direction 1 — Monochrome Authority)

| Token | Value | Use |
|---|---|---|
| `bg-base` | `#0a0a0a` | App background |
| `bg-panel` | `#000000` | Cards, sidebar |
| `border-line` | `#1a1a1a` | Hairlines |
| `text-ink` | `#ffffff` | Primary text |
| `text-mute` | `#888` | Secondary |
| `text-fade` | `#666` | Tertiary, captions |
| `bg-accent` / `text-accent` | `oklch(0.65 0.24 142)` | Cyan-green highlight |
| `font-heading` | JetBrains Mono | KPIs, headings, labels, badges |
| `font-sans` | IBM Plex Sans | Body, table cells, prose |

## What's wired vs. what's placeholder

| Surface | Backed by |
|---|---|
| Login / Register | `POST /auth/login`, `POST /auth/register`, `GET /auth/me` |
| Org switcher | memberships from `GET /auth/me`; persisted in localStorage |
| Connections list | `GET /connections` |
| Connect Stripe | `POST /connections/stripe/connect` → browser redirect to Stripe |
| Sync now | `POST /connections/{id}/sync` |
| Disconnect | `DELETE /connections/{id}` |
| AI Assistant | `POST /ai/messages` (single-shot; SSE streaming TBD) |
| Usage | `GET /ai/usage` |
| Dashboard KPIs + MRR chart + top customers | `GET /dashboard/overview`, `/trends`, `/top-customers` — computed in Python from the mirrored Stripe tables. |
| MRR movements chart + activity feed | `GET /dashboard/movements`, `/dashboard/activity` — per-month new vs. churned MRR and a recent-events feed. |
| AI weekly review card | `GET /ai/reviews/latest` + `POST /ai/reviews/generate` — Claude reads the past 7 days of aggregates and writes a 3-paragraph commentary. |

## Auth model on the client

- Tokens live in `localStorage` (`ip.access_token`, `ip.refresh_token`).
  Fine for an MVP; for production swap to httpOnly cookies via a Next.js
  Route Handler proxy.
- `lib/api.ts` is the single fetch wrapper. On any 401 it calls
  `POST /auth/refresh` once, replays the original request, and surfaces
  an `AuthRequiredError` if that also fails. The `AuthProvider` watches
  for this and redirects to `/login`.
- Active org id is persisted in `localStorage` too and attached as the
  `X-Organization-Id` header on every org-scoped request.

## Known gaps / next up

- Streaming responses for the AI Assistant (SSE from `/ai/messages/stream`).
- Form-validation polish (zod + react-hook-form).
- E2E tests (Playwright).
