/**
 * Escriba telemetry endpoint — a tiny Cloudflare Worker backed by D1.
 *
 * It receives anonymous usage pings from the Escriba app and lets you read
 * aggregate numbers for your resume. It stores ONLY what PRIVACY.md discloses:
 * an anonymous install id, an event name, minutes, version, and a timestamp.
 * No audio, no transcripts, no personal data.
 *
 *   POST /            { install_id, event, minutes, version }  + header x-escriba-key
 *   GET  /stats       -> { users, transcriptions, hours }      (public, read-only)
 *
 * Deploy:
 *   1. npm create cloudflare   (or use an existing Workers project)
 *   2. Create a D1 db:         npx wrangler d1 create escriba-telemetry
 *   3. Put the returned id in wrangler.toml, then load the schema:
 *                              npx wrangler d1 execute escriba-telemetry --file=schema.sql
 *   4. Set your secret:        npx wrangler secret put ESCRIBA_KEY
 *   5. npx wrangler deploy
 * Then point the app at it:
 *   export ESCRIBA_TELEMETRY_URL="https://<your-worker>.workers.dev"
 *   export ESCRIBA_TELEMETRY_KEY="<the key you set>"
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, x-escriba-key",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors });
    }

    // ---- read aggregate stats (safe to be public) ----
    if (request.method === "GET" && url.pathname === "/stats") {
      const row = await env.DB.prepare(
        `SELECT COUNT(DISTINCT install_id) AS users,
                COUNT(*)                  AS transcriptions,
                ROUND(COALESCE(SUM(minutes),0)/60.0, 1) AS hours
         FROM events WHERE event = 'transcription_complete'`
      ).first();
      return Response.json(row || { users: 0, transcriptions: 0, hours: 0 }, { headers: cors });
    }

    // ---- ingest a ping ----
    if (request.method === "POST" && url.pathname === "/") {
      // light abuse protection: a shared key, not a user secret
      if (env.ESCRIBA_KEY && request.headers.get("x-escriba-key") !== env.ESCRIBA_KEY) {
        return new Response("forbidden", { status: 403, headers: cors });
      }
      let body;
      try { body = await request.json(); } catch { return new Response("bad json", { status: 400, headers: cors }); }

      const install_id = String(body.install_id || "").slice(0, 64);
      const event = String(body.event || "").slice(0, 40);
      const minutes = Math.max(0, Math.min(Number(body.minutes) || 0, 600)); // clamp
      const version = String(body.version || "").slice(0, 20);
      if (!install_id || !event) {
        return new Response("missing fields", { status: 400, headers: cors });
      }

      await env.DB.prepare(
        `INSERT INTO events (install_id, event, minutes, version) VALUES (?, ?, ?, ?)`
      ).bind(install_id, event, minutes, version).run();

      return Response.json({ ok: true }, { headers: cors });
    }

    return new Response("Escriba telemetry", { headers: cors });
  },
};
