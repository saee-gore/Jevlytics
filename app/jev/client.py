"""Construction of the official TypeSafe SDK client. Imported only by the Jev adapter wiring.

SDK facts used here were confirmed against the installed typesafe-sdk==0.7.5 package and the
official TypeSafe Python SDK documentation (docs.typesafe.ai/sdk/python):
  * import name: typesafe_sdk (distribution name: typesafe-sdk)
  * TypeSafeClient(api_key=..., model=..., timeout=..., retry=RetryPolicy(...))
  * client.system_one(state=..., questions={...}) with Noul / Choice / Score questions
  * response.choices[name].choice / .confidence,  response.nouls[name].noul
  * exceptions: TypeSafeError and subclasses (API, connection, timeout, response validation)
"""

from __future__ import annotations

from typesafe_sdk import RetryPolicy, TypeSafeClient

from app.config import Settings


def build_typesafe_client(settings: Settings) -> TypeSafeClient:
    if not settings.jev_configured or settings.typesafe_api_key is None:
        raise RuntimeError("TYPESAFE_API_KEY is not configured")
    return TypeSafeClient(
        api_key=settings.typesafe_api_key.get_secret_value(),
        model=settings.typesafe_default_model,
        timeout=settings.typesafe_timeout_seconds,
        # No automatic retries: a failed screen must fail closed promptly and visibly.
        retry=RetryPolicy(max_retries=0),
    )
