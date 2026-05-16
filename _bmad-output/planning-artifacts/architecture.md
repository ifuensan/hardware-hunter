---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
status: complete
completedAt: 2026-05-10
lastStep: 8
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/prfaq-salvager.md
  - _bmad-output/planning-artifacts/prfaq-salvager-distillate.md
  - salvager-bmad-prompt.md
documentCounts:
  prd: 1
  prfaq: 2
  kickoff: 1
  ux: 0
  research: 0
  projectDocs: 0
workflowType: architecture
project_name: salvager
user_name: ifuensan
date: 2026-05-10
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:** 54 FRs across 9 capability areas. Architecturally relevant clusters:

- **Marketplace surfaces** (FR6–FR12, FR21, FR41–FR42): two distinct adapter shapes — Wallapop's two-path (unofficial API + TinyFish search/fetch fallback) and eBay.es's official-API single-path. Driver for a `PageFetcher` interface and per-marketplace adapter discipline.
- **Listing evaluation pipeline** (FR13–FR17): provider-agnostic LLM call wrapped by `ListingEvaluator`; per-URL evaluation cache with TTL; wishlist-anchored prompt with confidence levels. Driver for a clean prompt-management module + cache layer behind the evaluator interface.
- **Telegram surface** (FR18–FR22, FR24): two distinct alert shapes (listing alerts with inline buttons, operational alerts plain text); fixed v1 message format coupled to audit-log schema (FR22). Driver for a `TelegramSurface` module with shape contracts validated against the audit-log schema.
- **Autonomous purchase + guardrails** (FR23–FR35): the most architecturally demanding cluster. Per-entry settings, fail-closed UI checks, cross-source price reconciliation pre-buy, receipt-vs-alert reconciliation post-buy, daily synthetic smoke test, per-purchase circuit breaker, manual-only re-enable. Driver for a `BuyOrchestrator` that composes `BrowserSession`, `Reconciler`, `CircuitBreaker`, `AuditLog` — all behind interfaces, all independently testable.
- **Audit log** (FR36–FR38): three append-only artifact classes (alert snapshot, tap event, marketplace transaction) with photo perceptual hashes. Driver for a strict append-only `Store` contract — *application-layer* enforcement (no UPDATE/DELETE statements) per NFR-S4.
- **Operator CLI** (FR39–FR50): 18 subcommands across init/login/validate/test/explain/phase2/audit/health/logs/lifecycle. Daemon mode is implicit default. Driver for a clean separation between command-handler layer and the daemon worker layer (sharing the same domain code, different entry points).
- **Wishlist + repo hygiene** (FR1–FR5, FR51–FR54): structural arbitrage prevention enforced in the wishlist validator; CONTRIBUTING.md/ROADMAP.md/README as launch artifacts. Architecturally minor but tightly coupled to the schema validator — a single source-of-truth schema definition is needed.

**Non-Functional Requirements:** 30+ NFRs across 8 categories. Driving constraints:

- **Performance envelope (NFR-P1–P5):** 20-min p95 publication-to-alert; 60s p95 Phase 2 buy completion; 5s p95 LLM evaluation per listing; 2s read-only CLI commands; 30s daemon startup. Headline: most of the budget belongs to polling cadence and LLM call; the rest is generous.
- **Security (NFR-S1–S7):** payment-rail enforcement is structural (no codepath outside Wallapop Pay / eBay checkout); audit-log integrity is application-layer append-only; cookie/token files mode 0600 + startup permission check; no telemetry of any kind.
- **Reliability (NFR-R1–R6):** eBay.es adapter MUST share zero runtime state with Wallapop adapter so half-degraded > dead; two-path Wallapop fallback within the same poll cycle; **graceful degradation, not silent failure** (every degradation emits an operational Telegram alert).
- **Integration (NFR-I1–I6):** Hermes pinned to v0.13.x; TinyFish over MCP only (never SDK-embedded); LLM provider behind a `ListingEvaluator` interface (Gemini Flash assumed default, GPT-4o / Claude Haiku swappable); Telegram retried with exponential backoff (3/1min default).
- **Cost (NFR-C1–C3):** Phase 1 ≤ €0/month on existing hardware; ≤ €10/month worst case; LLM cache hit rate ≥ 60% target. Direct architecture impact: cache layer is part of the launch deliverable, not a fast-follow.
- **Maintainability (NFR-M1–M6):** **Adapter discipline is a v1 launch blocker** — CI lint custom import-graph rule blocks direct SDK imports from business logic. Phase 2 critical-path coverage ≥ 90% line. Smoke-test regression set grows with each marketplace UI surprise (fixtures tracked in repo, not generated).
- **Privacy (NFR-PR1–PR5):** all data local; user = data controller; sellers' listing data processed only for evaluation/audit-snapshot; no profiling, no aggregation beyond per-listing dedup.
- **Observability (NFR-O1–O5):** structured JSON Lines on stdout; `health` command exposes all relevant subsystem statuses; diagnostic completeness — every operational alert carries enough log context to root-cause without re-running the failing path.

**Scale & Complexity:**

- **Single-user product** by design ((c3) personal-use). Forks are independent installs; no multi-tenant story.
- **Wishlist bounded:** ~100 entries soft cap (validated). Realistic v1 use: ~50 entries.
- **Polling volume:** per `config.yaml` example, Wallapop every 15 min + eBay every 30 min. With ~50 entries × ~10 candidate listings/day = ~500 LLM evaluations/day, ~3M tokens/month at ~500 tokens/eval.
- **Phase 2 volume:** dozens of opt-in entries at most; few-to-low-tens of actual purchases per year. Buy-flow throughput is not a scaling concern; correctness per purchase is everything.
- **Complexity level:** **high** (per PRD classification override). Drivers, in order: (1) Phase 2 silent-failure-mode design with three independent defenses; (2) two-path Wallapop adapter under anti-bot pressure; (3) LLM evaluation accuracy on container detection unproven at launch; (4) Phase 2 buy-flow stability (PRFAQ-named hardest problem).
- **Primary technical domain:** self-hosted agent / backend automation. No web UI, no API surface to third parties, no mobile, no GUI. CLI + Telegram bot as user surfaces.

### Technical Constraints & Dependencies

**Locked stack — not for redebate (per PRD):**

- **Runtime:** Hermes Agent v0.13.x (Nous Research, MIT). Provides scheduler primitive, SQLite memory + FTS5, MCP support, subagents (up to 8 concurrent), `clarify` primitive, persistent inter-session memory.
- **Web automation:** TinyFish via MCP (Search + Fetch free tier; Browser credit-based for Phase 2). Endpoint `https://agent.tinyfish.ai/mcp`. Free-tier rate limits: Search 5 req/min, Fetch 25 URLs/min.
- **Marketplaces:** Wallapop unofficial API (`api.wallapop.com/api/v3/general/search`); eBay.es official API.
- **LLM:** Gemini Flash assumed default for cost; provider-agnostic via `ListingEvaluator` interface. Alternatives: GPT-4o, Claude Haiku.
- **User surface:** Telegram bot for alerts and approvals.
- **Host:** owned HPE DL160 Gen10 (Valencia colo) primary; small VPS (~€3–5/month) viable fallback.
- **Packaging:** single `Dockerfile` + `docker-compose.yml`; no multi-container deployment at v1.

**Configuration:** three files, three concerns (locked):

- `wishlist.yaml` — user content (entries, ceilings, keywords, container_keywords, per-entry Phase 2 settings)
- `config.yaml` — operational tunables (schedule, rate limits, Phase 2 thresholds, LLM provider, paths, log level)
- `.env` — credentials only (Telegram, Wallapop, eBay, TinyFish, LLM API keys)

**Persistence (locked):**

