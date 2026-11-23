# Merchant Payment Analytics: Frontend

A Next.js (App Router) dashboard for the merchant payment analytics backend. The sidebar has two pages: an AI assistant (chat) and an Activity page (demo transactions and a basic dashboard).

The frontend never talks to PostgreSQL, TypeSafe Jev, or the LLM directly. Every figure comes from the FastAPI backend, which enforces authentication, role checks, and tenant isolation. The merchant is taken from the access token, never from the browser.

## Requirements

- Node.js 18.18 or newer (required by Next.js 15)
- npm
- The backend running locally (only for live mode; see [configuration](../docs/setup/configuration.md))

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev        # http://localhost:3000
```

`.env.local` holds two settings:

| Variable | Values | Meaning |
| --- | --- | --- |
| `NEXT_PUBLIC_DATA_MODE` | `mock` (default), `live` | Read at build time. Changing it requires a rebuild or dev-server restart. |
| `BACKEND_URL` | e.g. `http://127.0.0.1:8000` | Server-side only. Where the FastAPI app listens. Used by the rewrite in `next.config.mjs`. |

No secret belongs in this file. The browser bundle only receives `NEXT_PUBLIC_*` values.

## Data modes

**Mock mode (default).** Shows fictional demo data for three demo merchants (`merchant_001`, `merchant_002`, `merchant_003`). A banner on every page says the data is fictional. The assistant answers from keyword rules in `src/lib/mock.ts`. Use it to look at the interface without a backend, a database, or a Jev key.

**Live mode.** Every request goes to `POST /chat` and `GET /capabilities` and `GET /health` on the backend, through the proxy.

```bash
NEXT_PUBLIC_DATA_MODE=live BACKEND_URL=http://127.0.0.1:8000 npm run build
npm run start
```

In live mode the Overview page does not load figures on open. It waits for **Refresh**, because each refresh asks the assistant six questions (one per KPI and panel), and each question can reach Jev and the LLM.

## How requests reach the backend

`next.config.mjs` rewrites `/api/backend/:path*` to `${BACKEND_URL}/:path*` on the Next.js server. The browser calls same-origin `/api/backend/...`. This avoids CORS, and the backend was not modified. The backend has no CORS middleware, so a browser calling it directly from another origin would be blocked.

## Authentication

There is no login endpoint in the backend, so the frontend cannot sign users in. In live mode:

