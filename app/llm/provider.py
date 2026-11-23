"""Provider-agnostic LLM adapter. Anthropic is implemented; other providers implement LLMProvider.

Credentials come only from backend environment variables. If no key is configured, the factory
returns None and the workflow reports temporarily_unavailable. Nothing is bypassed.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Protocol

from app.config import Settings
from app.llm.prompts import (
    EXPLANATION_SYSTEM,
    EXTRACTION_SYSTEM,
    explanation_user_message,
    extraction_user_message,
)

MAX_ANSWER_CHARS = 1500


class LLMUnavailableError(Exception):
    """Provider error, timeout or missing credentials. Fail closed."""


class LLMOutputError(Exception):
    """Provider answered, but the output is not in the required shape."""


class LLMProvider(Protocol):
    def extract_arguments(
        self,
        *,
        question: str,
        tool_name: str,
        json_schema: dict[str, Any],
        today_local: date,
        timezone: str,
    ) -> dict[str, Any]: ...

    def explain(
        self,
        *,
        question: str,
        tool_name: str,
        approved_payload: dict[str, Any],
    ) -> str: ...


class AnthropicProvider:
    def __init__(self, *, api_key: str, model: str, timeout: float, max_tokens: int) -> None:
        import anthropic  # local import keeps the dependency edge in one place

        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
        self._model = model
        self._max_tokens = max_tokens

    def _complete(self, system: str, user_text: str) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_text}],
            )
        except Exception as exc:  # any provider failure must fail closed
            raise LLMUnavailableError("llm request failed") from exc
        parts = [
            str(block.text)
            for block in response.content
            if getattr(block, "type", None) == "text" and hasattr(block, "text")
        ]
        return "".join(parts).strip()

    def extract_arguments(
        self,
        *,
        question: str,
        tool_name: str,
        json_schema: dict[str, Any],
        today_local: date,
        timezone: str,
    ) -> dict[str, Any]:
        text = self._complete(
            EXTRACTION_SYSTEM,
            extraction_user_message(
                question=question,
                tool_name=tool_name,
                json_schema=json_schema,
                today_local=today_local,
                timezone=timezone,
            ),
        )
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMOutputError("extraction output is not JSON") from exc
        arguments = parsed.get("arguments") if isinstance(parsed, dict) else None
        if not isinstance(arguments, dict):
            raise LLMOutputError("extraction output lacks an arguments object")
        return arguments

    def explain(self, *, question: str, tool_name: str, approved_payload: dict[str, Any]) -> str:
        text = self._complete(
            EXPLANATION_SYSTEM,
            explanation_user_message(
                question=question, tool_name=tool_name, approved_payload=approved_payload
            ),
        )
        if not text:
            raise LLMOutputError("empty explanation")
        return text[:MAX_ANSWER_CHARS]


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    """Returns None when no credentials are configured. Callers must fail closed on None."""
    if not settings.llm_configured or settings.anthropic_api_key is None:
        return None
    if settings.llm_provider != "anthropic":
        raise ValueError(f"unsupported LLM_PROVIDER {settings.llm_provider!r}")
    return AnthropicProvider(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.llm_model,
        timeout=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
    )
