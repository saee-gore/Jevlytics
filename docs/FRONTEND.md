# Frontend

The frontend is a Next.js dashboard. It shows transactions and analytics, and has an assistant panel for questions.

## Modes

The mode is set by `NEXT_PUBLIC_DATA_MODE` in `frontend/.env.local`.

| Mode | Data | Backend needed |
|---|---|---|
| `mock` (default) | Fictional demo data, labelled as fictional | No |
| `live` | Data from the backend. The browser calls `/api/backend`, and Next.js forwards the request to the URL in `BACKEND_URL`. | Yes |

The mode is read when the app is built, so rebuild after you change it.

In demo mode, the assistant uses keyword matching and returns fixed example answers. It does not use Jev or Claude.

## Pages

| Address | Contents |
|---|---|
| `/activity` | The transaction table, with editable start and end dates, and the assistant panel |
| `/analytics` | A form with a capability and a date range. Press Run to see the results. The page states that CSV export is not available. |
| `/capabilities` | A table of the analytics tools, with description, minimum role and supported filters |
| `/settings` | The data mode, the backend health status, the database status and the session token |

The app opens on `/activity`.

## Assistant

- The assistant is a chat panel in the bottom-right corner.
- Suggested questions are listed vertically above the input box.
- In demo mode, a question that names another merchant is refused.

## User switcher

The switcher is in the bottom-left corner. It lists the demo analysts, and each one is tied to a merchant. Changing user changes the merchant the dashboard uses. The switcher shows the ANALYST role.

## Transaction table

- The start and end dates are editable. Changing them changes the rows shown.
- The table holds up to 100 rows, and the page does not scroll as a whole.
- Dates are shown in your local calendar days.

## Browser tests

The browser tests are in `frontend/e2e/`. They need Chrome and a running dashboard. Each file is run with `APP_URL` set to the dashboard address, for example:

```bash
APP_URL=http://localhost:3000 node e2e/demo-flows.mjs
```

| File | Coverage |
|---|---|
| `demo-flows.mjs` | The main demo flows |
| `cross-merchant-flows.mjs` | Refusal of "merchant two" for Demo Analyst 001, and an answer for Demo Analyst 002 |
| `live-flows.mjs` | Flows against the live backend. Not yet run. It needs a sign-in token file, set with `TOKEN_FILE`. |

The `demo-flows.mjs` and `cross-merchant-flows.mjs` suites passed in demo mode during development.
