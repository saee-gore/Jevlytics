"""Server-derived tenant context.

The merchant and role used for every downstream decision come from the USERS table, keyed by the
verified token subject. A token whose merchant or role claims disagree with the database is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import AuthError, TokenClaims
from app.db.models import User


@dataclass(frozen=True)
class TenantContext:
    user_id: str
    merchant_id: str
    role: str


def resolve_tenant(session: Session, claims: TokenClaims) -> TenantContext:
    user = session.scalar(select(User).where(User.user_id == claims.subject))
    if user is None or not user.is_active:
        raise AuthError("unknown or inactive user")
    if user.merchant_id != claims.merchant_id or user.role != claims.role:
        # The token asserts something the database does not. Fail closed.
        raise AuthError("token claims do not match user record")
    return TenantContext(user_id=user.user_id, merchant_id=user.merchant_id, role=user.role)
