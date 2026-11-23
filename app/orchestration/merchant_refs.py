"""Deterministic screen for merchant references written into a message.

Jev and the LLM are advisory and can misclassify. An evaluation case asking for another merchant's
decline rate was labelled as supported analytics, so this check does not depend on them. If the
message names a merchant other than the caller's own, the request is refused before any model sees it.

Scope of the check:
- numbers after the word "merchant": "merchant_002", "merchant-002", "merchant 2",
  "merchant two", "Merchant Ten"
- indirect references to another merchant: "the other merchant", "another merchant", "a different merchant"

An indirect reference cannot be matched to the caller's own merchant, so it is always treated as another
merchant. Names of merchants (for example a trading name) are not caught here; Jev is told the caller's own
merchant and is asked to refuse any other merchant's data however it is worded.

Identity still never comes from the message: the merchant that is queried is always the one in the
database-derived TenantContext.
"""

from __future__ import annotations

import re

_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_NUMBER = r"\d+|" + "|".join(_NUMBER_WORDS)

_MERCHANT_NUMBER = re.compile(rf"\bmerchants?[\s_-]*({_NUMBER})\b", re.IGNORECASE)
_INDIRECT_MERCHANT = re.compile(r"\b(?:other|another|different)[\s_-]+merchants?\b", re.IGNORECASE)
OTHER_MERCHANT_KEY = "other"


def _key(token: str) -> str:
    """Normalise a merchant number so that '002', '02', '2' and 'two' compare equal."""
    lowered = token.lower()
    if lowered in _NUMBER_WORDS:
        return str(_NUMBER_WORDS[lowered])
    return str(int(token))


def _caller_key(merchant_id: str) -> str:
    match = _MERCHANT_NUMBER.search(merchant_id)
    if match:
        return _key(match.group(1))
    return merchant_id.strip().lower()


def foreign_merchant_refs(message: str, caller_merchant_id: str) -> list[str]:
    """Return merchant references in the message that differ from the caller's own merchant."""
    own = _caller_key(caller_merchant_id)
    found: list[str] = []
    for match in _MERCHANT_NUMBER.finditer(message):
        key = _key(match.group(1))
        if key != own and key not in found:
            found.append(key)
    if _INDIRECT_MERCHANT.search(message) and OTHER_MERCHANT_KEY not in found:
        found.append(OTHER_MERCHANT_KEY)
    return found
