/**
 * Minimal reverse proxy for NASA DONKI, meant to run on Cloudflare Workers'
 * free tier. You deploy this yourself — no third-party service is trusted
 * with your API key or your requests.
 *
 * What it does: forwards every request it receives to the same path/query
 * on https://api.nasa.gov/DONKI. Nothing else. Use this only if api.nasa.gov
 * is unreachable from your own network/region — the app's "Текущая
 * обстановка" mode never calls NASA at all, so this only matters for
 * historical mode and the /api/experiment endpoint.
 *
 * Deploy (free, no credit card needed for the free plan):
 *   1. Go to https://dash.cloudflare.com/ , sign up/sign in.
 *   2. Workers & Pages -> Create -> Create Worker.
 *   3. Replace the default script with the contents of this file, Save & Deploy.
 *   4. Copy the worker's URL (looks like https://<name>.<subdomain>.workers.dev).
 *   5. In backend/.env set:
 *        EVA_DONKI_BASE_URL=https://<name>.<subdomain>.workers.dev
 *      (Do NOT include a trailing slash or "/DONKI" — the app already adds
 *      the endpoint path itself, e.g. "/notifications".)
 */
export default {
  async fetch(request) {
    const incoming = new URL(request.url);
    const upstream = "https://api.nasa.gov/DONKI" + incoming.pathname + incoming.search;

    const response = await fetch(upstream, {
      method: request.method,
      headers: { "User-Agent": "donki-proxy-worker/1.0" },
    });

    return new Response(response.body, {
      status: response.status,
      headers: response.headers,
    });
  },
};
