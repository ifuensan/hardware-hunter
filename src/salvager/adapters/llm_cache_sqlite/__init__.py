"""LLM evaluation cache backed by local SQLite — Story 3.10.

The cache lives in its own SQLite file (default
``data_dir/llm_eval_cache.db``) separate from ``salvager.db`` so
operators can wipe cache without touching the append-only audit log,
and so a corrupt cache file cannot tank the daemon's audit plane.

Public surface:

  - :class:`SqliteLlmEvalCache` — the cache itself (``get`` / ``set``)
  - :class:`CachingListingEvaluator` — :class:`ListingEvaluator`
    decorator that consults the cache before delegating to an inner
    evaluator
"""

from salvager.adapters.llm_cache_sqlite.cache import (
    CachingListingEvaluator,
    SqliteLlmEvalCache,
)

__all__ = ["CachingListingEvaluator", "SqliteLlmEvalCache"]
