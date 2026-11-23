# Security

This document describes the security controls in the project and the known gaps. Jevlytics is a development project. It has not been reviewed for production use.

## Controls

**Execution.** Only the policy engine allows a tool to run. Jev and Claude return suggestions. A tool runs only after the `policy_allow` audit entry is written.

**Identity and merchant scope.** The merchant comes from the signed-in user's record in the database. A request cannot set it. The cross-merchant rule is described in [CROSS_MERCHANT_ACCESS.md](CROSS_MERCHANT_ACCESS.md).

**Database access.** The API and the analytics queries use separate database roles. The analytics connection is read-only and has a five-second statement timeout. Migrations run under a separate owner role.

**Model output.** Claude's parameters must match a strict schema, and Jev's answers must match a fixed label set and the enabled tool list.

**Audit log.** A `policy_allow` entry is written before a tool runs. Audit entries store a SHA-256 hash of the question, not the question text.

**Secrets.** Settings come from environment variables. `.env` and `.env.*` are excluded by `.gitignore`. `.env.example` contains placeholder values, which must be replaced before use. The repository includes a test in `tests/security/` for repository hygiene.

**Input limits.** The settings `MAX_MESSAGE_CHARS`, `MAX_DATE_SPAN_DAYS` and `RATE_LIMIT_PER_MINUTE` limit message size, date span and request rate.

## Known gaps

- **Rate limiting** is kept in the application's memory. Each server process has its own counts, so the limit does not hold across several processes.
- **Development tokens.** `scripts/issue_dev_token.py` issues tokens for local use. Do not expose the API beyond your own computer.
- **Demo mode.** The dashboard's demo figures are fixed and are not tied to the signed-in merchant.
- **VIEWER role.** The backend accepts the VIEWER role. The dashboard does not offer it.
- **Docker Compose.** The Compose file is written and has not been run.
- **Live services.** Jev and Claude have not been tested against their live services, so their refusal behaviour is not measured.
- **Production readiness.** The project has not had an independent security review.

## Reporting a problem

No reporting channel has been set up yet. Raise security issues privately with the project owner, not in a public issue.
