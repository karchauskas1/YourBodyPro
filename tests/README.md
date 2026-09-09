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

Payment checks are serialized per user within the API process. This matches the current single-process deployment; multiple API workers would require database-level coordination before relying on the same concurrency guarantee.
