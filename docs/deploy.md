# Deploy Pitwall (free stack)

```
 browser ──▶ Vercel: web/ (Next.js)  ──HTTPS──▶  Render: backend/ (FastAPI, Docker)
 Telegram ──webhook───────────────────────────▶   ├─▶ Neo4j AuraDB Free  (graph)
                                                  ├─▶ Supabase Postgres  (agent memory, spend ledger, locks)
                                                  └─▶ OpenF1              (telemetry, loaded on first use)
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

## 2. Supabase Postgres

Create a project at <https://supabase.com/dashboard>. Under **Connect**, copy the **Session pooler** URI
(port 5432). The direct URI is IPv6-only and Render cannot reach it. The API creates its own tables.

## 3. Render (API)

1. <https://dashboard.render.com> → **New** → **Blueprint** → pick the `pitwall` repo. Render reads `render.yaml`.
2. Fill in the secrets:

   | Key | Value |
   |---|---|
   | `PITWALL_OPENAI_API_KEY` | your OpenAI key |
   | `PITWALL_NEO4J_URI` | `neo4j+s://<id>.databases.neo4j.io` |
   | `PITWALL_NEO4J_PASSWORD` | the Aura password |
   | `PITWALL_DATABASE_URL` | the Supabase session pooler URI |
   | `PITWALL_API_URL` | `https://pitwall-api.onrender.com` (the service URL) |
   | `PITWALL_WEB_URL` | the Vercel URL from step 4 |
   | `PITWALL_CORS_ORIGINS` | `["<the Vercel URL>"]` (a JSON list) |
   | `PITWALL_TELEGRAM_BOT_TOKEN` | from step 5, or leave empty |

3. Check `https://pitwall-api.onrender.com/health` returns `"agent": true`.

## 4. Vercel (web)

<https://vercel.com/new> → import the repo → **Root Directory** `web` → add the environment variable
`NEXT_PUBLIC_API_URL=https://pitwall-api.onrender.com` → **Deploy**. Then put the Vercel URL into
`PITWALL_WEB_URL` and `PITWALL_CORS_ORIGINS` on Render.

## 5. Telegram bot

1. In Telegram, message [@BotFather](https://t.me/BotFather): `/newbot`, name it `Pitwall`, pick a username.
2. `/setuserpic` → send `brand/telegram-avatar.png`.
3. `/setdescription` → "Your race engineer for F1 2026: results, teammates and lap replays from a knowledge graph."
4. Put the token in `PITWALL_TELEGRAM_BOT_TOKEN` on Render. On start, the API registers the webhook
   (with the generated secret) and a menu button that opens the web app.

Local testing without a public URL: `uv run python -m pitwall.telegram` (long polling).

## Check it works

```bash
curl -s https://pitwall-api.onrender.com/health
curl -N https://pitwall-api.onrender.com/ask -H 'content-type: application/json' \
  -d '{"question": "Who leads the championship?"}'
```
