"""Gemini Flash :class:`ListingEvaluator` — Story 3.9 (FR13-FR17).

Pre-flight budget guard
-----------------------
Before calling the model, the evaluator checks ``listing.price_eur``
against both wishlist ceilings (``max_price_solo`` and
``max_price_in_device``). If the price strictly exceeds *both*, the
LLM is not consulted; the evaluator short-circuits to ``confidence=low``
with a "price exceeds wishlist max" take. This saves an API call per
out-of-budget listing and satisfies the Story 3.9 AC.

When max_price_in_device is None (container detection disabled per
FR5), the budget check uses only max_price_solo.

Response extraction
-------------------
LLMs sometimes wrap JSON in markdown code fences despite instructions
not to. :func:`_extract_json_object` finds the outermost ``{...}`` in
the response body — robust to leading/trailing prose and code fences.

Test seam
---------
The constructor accepts an injectable :data:`GeminiCallable`
(``async (str) -> str``). The production default wraps
``google.genai.Client.aio.models.generate_content`` and translates
provider-specific rate-limit errors into :class:`LlmRateLimited`.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from pydantic import SecretStr, ValidationError

from hardware_hunter.adapters.llm_gemini.schema import GeminiEvalResponse
from hardware_hunter.domain.errors import LlmEvaluationError, LlmRateLimited
from hardware_hunter.domain.evaluation import ListingEvaluation
from hardware_hunter.domain.listing import Listing
from hardware_hunter.domain.prompts import build_evaluation_prompt
from hardware_hunter.domain.wishlist import WishlistEntry
from hardware_hunter.interfaces.listing_evaluator import ListingEvaluator
from hardware_hunter.observability.logging import get_logger

#: Take any prompt string, return the model's raw text reply.
GeminiCallable = Callable[[str], Awaitable[str]]

_DEFAULT_MODEL = "gemini-2.0-flash"
_ONE_LINE_TAKE_MAX = 120


class GeminiFlashEvaluator(ListingEvaluator):
    """LLM-backed match judge — Gemini Flash by default, swappable per NFR-I3."""

    def __init__(
        self,
        api_key: SecretStr,
        *,
        model: str = _DEFAULT_MODEL,
        call: GeminiCallable | None = None,
    ) -> None:
        self._model = model
        self._call: GeminiCallable = (
            call if call is not None else _build_default_call(api_key.get_secret_value(), model)
        )
        self._log = get_logger("adapter.llm_gemini")

    async def evaluate(
        self,
        listing: Listing,
        entry: WishlistEntry,
    ) -> ListingEvaluation:
        # Pre-flight budget guard — no LLM call when the listing's price
        # exceeds every configured ceiling.
        if _exceeds_all_ceilings(listing, entry):
            return _budget_short_circuit(listing, entry)

        prompt = build_evaluation_prompt(listing, entry)
        raw = await self._call(prompt)

        try:
            json_blob = _extract_json_object(raw)
            parsed = GeminiEvalResponse.model_validate_json(json_blob)
        except (ValidationError, ValueError) as exc:
            self._log.error(
                "llm_eval_failed",
                extra={
                    "error_class": "LlmEvaluationError",
                    "listing_id": listing.listing_id,
                    "marketplace": listing.marketplace,
                },
            )
            raise LlmEvaluationError(f"malformed Gemini response: {raw[:200]}") from exc

        if len(parsed.one_line_take) > _ONE_LINE_TAKE_MAX:
            raise LlmEvaluationError(
                f"one_line_take too long ({len(parsed.one_line_take)} > {_ONE_LINE_TAKE_MAX} chars)"
            )

        return ListingEvaluation(
            listing_id=listing.listing_id,
            entry_key=entry.entry_key,
            confidence=parsed.confidence,
            one_line_take=parsed.one_line_take,
            is_container=parsed.is_container,
            wrapper_text=parsed.wrapper_text,
            extracted_text=parsed.extracted_text,
            evaluated_at=datetime.now(UTC),
            cache_hit=False,
        )


# ─────────────────────────────────────────────────────────────────────────
# Budget short-circuit
# ─────────────────────────────────────────────────────────────────────────


def _exceeds_all_ceilings(listing: Listing, entry: WishlistEntry) -> bool:
    """True iff the listing price is strictly above every configured ceiling.

    A None ceiling means "container detection disabled for that variant"
    (FR5) — we treat it as not-a-bound, so a None ceiling alone never
    triggers the short-circuit.
    """
    price = listing.price_eur
    ceilings = [c for c in (entry.max_price_solo, entry.max_price_in_device) if c is not None]
    if not ceilings:
        return False
    return all(price > ceiling for ceiling in ceilings)


def _budget_short_circuit(listing: Listing, entry: WishlistEntry) -> ListingEvaluation:
    return ListingEvaluation(
        listing_id=listing.listing_id,
        entry_key=entry.entry_key,
        confidence="low",
        one_line_take=(f"EUR {listing.price_eur} — price exceeds wishlist max."),
        is_container=False,
        wrapper_text=None,
        extracted_text=None,
        evaluated_at=datetime.now(UTC),
        cache_hit=False,
    )


# ─────────────────────────────────────────────────────────────────────────
# JSON extraction
# ─────────────────────────────────────────────────────────────────────────

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(raw: str) -> str:
    """Return the outermost ``{...}`` substring of ``raw``.

    Robust to LLMs that wrap JSON in markdown code fences or pad it
    with explanatory prose. Raises ``ValueError`` when no object is
    present — the caller wraps that as :class:`LlmEvaluationError`.
    """
    if not raw or not raw.strip():
        raise ValueError("empty LLM response")
    match = _JSON_OBJECT_RE.search(raw)
    if match is None:
        raise ValueError("no JSON object found in response")
    return match.group(0)


# ─────────────────────────────────────────────────────────────────────────
# Default callable — wraps google.genai
# ─────────────────────────────────────────────────────────────────────────


def _build_default_call(api_key: str, model: str) -> GeminiCallable:
    """Construct the production ``GeminiCallable`` backed by google.genai.

    Imports happen lazily so tests that inject their own ``call`` don't
    pull the SDK at import time — and so the adapter-discipline lint
    sees google.genai used exclusively inside this adapter package.
    """
    # Imports kept inside the factory:
    # - keeps the SDK out of the module-level import graph for tests
    # - matches NFR-I3 (provider-swappable) by making the SDK a runtime
    #   dependency of this specific adapter only.
    from google import genai
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=api_key)

    async def _call(prompt: str) -> str:
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
            )
        except genai_errors.APIError as exc:
            if getattr(exc, "code", None) == 429 or "rate" in str(exc).lower():
                raise LlmRateLimited(str(exc)) from exc
            raise LlmEvaluationError(f"Gemini API error: {exc}") from exc
        return response.text or ""

    return _call
