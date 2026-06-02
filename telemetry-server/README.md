# Escriba telemetry server

A tiny, free Cloudflare Worker + D1 database that receives anonymous usage pings
from the Escriba app and gives you aggregate numbers (users, transcriptions,
hours) for your resume. It's completely optional — Escriba works without it, and
it only ever receives the anonymous data described in [`../PRIVACY.md`](../PRIVACY.md).

## Why Cloudflare

This matches the stack you already use, the free tier is far more than enough for
this, and it's a few minutes to stand up.

## Deploy

```bash
cd telemetry-server
npm install -g wrangler          # if you don't have it

# 1. create the database
npx wrangler d1 create escriba-telemetry
#    -> copy the database_id it prints into wrangler.toml

# 2. load the table
npx wrangler d1 execute escriba-telemetry --file=schema.sql --remote

# 3. set a shared key (light anti-spam; not a personal secret)
npx wrangler secret put ESCRIBA_KEY
#    -> type any string, e.g. a random word

# 4. deploy
npx wrangler deploy
```

Wrangler prints your Worker URL (something like
`https://escriba-telemetry.<you>.workers.dev`).

## Point the app at it

On the machine running Escriba, set these before launching (or add them to the
launcher script):

```bash
export ESCRIBA_TELEMETRY_URL="https://escriba-telemetry.<you>.workers.dev"
export ESCRIBA_TELEMETRY_KEY="<the key you set in step 3>"
```

If these aren't set, the app sends nothing — telemetry is off by default.

## Read your numbers

```bash
curl https://escriba-telemetry.<you>.workers.dev/stats
# {"users":12,"transcriptions":210,"hours":430.5}
```

Those are the figures you can drop into your resume bullet.
