# Deploying InsightPlus

Three pieces, in this order. The chicken-and-egg traps in steps 2 and 3
are real — the order below avoids them.

## Stack

| Piece     | Where        | Free tier?                         |
| --------- | ------------ | ---------------------------------- |
| Postgres  | **Neon**     | Yes                                |
| Backend   | **Render**   | Yes (sleeps after 15 min idle)     |
| Frontend  | **Vercel**   | Yes                                |
| Redis     | *Skip*       | Not needed for the current UI      |

Redis would be required only if you start enqueueing through
`POST /ai/jobs`. The synchronous `/ai/messages` works without it, and
the "Sync now" button on Connections falls back to inline sync. Add
Upstash later if you start using async jobs.

---

## 1 · Postgres on Neon

1. Sign in to [neon.tech](https://neon.tech) → create a project (any
   region; closest to your Render region is best).
2. The dashboard shows a **Connection string**. Copy it. It looks like:
   ```
   postgresql://USER:PASSWORD@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
   ```
3. **Replace the `postgresql://` prefix with `postgresql+psycopg2://`.**
   SQLAlchemy needs the explicit driver hint. The full thing should be:
   ```
   postgresql+psycopg2://USER:PASSWORD@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
   ```
4. Hold onto this string — you'll paste it into Render's `DATABASE_URL`
   in step 2.

## 2 · Backend on Render

1. **Render → New → Blueprint**. Connect your GitHub account if you
   haven't. Pick the `my-shit` repo. Render will detect `render.yaml`
   and offer to deploy it.
2. Click **Apply**. Render starts building. The `ACCESS_TOKEN_SECRET`
   and `REFRESH_TOKEN_SECRET` are minted automatically; the
   `sync: false` ones (DATABASE_URL, CORS_ORIGINS, etc.) sit empty
   until you fill them in.
3. In **Environment → Add Environment Variable** (or edit the missing
   ones), set:
   - `DATABASE_URL` → the Neon string from step 1.
   - Leave the rest blank for now — you'll fill them after step 3.
4. Trigger a manual deploy. The `release: alembic upgrade head` line
   runs *before* the web process gets traffic, so your schema lands.
   On first deploy this creates every table.
5. Once "Live" shows in the dashboard, copy your Render URL. It'll
   look like:
   ```
   https://insightplus-backend.onrender.com
   ```
6. Test:
   ```
   curl https://insightplus-backend.onrender.com/health
   # {"status":"healthy"}
   ```
   If you get HTTP 503 or a long delay, the service is asleep — wait
   30–50s for the cold start, then retry.

## 3 · Frontend on Vercel

1. **Vercel → Add New → Project**. Pick the `my-shit` repo.
2. In the configure step, **set the Root Directory to `frontend`**.
   Vercel auto-detects Next.js after that.
3. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_BASE_URL` = your Render URL (e.g.
     `https://insightplus-backend.onrender.com`). No trailing slash.
4. Click **Deploy**. ~60 seconds.
5. Once it's up, you'll get a Vercel URL like:
   ```
   https://my-shit.vercel.app
   ```
   (Or whatever Vercel auto-generates from the repo name. You can rename
   in Settings → Domains.)

## 4 · Wire the two together

Now that both URLs exist, go back to Render and **update the env
vars that depend on the deployed URLs**:

```
CORS_ORIGINS           = https://my-shit.vercel.app
```

If you set up Stripe Connect in dev, also update:

```
STRIPE_OAUTH_REDIRECT_URI = https://insightplus-backend.onrender.com/api/v1/connections/stripe/callback
STRIPE_OAUTH_SUCCESS_URL  = https://my-shit.vercel.app/oauth/stripe?stripe=ok
STRIPE_OAUTH_FAILURE_URL  = https://my-shit.vercel.app/oauth/stripe?stripe=error
```

…and **add the new `STRIPE_OAUTH_REDIRECT_URI` to Stripe Connect**:
Stripe Dashboard → Settings → Connect → Integration → Redirects.
Stripe is strict about exact byte-match — including the protocol and
no trailing slash.

Render restarts the service whenever you change env vars. ~30s.

## 5 · Optional: Anthropic key

If you want the AI Assistant + AI weekly review to work in production:
- Render → Environment → set `ANTHROPIC_API_KEY` to a key from
  `console.anthropic.com`. Service restarts automatically.

Without it, the AI endpoints return 503 with a clear "AI is not
configured" message; nothing else breaks.

## 6 · First run

1. Open the Vercel URL.
2. Sign up — registration auto-creates a personal org with you as
   owner. Same flow as local.
3. (Optional) Two ways to populate the dashboard:
   - Connect a real Stripe account and click Sync.
   - Use the Render shell (Render → your service → Shell tab) and run
     `python scripts/seed_db.py && python scripts/seed_demo_data.py`.
     The seed_db users (`test@insightplus.com / password123`) will
     also work; the demo data will appear under that account.

---

## Known quirks of this stack

- **Render free tier sleeps after 15 minutes of inactivity.** First
  request after a sleep takes 30–50 seconds. Fine for portfolio
  demos; not for production traffic. Upgrade to Starter ($7/mo) to
  keep it always-on.
- **Neon free tier pauses the compute after 5 minutes of idle and
  resumes on first connection** (~1s). Less disruptive than Render's
  sleep.
- **`autoDeploy: true` in `render.yaml` means every push to `main`
  triggers a deploy.** Convenient; also means a bad push immediately
  becomes a bad deploy. The pre-deploy `alembic upgrade head` will
  bail out before traffic switches if the migration fails, but it
  won't catch app-logic bugs.
- **CORS:** if the dashboard works for you but a reviewer hits CORS
  errors from a different domain, you set `CORS_ORIGINS` to a single
  URL. Add multiple comma-separated values to allow more origins.

## Updates after the initial deploy

Push to `main`. Render rebuilds and redeploys automatically. Vercel
does the same. No further manual steps unless you change the env
vars.