1. Get an access token from whatever issues tokens for your environment (the backend's JWT settings are in [configuration](../docs/setup/configuration.md)).
2. Open **Settings** and paste the token.
3. The token is kept in `sessionStorage` under `mpa_access_token`. It is removed when the tab closes and when you press **Sign out**.

The token is sent as a bearer header by `src/lib/api.ts`. The frontend decodes its claims (for example the merchant identifier) only to display them in the sidebar. It does not verify the signature. Verification happens in the backend, and the backend ignores any merchant identifier supplied by the browser.

Do not store API keys (TypeSafe, Anthropic) in this project's frontend. None are read or sent by the frontend.

## Pages

| Page | What it does | Backend used |
| --- | --- | --- |
| Overview | KPI cards (volume, count, decline rate, chargeback rate), status and currency panels | `POST /chat` (six questions per refresh in live mode) |
| Analytics | Pick a capability, date range, then run. Builds a natural-language question for the backend. | `POST /chat` |
| AI Assistant | Chat with suggested questions (always visible) | `POST /chat` |
| Activity | Demo transaction list and dashboard (mock mode). In live mode, the questions asked in this browser tab | None in live mode; demo rows in mock mode |

Routes that are not in the sidebar (`/`, `/analytics`, `/capabilities`, `/settings`) redirect to the AI Assistant (`redirects()` in `next.config.mjs`). Their page files remain in `src/app` and can be deleted.

Responses are rendered by status. `answered` shows charts and tables. `unsupported` and `blocked` show the backend's text unchanged. `clarification_required` shows the backend's text plus a "Did you mean one of these?" list. The list is chosen in the browser from the topic of the question (`src/lib/clarify.ts`); the backend sends no suggestions. `temporarily_unavailable` shows an unavailable state. Currencies are never summed; charts are drawn only for single-currency data.

The Activity page's transaction list comes from `src/lib/demo-transactions.ts`: the latest 300 rows of the synthetic `data/transactions_merchant_001.csv`. In live mode the page says the API has no transaction endpoint.

## Gaps in the backend contract

These are things the UI needs or shows that the backend does not provide. The frontend documents each gap in place. It does not invent backend behaviour to fill it.

1. **No login endpoint.** Tokens are pasted manually (see Authentication).
2. **No merchant name.** No endpoint returns it. The sidebar shows the merchant identifier from the token claims, labelled as display-only.
3. **No time-series endpoint.** The Overview trend chart is replaced by "Trend data is not available."
4. **No comparison or previous-period data.** KPI cards show "No comparison available."
5. **No structured analytics filters.** The Analytics page sends a natural-language question with a date range. It cannot send structured filters, and there is no CSV export.
6. **No transaction list or audit endpoint.** The API cannot list individual transactions, so live mode shows no transaction table. The session question log on the Activity page is browser-side and is labelled "Not the audit trail."
7. **No conversation support.** The chat contract ignores any conversation identifier, so each question is independent.
8. **Capabilities lack filter and permission data.** `GET /capabilities` does not report supported filters or the caller's permissions, so the page says "Not reported by the API."
9. **Chat responses have no classification label.** `POST /chat` returns a `status` only. `chart` is always `null` from the backend, so charts are built from `data`.
10. **Overview cost in live mode.** Each refresh makes six assistant calls, which can reach Jev and the LLM.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Development server (not browser-tested in this build) |
| `npm run build` | Production build (mode from `NEXT_PUBLIC_DATA_MODE`) |
| `npm run start` | Serve the production build |
| `npm run typecheck` | `tsc --noEmit` with strict mode |

## Browser checks (optional)

`e2e/` contains two puppeteer-core scripts. They drive a locally installed Google Chrome (`CHROME_PATH`, default `/usr/bin/google-chrome`). Run each against the matching build:

```bash
# Mock build on port 3002
NEXT_PUBLIC_DATA_MODE=mock npm run build && npx next start -p 3002
APP_URL=http://localhost:3002 node e2e/demo-flows.mjs

# Live build on port 3001, with the backend running
NEXT_PUBLIC_DATA_MODE=live BACKEND_URL=http://127.0.0.1:8765 npm run build && npx next start -p 3001
APP_URL=http://localhost:3001 TOKEN_FILE=./token.txt node e2e/live-flows.mjs
```

Both scripts print a JSON object of checks, plus any page errors. Every check should be `true` and `pageErrors` should be empty. `demo-flows` checks text and layout in mock mode. `live-flows` assumes a valid token in `TOKEN_FILE`.

## Components

Components in `src/components/ui/` are written by hand in the shadcn/ui style. They are not generated by the shadcn CLI, so there is no `components.json`. Charts use Recharts 2.x, which logs a deprecation warning. Recharts 3 is available as a later migration.

## What has been tested

- Typecheck (`tsc --noEmit`) passes in strict mode.
- Production builds pass in both modes.
- Browser checks pass in mock mode (overview, charts, unsupported, blocked, and clarification states, activity log, no page errors).
- Browser checks pass in live mode against the backend (assistant answers or shows the unavailable state, capabilities list has nine rows, health shown, no page errors).

## What has not been tested

- The `npm run dev` server. Only production builds were run.
- Real Jev-backed answers in the UI. Live checks confirmed the wiring, not model output quality.
- Screenshots of live data. Visual checks used mock data.
- Layouts at narrow (mobile) widths.
- Other browsers. Only headless Chrome was used.
