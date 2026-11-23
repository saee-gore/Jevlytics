# Synthetic data

All data in Jevlytics is generated. It does not contain real merchant, cardholder or payment data. The merchant names are marked as fictional.

## Contents

| Item | Value |
|---|---|
| Date range | 24 July 2026 to 20 November 2026 |
| Random seed | 20261120 |
| Merchants | 3 |
| Transactions | 8,200 (2,900 for merchant 1, 2,600 for merchant 2, 2,700 for merchant 3) |
| Settlements | 706 |
| Chargebacks | 90 |

The generator uses a fixed seed and fixed dates, so running it again produces the same files.

## Merchants

| Merchant ID | Legal name | Vertical | Time zone |
|---|---|---|---|
| `merchant_001` | Northwind Outdoor Supply (fictional) | retail_ecommerce | America/Los_Angeles |
| `merchant_002` | Lumen Subscription Services (fictional) | subscription_services | America/New_York |
| `merchant_003` | Harbor Stays Hospitality (fictional) | travel_hospitality | Europe/London |

## Files

| File | Contents |
|---|---|
| `merchants.csv` | One row for each merchant |
| `transactions_merchant_001.csv`, `_002.csv`, `_003.csv` | Transactions, one file for each merchant |
| `settlements.csv` | Settlements |
| `chargebacks.csv` | Chargebacks |
| `users.csv` | Demo users, with their merchant and role |
| `MANIFEST.json` | The seed, the date range and the checksum of each file |
| `jev_eval/jev_eval_cases.jsonl` | Test cases for the Jev evaluation |

## Demo users

| User ID | Merchant | Role | Shown in the dashboard |
|---|---|---|---|
| `demo-analyst-001` | `merchant_001` | ANALYST | Yes |
| `demo-viewer-001` | `merchant_001` | VIEWER | No |
| `demo-analyst-002` | `merchant_002` | ANALYST | Yes |
| `demo-analyst-003` | `merchant_003` | ANALYST | Yes |

## Regenerating and checking the data

Regenerate the files:

```bash
python scripts/generate_dummy_data.py
```

Check the files against the manifest without changing them:

```bash
python scripts/generate_dummy_data.py --check
```

Load the data into the database:

```bash
python scripts/seed_database.py
```

The seed script refuses to run when `APP_ENV=production`, unless you pass `--allow-production`.

## Demo data in the dashboard

The dashboard in demo mode reads `frontend/public/demo/transactions.json`. This file is a copy of the transactions. Its figures are fixed and are not tied to the signed-in merchant.
