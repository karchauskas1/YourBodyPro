# Functional audit — 9 September 2026

The audit covered the bot, FastAPI, SQLite, the mobile web app, HTTPS gateway, old entrypoints, and external service connectivity. Production customer records were not used for test writes. Payments and outgoing messages were mocked in automated tests; no test charges or customer messages were sent.

## Findings and fixes

- Direct connections from the VPS to Telegram timed out and OpenRouter returned HTTP 403. Both services worked through the SOCKS connection already used by the bot. API and habit integrations now share that configurable connection.
- The browser stopped ordinary requests after 12 seconds and the HTTPS gateway disconnected after 15 seconds, while AI requests allowed 20–45 seconds. Analysis and payment checks now have a 60-second browser deadline and the gateway allows 75 seconds.
- Failed AI responses could be silently saved as food analysis or cached indefinitely as summaries. Failed web app analysis now returns a retryable error before writing a food entry. Failed summaries are not cached, and old cached errors are ignored.
- Daily and weekly summaries were not invalidated when the underlying food, sleep or workout records changed. A changed day now invalidates its affected summaries. Weekly reviews also recognize weeks containing only workouts.
- Food detail pages searched only today's entries, so opening an earlier day's record failed. A dedicated authenticated endpoint now loads the requested record by ID and owner.
- Updating a missing or another user's food record could report success despite changing nothing. Those requests now return 404.
- Bot payment checks did not validate the account in payment metadata and could reapply an old successful payment. The bot and API now settle payments in one SQLite transaction, with ownership checks and protection against retries from different processes. Paid and configured grace days are added while preserving existing access.
- A stale pending result could overwrite a successful payment status. Successful statuses are now preserved; repeated payment saves do not duplicate rows.
- Recurring payment retries used new provider request IDs after a lost response. They now reuse a stable idempotency key for the same subscription period, persist pending payments, and use the same atomic settlement as manual checks.
- Creating a payment blocked the API event loop. The provider request now runs off that loop. A provider creation failure no longer consumes a referral discount.
- Rejected Telegram messages could be treated as delivered. Delivery failure is now recorded without reverting paid access.
- Malformed URL encoding could crash the HTTPS gateway. It now returns a controlled error and continues serving requests.
- The bot did not close SQLite connections during shutdown and needed systemd's forced stop timeout. Shutdown now cancels owned workers and closes both database connections.
- The `/habits` command imported a second copy of `app.py` when the bot was started as a script. It now receives the running bot's database explicitly.
- The legacy `/yourbody-app/` entrypoint on the API hostname served HTML whose JavaScript and CSS returned 404. Its nginx locations now redirect to the canonical application, preserving deep paths and query parameters.

## Validation

- 60 Python tests, including real FastAPI/SQLite integration, graceful shutdown and mocked bot/payment provider scenarios.
- 52 mobile Chromium browser scenarios, including all 16 main screens, historical food access, payment recovery, slow AI responses, retries, reversed response order, navigation cancellation and offline recovery.
- 3 HTTPS gateway tests, including a real 16-second upstream response.
- Production read-only checks: all 17 selected user/admin API routes returned HTTP 200, SQLite `quick_check` returned `ok`, all four application services were running, and no successful payments from the preceding day lacked active access.
- Real OpenRouter checks through the working connection succeeded for text analysis, vision transport, daily analysis and weekly analysis in approximately 1.5–3.3 seconds. The vision connectivity check used a synthetic blank image, not customer photos or an accuracy benchmark.

## Scope limits

The automated mobile browser is Chromium with an iPhone-sized viewport; native Telegram on an actual iPhone was not exercised. Live payment creation, actual recurring charges, customer messages and destructive admin actions were not run against production. Those paths use isolated database tests and mocked external services.

The subsequent lint audit resolved all 10 errors and 9 warnings without disabling rules. `npm run lint -- --max-warnings=0` is now required in CI. Production TypeScript compilation also passes.

## Lint follow-up: functional risks

- Admin list filters changed during the initial load were ignored. Late search/filter responses could overwrite the selected results. Requests are now keyed by the exact applied search and filter using the already installed TanStack Query library.
- A slow or failed client-detail request could leave the previous client's subscription action buttons visible. Detail responses now belong to a specific client, pending/failed details hide actions, and changing selection cancels the obsolete read. Overlapping admin actions are blocked; successful actions refresh the currently selected views.
- Calendar and daily-summary requests could display data from a previously selected month/day. Their request keys include the month/day, and leaving a selection cancels its request.
- A failed request from an unmounted food-detail screen could navigate away from a subsequently opened entry. Cleanup now prevents both stale data and stale error navigation.
- The food list and calendar could present failed reads as empty data, while admin operations reported server outages as denied access. They now show retryable load errors. Explicit authorization failures retain the denied-access state.
- Dashboard workouts used the UTC date, which differed from the tracker date near local midnight. Workouts now use the date returned by the dashboard API.
- API cancellation and request deadlines now share one controller, so a caller's cancellation signal does not bypass the timeout. Loading works through the same bounded error path even when the browser reports that it is offline.
- Authentication initialization now has stable, complete dependencies while preserving the attempt guard against stale sign-in results. Unsafe explicit `any` uses were replaced with type narrowing.

Eighteen new browser regression cases cover these loading paths. Five focused checks were also run against an isolated copy of the previous `ff758ee` source and reproduced the pre-fix failures. No production records were involved. Query identity follows the [official TanStack query-key guidance](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys); cache retention is disabled for these read screens so returning after an edit retrieves current data.

Synthetic browser response fixtures are generated by `tests/generate_browser_fixtures.py` from the real API and a temporary database. Regression checks run automatically on pushes and pull requests.

After deployment, run `python tools/check_webapp_entrypoints.py` to verify public entrypoints, their actual JS/CSS resources, and legacy CORS without touching customer records.
