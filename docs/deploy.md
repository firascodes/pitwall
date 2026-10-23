# Deploy Pitwall on Vercel

Two Vercel projects from this one repo, plus two free databases:

```
 browser ──▶ Vercel project "pitwall"      (root: web/, Next.js)
                 │ HTTPS, SSE
                 ▼
            Vercel project "pitwall-api"  (root: backend/, FastAPI as a Python function)
 Telegram ──webhook──┘   ├─▶ Neo4j AuraDB Free   (the graph)
                         ├─▶ Supabase            (Postgres: agent memory, quotas, spend ledger; Auth)
                         └─▶ OpenF1               (telemetry, cached in /tmp on first use)
```

Cost: $0 a month for hosting. LLM spend is capped by `PITWALL_DAILY_USD_CAP` (default $0.25 a day).
Also set a hard monthly limit in the OpenAI dashboard.

## 1. Neo4j AuraDB Free

1. Create a free instance at <https://console.neo4j.io>. Save the password: Aura shows it once.
2. Copy the local graph into it (about a minute):

   ```bash
   cd backend
   PITWALL_TARGET_NEO4J_URI='neo4j+s://<id>.databases.neo4j.io' \
   PITWALL_TARGET_NEO4J_PASSWORD='<aura password>' \
   uv run pitwall-copy-graph
   ```

AuraDB Free pauses after 3 days with no queries. Resume it in the console if the API says the graph is down.

## 2. Supabase

1. Create a project at <https://supabase.com/dashboard>. Under **Connect**, copy the **Transaction pooler**
   URI (port 6543): serverless functions open many short connections, which is what that pooler is for.
   The API creates its own tables.
2. Sign-in (guests get one question a day per network; signed-in users get 30):
   - **Authentication → URL Configuration:** Site URL = the web URL, and add `<web URL>/chat` to Redirect URLs.
   - **Authentication → Sign In / Providers:** email links are on by default. For Google and GitHub, create an
     OAuth app with each provider, using the callback URL Supabase shows.
   - **Project Settings → API Keys:** copy the **publishable** key (never the secret key).
   - **Project Settings → JWT Keys:** the project must sign with an asymmetric key (ECC P-256, the default).

## 3. The API on Vercel

New project → import `firascodes/pitwall` → **Root Directory** `backend`. Vercel finds `app.py` and installs
from `uv.lock`. Environment variables:

| Key | Value |
|---|---|
| `PITWALL_OPENAI_API_KEY` | your OpenAI key |
| `PITWALL_NEO4J_URI` | `neo4j+s://<id>.databases.neo4j.io` |
| `PITWALL_NEO4J_PASSWORD` | the Aura password |
| `PITWALL_DATABASE_URL` | the Supabase transaction pooler URI |
| `PITWALL_SUPABASE_URL` | `https://<ref>.supabase.co` (turns on the guest limit and sign-in) |
| `PITWALL_IP_SALT` | any long random string |
| `PITWALL_API_URL` | this project's URL, e.g. `https://pitwall-api.vercel.app` |
| `PITWALL_WEB_URL` | the web project's URL |
| `PITWALL_CORS_ORIGINS` | `["<the web URL>"]` (a JSON list) |
| `PITWALL_TELEGRAM_BOT_TOKEN` | from step 5, or leave it out |
| `PITWALL_TELEGRAM_WEBHOOK_SECRET` | any long random string, if the bot is on |

Check `https://<api>/health` returns `"agent": true`.

## 4. The web app on Vercel

New project → the same repo → **Root Directory** `web`. Environment variables:

| Key | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | the API URL from step 3 |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://<ref>.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | the publishable key |
| `NEXT_PUBLIC_TELEGRAM_BOT` | the bot username, without `@` |

## 5. Telegram bot

1. In Telegram, message [@BotFather](https://t.me/BotFather): `/newbot`, name it `Pitwall`, pick a username.
2. `/setuserpic` → send `brand/telegram-avatar.png`.
3. Put the token in the API project and redeploy. On start, the API registers the webhook (with the secret)
   and a menu button that opens the web app. On Vercel the webhook answers inline, because a function can stop
   once it has responded.

Local testing without a public URL: `uv run python -m pitwall.telegram` (long polling).

## Check it works

```bash
curl -s https://<api>/health
curl -N https://<api>/ask -H 'content-type: application/json' -d '{"question": "Who leads the championship?"}'
```

## Other hosts

`backend/Dockerfile` runs the same API on any container host; `render.yaml` is a ready Render blueprint.
