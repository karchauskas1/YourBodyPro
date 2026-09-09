# Payment and subscription regression checks

Backend checks (Python 3.10+):

```sh
python -m pip install -r webapp/backend/requirements.txt
python -m unittest discover -s tests -v
```

Browser checks:

```sh
cd webapp/frontend
npm ci
npm run test:e2e
```

Local browser tests use installed Google Chrome at an iPhone-sized viewport. CI installs Chromium automatically. These tests check the built frontend with mocked Telegram and payment responses; they do not send messages, create payments, or use production credentials. They do not simulate Telegram's native iOS WebView or real banking transactions.

The workflow in `.github/workflows/payment-access.yml` runs both suites on pushes and pull requests.

`test_webapp_origins.py` also exercises the real FastAPI CORS middleware with the current HTTPS origin (including port 9443) and the legacy Telegram entrypoint. Unlike mocked browser API responses, this catches a rejected preflight before authentication runs. The legacy host redirects HTML navigations to the VPS; its exact origin remains allowed for already-open windows. Static asset requests are not redirected so cached old HTML can still load its matching bundle.

Covered failure paths include successful and repeated checks, concurrent checks for the same user, already-active subscriptions, pending/canceled payments, mismatched payment owners, provider outages, database activation failures, and Telegram invite timeouts. Browser checks cover active access, missing subscription, authentication and network failures, invalid responses, retry recovery, stale responses from an earlier sign-in attempt, and response bodies that never finish downloading.

Payment settlement uses a separate SQLite transaction shared by the bot and API. Tests cover independent concurrent connections, ownership, rollback, stale pending responses, duplicate saves, and retaining existing subscription days. Automatic renewal retries reuse the provider idempotency key for the same user and subscription period; they never make real charges in tests.

`test_tracker_integration.py` runs real FastAPI routes against a temporary SQLite database initialized from the bot's actual schema. It covers profile/settings, food/photo/history/calendar, sleep, workouts, summaries, achievements, subscription guards, and admin reads. Only external AI, payment and messaging calls are replaced.

`tracker-flows.spec.ts` opens all 16 main screens at a mobile viewport and checks runtime errors, layout overflow, historical food access, slow analysis, and retry after an AI failure. Its synthetic response fixtures come from the real routes; refresh them with `python tests/generate_browser_fixtures.py`.

Run `node --test webapp/gateway/server.test.cjs` for the HTTPS gateway checks. They use temporary certificates and a local upstream, including a real 16-second response to catch the former 15-second disconnect.

Production uses `OUTBOUND_PROXY_URL=socks5://127.0.0.1:1080` for Telegram and OpenRouter, matching the bot's existing network route. Install the backend requirements with SOCKS support. Keep that proxy unset for ordinary local development. HTTPX 0.25 and current HTTPX proxy argument names are both supported.
