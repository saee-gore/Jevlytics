#!/usr/bin/env python3
"""Issue a short-lived DEVELOPMENT token for a demo user. Never use in production.

The role and merchant are read from the users table, so the token always matches the database.

    export JWT_SECRET=...   # from .env, at least 32 characters
    export DATABASE_URL=...  # application role (reads users)
    python scripts/issue_dev_token.py demo-analyst-001 --minutes 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.jwt import issue_token  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.session import app_engine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("user_id")
    parser.add_argument("--minutes", type=int, default=30)
    args = parser.parse_args()

    settings = get_settings()
    with Session(app_engine()) as session:
        user = session.scalar(select(User).where(User.user_id == args.user_id))
        if user is None or not user.is_active:
            print("unknown or inactive user", file=sys.stderr)
            return 1
        token = issue_token(
            settings=settings,
            user_id=user.user_id,
            merchant_id=user.merchant_id,
            role=user.role,
            ttl_minutes=args.minutes,
        )
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
