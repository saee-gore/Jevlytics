# Jevlytics

Ask questions about a merchant's card payments in plain English, and get answers with the figures and their definitions. Ask about decline rates, settlements, chargebacks, card types, regions or fraud indicators.

> **Fictional data only.** This is a local development project. It does not process payments, accept transaction files, or hold real customer data.

## Design statement

Models suggest; a policy engine decides; the database calculates.

- **Jev classifies, it does not authorise.** Jev labels each question and picks a tool from a closed list. Its answer is checked against the policy engine before anything runs.
- **Claude reads and writes, it does not compute.** Claude turns a question into parameters and writes the final sentence from approved figures. It never writes SQL and never sets the merchant.
- **The merchant comes from the token, never from the question.** Any reference to another merchant is refused, however it is worded.
- **Every failure is closed.** If a model is unavailable or returns an unexpected answer, the request stops with a fixed response instead of guessing.

## Decision log

Each entry records a decision, the reason for it, and what it costs.

**1. Jev is a classifier with a closed label set, not a free-form judge.**
*Why Jev:* Jev returns one label from a fixed list, with a confidence value. That output can be checked, tested against a dataset, and logged. A free-text answer from a model cannot be checked in the same way.
*Trade-off:* the labels are only as good as their descriptions, and the thresholds are provisional until the evaluation runs.

**2. Jev sits behind a deterministic screen, not in its place.**
*Why:* a cross-merchant refusal must not depend on a model being available. The regex screen catches identifiers, number words such as "merchant two", and phrases such as "the other merchant", and it runs first.
*Trade-off:* the screen cannot see trading names or typos. Jev is the only layer that catches those, so its accuracy matters for that case.

**3. Jev is told the caller's merchant, but the merchant is never taken from Jev.**
*Why:* the server supplies the caller's merchant as trusted context, so Jev can tell the caller's own data from another merchant's. Identity still comes only from the verified token.
*Trade-off:* a model error can produce a wrong label, so tenant scoping in the database stays as the final layer.

**4. The language model is kept out of execution.**
*Why:* a model that chooses SQL or sets parameters can be steered by the user's wording. Here the model's output must match a strict schema, the policy engine checks it again, and the analytics layer uses parameterised queries.
*Trade-off:* the system can refuse valid questions that a free-form assistant would answer.

**5. The analytics database is read-only.**
*Why:* the analytics role can only select data, and each query runs with a timeout. Even a successful injection cannot change data.
*Trade-off:* the role needs maintaining whenever the schema changes.

**6. The system fails closed when models are unavailable.**
*Why:* a missing key or a timeout should stop a request, not produce an unchecked answer.
*Trade-off:* without a configured key, analytics questions return `temporarily_unavailable`, which makes first-run setup depend on the keys.

## Start here

Follow **[GETTING_STARTED.md](GETTING_STARTED.md)**. It takes about 30 minutes and walks you through each step, from installing the tools to asking your first question.

If you only want to look at the dashboard, you can skip the backend. Run the frontend in demo mode, as described in Step 10 of the guide.

## What you can do

- Ask questions about a merchant's own data, and see the metric definition beside each figure.
- Try the assistant's limits. It refuses requests for another merchant's data, however they are worded. See [the cross-merchant rule](docs/CROSS_MERCHANT_ACCESS.md).
- Use the dashboard to browse transactions, change the date range, and switch between demo users.

It also refuses payment actions such as refunds, requests for credentials, attempts to override its instructions, and questions outside payment analytics.

## What it does not do

- It does not process payments, issue refunds or move money.
- It does not accept transaction file uploads.
- It has not been deployed to production.
- The Docker Compose setup has been written but has not been run.

## Current status

| Area | Status |
|---|---|
| Analytics over PostgreSQL 16 | Built and tested |
| Sign-in, roles, tenant separation, policy engine | Built and tested |
| Refusing other merchants' data | Built and tested with fake models |
| Jev classification (TypeSafe) | Built and tested with fake clients. Not yet run against the live service. |
| Claude for extracting arguments and writing answers | Built and tested with fake clients |
| Dashboard (demo and live modes) | Built. Browser tests pass in demo mode. |
| Docker Compose | Written, not yet run |

Until a TypeSafe key is set, analytics questions return `temporarily_unavailable`. The system stops rather than guess.

## How a question is answered

```
your question
  -> cross-merchant check          (no AI; refuses other merchants' data)
  -> Jev: is this a valid request? (scope and risk)
  -> Jev: which tool fits?         (or no tool)
  -> Claude: read the parameters   (checked against a strict format)
  -> policy engine: is it allowed? (role, dates, merchant)
  -> audit log entry               (must be written first)
  -> analytics: calculate figures  (read-only database access)
  -> Claude: write the answer      (from approved figures only)
  -> response
```
<img width="1263" height="743" alt="Screenshot 2026-11-22 at 5 08 26 PM" src="https://github.com/user-attachments/assets/4360bea5-1e25-4032-b1a0-4a07d3e755ee" />


Every failure returns one of five fixed responses: `answered`, `clarification_required`, `unsupported`, `blocked`, or `temporarily_unavailable`. Figures appear only with `answered`.

## Documentation

| Document | Read it to learn |
|---|---|
| [GETTING_STARTED.md](GETTING_STARTED.md) | How to install and run the project, step by step |
| [docs/RUNNING.md](docs/RUNNING.md) | Settings, test commands, and common problems |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the parts fit together, the database roles, and the API endpoints |
| [docs/JEV_AND_LLM.md](docs/JEV_AND_LLM.md) | What the two AI models do, and what they are not allowed to do |
| [docs/CROSS_MERCHANT_ACCESS.md](docs/CROSS_MERCHANT_ACCESS.md) | How the rule about other merchants is enforced, and its limits |
| [docs/SECURITY.md](docs/SECURITY.md) | Security controls, how secrets are handled, and known gaps |
| [docs/DATA.md](docs/DATA.md) | The synthetic data, the demo users, and how to regenerate it |
| [docs/FRONTEND.md](docs/FRONTEND.md) | The dashboard pages, the assistant, and the browser tests |

## Licence

MIT licence.
