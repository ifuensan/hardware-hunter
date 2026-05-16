"""Gemini Flash :class:`ListingEvaluator` adapter — Story 3.9.

Public surface:

  - :class:`GeminiFlashEvaluator` — the concrete :class:`ListingEvaluator`
  - :class:`GeminiEvalResponse` — pydantic shape for the model's reply
  - :data:`GeminiCallable` — the protocol callers can inject for tests
"""

from salvager.adapters.llm_gemini.evaluator import (
    GeminiCallable,
    GeminiFlashEvaluator,
)
from salvager.adapters.llm_gemini.schema import GeminiEvalResponse

__all__ = [
    "GeminiCallable",
    "GeminiEvalResponse",
    "GeminiFlashEvaluator",
]
