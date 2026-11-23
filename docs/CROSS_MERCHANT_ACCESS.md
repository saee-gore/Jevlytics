# Cross-merchant access

**Rule:** a user can see only the data of their own merchant. A question that names another merchant is refused. A question that names the user's own merchant is allowed.

## Forms the screen recognises

The deterministic screen in `app/orchestration/merchant_refs.py` recognises these forms of reference:

| Form | Examples |
|---|---|
| Identifier | `merchant_002`, `merchant-002`, `merchant 2` |
| Number as a word | `merchant two`, `Merchant Ten` |
| Indirect phrase | `the other merchant`, `another merchant`, `a different merchant` |

A reference to the caller's own merchant is not refused.

## Forms the screen does not recognise

The screen does not recognise trading names, such as "Lumen Subscription Services", or misspellings, such as "merchnat two". Jev is the only check for those forms. The accuracy of that check has not been measured.

## Layers

Three layers apply, in this order.

1. **Deterministic screen.** Runs on every message before any model. It reads the caller's merchant from the signed-in session and refuses a message that refers to another merchant. It does not need a model.
2. **Jev.** Jev receives the caller's merchant, set by the server, and is told to label a request for another merchant's data as `PROMPT_INJECTION_OR_POLICY_BYPASS`.
3. **Merchant scoping.** The merchant used by each analytics query comes from the signed-in user's record. A message cannot change it.

## Checked by tests

| Behaviour | Where it is checked |
|---|---|
| The screen recognises identifiers, number words and indirect phrases, and ignores the caller's own merchant | `tests/unit/test_merchant_refs.py` |
| Jev receives the caller's merchant, and its instructions include the rule | `tests/unit/test_jev_adapter.py` |
| In demo mode, "merchant two" is refused for Demo Analyst 001, and answered for Demo Analyst 002 | `frontend/e2e/cross-merchant-flows.mjs` |

The Jev evaluation cases `xm-001` to `xm-009` are in `data/jev_eval/jev_eval_cases.jsonl`. They have not been run against the live Jev service.