- All local SQLite. Three logical stores:
  - **Seen-listings dedup index** (URL + perceptual photo hash + first/last-seen timestamps + match-fired flag)
  - **Phase 2 audit log** (append-only `alert_snapshots` + `tap_events` + `transactions` tables)
  - **LLM evaluation cache** (per-listing-URL with TTL; sits inside Hermes' SQLite memory + FTS5 per CLI section)
- Cookie file (Wallapop) and OAuth token file (eBay) live on filesystem with mode 0600.

**Mandated interfaces (adapter discipline, launch-blocker):**

- `PageFetcher` — Wallapop two-path + eBay.es single-path adapters
- `BrowserSession` — TinyFish Browser (Phase 2 buy flow); Playwright self-hosted as documented bare-metal fallback
- `ListingEvaluator` — LLM call wrapper, provider-agnostic
- `Store` — SQLite stores with append-only enforcement on audit tables
- `Scheduler` — Hermes scheduler abstraction (so Hermes can be swappable in principle)
- `TelegramSurface` (implied) — Telegram bot delivery + retry semantics

**Excluded by design (do not introduce):**

- No remote logging, no telemetry, no usage analytics, no crash reports.
- No API exposed to third parties (FR makes the agent self-contained).
- No multi-tenant model, no RBAC, no cloud-hosted SaaS variant.
- No off-wishlist surfacing path (no "good deals" alerts the user didn't ask for).
- No arbitrage/resale-value/margin codepath anywhere — schema, prompt, LLM-output handling are all structurally arbitrage-free.

### Cross-Cutting Concerns Identified

1. **Adapter discipline** (NFR-M1, FR launch blocker). CI-enforced import-graph rule. Affects every external integration: Wallapop, eBay.es, TinyFish, LLM provider, Hermes scheduler, Telegram. Each gets exactly one wrapper module; business logic imports interfaces only.
2. **Failure visibility** (NFR-R3, FR21). Every degradation surface must produce: (a) a structured log line (NFR-O1), (b) an operational Telegram alert (FR21), and (c) an entry visible in `health` (NFR-O2). No silent failures permitted. This forms a cross-cutting "degradation reporting" channel that needs a single notification spine.
3. **Append-only enforcement** (NFR-S4). At application layer for audit log. Affects how the `Store` interface for audit tables is shaped: writer methods only (`record_alert_snapshot`, `record_tap`, `record_transaction`), no `update_*` / `delete_*` methods exist. Annotation-via-append for corrections. CI lint or property-based test should verify.
4. **Phase 2 manual-recovery boundaries** (NFR-R4). The agent must NOT auto-recover from: Wallapop session expiry, Phase 2 auto-disable, config-file overwrite. These boundaries cut across multiple modules; needs a uniform "manual-only" pattern (e.g. `RequiresOperator` marker or explicit `/manual` action handlers in CLI).
5. **(c3) scope discipline** structurally enforced. Schema validator (FR3) blocks arbitrage fields; LLM prompt is anchored ("does this listing match wishlist entry X?", never "find good deals"); no codepath surfaces off-wishlist listings; CONTRIBUTING.md gates PRs. Architecturally: the wishlist schema definition is single-source-of-truth; the prompt-template module owns the anchoring; both need property-tests that rule out drift.
6. **Anti-bot mitigation** (NFR-S, FR8, FR12, FR41, FR30). Polling at human-volume rates, long-lived sessions with manual re-auth, stealth Chromium for Phase 2, per-purchase circuit breaker. Cuts across scheduler, adapters, buy-flow. Each adapter must respect rate limits client-side regardless of remote enforcement (NFR-I2).
7. **Phase 2 self-disabling stack** (FR31–35). Three independent defense layers must remain truly independent (no shared parsing path between cross-source reconciliation and smoke test, otherwise a single bug bypasses both). This is a structural design constraint, not a coding-style one — needs to be expressed in module boundaries.
8. **Local-only data plane** (NFR-PR3, NFR-S7). Architectural prohibition: no network egress beyond the named external APIs (Wallapop, eBay, Telegram, TinyFish, LLM provider). CI lint should be able to enforce a deny-list of well-known telemetry SDKs.
9. **Test coverage on Phase 2 critical path** (NFR-M2). ≥ 90% line coverage on cross-source reconciliation, fail-closed UI checks, circuit breaker, audit-log writes, receipt-vs-alert reconciliation. Means these modules must be designed for testability — pure functions where possible, dependency injection for the marketplace adapter and the audit store, recorded fixtures for marketplace HTML/API responses.
10. **Smoke-test regression set growth** (NFR-M3). Synthetic fixtures tracked in repo grow with every marketplace UI surprise. Architecturally: a fixtures package + a smoke-test harness that loads fixtures uniformly across both reconciliation paths and the synthetic price-parse test.

### Open Questions Carrying Forward into Architecture

PRD captures 8 OQs. Architectural relevance:

| OQ | Relevance to architecture |
|---|---|
| **OQ1** Reconciliation auto-disable scope (global vs per-entry) | Affects circuit-breaker state model. Default: global. Architecture should make per-entry refactor cheap if data drives the change. |
| **OQ2** Container detection prompt criterion (strict ceiling vs LLM "vale la pena") | Localized to `ListingEvaluator` prompt-template module. Both criteria can coexist behind a config flag in v1. |
| **OQ3** TinyFish Browser per-purchase cost (blocking Phase 2 docs) | Not architectural — measurement task during Phase 1. |
| **OQ4** Wishlist scale assumptions | Not architectural — empirical validation during Phase 1. |
| **OQ5** Adapter break frequency | Not architectural — empirical observation. |
| **OQ6** LLM language-register bias (blocking Phase 2 enablement for non-Castilian users) | Affects validation methodology, not module design. |
| **OQ7** Phase 2 fallback when TinyFish Browser unavailable mid-buy | Architecturally minor: fail closed + emit operational Telegram with manual buy link. Encoded in `BuyOrchestrator` failure path. |
| **OQ8** agentskills.io publication | Distribution decision, not architecture. |

Five of eight OQs do not require architectural changes; the architecture needs to leave OQ1 and OQ2 cheap to revisit, and codify the OQ7 default behavior.

## Starter Template Evaluation

### Primary Technology Domain

**Python self-hosted agent / CLI tool.** No web/mobile/full-stack starter applies. The PRD locks the runtime stack (Hermes Agent + TinyFish via MCP + Telegram + LLM provider) and leaves language open with strong signals toward Python — Hermes Agent is Python-native, ships with MCP support and a built-in scheduler, and the awesome-hermes-agent ecosystem is referenced in the kickoff document.

### Starter Options Considered

| Option | Provides | Adopted? |
|---|---|---|
| **Minimal scaffold** (`uv init --package`) | Clean modern Python project, zero unwanted conventions, directory layout encoding the adapter discipline that NFR-M1 mandates | **Yes** |
| Hermes Agent skill template (Skills Hub / agentskills.io) | Hermes-ecosystem-aligned scaffolding | No — couples our directory structure to a Hermes-specific layout; agentskills.io publication is OQ8 (deferred to Vision) |
| Cookiecutter Python CLI starter | Pre-baked CI, docs, license, changelog | No — imports opinions we didn't choose; adapter-discipline layout still has to be hand-built on top |

### Selected Approach: Minimal `uv` Scaffold

**Rationale.** Adapter discipline (NFR-M1) is a launch blocker, enforced by a CI lint custom import-graph rule. The directory layout encodes the boundary between business logic and external-SDK adapters; a starter that hides that boundary inside its conventions is a net negative. uv's modern lockfile model + Astral's fast tool ecosystem (uv + ruff + ty) gives us the cleanest dev-loop available in Python (May 2026).

### Tooling Decisions (verified May 2026)

| Concern | Tool | Version | Notes |
|---|---|---|---|
| Python runtime | CPython | **≥ 3.12** | TaskGroup, typing niceties, broad OS package availability |
| Package & venv manager | **uv** | latest (rolling) | Drop-in replacement for pip/virtualenv/pip-tools, 10–100× faster |
| CLI framework | **typer** | ≥ 0.12.1 | Type-hint-driven, built on Click; matches the 18-subcommand structure (FR39–48) |
| Lint + format | **ruff** | latest | Replaces black + isort + flake8; Astral, pairs naturally with uv |
| Type checker | **ty** (Astral) | beta/RC as of May 2026 | Fast, ecosystem-aligned. **Maturity caveat:** if ty fails on a Hermes / TinyFish / LLM-SDK type stub before v1.0, fall back to mypy without ceremony. CI runs both for the first release until ty is proven stable on the project's full surface. |
| Test framework | **pytest** | latest | Universal; required for ≥ 90% Phase 2 critical-path coverage (NFR-M2) |
| Test extras | pytest-cov, pytest-asyncio, syrupy (snapshot tests for marketplace fixtures) | latest | Coverage reporting, async test support, snapshot-based fixture comparison |
| Schema validation | **pydantic** v2 | latest | Single-source-of-truth schemas for `wishlist.yaml` / `config.yaml` / audit-log rows |
| YAML | PyYAML | latest | Config loading |
| HTTP | httpx | latest | Async-friendly Wallapop unofficial-API client and eBay.es client |
| Dataclass-style configs | pydantic-settings | latest | `.env` loading with type validation |
| Docker base | `python:3.12-slim` | rolling | Official, minimal, fast `apt-get` |

**Hermes Agent and TinyFish are runtime dependencies, not starter scaffolding** — Hermes is added via `uv add hermes-agent` (pinned to v0.13.x per NFR-I1); TinyFish is configured as an MCP server endpoint in Hermes' config, not embedded as an SDK dependency (NFR-I2).

### Initialization Commands

```bash
# 1. Create the project
uv init --package salvager --python 3.12
cd salvager

# 2. Add runtime dependencies
uv add typer pydantic 'pydantic-settings' pyyaml httpx
uv add hermes-agent                                      # pin to v0.13.x in pyproject
uv add python-telegram-bot                                # Telegram bot
uv add google-genai                                       # default LLM provider (Gemini Flash); swappable behind ListingEvaluator

# 3. Add development dependencies
uv add --dev pytest pytest-cov pytest-asyncio syrupy
uv add --dev ruff
uv add --dev ty                                           # Astral type checker; mypy as fallback (see caveat)

# 4. Initialize git, add .gitignore, write the lock file
git init
echo "/.env\n/wishlist.yaml\n/config.yaml\n/data/\n/.venv/\n.ruff_cache/\n.pytest_cache/\n.ty_cache/\n__pycache__/" > .gitignore
uv lock

# 5. Verify the toolchain works
uv run ruff check .
uv run ty .                # or: uv run mypy . if ty isn't ready
uv run pytest -q
```

### Project Structure (target — encoded in v1.0)

The layout encodes the adapter discipline launch blocker:

```text
salvager/
├── pyproject.toml                  # uv-managed; pins runtime + dev deps
├── uv.lock                         # committed
├── Dockerfile                      # python:3.12-slim base
├── docker-compose.yml              # single service, mounts ./data and ./config
├── .env.example                    # tracked; .env is gitignored
├── wishlist.example.yaml           # tracked; wishlist.yaml is gitignored
├── config.example.yaml             # tracked; config.yaml is gitignored
├── README.md                       # personal monitoring tool framing + legal disclaimer
├── CONTRIBUTING.md                 # "no arbitrage PRs" rule + 3 invitation categories
├── ROADMAP.md                      # multi-marketplace, arbitrage-as-separate-repo, C&D-induced sunset
├── LICENSE                         # MIT
│
├── src/salvager/
│   ├── __init__.py
│   ├── __main__.py                 # `python -m salvager` entry
│   │
│   ├── cli/                        # typer subcommands (FR39–FR48)
│   │   ├── __init__.py
│   │   ├── app.py                  # main typer.Typer() with subcommand groups
│   │   ├── init_cmd.py
│   │   ├── login_cmd.py
│   │   ├── validate_cmd.py
│   │   ├── test_search_cmd.py
│   │   ├── explain_cmd.py
│   │   ├── phase2_cmd.py
│   │   ├── audit_cmd.py
│   │   ├── health_cmd.py
│   │   ├── logs_cmd.py
│   │   └── daemon_cmd.py
│   │
│   ├── domain/                     # pure domain logic; NO external SDK imports
│   │   ├── __init__.py
│   │   ├── wishlist.py             # Wishlist, Entry models (pydantic)
│   │   ├── listing.py              # Listing model
│   │   ├── evaluation.py           # ListingEvaluation, ConfidenceLevel
│   │   ├── alert.py                # AlertSnapshot, AlertButton
│   │   ├── audit.py                # AuditEntry types: AlertSnapshot/TapEvent/Transaction
│   │   ├── reconciliation.py       # ReconciliationResult, tolerance math (pure)
│   │   ├── scope_guard.py          # arbitrage-field rejection logic (pure)
│   │   └── prompts.py              # wishlist-anchored prompt templates (pure strings)
│   │
│   ├── interfaces/                 # ABCs for adapter discipline (NFR-M1)
│   │   ├── __init__.py
│   │   ├── page_fetcher.py         # PageFetcher (Wallapop two-path + eBay.es)
│   │   ├── browser_session.py      # BrowserSession (TinyFish Browser; Playwright fallback)
│   │   ├── listing_evaluator.py    # ListingEvaluator (LLM provider-agnostic)
│   │   ├── store.py                # Store (SQLite stores; append-only audit subset)
│   │   ├── scheduler.py            # Scheduler (Hermes scheduler abstraction)
│   │   └── telegram_surface.py     # TelegramSurface (delivery + retry)
│   │
│   ├── adapters/                   # external SDK imports live HERE and ONLY here
│   │   ├── __init__.py
│   │   ├── wallapop_api/           # unofficial-API path (httpx)
│   │   ├── wallapop_tinyfish/      # TinyFish search/fetch fallback path (MCP)
│   │   ├── ebay_api/               # official eBay API
│   │   ├── tinyfish_browser/       # Phase 2 buy flow over MCP
│   │   ├── llm_gemini/             # google-genai
│   │   ├── llm_openai/             # optional alt; importable via config
│   │   ├── hermes_scheduler/       # Hermes cron primitive wrapper
│   │   ├── telegram_bot/           # python-telegram-bot wrapper
│   │   └── sqlite_store/           # SQLite append-only enforcement
│   │
│   ├── orchestration/              # daemon + buy-flow orchestrators
│   │   ├── __init__.py
│   │   ├── poll_loop.py            # registers polling jobs with Scheduler; emits alerts
│   │   ├── buy_orchestrator.py     # FR23–FR35: composes BrowserSession + Reconciler + CircuitBreaker + Store
│   │   ├── circuit_breaker.py      # Phase 2 per-purchase circuit breaker (pure-ish)
│   │   ├── reconciler.py           # cross-source + receipt-vs-alert reconciliation
│   │   ├── smoke_test.py           # daily Phase 2 synthetic smoke test
│   │   └── degradation_reporter.py # "no silent failure" channel: log + Telegram + health
│   │
│   ├── config/                     # config loaders (pydantic-settings + yaml)
│   │   ├── __init__.py
│   │   ├── env.py                  # .env via pydantic-settings
│   │   ├── config_yaml.py          # config.yaml schema + loader
│   │   └── wishlist_yaml.py        # wishlist.yaml schema + validator (FR3 scope-guard hook)
│   │
│   └── observability/
│       ├── __init__.py
│       ├── logging.py              # structured JSON Lines on stdout
│       └── health.py               # `health` command implementation
│
├── tests/
│   ├── __init__.py
│   ├── unit/                       # domain + orchestration pure-logic tests
│   ├── integration/                # adapter tests against recorded fixtures
│   ├── e2e/                        # full daemon-loop tests with mocked adapters
│   └── fixtures/                   # smoke-test regression set (NFR-M3)
│       ├── wallapop_api/
│       ├── wallapop_html/
│       ├── ebay_api/
│       └── price_parsers/          # comma vs dot fixtures (the Q9 scenario)
│
└── scripts/
    ├── adapter_discipline_lint.py  # CI gate for NFR-M1 import-graph rule
    └── ...
```

### Architectural Decisions Provided by This Scaffold

**Language & Runtime.** Python ≥ 3.12 (CPython, official). Async-friendly (`asyncio` + `httpx`); concurrency for per-listing LLM evaluation maps to Hermes subagents (up to 8) per NFR-P3.

**Build Tooling.** uv-managed `pyproject.toml` + `uv.lock` (committed). All tasks invoked via `uv run <tool>`; no global tool installs needed for contributors.

**Code Quality.**

- ruff for lint + format (replaces black + isort + flake8). Configured in `pyproject.toml`.
- ty (Astral) for type checking, with **mypy as an immediate fallback** if ty hits a stub it can't process. CI runs both for the first release.
- pytest with coverage thresholds: ≥ 90% line coverage on `orchestration/buy_orchestrator.py`, `orchestration/reconciler.py`, `orchestration/circuit_breaker.py`, `adapters/sqlite_store/audit_*.py`, `orchestration/smoke_test.py` (NFR-M2).

**Testing Infrastructure.**

- `tests/unit/` for pure domain code (no IO, no adapters).
- `tests/integration/` for each adapter against recorded fixtures.
- `tests/e2e/` for full daemon-loop with all adapters mocked.
- `tests/fixtures/` is the smoke-test regression set (NFR-M3) — every marketplace UI surprise (parser drift, format change, button rename) adds a fixture here, and CI runs the full suite on every PR.
- `syrupy` for snapshot tests on Telegram message bodies (FR22 fixed format) and on LLM prompt rendering.

**Code Organization.**

- `domain/` is **pure** — pydantic models + functions, no IO, no SDK imports. This is the half of the codebase that stays stable across stack swaps.
- `interfaces/` defines ABCs that `domain/` and `orchestration/` import; `adapters/` implements them.
- `adapters/` is the **only** package allowed to import Hermes / TinyFish / google-genai / python-telegram-bot / httpx / Wallapop endpoints / eBay endpoints — verified by `scripts/adapter_discipline_lint.py` in CI (NFR-M1).
- `orchestration/` composes interfaces; never imports an adapter directly.

**Development Experience.**

- `uv run salvager <subcommand>` runs the CLI without installs.
- `uv run pytest -q` for tests; `uv run ruff check .` and `uv run ty .` for quality gates.
- `uv sync` is the contributor-onboarding command; no separate virtualenv setup.
- `docker-compose up -d` for the daemon mode; `docker-compose run salvager <subcommand>` available but the supported operator path is host-installed `salvager` calling into the running container.

**Note.** Project initialization using `uv init --package salvager --python 3.12` plus the dependency-add commands above should be the **first implementation story** in Phase 1. The directory layout above is itself part of that story, since the adapter discipline boundary cannot be added retroactively without rework.

## Core Architectural Decisions

This section is the authoritative decision register. Each decision links to its driving FR/NFR and notes which decisions were locked upstream (PRD), which are confident defaults the architecture sets, and which were resolved in collaboration during this step.

### Decision Priority Analysis

**Critical decisions (block implementation) — all resolved:**

- Persistence engine, schema layout, migration strategy
- Phase 2 state source-of-truth and CLI-mutation strategy
- Adapter-discipline enforcement mechanism (CI lint)
- Daemon ↔ CLI communication model
- Concurrency model (async daemon / sync CLI)
- Container image distribution path

**Important decisions (shape the architecture) — all resolved:**

- Internal data flow pattern (synchronous pipeline within async runtime, no event bus)
- Internal architectural style (hexagonal / ports-and-adapters)
- Logging schema (structured JSON Lines on stdout)
- CI gate composition

**Deferred decisions (post-MVP):**

- PyPI publication of the `salvager` package (post-launch nice-to-have; container image is the v1 distribution channel)
- agentskills.io publication for Hermes ecosystem visibility (OQ8 from PRD; community-distribution decision tied to v1 outcomes)
- Grafana / external observability integration (none at v1; logs are docker-compose-captured)
- LLM provider switch automation — provider is config-driven (`config.yaml > llm.provider`) but no auto-switch on rate-limit; out of scope for v1
- Wallapop unofficial-API alternate-API discovery (continue using `api.wallapop.com/api/v3/general/search` as documented in the kickoff)

### Data Architecture

| Decision | Choice | Rationale | Driving FRs/NFRs |
|---|---|---|---|
| **Persistence engine** | SQLite (file-based) | Local-only data plane mandate (NFR-PR3, NFR-S7); single-user; no remote sync to manage | NFR-PR1–PR5, NFR-S7, FR36 |
| **DB layout** | Single `salvager.db` file with multiple logical tables | Single backup target; no cross-DB joins; WAL mode allows daemon-write + CLI-read concurrency | FR4, FR10, FR36, NFR-R5 |
| **WAL mode** | Enabled at first connect (`PRAGMA journal_mode=WAL`) | Concurrent CLI reads while daemon writes; consistent state across crash/restart (NFR-R5) | NFR-R5 |
| **Tables (initial schema)** | `wishlist_runtime_state`, `seen_listings`, `alert_snapshots`, `tap_events`, `transactions`, `phase2_smoke_tests`, `_meta` | One table per concern; foreign keys via `(manufacturer, model, ref)` entry key (FR4) | FR4, FR10, FR36, FR33 |
| **Append-only enforcement** | Application layer; `Store` interface exposes only `record_*` writers for `alert_snapshots`/`tap_events`/`transactions`; no `update_*`/`delete_*` methods exist on these tables | NFR-S4 cannot be enforced at SQLite layer alone; must be by interface design | NFR-S4 |
| **Migrations** | Hand-rolled, `_meta.schema_version` row + numbered `.sql` files in `src/salvager/migrations/`, applied at daemon startup; CLI `validate-config` flags drift | Alembic overkill for ~7 tables; keeps deps small (NFR-M5); single-user means no rolling-deploy concern | NFR-M5 |
| **Cache strategy (LLM evals)** | Hermes Agent's built-in SQLite memory + FTS5 hosts the per-URL evaluation cache; not in `salvager.db` | Reuses existing Hermes infrastructure; FTS5 on the prompt+response is useful for `explain` debugging; keeps stack-swap clean (replace Hermes → replace cache) | FR16, NFR-C3 |
| **TTL on cache** | 24 h default; shorter (1 h) for low-confidence results; configurable via `config.yaml > llm.cache_ttl` | Balances freshness vs cost; NFR-C3 hit-rate target ≥ 60% | FR16, NFR-C3 |
| **File-based state** | Cookie file (Wallapop), OAuth token file (eBay), `wishlist.yaml`, `config.yaml`, `.env` — all live in `data_dir` / `config_dir` mounted into the container | Mode 0600 enforced at startup (NFR-S2); user backs up via existing homelab backup story | NFR-S2, FR41–42 |

### Authentication & Security

No app-level authentication exists — single-user product, no third-party API exposed. All auth is delegated to marketplace and notification providers.

| Decision | Choice | Rationale | Driving FRs/NFRs |
|---|---|---|---|
| **Wallapop session** | Long-lived cookie file in Netscape cookies.txt format; mode 0600; never silently re-logged-in | Native format for both httpx and real-browser sessions; tooling-friendly; manual re-auth honors anti-bot posture | FR12, FR41, NFR-S1, NFR-S2 |
| **eBay.es OAuth** | OAuth 2.0 via official eBay developer flow; refresh + access tokens persisted to `oauth_tokens.json` (0600) at `data_dir/auth/`; auto-refresh before expiry within the daemon | eBay's official path; no manual re-auth pain (refresh tokens) | FR42, NFR-I5, NFR-S2 |
| **Telegram bot binding** | Bot token (`TELEGRAM_BOT_TOKEN`) + recipient chat ID (`TELEGRAM_CHAT_ID`) in `.env`; the daemon **silently drops** any inbound message from any chat ID other than `TELEGRAM_CHAT_ID` | Prevents accidental cross-talk if the bot token leaks; simple chat-ID allowlist is sufficient for single-user | NFR-S1, NFR-S7, FR18, FR24 |
| **TinyFish auth** | API key in `.env` (`TINYFISH_API_KEY`); passed to Hermes' MCP server config at startup; never logged | Hermes owns the MCP connection; we don't manage TinyFish auth directly | NFR-S1, NFR-I2 |
| **LLM auth** | API key in `.env` (`LLM_API_KEY`); passed to the configured provider adapter at startup | Provider-agnostic; switching providers means switching the adapter, not the auth model | NFR-I3 |
| **Credential hot-reload** | None at v1. `.env` loaded once at process start; rotation requires `docker-compose restart` | Simpler; aligned with FR49 ("loads `.env` once at process start with no hot-reload") | FR49 |
| **Permission verification at startup** | Daemon verifies cookie file, OAuth token file, and `.env` are mode 0600; refuses to start if any is permissive | NFR-S2 enforcement | NFR-S2 |
| **TLS posture** | All external HTTP calls via httpx with default TLS 1.2+; `verify=True` always; no `verify=False` codepath exists | NFR-S3 enforcement | NFR-S3 |
| **Payment-rail enforcement** | All Phase 2 buy flows go through the `BuyOrchestrator` → `BrowserSession` interface, which is implemented exclusively by `tinyfish_browser` adapter scoped to Wallapop Pay / eBay checkout flows; CI lint deny-listing other rails (`bizum`, `transferencia`) catches accidental introduction | NFR-S5 enforcement; structurally impossible to add an alternate rail without a visible code change | NFR-S5, FR25 |

### API & Communication Patterns

No third-party API surface. Internal communication patterns:

| Decision | Choice | Rationale | Driving FRs/NFRs |
|---|---|---|---|
| **Daemon ↔ CLI comm** | **Shared filesystem + SQLite, no IPC, no HTTP control plane.** CLI commands either: (a) read-only — read SQLite + config files (`audit show`, `health`, `phase2 status`); (b) config-mutating — rewrite `wishlist.yaml` / SQLite tables; daemon picks up changes on next poll cycle (or on a 30-second config-rescan tick). | Single-user simplicity; no network surface; CLI works whether daemon is running or not (graceful) | FR39, FR45–47, NFR-P4 |
| **Phase 2 state source-of-truth** | **`wishlist.yaml` is canonical.** `phase2 enable <entry>` and `phase2 disable <entry>` rewrite the YAML using **`ruamel.yaml`** (preserves comments and formatting). The daemon parses `wishlist.yaml` at the start of every poll cycle. SQLite carries no override table for Phase 2 enable/disable. | Single source of truth; user can grep / hand-edit / version-control the wishlist; (c3)-aligned ("the wishlist is the user's intent") | FR23, FR45, FR3 |
| **Phase 2 auto-disable persistence** | When the agent auto-disables Phase 2 (FR32–34), it writes a global "Phase 2 lockout" row to `phase2_state` SQLite table; this row takes runtime precedence over the YAML's per-entry `enabled: true` until explicitly cleared by `phase2 enable <entry>` (which clears the lockout AND keeps the entry enabled). | Auto-disable must persist across daemon restarts; user-edited YAML alone could miss this. Manual operator action required to re-enable (NFR-R4). | FR32–35, NFR-R4 |
| **Daemon polling cadence change** | Operator edits `config.yaml > schedule.*`; daemon re-reads `config.yaml` on next 30-second config-rescan tick (or restart for the surest result). | Hermes scheduler accepts re-registered jobs at runtime per the kickoff doc; matches the "no daemon restart for routine config changes" UX | NFR-P5, NFR-O4 |
| **Inter-marketplace independence** | Wallapop and eBay.es adapter packages share zero runtime state — independent connection pools, independent rate-limiters, independent session/token files. A failure in one cannot block the other. | NFR-R1 enforcement (eBay.es independence) | NFR-R1, FR7 |
| **Internal data flow** | Synchronous pipeline within an async runtime: `poll_loop` → `PageFetcher.search` → `PageFetcher.fetch` → `Store.is_seen?` → `ListingEvaluator.evaluate` → `Store.record_seen` → `TelegramSurface.send_alert`. No internal event bus, no message broker. | Single-user volumes don't need event-driven architecture; pipeline is easier to test, easier to reason about, easier to recover from crashes | NFR-M2, simplicity |
| **Concurrency model** | **Async daemon (`asyncio` + `httpx`); sync CLI subcommands.** Daemon uses Hermes' subagent primitive (up to 8 concurrent workers) to parallelize per-listing LLM evaluation. CLI subcommands are short-lived and synchronous; no benefit to async overhead. | NFR-P3 (concurrency for batch evaluation); FR39–48 (CLI ergonomics) | NFR-P3, FR39 |
| **Telegram retry semantics** | Failed sends retried with exponential backoff (default 3 attempts over ~1 minute); persistent failure surfaces as a structured-log error; the daemon does not block polling on Telegram outages. | NFR-I6 enforcement | NFR-I6 |
| **Operational alert channel** | Same Telegram chat as listing alerts; distinguished by `⚠️` (high-priority) and `ℹ️` (informational) prefixes; no inline buttons; no separate "ops chat" at v1. | FR21 spec; single user means no need to split channels | FR21 |

### Frontend Architecture

**N/A by design.** No browser-facing UI, no mobile app. The user surface is:

- **Telegram bot** — listing alerts (with inline buttons), operational alerts (plain text). Format is fixed for v1 per FR22.
- **CLI** — `salvager <subcommand>`. Plain text + ANSI colors when stdout is a TTY; `--format json` for scripting.

No frontend decisions. No state management library, no routing strategy, no bundle optimization.

### Infrastructure & Deployment

| Decision | Choice | Rationale | Driving FRs/NFRs |
|---|---|---|---|
| **Hosting (primary)** | Owned HPE DL160 Gen10, Valencia colo | PRD; €0/month operational cost | NFR-C1 |
| **Hosting (fallback)** | Small VPS (~€3–5/month), provider-agnostic | Documented for OSS forkers and as walk-away resilience | NFR-C1, FR54 |
| **Packaging** | Single `Dockerfile` (base `python:3.12-slim`) building a single-service `docker-compose.yml` that mounts `./data` (SQLite, audit log, cookies) and `./config` (wishlist.yaml, config.yaml, .env) | FR51; minimal-deployment story | FR51, NFR-P5 |
| **Image distribution** | **GitHub Container Registry (`ghcr.io/ifuensan/salvager`)**, semver-tagged (`v0.1.0`, `v0.2.0`, …, `v1.0.0`). PyPI publication deferred post-launch. | Free for public repos; native auth via GitHub; matches the (c3) single-deployment-shape posture | NFR-M4, FR51 |
| **CI/CD** | GitHub Actions on every PR + tag. Gates: `ruff check`, `ty` (with `mypy` fallback), `pytest --cov` with coverage thresholds (≥ 90% on Phase 2 critical path), `python scripts/adapter_discipline_lint.py`, daemon smoke test (synthetic SKU end-to-end with all adapters mocked). On tag push: build + push GHCR image. | Free tier sufficient for solo project; integrates with personal GitHub | NFR-M1, NFR-M2 |
| **Adapter-discipline lint** | **Custom AST-based script** at `scripts/adapter_discipline_lint.py`. Walks every `.py` file; for files outside `src/salvager/adapters/**`, fails the build on any `import` or `from … import` of a configured deny-list (`hermes_agent`, `tinyfish_*`, `google.genai`, `openai`, `anthropic`, `telegram`, `httpx` for marketplace endpoints, Wallapop/eBay SDK names). Zero external dep; ~50 lines. | Lock the launch-blocker NFR with code we own; no third-party tool drift | NFR-M1 |
| **Restart policy** | `docker-compose.yml: restart: on-failure` with default backoff; `stop_grace_period: 30s` to match FR50 SIGTERM drain budget | NFR-R5 enforcement | NFR-R5, FR50 |
| **Backups** | **Out of project scope.** README documents that `data_dir/` (SQLite stores, cookies, OAuth tokens) and `config_dir/` (wishlist.yaml, config.yaml, .env) are the user's responsibility to back up alongside their existing homelab backup story. | (c3) personal-use; no opinion-imposing on the user's existing infrastructure | (c3), FR54 |
| **Monitoring** | None external at v1. `health` CLI command + structured JSON logs are the operator's window. Optional: a cron-driven external script can shell `salvager health --format json` and Telegram-ping if anything goes red. | NFR-O5 (no remote logging); NFR-O2 (health command) | NFR-O2, NFR-O5 |
| **Secret management** | `.env` with mode 0600 in the user's `config_dir/`. No secrets manager (Vault, SOPS, etc.) at v1. | (c3) single-user; secrets manager is overkill | NFR-S1 |
| **Versioning policy** | Semver. `0.x` until first Phase 2 purchase by ifuensan. `1.0.0` released after: (a) Phase 1 stable for 4–8 weeks, AND (b) at least one successful Phase 2 purchase has been completed end-to-end. | NFR-M4; matches the customer-FAQ Phase 2 trust window | NFR-M4 |

### Decision Impact Analysis

**Implementation sequence (the order epics should pick these up):**

1. **Project initialization** (uv scaffold, directory layout, CI gates skeleton, adapter-discipline lint script, .gitignore, .env.example, wishlist.example.yaml, config.example.yaml).
2. **Domain models** (pydantic schemas for wishlist / listing / evaluation / alert / audit / reconciliation).
3. **Interfaces** (ABCs in `interfaces/` for `PageFetcher`, `BrowserSession`, `ListingEvaluator`, `Store`, `Scheduler`, `TelegramSurface`).
4. **Config + persistence layer** (`.env` loader, `config.yaml` loader, `wishlist.yaml` validator with FR3 scope-guard, `sqlite_store` adapter with append-only enforcement, migrations runner).
5. **Marketplace adapters** (Wallapop unofficial-API + Wallapop TinyFish fallback + eBay.es official-API), with recorded fixtures and integration tests.
6. **LLM evaluator + cache** (Gemini Flash adapter; Hermes-memory-backed cache; wishlist-anchored prompt template).
7. **Telegram surface** (alert + operational message rendering, inline-button handling, retry semantics).
8. **Poll loop orchestrator** (Hermes scheduler integration; the synchronous pipeline; degradation reporter).
9. **CLI subcommands** (init, login, validate-*, test-search, explain, audit, health, logs).
10. **Phase 1 gate**: deploy and run for 4–8 weeks.
11. **Phase 2 buy orchestrator + reconciliation stack** (cross-source reconciliation, receipt-vs-alert reconciliation, daily smoke test, circuit breaker, audit log writes).
12. **Phase 2 CLI** (`phase2 enable/disable/status/smoke-test/reconcile`).
13. **Phase 2 gate**: empirical bias audit (OQ6) and TinyFish per-purchase cost measurement (OQ3).
14. **v1.0 release**.

**Cross-component dependencies:**

- `interfaces/` MUST land before `orchestration/` and `cli/` (everything else depends on the contracts).
- `domain/` and `interfaces/` share zero runtime imports (`domain/` only imports stdlib + pydantic).
- `adapters/` is the **only** package allowed to import marketplace SDKs / Hermes / TinyFish / google-genai / python-telegram-bot. Verified by `scripts/adapter_discipline_lint.py`.
- The `Store` interface is the data-access seam; both `orchestration/` and `cli/` share the same store implementation (different lifecycles — daemon long-lived, CLI short-lived — but identical semantics).
- The `degradation_reporter` ties three surfaces (structured log + Telegram operational alert + `health` state); each subsystem reports degradation through it, never directly to one surface.
- `wishlist.yaml` is the canonical source of truth for entries AND per-entry Phase 2 settings; `phase2_state` SQLite table holds only the **auto-disable lockout** flag (cleared by explicit operator re-enable).
- `BuyOrchestrator` (Phase 2) composes `BrowserSession` + `Reconciler` + `CircuitBreaker` + `Store` + `TelegramSurface`. It is the most-tested module in the codebase per NFR-M2 (≥ 90% line coverage).

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

This section locks 11 pattern categories where independent contributors (human or AI agent) could reasonably diverge. The bias: if it could plausibly differ across two agents implementing two stories, it's specified here. Categories not listed inherit from PEP 8 and ruff defaults.

### Naming Patterns

**Python identifiers (PEP 8, enforced by ruff):**

- Modules and files: `snake_case.py` — no exceptions.
- Classes: `PascalCase`. Pydantic models: `PascalCase` (`WishlistEntry`, `AlertSnapshot`). ABCs in `interfaces/` are `PascalCase` and named after the role, not the implementation (`PageFetcher`, not `MarketplaceFetcher`).
- Functions, methods, variables: `snake_case`. No verb prefixes (`fetch_listing`, not `do_fetch_listing`). Boolean returns: `is_*`, `has_*`, `should_*`.
- Module-level constants: `UPPER_SNAKE_CASE`. Reserved for configuration constants only; runtime config comes from `config.yaml`/`.env`.
- Async functions: `async def name`, no prefix. Do not name async functions `a_*` or `async_*`.
- Private members: single leading underscore (`_helper`). Double leading underscore (name mangling) is never used.

**SQLite identifiers:**

- Table names: `snake_case_plural` (`alert_snapshots`, `tap_events`, `transactions`, `seen_listings`, `phase2_state`, `phase2_smoke_tests`, `_meta`). The `_meta` table name preserves leading underscore as a "system table" marker.
- Column names: `snake_case`. Boolean columns: `is_*`, `has_*` (e.g., `is_match_fired`).
- Primary keys: `id INTEGER PRIMARY KEY` for tables needing a surrogate key. Natural composite keys for tables that have one — `wishlist_runtime_state` keys on `(manufacturer, model, ref)`.
- Foreign keys: `<referenced_table_singular>_id` (e.g., `alert_snapshot_id` referencing `alert_snapshots(id)`). Always declared with `REFERENCES <table>(id) ON DELETE RESTRICT` (no cascading deletes — append-only).
- Index names: `idx_<table>_<columns>` (e.g., `idx_seen_listings_url`, `idx_alert_snapshots_created_at`).
- Timestamps: column suffix `_utc`, type `TEXT`, value ISO 8601 with `Z` suffix and millisecond precision (`'2026-05-10T14:32:17.842Z'`). SQLite has no native timestamp type; ISO strings sort correctly lexically.

**YAML key names (wishlist.yaml, config.yaml):**

- `snake_case`. Match the pydantic model field names exactly (no field aliasing in pydantic configs at v1).

**Telegram identifiers:**

- Inline button `callback_data` strings: `<surface>:<verb>:<id>` (e.g., `listing:skip:abc123`, `listing:buy:def456`, `listing:snooze:abc123`). Three-segment colon-delimited, never longer.
- Operational alert prefixes (FR21): `⚠️ ` (high-priority, with trailing space) and `ℹ️ ` (informational, with trailing space). Locked emoji bytes — do not substitute visually similar codepoints.

**Logging `event` taxonomy:**

- Format: `<subsystem>.<verb>` (e.g., `poll.start`, `poll.complete`, `fetch.success`, `fetch.fallback`, `evaluate.cache_hit`, `evaluate.llm_call`, `alert.sent`, `alert.delivery_failed`, `phase2.buy_started`, `phase2.reconcile_passed`, `phase2.reconcile_tripped`, `phase2.smoke_passed`, `phase2.smoke_drift`, `phase2.auto_disabled`, `phase2.purchase_completed`, `phase2.circuit_opened`, `auth.session_expired`, `daemon.startup`, `daemon.shutdown`).
- The complete enumerated set lives in `src/salvager/observability/events.py` as a `StrEnum`. Adding a new event requires adding it to the enum first; no free-form `event=` strings in code.
- Subsystems: `poll`, `fetch`, `evaluate`, `alert`, `phase2`, `auth`, `daemon`, `audit`, `health`, `cli`.

### Structure Patterns

**Project organization:** locked in step 3. Repeating only the load-bearing rules:

- Tests live in `tests/` as a sibling of `src/`. Never co-located `*_test.py` next to source modules.
- Test files mirror source structure: `src/salvager/orchestration/buy_orchestrator.py` ↔ `tests/unit/orchestration/test_buy_orchestrator.py`. Use `conftest.py` per directory for shared fixtures.
- Recorded marketplace fixtures live in `tests/fixtures/<marketplace>/<scenario>.json` (or `.html` for Wallapop HTML responses). One fixture file per scenario; never inlined into test code.
- Domain code (`src/salvager/domain/`) imports only stdlib + pydantic. **Imports are checked by `scripts/adapter_discipline_lint.py`.**
- Adapter code (`src/salvager/adapters/<package>/`) is the **only** location that imports marketplace SDKs / Hermes / TinyFish / google-genai / python-telegram-bot. Same lint enforces this.
- Orchestration code (`src/salvager/orchestration/`) imports `interfaces/` only — never adapters directly.

**Module-level layout (within a single .py file):**

1. `from __future__ import annotations` (always; standardizes type-hint behavior).
2. Module docstring (one-liner minimum; explains the module's role in the architecture, not what each function does).
3. Stdlib imports (alphabetical, ruff-managed).
4. Third-party imports (alphabetical, ruff-managed).
5. Local imports (alphabetical, ruff-managed).
6. Module-level constants (`UPPER_SNAKE_CASE`).
7. Type aliases.
8. Public classes / functions (in dependency order — used-first, used-by later).
9. Private classes / functions (`_leading_underscore`).

### Format Patterns

**Type-hint style (Python ≥ 3.12):**

- `X | None` instead of `Optional[X]`. `list[X]` instead of `List[X]`. `dict[K, V]` instead of `Dict[K, V]`. `Literal[...]`, `TypedDict`, and `Self` from `typing`.
- Generic type parameters use the **PEP 695** syntax: `def foo[T](x: T) -> T: ...` and `class Container[T]: ...` (Python 3.12 feature). Older `TypeVar` forms only when interfacing with libraries that still need them.
- Function signatures prefer keyword-only arguments where ambiguity is possible: `def fetch(self, *, url: str, headers: dict[str, str] | None = None) -> Response`.
- All public functions, methods, and module-level callables have full type annotations. Private (`_leading_underscore`) helpers may omit annotations on local variables but retain them on parameters and return types.

**Domain models (boundary types):**

- `pydantic.BaseModel` for **everything that crosses a boundary** — config files (wishlist, config.yaml, .env), audit log rows, alert payloads, LLM evaluation results, marketplace API responses.
- `model_config = ConfigDict(frozen=True, extra="forbid")` is the default for all boundary models. `extra="forbid"` is the FR3 scope-guard mechanism for wishlist (catches arbitrage fields automatically).
- Field naming: `snake_case`. No `Field(alias=...)` at v1 — keep the same name on Python and YAML/JSON sides.
- Validators: `@field_validator` and `@model_validator` (pydantic v2 style). No legacy v1 `@validator`.

**Pure value objects (internal-only):**

- `dataclasses.dataclass(frozen=True, slots=True)` for value objects that never cross a boundary (e.g., `PriceTolerance`, `EvaluationKey`, `PollWindow`).
- Don't reach for pydantic when a frozen dataclass suffices — pydantic adds startup cost we don't need for internal values.

**Domain-layer datetime handling:**

- Always tz-aware `datetime.datetime` in UTC (`datetime.now(tz=datetime.UTC)`). Naive datetimes are forbidden in the codebase.
- ISO 8601 with millisecond precision and `Z` suffix when serialized to SQLite or JSON.
- Helper module `domain/time.py` exposes `now_utc()`; tests inject a `Clock` interface to control time.

**JSON serialization (CLI `--format json`, audit-log export):**

- `snake_case` field names (matches Python).
- Datetimes serialized as ISO 8601 strings (`'2026-05-10T14:32:17.842Z'`).
- Booleans as `true`/`false`. `null` for absent values; do NOT use empty strings or `0` as null sentinels.
- No wrapper envelope: `audit show --format json` emits an array of audit objects directly. No `{"data": [...], "error": null}`.
- Errors from CLI commands go to **stderr** as one or more single-line JSON objects with `{"error": "<class>", "message": "...", "exit_code": <n>}`. stdout is reserved for the actual command output (or empty on error).

**SQLite I/O conventions:**

- Connection per worker: long-lived for the daemon, short-lived for CLI subcommands. Both connections set `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` on open.
- All queries use parameterized statements (`?`-style). String concatenation into SQL is forbidden.
- Schema migrations applied at daemon startup before scheduling any jobs; CLI subcommands fail fast (exit 2) if the schema is out of date and refuse to attempt write operations against an outdated schema.
- `Store` interface methods return either pydantic models (for typed reads) or raise; never return raw `sqlite3.Row` outside the `adapters/sqlite_store/` package.

### Communication Patterns

**Internal data flow (intra-process):**

- Synchronous pipeline expressed as `async def` functions with explicit `await` between stages. No internal event bus, no `asyncio.Queue`-based decoupling at v1.
- Each pipeline stage takes the previous stage's output and returns the next stage's input. No global state passed sideways.
- The pipeline is composed in `orchestration/poll_loop.py`; individual stages live in their respective modules.

**Telegram message construction:**

- All listing alerts are constructed via a single function: `domain/alert.py: render_listing_alert(snapshot: AlertSnapshot, phase2_enabled: bool) -> RenderedAlert`. There is **no** alternate code path that builds listing alerts.
- All operational alerts are constructed via `domain/alert.py: render_operational_alert(severity: Literal["info", "warn"], event: EventName, ctx: dict[str, Any]) -> RenderedAlert`.
- `RenderedAlert` is a pydantic model with `text: str`, `parse_mode: Literal["MarkdownV2"]`, `photo_url: str | None`, `inline_keyboard: list[list[InlineButton]] | None`. The Telegram adapter translates `RenderedAlert` → telegram-bot SDK calls; it never assembles message text itself.
- Snapshot tests (syrupy) lock the rendered output for a fixed set of fixtures. Format changes require snapshot regeneration AND an audit-log schema migration (FR22).

**Concurrency rules:**

- The daemon's `poll_loop` uses `asyncio.TaskGroup` (Python 3.11+) to fan out per-listing LLM evaluation across at most 8 concurrent tasks (Hermes subagent ceiling per kickoff). One `TaskGroup` per poll cycle; if any task raises, the group propagates and the cycle's results are discarded.
- All shared mutable state across async tasks is protected by `asyncio.Lock` instances owned by the orchestrator — never module-level globals.
- The CLI subcommands run sync; they call into core modules via a small synchronous facade that internally uses `asyncio.run()` only when an async path is unavoidable (e.g., `test-search` performs a single fetch+evaluate). Most CLI commands stay fully sync against the SQLite store.

### Process Patterns

**Exception hierarchy and exit-code mapping:**

- Single root: `class HardwareHunterError(Exception)` in `domain/errors.py`.
- Subclasses, each mapped 1:1 to an exit code per FR48:

  | Exception | Exit code | Use |
  |---|---|---|
  | `UsageError` | 1 | CLI argument problems, unknown subcommand |
  | `ConfigError` | 2 | wishlist/config/.env validation failure |
  | `AdapterError` | 3 | network/marketplace/TinyFish/Hermes failure |
  | `AuthError` | 4 | cookie/OAuth/Telegram-bot-token failure |
  | `Phase2GuardrailTripped` | 5 | smoke-test drift, reconciliation mismatch, circuit breaker open |

- Adapter packages raise more specific subclasses internally (e.g., `WallapopRateLimited(AdapterError)`), but the top-level handler maps to exit code 3.
- The CLI's top-level handler in `cli/app.py` catches `HardwareHunterError`, logs a structured JSON Lines error event, prints the JSON error to stderr, and `sys.exit(err.exit_code)`. Unexpected exceptions exit 70 (sysexits.h `EX_SOFTWARE`) with a full traceback in the structured log.
- The daemon's top-level handler logs the exception structurally, emits an operational Telegram alert (FR21), and exits non-zero. Docker `restart: on-failure` restarts the container.

**Error handling within modules:**

- No `except Exception` or bare `except:` outside of the top-level handlers. All `except` clauses name a specific exception class.
- No exception suppression silently. If a caller wants to convert an exception, it must be logged at `info`+ level via the `degradation_reporter`.
- `try/except/raise` re-raise pattern: only when adding context — `raise ConfigError(...) from e`.

**Degradation reporting (cross-cutting):**

- **Single helper** in `orchestration/degradation_reporter.py`: `report_degradation(event: EventName, severity: Literal["info", "warn"], ctx: dict[str, Any]) -> None`.
- It produces three side effects per call: structured-log entry, operational Telegram alert, `phase2_state` SQLite row (if applicable). Each surface is a separate try/except so a Telegram outage does not block the log entry.
- **No subsystem ever talks directly to one of those three surfaces for a degradation event.** The reporter is the only path.
- Tests assert on the reporter's call set, not on individual surfaces — this is the integration seam for "no silent failure."

**Loading-state and retry conventions:**

- HTTP adapters use httpx with `timeout=httpx.Timeout(30.0)` default; per-call override via parameter.
- Retries for transient external failures (5xx, network errors) use **tenacity** (or equivalent) with exponential backoff. Default: 3 attempts, base 1s, factor 2, jitter ±25%. Max attempts and base configurable per adapter via `config.yaml`.
- Rate-limit responses (429) honor `Retry-After` headers; if not present, use the default retry policy capped at the configured RPM.
- **Phase 2 buy-flow has zero retry** at v1. A failure aborts the buy and logs a degradation. Retries on a buy-flow failure are an explicit anti-pattern (NFR-S5: never accidentally double-buy).

**CLI conventions (typer):**

- Subcommand grouping is hierarchical: `phase2 enable`, `audit show`, `validate-wishlist`. Hyphenated subcommand names use a hyphen (typer renders Python `validate_wishlist` ↔ CLI `validate-wishlist` automatically with `name="validate-wishlist"`).
- Long flags only (`--format json`, `--last 50`). No short flags except for typer's built-in `--help`/`-h` and `--version`/`-v`.
- All flag values that map to a finite set use `typer.Option(..., case_sensitive=False)` with `Literal[...]` types (e.g., `--format` ∈ `{"text", "json"}`).
- Output: human-readable plain text by default with ANSI colors when stdout is a TTY (`rich.console.Console(soft_wrap=True)`); `--format json` switches to JSON Lines on stdout. The same data structure underlies both formats — never compute different content per format.
- Read-only commands: idempotent, no side effects beyond rate-limited fetches (NFR / FR43–47).
- Destructive commands (`init --force`, `phase2 disable --all`): require interactive `typer.confirm()` prompt; in non-TTY context they fail (NFR-S6, FR48).

### Testing Patterns

**Test naming:**

- File: `test_<module_under_test>.py` (so `domain/wishlist.py` → `tests/unit/domain/test_wishlist.py`).
- Function: `test_<unit>_<scenario>_<expected>` (e.g., `test_wishlist_validator_rejects_arbitrage_field`, `test_reconciler_passes_when_prices_match`).
- Class-based grouping (`class TestWishlistValidator:`) only when sharing setup; otherwise function-style.

**Fixture conventions:**

- Pure-data fixtures (e.g., a sample `WishlistEntry`) live in `conftest.py` files at the appropriate scope.
- Recorded marketplace HTTP fixtures live in `tests/fixtures/<marketplace>/<scenario>.json` and are loaded via a `load_fixture(name: str)` helper. Never inline a 2KB API response in a test function.
- Async tests use `pytest-asyncio` with `@pytest.mark.asyncio` per test (avoid the `auto` mode that surprises contributors).
- Time is controlled via a `frozen_time` fixture that injects a fixed `Clock`. No `freezegun` — the `Clock` interface is project-owned (composability with test doubles).

**Coverage expectations:**

- Phase 2 critical-path modules require ≥ 90% line coverage at v1.0 (NFR-M2). Coverage is verified in CI; PRs that drop coverage on these modules below threshold fail the build.
- Other modules: best-effort coverage; no hard threshold below which CI fails. Quality > quantity.

### Logging and Observability Patterns

**Log line schema (NFR-O1):**

- Single-line JSON object per log event. Required fields (every event):
  - `level` ∈ `{debug, info, warn, error}`
  - `ts` — ISO 8601 UTC with milliseconds and `Z` suffix
  - `event` — from the `EventName` enum
- Conditional fields, included when the value applies:
  - `entry` — wishlist entry key as `"<manufacturer>|<model>|<ref>"`
  - `marketplace` ∈ `{wallapop, ebay}`
  - `listing_id` — marketplace-issued listing identifier
  - `latency_ms` — integer milliseconds
  - `error_class` — fully qualified Python class name on error events
  - `path` — adapter path used for fetch (`wallapop_api`, `wallapop_tinyfish`, `ebay_api`)
- Forbidden in log lines: credentials, cookie values, OAuth tokens, full listing descriptions (use `listing_id`), full LLM prompt+response bodies (the cache holds those for `explain` debugging).

**Health command output (NFR-O2):**

- Single JSON object emitted to stdout under `--format json`. Same data rendered as a colorized text table by default.
- Top-level keys: `daemon_status` (`running|stopped|degraded`), `adapters` (per-adapter status object), `scheduler` (job count + last-tick), `last_poll` (per-marketplace), `last_alert`, `phase2` (per-entry enabled state + global lockout flag).
- Suitable for a cron-driven external health check that pipes to `jq`.

### YAML Round-Tripping (`ruamel.yaml`)

- `phase2 enable/disable` rewrites `wishlist.yaml` using `ruamel.yaml` round-trip mode (`YAML(typ='rt')`) — preserves comments, key order, list style.
- The wishlist read path (daemon load, validator) uses **plain PyYAML** for speed — pydantic validation rejects any field changes accidentally introduced by ruamel.yaml's serialization.
- A snapshot test (syrupy) covers a sample `wishlist.example.yaml` round-tripped through enable/disable to lock the format. Format drift fails the build.

### Pattern Enforcement

**Verified by CI (build fails on violation):**

| Pattern | Tool |
|---|---|
| PEP 8 / import order / format | `ruff check` + `ruff format --check` |
| Type hints conformance | `ty .` (with `mypy .` fallback) |
| Adapter discipline (NFR-M1) | `python scripts/adapter_discipline_lint.py` |
| Phase 2 critical-path coverage ≥ 90% | `pytest --cov` with thresholds in `pyproject.toml` |
| Telegram message format stability | syrupy snapshot tests |
| YAML round-trip stability | syrupy snapshot tests |
| Audit-table append-only enforcement | property-based test asserting `Store` interface lacks `update_*`/`delete_*` methods on audit tables |
| Logging event vocabulary | unit test asserting every `event=...` literal in code matches `EventName` enum |

**Verified by code review (no automated check):**

- Naming conventions for test functions, fixtures, callback_data strings, log event taxonomy.
- "No silent failure": every `except` clause either re-raises or calls `degradation_reporter.report_degradation`.
- Domain code stays import-pure (PEP 8 imports + ruff lint catch most cases; reviewer verifies semantics).

### Pattern Examples

**Good — adapter-disciplined module:**

```python
# src/salvager/orchestration/poll_loop.py
from __future__ import annotations

import asyncio
import datetime as dt

from salvager.domain.alert import AlertSnapshot, render_listing_alert
from salvager.domain.errors import AdapterError
from salvager.interfaces import (
    ListingEvaluator,
    PageFetcher,
    Scheduler,
    Store,
    TelegramSurface,
)
from salvager.observability.events import EventName
from salvager.observability.logging import log

# Note: no imports from salvager.adapters here — passes adapter discipline lint.
```

**Anti-pattern — adapter discipline violation:**

```python
# src/salvager/orchestration/poll_loop.py
from salvager.adapters.wallapop_api import WallapopAPIClient   # ❌ direct adapter import
import google.generativeai as genai                                    # ❌ external SDK in business logic
```

**Good — degradation reporting:**

```python
try:
    listing = await fetcher.fetch(url=listing_url)
except AdapterError as err:
    degradation_reporter.report_degradation(
        event=EventName.FETCH_FAILED,
        severity="warn",
        ctx={"marketplace": "wallapop", "listing_id": listing_id, "error_class": err.__class__.__qualname__},
    )
    return None
```

**Anti-pattern — silent failure:**

```python
try:
    listing = await fetcher.fetch(url=listing_url)
except Exception:
    return None       # ❌ broad except + silent return; "no silent failure" rule violated
```

### All AI Agents Implementing on This Codebase MUST:

- Run `uv sync` before doing anything; never invoke pip directly.
- Run `uv run ruff check .`, `uv run ty .` (or `uv run mypy .`), and `uv run pytest -q` before committing.
- Run `uv run python scripts/adapter_discipline_lint.py` before adding any import that touches Hermes / TinyFish / google-genai / python-telegram-bot / marketplace SDKs.
- Use only events from `EventName` enum in `event=` log fields; add new events to the enum first.
- Use only exception subclasses of `HardwareHunterError`; never raise bare `Exception` or `RuntimeError`.
- Never assemble Telegram message text outside `domain/alert.py` rendering helpers.
- Never write to audit tables outside `Store.record_*` methods.
- Never bypass `degradation_reporter` for any failure that should be visible to the operator.

## Project Structure & Boundaries

### Complete Project Directory Structure (authoritative)

```text
salvager/
├── .github/
│   └── workflows/
│       ├── ci.yml                                    # PR + push: ruff, ty/mypy, pytest+cov, adapter-discipline lint, daemon smoke test
│       └── release.yml                               # tag push: build + push GHCR image
├── .gitignore                                        # /.env, /wishlist.yaml, /config.yaml, /data/, /.venv/, .ruff_cache/, .pytest_cache/, .ty_cache/, __pycache__/
├── pyproject.toml                                    # uv-managed; deps + ruff + ty + pytest + coverage thresholds
├── uv.lock                                           # committed
├── Dockerfile                                        # python:3.12-slim base; multi-stage; entrypoint = `salvager`
├── docker-compose.yml                                # single service; mounts ./data and ./config; restart: on-failure; stop_grace_period: 30s
├── .env.example                                      # tracked
├── wishlist.example.yaml                             # tracked; example HDD + RAM entries
├── config.example.yaml                               # tracked; default rates/thresholds/log level
├── README.md                                         # personal monitoring tool framing + legal disclaimer + secondary-account recommendation (FR54)
├── CONTRIBUTING.md                                   # "no arbitrage PRs" rule + 3 invitation categories (FR52)
├── ROADMAP.md                                        # multi-marketplace, arbitrage-as-separate-repo, C&D-induced sunset (FR53)
├── LICENSE                                           # MIT (FR54)
│
├── src/salvager/
│   ├── __init__.py
│   ├── __main__.py                                   # `python -m salvager` entry; calls cli.app:main
│   │
│   ├── cli/                                          # FR39–FR48
│   │   ├── __init__.py
│   │   ├── app.py                                    # main typer.Typer(); top-level error handler; exit-code mapping
│   │   ├── init_cmd.py                               # FR40
│   │   ├── login_cmd.py                              # FR41 (wallapop), FR42 (ebay)
│   │   ├── validate_cmd.py                           # FR3 (validate-wishlist), validate-config
│   │   ├── test_search_cmd.py                        # FR43
│   │   ├── explain_cmd.py                            # FR44
│   │   ├── phase2_cmd.py                             # FR45, FR46 (status/enable/disable/smoke-test/reconcile)
│   │   ├── audit_cmd.py                              # FR37 (show/export)
│   │   ├── health_cmd.py                             # FR47, NFR-O2
│   │   ├── logs_cmd.py                               # FR48 helper
│   │   └── daemon_cmd.py                             # FR39 (implicit default), FR50 (SIGTERM drain)
│   │
│   ├── domain/                                       # PURE; stdlib + pydantic only
│   │   ├── __init__.py
│   │   ├── wishlist.py                               # WishlistEntry, Wishlist; FR1, FR2, FR4, FR5, FR17 schema
│   │   ├── scope_guard.py                            # FR3 arbitrage-field rejection (extra="forbid" + custom validator)
│   │   ├── prompts.py                                # wishlist-anchored prompt template; FR13, FR15, FR17
│   │   ├── listing.py                                # Listing model
│   │   ├── evaluation.py                             # ListingEvaluation, ConfidenceLevel enum
│   │   ├── alert.py                                  # AlertSnapshot, RenderedAlert; render_listing_alert(), render_operational_alert(); FR18, FR19, FR21, FR22
│   │   ├── audit.py                                  # AlertSnapshotRow, TapEventRow, TransactionRow; FR36
│   │   ├── reconciliation.py                         # ReconciliationResult, tolerance math (pure); FR31
│   │   ├── circuit.py                                # CircuitBreakerState (pure FSM); FR34
│   │   ├── errors.py                                 # HardwareHunterError + 5 subclasses; FR48 exit-code mapping
│   │   ├── time.py                                   # now_utc() and Clock interface
│   │   └── perceptual_hash.py                        # photo perceptual hash type + comparison (pure); FR36
│   │
│   ├── interfaces/                                   # ABCs only; NFR-M1
│   │   ├── __init__.py
│   │   ├── page_fetcher.py                           # PageFetcher (search + fetch); FR6, FR7, FR9
│   │   ├── browser_session.py                        # BrowserSession (Phase 2 buy flow); FR24, FR30
│   │   ├── listing_evaluator.py                      # ListingEvaluator (LLM-agnostic); FR13, FR16
│   │   ├── store.py                                  # Store (write-only on audit subset); FR10, FR36, NFR-S4
│   │   ├── scheduler.py                              # Scheduler (Hermes abstraction); FR8
│   │   └── telegram_surface.py                       # TelegramSurface (delivery + retry); FR18, FR21, NFR-I6
│   │
│   ├── adapters/                                     # ONLY package allowed to import external SDKs (NFR-M1)
│   │   ├── __init__.py
│   │   ├── wallapop_api/                             # FR6 primary path
│   │   │   ├── __init__.py
│   │   │   ├── client.py                             # httpx-based unofficial-API client
│   │   │   ├── parser.py                             # response → domain Listing
│   │   │   └── rate_limiter.py                       # client-side rate limiter (NFR-I2)
│   │   ├── wallapop_tinyfish/                        # FR6 fallback path
│   │   │   ├── __init__.py
│   │   │   └── client.py                             # TinyFish Search/Fetch via Hermes MCP
│   │   ├── ebay_api/                                 # FR7
│   │   │   ├── __init__.py
│   │   │   ├── client.py                             # official eBay Browse API
│   │   │   ├── oauth.py                              # FR42 token persistence + refresh
│   │   │   └── rate_limiter.py                       # NFR-I5
│   │   ├── tinyfish_browser/                         # FR30 Phase 2 buy flow
│   │   │   ├── __init__.py
│   │   │   ├── wallapop_pay.py                       # Wallapop chat → Wallapop Pay flow
│   │   │   └── ebay_checkout.py                      # eBay.es Cómpralo-ya checkout
│   │   ├── llm_gemini/                               # FR13, FR16
│   │   │   ├── __init__.py
│   │   │   ├── evaluator.py                          # google-genai wrapper
│   │   │   └── cache.py                              # Hermes-memory-backed per-URL cache
│   │   ├── llm_openai/                               # alt provider (config-driven)
│   │   ├── llm_anthropic/                            # alt provider (config-driven)
│   │   ├── hermes_scheduler/                         # FR8
│   │   │   └── client.py                             # Hermes scheduler primitive wrapper
│   │   ├── telegram_bot/                             # FR18, FR21, NFR-I6
│   │   │   ├── __init__.py
│   │   │   ├── delivery.py                           # python-telegram-bot wrapper + retry
│   │   │   └── inline_callbacks.py                   # callback_data parsing for buttons
│   │   └── sqlite_store/                             # NFR-S4 append-only enforcement
│   │       ├── __init__.py
│   │       ├── connection.py                         # WAL + foreign_keys=ON setup
│   │       ├── seen_listings.py                      # FR10
│   │       ├── audit_writer.py                       # record_alert_snapshot/record_tap/record_transaction (write-only)
│   │       ├── audit_reader.py                       # read-only audit queries
│   │       ├── phase2_state.py                       # auto-disable lockout flag
│   │       └── meta.py                               # _meta.schema_version
│   │
│   ├── orchestration/                                # composes interfaces; never imports adapters directly
│   │   ├── __init__.py
│   │   ├── poll_loop.py                              # FR8, FR11; the synchronous pipeline within asyncio.TaskGroup
│   │   ├── buy_orchestrator.py                       # FR23–FR35; the most-tested module (NFR-M2)
│   │   ├── reconciler.py                             # FR31 (cross-source pre-buy), FR32 (receipt-vs-alert post-buy)
│   │   ├── circuit_breaker.py                        # FR34 (composes domain.circuit FSM with Store persistence)
│   │   ├── smoke_test.py                             # FR33 daily synthetic
│   │   ├── degradation_reporter.py                   # NFR-R3 + FR21; the "no silent failure" spine
│   │   └── pipeline_stages.py                        # individual stages (search, fetch, dedup, evaluate, alert)
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── env.py                                    # pydantic-settings .env loader; FR49
│   │   ├── config_yaml.py                            # config.yaml schema + loader
│   │   ├── wishlist_yaml.py                          # wishlist.yaml loader (PyYAML for read; ruamel.yaml for write); calls scope_guard
│   │   ├── permissions.py                            # NFR-S2 mode 0600 verification at startup
│   │   └── paths.py                                  # data_dir / config_dir resolution
│   │
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── events.py                                 # EventName StrEnum (NFR-O1 vocabulary)
│   │   ├── logging.py                                # JSON Lines logger; structured fields; secret redaction
│   │   └── health.py                                 # health command implementation; FR47, NFR-O2
│   │
│   └── migrations/                                   # SQL migration files; applied at daemon startup
│       ├── 001_initial.sql
│       ├── 002_phase2_state.sql
│       └── ...
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                                   # global fixtures: tmp data dir, fake Clock, fake Store
│   ├── unit/
│   │   ├── domain/                                   # pure-logic tests (high coverage, fast)
│   │   ├── orchestration/                            # NFR-M2 ≥ 90% on buy_orchestrator/reconciler/circuit_breaker/smoke_test/audit_writer
│   │   ├── config/
│   │   └── observability/
│   ├── integration/
│   │   ├── adapters/
│   │   │   ├── wallapop_api/                         # against tests/fixtures/wallapop_api/*.json
│   │   │   ├── wallapop_tinyfish/
│   │   │   ├── ebay_api/
│   │   │   ├── tinyfish_browser/                     # against recorded buy-flow fixtures
│   │   │   ├── llm_gemini/                           # canned prompt → response fixtures
│   │   │   ├── telegram_bot/
│   │   │   └── sqlite_store/                         # round-trip + append-only enforcement tests
│   │   └── cli/                                      # end-to-end CLI invocations against tmp dirs
│   ├── e2e/
│   │   └── test_daemon_cycle.py                      # full poll cycle with all adapters mocked; CI smoke test
│   ├── fixtures/
│   │   ├── wallapop_api/                             # recorded API responses
│   │   ├── wallapop_html/                            # recorded HTML detail pages
│   │   ├── ebay_api/
│   │   ├── llm_responses/                            # canned LLM eval responses
│   │   ├── telegram_messages/                        # syrupy snapshots for FR22 stability
│   │   ├── price_parsers/                            # comma vs dot fixtures (the Q9 scenario regression set)
│   │   └── wishlist_round_trip/                      # ruamel.yaml round-trip snapshots
│   └── property/
│       └── test_store_audit_append_only.py           # property test asserting Store has no update_*/delete_* on audit tables
│
└── scripts/
    ├── adapter_discipline_lint.py                    # NFR-M1; AST walks src/, verifies imports
    ├── verify_log_event_vocabulary.py                # asserts every event= literal matches EventName
    └── ...
```

### Architectural Boundaries

**Boundary diagram (high-level):**

```text
                 ┌────────────────────────────────────────────────────────┐
                 │                       cli/                             │
                 │   (typer subcommands; sync; FR39–FR48)                 │
                 └────────────┬───────────────────────────┬───────────────┘
                              │                           │
                              │ uses                      │ uses
                              ▼                           ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                   orchestration/                            │
        │   poll_loop · buy_orchestrator · reconciler · circuit       │
        │   smoke_test · degradation_reporter                         │
        │   (composes interfaces; never imports adapters)             │
        └─────┬───────────────┬───────────────────────────────┬───────┘
              │               │                               │
              │ imports       │ imports                       │ imports
              ▼               ▼                               ▼
  ┌────────────────┐  ┌─────────────────┐         ┌─────────────────┐
  │  interfaces/   │  │   domain/       │         │   config/       │
  │   (ABCs)       │  │  (PURE: stdlib  │         │  (loaders;      │
  │                │  │  + pydantic)    │         │  pydantic-      │
  │                │  │                 │         │  settings)      │
  └────────┬───────┘  └─────────────────┘         └─────────────────┘
           │
           │ implemented by
           ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                          adapters/                               │
  │                                                                  │
  │   wallapop_api · wallapop_tinyfish · ebay_api · tinyfish_browser │
  │   llm_gemini · llm_openai · llm_anthropic · hermes_scheduler     │
  │   telegram_bot · sqlite_store                                    │
  │                                                                  │
  │   ↑ ONLY package allowed to import external SDKs (NFR-M1)        │
  └──────────────────────────────────────────────────────────────────┘
                                  │
                                  │ external
                                  ▼
        Wallapop API · TinyFish MCP · eBay API · Telegram · LLM provider · SQLite
```

**API boundaries:**

| Boundary | Direction | Owner | Enforcement |
|---|---|---|---|
| `domain/` ← rest of code | inbound only (others import domain) | `domain/__init__.py` re-exports | Adapter-discipline lint forbids domain → adapters/orchestration/cli imports |
| `interfaces/` ← `domain/`, `orchestration/`, `cli/` | inbound only | ABC contracts | Adapter packages must subclass these ABCs |
| `adapters/` ← `interfaces/` (implementing) and external SDKs | inbound from interfaces; outbound to SDKs | One package per concern | Adapter-discipline lint: no business logic outside `adapters/` may import the deny-listed external SDKs |
| `orchestration/` ← `cli/` and `__main__.py` | inbound only | Composition root | `cli/app.py` is the sole composition root for CLI; `cli/daemon_cmd.py` for daemon |
| `config/` ← all packages | inbound only (others read configs) | Schema validators in `config/`; load-once in process | Hot-reload forbidden (FR49) |
| External boundary (network) | outbound only | `adapters/` | TLS verify=True always (NFR-S3); rate-limited per adapter (NFR-I2/I5) |
| User boundary (Telegram) | bidirectional | `adapters/telegram_bot/` | Inbound chat-ID allowlist (NFR-S1); inbound from non-allowed chat IDs silently dropped |

**Component boundaries (inside `orchestration/`):**

| Component | Composes | FRs covered |
|---|---|---|
| `poll_loop` | `Scheduler` + `PageFetcher` + `Store` (seen_listings + dedup + alert_snapshots) + `ListingEvaluator` + `TelegramSurface` | FR6–11, FR13–16, FR18–21 |
| `buy_orchestrator` | `BrowserSession` + `Reconciler` + `CircuitBreaker` + `Store` (audit_writer, phase2_state) + `TelegramSurface` | FR23–FR35 |
| `reconciler` | `PageFetcher` (alternate path) + `Store` (transaction record lookup) | FR31, FR32 |
| `circuit_breaker` | `Store` (phase2_state) + `domain/circuit` FSM | FR34, FR35 |
| `smoke_test` | `PageFetcher` (synthetic listing fetch) + `domain/reconciliation` | FR33 |
| `degradation_reporter` | `observability/logging` + `TelegramSurface` + `Store` (phase2_state when applicable) | NFR-R3, FR21 |

**Data boundaries:**

| Data class | Owner | Reader | Writer |
|---|---|---|---|
| `wishlist.yaml` | User edits + `cli/phase2_cmd` (via ruamel.yaml) | daemon poll cycle, `cli/validate_cmd`, `cli/explain_cmd`, `cli/test_search_cmd` | User; `cli/phase2_cmd` |
| `config.yaml` | User edits | All loaders at startup; daemon's 30-second config rescan | User only |
| `.env` | User edits | `pydantic-settings` once at process start | User only; never written by code |
| Cookie file (Wallapop) | `cli/login_cmd` (writes), daemon (reads) | `adapters/wallapop_api`, `adapters/tinyfish_browser` (Phase 2) | `cli/login_cmd` |
| OAuth tokens (eBay) | `cli/login_cmd` (initial), daemon (refresh) | `adapters/ebay_api` | `cli/login_cmd`, `adapters/ebay_api/oauth.py` (refresh path) |
| `seen_listings` table | daemon | daemon + `cli/audit_cmd` (read-only) | daemon (poll cycle) |
| `alert_snapshots` table | daemon | daemon + `cli/audit_cmd`, `cli/explain_cmd`, `buy_orchestrator` | daemon only via `Store.record_alert_snapshot` (append-only) |
| `tap_events` table | daemon | daemon + `cli/audit_cmd` | daemon only via `Store.record_tap` (append-only) |
| `transactions` table | daemon | daemon + `cli/audit_cmd`, `reconciler` | daemon only via `Store.record_transaction` (append-only) |
| `phase2_state` table | daemon + `cli/phase2_cmd` | daemon + `cli/phase2_cmd`, `cli/health_cmd` | daemon (auto-disable), `cli/phase2_cmd` (manual re-enable) |
| `_meta` table | daemon at startup | migrations runner | migrations runner only |

### Requirements to Structure Mapping

**Functional Requirements → modules:**

| FR group | Primary module(s) | Supporting modules |
|---|---|---|
| **FR1–FR5** Wishlist Management | `domain/wishlist.py`, `domain/scope_guard.py`, `config/wishlist_yaml.py`, `cli/validate_cmd.py` | `cli/phase2_cmd.py` (writes via ruamel.yaml) |
| **FR6–FR12** Marketplace Monitoring | `adapters/wallapop_api/`, `adapters/wallapop_tinyfish/`, `adapters/ebay_api/`, `orchestration/poll_loop.py`, `adapters/sqlite_store/seen_listings.py` | `adapters/hermes_scheduler/`, `interfaces/page_fetcher.py`, `interfaces/scheduler.py` |
| **FR13–FR17** Listing Evaluation | `adapters/llm_gemini/evaluator.py`, `adapters/llm_gemini/cache.py`, `domain/prompts.py`, `domain/evaluation.py` | `interfaces/listing_evaluator.py` |
| **FR18–FR22** Alert Notifications | `domain/alert.py`, `adapters/telegram_bot/delivery.py`, `orchestration/poll_loop.py` | `interfaces/telegram_surface.py`, `adapters/telegram_bot/inline_callbacks.py` |
| **FR23–FR30** Autonomous Purchase | `orchestration/buy_orchestrator.py`, `adapters/tinyfish_browser/wallapop_pay.py`, `adapters/tinyfish_browser/ebay_checkout.py` | `interfaces/browser_session.py`, `cli/phase2_cmd.py` |
| **FR31–FR35** Phase 2 Failure Defense | `orchestration/reconciler.py`, `orchestration/circuit_breaker.py`, `orchestration/smoke_test.py`, `domain/circuit.py`, `domain/reconciliation.py` | `adapters/sqlite_store/phase2_state.py` |
| **FR36–FR38** Audit & Dispute Evidence | `adapters/sqlite_store/audit_writer.py`, `adapters/sqlite_store/audit_reader.py`, `domain/audit.py`, `cli/audit_cmd.py` | `domain/perceptual_hash.py` |
| **FR39–FR50** Operator Tools & Configuration | `cli/*` (all subcommand modules), `config/*`, `domain/errors.py` | `observability/logging.py` (structured logs and exit-code mapping in `cli/app.py`) |
| **FR51–FR54** Project Distribution | `Dockerfile`, `docker-compose.yml`, `.env.example`, `wishlist.example.yaml`, `config.example.yaml`, `README.md`, `CONTRIBUTING.md`, `ROADMAP.md`, `LICENSE` | repo-root files; `.github/workflows/release.yml` builds GHCR images |

**Non-Functional Requirements → enforcement points:**

| NFR cluster | Enforcement location |
|---|---|
| **NFR-P1–P5** Performance | `config.yaml` (poll cadences); `orchestration/poll_loop.py` (concurrency via `asyncio.TaskGroup`); CI daemon smoke test asserts cold-boot ≤ 30s; per-listing LLM eval latency tracked in logs |
| **NFR-S1–S7** Security | `config/permissions.py` (mode 0600 startup check); `adapters/sqlite_store/audit_writer.py` (append-only, write-only methods); `scripts/adapter_discipline_lint.py` (deny-list incl. payment-rail names like `bizum`); `observability/logging.py` (secret redaction filter) |
| **NFR-R1–R6** Reliability | Adapter packages share zero state (NFR-R1); `adapters/wallapop_api/client.py` falls through to `wallapop_tinyfish` (NFR-R2); `orchestration/degradation_reporter.py` is the universal "no silent failure" spine (NFR-R3) |
| **NFR-I1–I6** Integration | Per-adapter rate limiters; httpx TLS defaults; `pyproject.toml` pins (Hermes v0.13.x); `interfaces/listing_evaluator.py` enables provider swap |
| **NFR-C1–C3** Cost | `adapters/llm_gemini/cache.py` (TTL cache; ≥ 60% hit-rate target); `config.yaml` rate limits enforce client-side budget |
| **NFR-M1–M6** Maintainability | `scripts/adapter_discipline_lint.py` (NFR-M1); `pyproject.toml` coverage thresholds (NFR-M2); `tests/fixtures/` regression set (NFR-M3); Semver enforced via release workflow + CHANGELOG.md gate (NFR-M4); dep-count budget tracked in PR template |
| **NFR-PR1–PR5** Privacy | All persistence local; no remote-logging codepath exists (verified by lint); per-listing scope of data processing in `adapters/wallapop_api/parser.py` and `adapters/ebay_api/client.py` (no profiling, no cross-listing aggregation) |
| **NFR-O1–O5** Observability | `observability/events.py` (event vocabulary); `observability/logging.py` (JSON Lines); `observability/health.py` + `cli/health_cmd.py` (operator surface) |

### Integration Points

**External integrations (all outbound, single-direction except Telegram):**

| Service | Adapter | Auth | Quota / cost |
|---|---|---|---|
| Wallapop unofficial API | `adapters/wallapop_api/` | Cookie file (Netscape format) | Client-side rate limited; human-volume cadence; no bulk extraction |
| Wallapop via TinyFish | `adapters/wallapop_tinyfish/` | TinyFish API key | Free tier: Search 5 req/min, Fetch 25 URLs/min |
| eBay.es Browse API | `adapters/ebay_api/` | OAuth 2.0 | Daily request budget tracked (NFR-I5) |
| TinyFish Browser (Phase 2) | `adapters/tinyfish_browser/` | TinyFish API key | Credit-based; ≤ €1.00/purchase target (NFR-C2; OQ3 measurement task) |
| Gemini Flash (default LLM) | `adapters/llm_gemini/` | API key in `.env` | ~3M tokens/month estimated (NFR-C1) |
| Telegram Bot API | `adapters/telegram_bot/` | Bot token + chat-ID allowlist | Free; rate-limited by Telegram (~30 msg/sec global, ~1 msg/sec/chat) |

**Internal data flow (one poll cycle, Phase 1):**

```text
1. Hermes scheduler fires the wallapop_poll job
   └─→ orchestration/poll_loop.py: poll_marketplace("wallapop")
        │
        ▼
2. Load wishlist.yaml (PyYAML); validate via domain/wishlist + domain/scope_guard
        │
        ▼
3. For each WishlistEntry → asyncio.TaskGroup (≤ 8 concurrent):
        │
        ▼
4.   PageFetcher.search(entry) → list[ListingSummary]
       │ (Wallapop: API path → on failure, fall through to TinyFish path)
        │
        ▼
5.   For each candidate ListingSummary:
        │   (deduped via Store.is_seen by URL + perceptual hash)
        ▼
6.     PageFetcher.fetch(listing_url) → Listing
        │
        ▼
7.     ListingEvaluator.evaluate(listing, entry) → ListingEvaluation
        │   (cache-first via Hermes memory; cache miss → LLM call)
        ▼
8.     If evaluation.is_match AND price ≤ ceiling:
        │     ▼
9.       domain/alert.py: render_listing_alert(snapshot, phase2_enabled)
        │     ▼
10.      Store.record_alert_snapshot(snapshot)        # append-only
        │     ▼
11.      TelegramSurface.send(rendered_alert)          # retry policy applies
        │
12.    Store.record_seen(listing.url, listing.photo_hash)
        │
13. (degradation reporter is invoked from any except clause along the path)
```

**Internal data flow (one Phase 2 buy, on user tap):**

```text
1. Telegram callback arrives → adapters/telegram_bot/inline_callbacks.py
   parses callback_data: "listing:buy:<alert_id>"
        │
        ▼
2. orchestration/buy_orchestrator.py: handle_buy(alert_id)
        │
        ▼
3.   Load AlertSnapshot from Store; verify Phase 2 still enabled for entry
        │   (check phase2_state for global lockout, then wishlist.yaml per-entry flag)
        ▼
4.   Reconciler.cross_source_check(alert_snapshot)
        │   re-fetches via alternate PageFetcher path; comparison via domain/reconciliation
        ▼
5.   On disagreement: degradation_reporter.report_degradation(PHASE2_RECONCILE_TRIPPED)
        │   Store.record_phase2_lockout(global=True)
        │   abort buy; return to caller
        ▼
6.   BrowserSession.execute_buy(listing_url, max_price)
        │   (Wallapop Pay or eBay Cómpralo-ya; fail-closed UI element check)
        ▼
7.   On UI element missing: degradation_reporter; abort
        │   On 5xx: zero retry; degradation_reporter; abort
        ▼
8.   Receipt obtained → Reconciler.receipt_check(alert_snapshot, receipt)
        │   On mismatch: degradation_reporter + global lockout
        ▼
9.   Store.record_tap(...) and Store.record_transaction(...)
        │
        ▼
10.  TelegramSurface.send(success_alert with receipt screenshot)
        │
11.  CircuitBreaker.record_success()    (resets consecutive-failure counter)
```

### File Organization Patterns

**Configuration files** — three concerns, three files (already locked):

- User content (`wishlist.yaml`) → mounted into the container at `/config/wishlist.yaml`
- Operational tunables (`config.yaml`) → mounted at `/config/config.yaml`
- Credentials (`.env`) → mounted at `/config/.env` with mode 0600

`docker-compose.yml`:

```yaml
services:
  salvager:
    image: ghcr.io/ifuensan/salvager:${SALVAGER_VERSION:-latest}
    volumes:
      - ./config:/config:ro
      - ./data:/data
    environment:
      SALVAGER_CONFIG_DIR: /config
      SALVAGER_DATA_DIR: /data
    restart: on-failure
    stop_grace_period: 30s
```

**Source organization** — strict layering, encoded in directory names:

- `domain/` is the deepest layer (no IO, no external deps).
- `interfaces/` defines ABCs that domain/orchestration/cli all import.
- `adapters/` is the only outward-facing layer (external SDK imports live here).
- `orchestration/` and `cli/` are composition layers; they wire adapters to interfaces.
- `config/`, `observability/`, `migrations/` are utility layers shared across the rest.

**Test organization** — three tiers + a fixture corpus:

- `tests/unit/` — fast, no IO, mirrors `src/` structure 1:1
- `tests/integration/` — adapter-by-adapter against fixtures
- `tests/e2e/` — full daemon cycle with mocked externals
- `tests/fixtures/` — recorded marketplace responses, syrupy snapshots, regression set

**Asset organization** — none. No static assets, no images, no fonts. The Telegram alerts include user-provided photos via Telegram's photo-by-URL feature; we don't host any assets.

### Development Workflow Integration

**Development server structure:**

- `uv run salvager <subcommand>` for CLI work — no install needed.
- `uv run salvager daemon` to run the agent locally (uses local `./config` and `./data` directories, NOT the docker mounts).
- `uv run pytest -q` for tests.
- Live-coding loop: edit a file under `src/`, re-run targeted tests via `uv run pytest tests/unit/<area>/`.

**Build process structure:**

- `pyproject.toml` declares package metadata + `[tool.hatch.build]` configuration so `uv build` produces a wheel.
- `Dockerfile` is multi-stage: stage 1 uses `uv sync` to install deps into a virtualenv; stage 2 (slim runtime) copies the venv + source.
- CI builds on every tag push and uploads to GHCR.

**Deployment structure:**

- One `docker-compose.yml` is the user-facing deployment artifact.
- `data/` directory on the host holds SQLite stores + cookies + OAuth tokens; user owns backup.
- `config/` directory on the host holds the three config files; user-edited.
- Image is pulled fresh on `docker-compose up` if a new tag is published; container restarts on failure.

### Phase 1 vs Phase 2 File Split

**Phase 1 files (must exist for v0.x — alerts only):**

All files listed above EXCEPT:

- `src/salvager/orchestration/buy_orchestrator.py`
- `src/salvager/orchestration/reconciler.py`
- `src/salvager/orchestration/circuit_breaker.py`
- `src/salvager/orchestration/smoke_test.py`
- `src/salvager/adapters/tinyfish_browser/`
- `src/salvager/adapters/sqlite_store/audit_writer.py` (write side; tap_events + transactions tables)
- `src/salvager/cli/phase2_cmd.py` (the `enable/disable/status/smoke-test/reconcile` subcommands)

These are present at v0.x as **stubs that raise `Phase2GuardrailTripped("Phase 2 not yet enabled in this build")`** so the `phase2 status` subcommand returns sensibly without code paths half-existing. Stubs are removed and full implementations land at the v0.x → v1.0 boundary (Phase 1 stabilization gate).

**Phase 1 tests** include adapter discipline lint, ruff/ty/mypy, the full unit + integration suite for everything that exists, and an e2e daemon smoke test using mocked Wallapop API + Telegram. Coverage threshold is best-effort.

**Phase 2 land brings:** full implementations of the stubbed files; coverage threshold ≥ 90% on the named critical-path modules (NFR-M2); the smoke-test regression set begins to grow. Phase 2 enable for ifuensan blocks on OQ3 (per-purchase cost measured) AND OQ6 (LLM language-register bias audit completed for Castilian baseline).

## Architecture Validation Results

### Coherence Validation ✅

**Decision compatibility:** Stack components (Python 3.12 + uv + typer + ruff + ty/mypy + pytest + pydantic v2 + pydantic-settings + httpx + ruamel.yaml + Hermes v0.13.x + python-telegram-bot + google-genai + SQLite) are all current as of May 2026 and have no version-incompatibility flags. Hermes Agent's MCP-server model accommodates TinyFish without SDK embedding; Hermes' built-in scheduler obviates external cron; Hermes' SQLite memory hosts the LLM evaluation cache without colliding with the application's own SQLite store (separate database files).

**Pattern consistency:** The hexagonal/ports-and-adapters style is reinforced in five places (project structure, decisions, patterns, structure boundaries, lint enforcement) without drift. Naming conventions for Python identifiers, SQLite columns, YAML keys, Telegram callback_data, and log event taxonomy are each defined once and referenced from the file/module-organization tables. Type-hint style (PEP 695 generics, `X | None`, kw-only args) is consistent across domain/interfaces/orchestration examples.

**Structure alignment:** The project structure encodes adapter discipline — `domain/` is import-pure, `interfaces/` defines ABCs, `adapters/` is the only place external SDKs land, `orchestration/` composes interfaces. CI lint mechanically enforces the boundary. The Phase 1 vs Phase 2 file split is concrete (named files), so v0.x vs v1.0 deliverables are unambiguous.

### Requirements Coverage Validation ✅

**Functional Requirements (54/54 covered):**

| FR group | Architectural support | Verified |
|---|---|---|
| FR1–FR5 Wishlist Management | `domain/wishlist.py`, `domain/scope_guard.py`, `config/wishlist_yaml.py`, `cli/validate_cmd.py` | ✓ |
| FR6–FR12 Marketplace Monitoring | `adapters/wallapop_api/`, `adapters/wallapop_tinyfish/`, `adapters/ebay_api/`, `orchestration/poll_loop.py`, `adapters/sqlite_store/seen_listings.py`, `adapters/hermes_scheduler/` | ✓ |
| FR13–FR17 Listing Evaluation | `adapters/llm_gemini/evaluator.py`, `adapters/llm_gemini/cache.py` (Hermes-memory-backed), `domain/prompts.py`, `domain/evaluation.py` | ✓ |
| FR18–FR22 Alert Notifications | `domain/alert.py` (single rendering point), `adapters/telegram_bot/delivery.py`, syrupy snapshot tests for FR22 stability | ✓ |
| FR23–FR30 Autonomous Purchase | `orchestration/buy_orchestrator.py`, `adapters/tinyfish_browser/{wallapop_pay,ebay_checkout}.py`, payment-rail enforcement via interface scoping + lint deny-list | ✓ |
| FR31–FR35 Phase 2 Failure Defense | `orchestration/reconciler.py`, `orchestration/circuit_breaker.py`, `orchestration/smoke_test.py`, `domain/circuit.py`, `domain/reconciliation.py`, `adapters/sqlite_store/phase2_state.py` | ✓ |
| FR36–FR38 Audit & Dispute Evidence | `adapters/sqlite_store/audit_writer.py` (write-only), `adapters/sqlite_store/audit_reader.py`, `domain/audit.py`, `cli/audit_cmd.py`; property test asserts append-only | ✓ |
| FR39–FR50 Operator Tools & Configuration | All `cli/*` subcommand modules, `config/*`, `domain/errors.py` exit-code mapping, `observability/logging.py` JSON Lines, FR48 stable exit codes documented | ✓ |
| FR51–FR54 Project Distribution & Artifacts | Repo-root files (Dockerfile, docker-compose.yml, .env.example, wishlist.example.yaml, config.example.yaml, README.md, CONTRIBUTING.md, ROADMAP.md, LICENSE), `.github/workflows/release.yml` for GHCR builds | ✓ |

**Non-Functional Requirements (all 30+ covered):**

| NFR cluster | Enforcement location | Verified |
|---|---|---|
| NFR-P1–P5 Performance | Poll cadences in `config.yaml`, `asyncio.TaskGroup` concurrency in `poll_loop`, CI cold-boot smoke test | ✓ |
| NFR-S1–S7 Security | `config/permissions.py` (mode 0600 startup check), Store interface design (write-only on audit), `scripts/adapter_discipline_lint.py` deny-list incl. `bizum`/`transferencia`, log secret-redaction filter, TLS-verify always | ✓ |
| NFR-R1–R6 Reliability | Adapter packages share zero state; two-path Wallapop fallback within poll cycle; `degradation_reporter` is the universal "no silent failure" spine; manual-recovery boundaries (no silent re-login, no auto Phase 2 re-enable) | ✓ |
| NFR-I1–I6 Integration | Per-adapter rate limiters (NFR-I2/I5); httpx TLS defaults; pinned Hermes v0.13.x; `ListingEvaluator` interface enables provider swap (NFR-I3); telegram retry policy with exponential backoff | ✓ |
| NFR-C1–C3 Cost | Hermes-memory-backed LLM eval cache with TTL targeting ≥ 60% hit rate; client-side rate limits cap LLM token spend | ✓ |
| NFR-M1–M6 Maintainability | `scripts/adapter_discipline_lint.py` (launch-blocker NFR-M1); pyproject.toml coverage thresholds for Phase 2 critical-path (NFR-M2); `tests/fixtures/` regression set (NFR-M3); Semver via release workflow (NFR-M4); dep budget tracked | ✓ |
| NFR-PR1–PR5 Privacy | All persistence local; no remote-logging codepath exists (verified by lint deny-list); listing-data scope confined to evaluation/audit | ✓ |
| NFR-O1–O5 Observability | `observability/events.py` enum vocabulary; `observability/logging.py` JSON Lines on stdout; `observability/health.py` + `cli/health_cmd.py` operator surface | ✓ |

**User journey coverage (5/5 from PRD):**

- Journey 1 (Phase 1 happy path) — covered by `poll_loop` pipeline + Telegram alert flow.
- Journey 2 (Phase 2 happy path) — covered by `buy_orchestrator` composing `Reconciler` + `BrowserSession` + `Store` + `TelegramSurface`.
- Journey 3 (Q9 silent-failure caught) — covered by the three independent defenses (cross-source reconciliation, receipt-vs-alert reconciliation, daily smoke test) + circuit breaker; degradation reporter wires the auto-disable + alert path.
- Journey 4 (operator hat: Wallapop re-auth + wishlist update) — covered by `cli/login_cmd.py`, `cli/validate_cmd.py`, `cli/test_search_cmd.py`, ruamel.yaml-backed `cli/phase2_cmd.py` for wishlist edits.
- Journey 5 (OSS contributor fork runner) — covered by docker-compose deployment shape, `.env.example`, `wishlist.example.yaml`, `config.example.yaml`, README/CONTRIBUTING/ROADMAP launch artifacts.

### Implementation Readiness Validation ✅

**Decision completeness:** All 5 core decision categories (Data, Auth/Security, API/Communication, Frontend [N/A], Infrastructure) have explicit choices with rationale and FR/NFR back-links. Versions are verified web-current (uv/typer/Hermes May 2026). The 14-step implementation sequence in "Decision Impact Analysis" is concrete enough to slice into epics.

**Structure completeness:** Complete file-level project tree is documented. Every FR group maps to specific modules. Phase 1 vs Phase 2 file split is named (not implied). Test organization mirrors source layout 1:1.

**Pattern completeness:** 11 pattern categories specified, with concrete examples (good + anti-pattern). Naming conventions cover Python identifiers, SQLite, YAML, Telegram callback_data, log events. Process patterns cover exception hierarchy → exit-code mapping (FR48), retry conventions, degradation reporting (NFR-R3 spine), CLI conventions, testing conventions.

### Gap Analysis Results

**Critical gaps:** None.

**Important gaps (deferred to implementation; not blocking):**

| Gap | Why deferred |
|---|---|
| Concrete schema for Wallapop unofficial API responses | Adapter implementation detail; the architecture pins the parser location (`adapters/wallapop_api/parser.py`) and the testing approach (recorded fixtures). Schemas land with the adapter. |
| Concrete schema for eBay.es Browse API responses | Same — pinned to `adapters/ebay_api/client.py`. |
| Phase 2 buy-flow "expected UI elements" checklist (per FR28) | Marketplace-specific and likely to drift; tracked alongside `adapters/tinyfish_browser/{wallapop_pay,ebay_checkout}.py` with the smoke-test regression set as the durable home. |
| Hermes scheduler natural-language cron syntax | Documented by Hermes upstream; we consume it via `adapters/hermes_scheduler/client.py`. |
| Final wishlist `pydantic` schema (constraints, validators) | Specified at the field-list level by the PRD; concrete pydantic implementation lands with the first wishlist-related epic in Phase 1. |

**Important gaps (empirical, not architectural — blocking Phase 2 only):**

| Gap | Where it's tracked |
|---|---|
| OQ3: TinyFish Browser per-purchase cost measurement | Open Questions section in PRD; blocker for Phase 2 customer-FAQ docs going public. |
| OQ6: LLM language-register bias audit | Open Questions section in PRD; blocker for Phase 2 enablement for non-Castilian users. |
| OQ4: Wishlist scale assumptions validation | First month of personal Phase 1 use validates this. |
| OQ5: Per-marketplace adapter break frequency | Empirical observation across Phase 1 + Phase 2. |

**Nice-to-have gaps (truly optional):**

- No explicit `CHANGELOG.md` template — convention can be set with the first release.
- No PR template specifying the "why not stdlib or existing dep" check (NFR-M5 dep-budget rule) — could land as a `.github/pull_request_template.md` in the initialization story.
- No specific Grafana dashboard or external alerting integration — intentionally out of scope at v1 (NFR-O5).

### Validation Issues Addressed

No critical issues found. Important gaps above are implementation-detail or empirical-validation items, not architectural deficiencies. They're tracked in:

- The PRD's Open Questions section (OQ3, OQ4, OQ5, OQ6)
- The Phase 1 vs Phase 2 file split (Phase 2 stubs that raise `Phase2GuardrailTripped`)
- The implementation sequence (steps 12–13 explicitly include Phase 2 gate validation)

### Architecture Completeness Checklist

**Requirements Analysis**

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**

- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**Implementation Patterns**

- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**Project Structure**

- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** **READY FOR IMPLEMENTATION**

All 16 checklist items are confirmed. No Critical Gaps. Important gaps are implementation-detail items (schemas to land with their adapters) or empirical-validation items (OQs blocking Phase 2 enablement, not Phase 1 implementation).

**Confidence Level:** **High**

The PRD itself is unusually detailed (54 FRs, 30+ NFRs, 8 OQs with defaults, named interfaces). The architecture refines those locks into concrete modules, file paths, and CI-enforced rules. The hexagonal layering + adapter discipline lint creates a structural seam that is hard to violate accidentally — exactly what NFR-M1 demanded.

**Key strengths:**

- **Adapter discipline is mechanically enforced**, not aspirational — `scripts/adapter_discipline_lint.py` is a launch blocker that fails CI on direct external-SDK imports outside `adapters/`.
- **Three independent Phase 2 defenses** are physically separated into distinct modules (`reconciler.py`, `circuit_breaker.py`, `smoke_test.py`) so a single bug cannot bypass all three.
- **No silent failure path:** every `except` clause routes through `degradation_reporter`, which fans out to log + Telegram + `health` state. The pattern is testable end-to-end.
- **Append-only audit log** is enforced at the interface level (no `update_*`/`delete_*` methods exist on the audit subset of `Store`) and verified by a property test.
- **(c3) scope contract is structurally encoded** — the wishlist schema's `extra="forbid"` rejects arbitrage fields automatically; the LLM prompt module is wishlist-anchored; CI lint deny-listing payment rails outside protected ones blocks accidental drift.
- **Phase 1 / Phase 2 file split is named, not implied** — v0.x vs v1.0 deliverables are unambiguous.
- **Stack-swap cost is bounded** by interfaces — replacing TinyFish with self-hosted Playwright is days, not weeks.
- **All data is local** — no remote logging, no telemetry, no cloud sync; verified by lint deny-list.
- **CI-enforced consistency rules** cover ruff/ty/mypy, coverage thresholds on Phase 2 critical path, adapter discipline, log event vocabulary, audit-table append-only, Telegram message format, YAML round-trip stability.

**Areas for future enhancement (post-v1):**

- Per-entry Phase 2 auto-disable (OQ1) if global proves too aggressive in practice — refactor cost is intentionally low (single `Store` method signature change).
- Container-detection prompt criterion variant (OQ2) — both criteria are localized to `domain/prompts.py`; A/B can run behind a config flag.
- Accuracy dashboard for hidden-component detection (PRFAQ launch-week priority post-launch).
- Empirical LLM bias audit (OQ6) — gates Phase 2 enablement for non-Castilian users.
- agentskills.io publication for Hermes-ecosystem visibility (OQ8) — distribution decision based on v1 outcomes.
- PyPI package distribution (deferred from v1; today's distribution is GHCR Docker image only).
- Optional Grafana / external observability integration (intentionally out of scope at v1).

### Implementation Handoff

**AI Agent Guidelines:**

- Follow all architectural decisions exactly as documented; do not relitigate locked stack/structure choices.
- Use implementation patterns consistently across all components — events from the `EventName` enum, exceptions as `HardwareHunterError` subclasses, Telegram messages only via `domain/alert.py` rendering helpers, audit writes only via `Store.record_*` methods.
- Respect the `domain/ → interfaces/ → orchestration/ → adapters/` layering boundary; the adapter-discipline lint will block PRs that violate it.
- Refer to this `architecture.md` for all architectural questions; if a decision isn't here, it likely belongs in a follow-up architecture revision rather than ad-hoc story-level invention.
- Phase 2 implementation must NOT begin until Phase 1 has run cleanly for 4–8 weeks of personal use AND OQ3 (per-purchase cost) is measured AND OQ6 (LLM bias baseline for Castilian) is audited.

**First Implementation Priority:**

```bash
uv init --package salvager --python 3.12
cd salvager
uv add typer pydantic pydantic-settings pyyaml ruamel.yaml httpx hermes-agent python-telegram-bot google-genai
uv add --dev pytest pytest-cov pytest-asyncio syrupy ruff ty
uv lock
```

…followed by the directory layout from this document and the CI gates skeleton (ruff, ty/mypy, pytest, `scripts/adapter_discipline_lint.py`). This is the first implementation story.
