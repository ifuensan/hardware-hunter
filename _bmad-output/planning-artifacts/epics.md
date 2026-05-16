---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
workflowStatus: complete
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
project_name: salvager
user_name: ifuensan
date: 2026-05-10
---

# salvager - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for salvager, decomposing the requirements from the PRD, UX Design Specification, and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

**Wishlist Management (FR1–FR5):**

- **FR1.** The user can declare wishlist entries in a YAML file with fields for manufacturer, model, reference, type (`hdd`/`ram`), maximum standalone price (`max_price_solo`), maximum in-device price (`max_price_in_device`), keywords list, and container keywords list.
- **FR2.** The user can specify a per-entry Phase 2 enable/disable flag and a per-entry confidence threshold (`low`/`medium`/`high`).
- **FR3.** The operator can run a wishlist validator that verifies schema conformance, uniqueness of `(manufacturer, model, ref)` keys, soft-cap of ~100 entries, and structural absence of arbitrage-related fields (`expected_resale_value`, `min_margin_percent`, `current_market_price`); the agent refuses to load any wishlist containing such fields and points the operator to the (c3) scope contract and the future-research repo path.
- **FR4.** The agent uses `(manufacturer, model, ref)` as the entry key for alerts, audit log, dedup, and Phase 2 controls.
- **FR5.** Setting `max_price_in_device` to nil disables container detection for that entry; the entry continues to alert on direct matches against `max_price_solo`.

**Marketplace Monitoring (FR6–FR12):**

- **FR6.** The agent monitors Wallapop continuously via two independent paths — a primary unofficial-API path and a fallback search/fetch path — such that either path alone can carry Phase 1 alerts.
- **FR7.** The agent monitors eBay.es continuously via the official eBay API, structurally independent from any Wallapop adapter.
- **FR8.** The agent polls each marketplace at human-volume rates configurable per marketplace (e.g. Wallapop every 15 minutes, eBay every 30 minutes), driven by Hermes Agent's built-in scheduler.
- **FR9.** The agent generates marketplace-specific search queries from each wishlist entry's `keywords` and `container_keywords`.
- **FR10.** The agent persists a seen-listings dedup index (URL + perceptual photo hash + first-seen and last-seen timestamps + match-fired flag) so a single listing fires at most one alert per wishlist entry.
- **FR11.** The agent never surfaces listings that do not match any wishlist entry; there is no "good deals" surfacing path.
- **FR12.** The agent stops polling Wallapop and emits an operational Telegram alert when the Wallapop session expires; it never attempts silent automated re-login.

**Listing Evaluation (FR13–FR17):**

- **FR13.** For each candidate listing, the agent invokes a wishlist-anchored LLM evaluation that answers one question — *"does this listing match this wishlist entry?"* — and returns a confidence level (`low`/`medium`/`high`).
- **FR14.** The agent evaluates standalone listings against the entry's `max_price_solo` ceiling and container/wrapper listings against `max_price_in_device`, using `container_keywords` to identify wrapper candidates (NAS, mini-PC, workstation, etc.).
- **FR15.** The agent surfaces the LLM's one-line take on listing authenticity (e.g. *"photos show a real WD Red, serial visible"*) in every alert.
- **FR16.** The agent caches LLM evaluation results per listing URL with a configurable TTL (default 24h, shorter for low-confidence results) to avoid redundant queries on re-fetch.
- **FR17.** The agent never scores listings for resale value, margin, expected market value, or any arbitrage-related metric.

**Alert Notifications (FR18–FR22):**

- **FR18.** The user receives a Telegram alert per matched listing containing photo, price, seller location, one-line LLM take, confidence level, matched wishlist entry, and a deep link to the listing.
- **FR19.** Phase 1 alerts include inline action buttons: *View*, *Skip*, *Snooze*.
- **FR20.** The user can tap *Snooze* on any alert to suppress further alerts for the same wishlist entry for a configurable window (default 24h).
- **FR21.** The agent emits operational Telegram alerts — distinct from listing alerts — for: marketplace authentication expiry, Phase 2 auto-disable events, smoke-test drift, circuit-breaker openings, and reconciliation tripping. Operational alerts are prefixed (`⚠️` for high-priority, `ℹ️` for informational) and contain no inline action buttons.
- **FR22.** The Telegram alert format for Phase 1 and Phase 2 listing alerts is fixed for v1; changes require a coordinated audit-log schema migration.

**Autonomous Purchase / Phase 2 (FR23–FR30):**

- **FR23.** The user can enable Phase 2 per wishlist entry (default disabled). Phase 2 is never enabled by default; there is no setting that flips it on globally.
- **FR24.** Phase 2-enabled entry alerts include *Buy*, *Skip*, *View* buttons; tapping *Buy* initiates the autonomous purchase flow.
- **FR25.** The agent completes Phase 2 purchases exclusively via platform-protected payment rails (Wallapop Pay, eBay.es checkout); the agent has no codepath that uses Bizum, transferencia, or any unprotected rail.
- **FR26.** The agent enforces per-entry maximum prices as a hard ceiling; any listing exceeding the ceiling fails closed without offering a *Buy* button.
- **FR27.** The agent enforces per-entry confidence thresholds; listings below the threshold present a manual-review-only path even when Phase 2 is enabled.
- **FR28.** The agent verifies all expected UI elements are present in the marketplace buy flow before proceeding (fail-closed UI check); any missing element aborts the purchase and emits an operational Telegram alert.
- **FR29.** The agent has no fully-autonomous mode. There is no setting, flag, environment variable, or CLI command that bypasses the per-purchase Telegram tap.
- **FR30.** Phase 2 buy flows execute via a stealth browser session (real browser, not API token forgery), using the marketplace's own login state.

**Phase 2 Failure Defense (FR31–FR35):**

- **FR31.** Before completing a Phase 2 purchase, the agent re-fetches the listing via the alternate marketplace path (cross-source price reconciliation) and aborts the purchase if prices disagree beyond a configurable tolerance (€ floor + percentage, whichever is greater).
- **FR32.** After every Phase 2 purchase, the agent compares the alert price to the marketplace receipt price (receipt-vs-alert reconciliation); a mismatch raises a high-priority Telegram alert and auto-disables Phase 2.
- **FR33.** The agent runs a daily synthetic Phase 2 smoke test against a known-price fixture; drift between parsed and independent values auto-disables Phase 2 globally.
- **FR34.** The agent maintains a per-purchase circuit breaker that auto-disables Phase 2 globally after N consecutive Phase 2 failures (default 3, configurable).
- **FR35.** After any Phase 2 auto-disable, the operator must explicitly re-enable Phase 2 via the CLI; the agent never re-enables itself, regardless of subsequent successful smoke tests.

**Audit & Dispute Evidence (FR36–FR38):**

- **FR36.** The agent persists an append-only SQLite audit log per Phase 2 purchase with three artifacts: alert snapshot, tap event, transaction record (price paid, payment method, marketplace receipt ID, screenshot path, timestamp).
- **FR37.** The operator can view audit log entries (`audit show`, optionally scoped by entry or time window) and export them to JSONL (`audit export`).
- **FR38.** All audit log data is stored locally; the agent never transmits audit data to remote servers and emits no telemetry.

**Operator Tools (FR39–FR48):**

- **FR39.** The operator interacts with salvager through a single `salvager` binary with subcommands. Daemon mode is the implicit default when no subcommand is given.
- **FR40.** The operator can scaffold initial config files (`wishlist.yaml`, `config.yaml`, `.env`) from tracked examples via `init`; the command refuses to overwrite existing files unless `--force` is given alongside an interactive confirmation prompt.
- **FR41.** The operator can authenticate Wallapop interactively via `login wallapop`, which opens a real browser session, walks the operator through credentials and 2FA, and persists the resulting cookie with restrictive filesystem permissions.
- **FR42.** The operator can authenticate eBay.es via `login ebay`, completing OAuth and persisting tokens locally with restrictive permissions.
- **FR43.** The operator can perform a dry-run search (`test-search`) against a wishlist entry or arbitrary query without sending alerts, mutating state, or counting beyond actual rate-limit usage.
- **FR44.** The operator can perform a one-shot LLM evaluation of any listing URL (`explain`) to inspect how the agent would treat it, including confidence and the alert message body.
- **FR45.** The operator can view, enable, and disable per-entry Phase 2 settings via `phase2 status`, `phase2 enable <entry>`, and `phase2 disable <entry|--all>`.
- **FR46.** The operator can manually trigger the synthetic smoke test (`phase2 smoke-test`) and re-run a receipt-vs-alert reconciliation on a past receipt (`phase2 reconcile <receipt-id>`).
- **FR47.** The operator can inspect agent health (`health`) — adapter status, scheduler status, last poll, last alert, last Phase 2 event — to diagnose problems without reading raw logs.
- **FR48.** All read-only operator commands support a `--format json` flag for scripting; daemon logs emit structured JSON Lines on stdout. Operator commands return stable, documented exit codes (0 success / 1 usage / 2 validation / 3 adapter / 4 auth / 5 Phase 2 guardrail).

**Configuration & Lifecycle (FR49–FR50):**

- **FR49.** Configuration is split across `wishlist.yaml` (user content), `config.yaml` (operational tunables: rates, thresholds, paths, log level), and `.env` (credentials only, never logged); the agent loads `.env` once at process start with no hot-reload.
- **FR50.** The agent handles SIGTERM gracefully — drains in-flight LLM evaluations, flushes the audit log, completes pending Telegram alerts, exits within 30 seconds.

**Project Distribution & Artifacts (FR51–FR54):**

- **FR51.** The repository ships a single `docker-compose.yml` install path with example wishlist entries, an `.env.example`, and a `config.example.yaml`; user-specific files (`wishlist.yaml`, `config.yaml`, `.env`) are gitignored.
- **FR52.** The repository includes a `CONTRIBUTING.md` with an explicit "no arbitrage PRs" rule and three named invitation categories (wishlist examples, prompt improvements, Wallapop selector patches), pointing to a separate-repo path for arbitrage forks.
- **FR53.** The repository includes a `ROADMAP.md` naming future-multi-marketplace expansion, future-arbitrage-as-separate-repo, and "C&D-induced sunset" as a documented possible end state.
- **FR54.** The README positions salvager as a personal monitoring tool (not a "Wallapop scraper"), includes a legal disclaimer covering Spanish ToS posture and the secondary-account recommendation, and contains no Wallapop trademarks, logos, or proprietary terms in titles, package names, or domain references.

### NonFunctional Requirements

**Performance (NFR-P1–P5):**

- **NFR-P1.** Alert delivery latency: ≤ 20 minutes p95 from listing publication to Telegram alert (bounded by polling cadence + LLM evaluation + Telegram delivery).
- **NFR-P2.** End-to-end Phase 2 buy completion (Telegram tap → marketplace receipt screenshot): ≤ 60 seconds p95 under normal marketplace load. Cross-source reconciliation pre-check accounts for ≤ 10 seconds.
- **NFR-P3.** Per-listing LLM evaluation: ≤ 5 seconds p95 with Gemini Flash. Concurrent processing (Hermes subagents, up to 8 workers).
- **NFR-P4.** Read-only operator commands (`audit show`, `health`, `phase2 status`, `validate-wishlist`, `validate-config`) complete in ≤ 2 seconds for typical wishlist sizes (≤ 100 entries).
- **NFR-P5.** Daemon cold boot from `docker-compose up` to first scheduled poll registered with Hermes scheduler: ≤ 30 seconds.

**Security (NFR-S1–S7):**

- **NFR-S1.** All marketplace credentials, Telegram bot tokens, TinyFish API keys, and LLM API keys loaded exclusively from `.env` at process start; never logged, never persisted outside cookie/token files, never transmitted to remote services beyond their target API.
- **NFR-S2.** Wallapop session cookie file and eBay OAuth token file created with mode `0600`. The agent verifies permissions at startup and refuses to load if mode is permissive.
- **NFR-S3.** All external API calls (Wallapop, eBay, Telegram, TinyFish, LLM provider) use TLS 1.2 or higher. Reject connections that fall back to weaker protocols or accept invalid certificates.
- **NFR-S4.** Phase 2 audit log is append-only at the application layer (no `UPDATE` or `DELETE` issued against `alert_snapshots`, `tap_events`, or `transactions`). Existing rows never mutated.
- **NFR-S5.** No codepath initiates a transfer outside Wallapop Pay or eBay.es checkout. CI lint flags introductions of relevant API calls outside the protected-rail wrapper.
- **NFR-S6.** Operator commands that affect Phase 2 globally (`phase2 disable --all`) or destroy state (`init --force`) require an interactive confirmation prompt; in non-TTY contexts these commands fail.
- **NFR-S7.** No telemetry, no usage analytics, no crash reports to any external service. Logs go to stdout; audit log stays local; SQLite stores stay local.

**Reliability (NFR-R1–R6):**

- **NFR-R1.** A complete Wallapop outage (both adapter paths down) does not affect eBay.es polling, alerts, or Phase 2. The two marketplace adapters share no runtime state at the polling/evaluation/alerting layer.
- **NFR-R2.** When the unofficial-API path fails, the agent automatically falls back to the TinyFish search/fetch path within the same poll cycle. The agent logs the path used per request.
- **NFR-R3.** No silent failure. When a capability is degraded, the agent emits an operational Telegram alert.
- **NFR-R4.** The agent **never** automatically: silently re-logs into Wallapop (FR12); re-enables Phase 2 after auto-disable (FR35); overwrites an existing config file (FR40).
- **NFR-R5.** On unhandled exception, the agent exits non-zero with structured log line; docker-compose `restart: on-failure` (with backoff) is the supported recovery model. Audit log and seen-listings dedup remain consistent across crash/restart.
- **NFR-R6.** After a marketplace UI/API change, operator restores service within ≤ 30 hours of patch effort, ≤ 3 attempts. Beyond either, technical-debt walk-away trigger fires.

**Integration (NFR-I1–I6):**

- **NFR-I1.** Hermes Agent pinned to v0.13.x at v1; floor/ceiling specified in dependency manifest.
- **NFR-I2.** TinyFish configured as Hermes MCP server endpoint; agent does not embed TinyFish SDKs directly. Free-tier rate limits respected (5 req/min Search, 25 URLs/min Fetch); enforced client-side.
- **NFR-I3.** A `ListingEvaluator` interface wraps the LLM call; provider switch (Gemini Flash → GPT-4o → Claude Haiku) requires only adapter swap and config change. CI lint enforces no direct LLM-SDK imports outside the adapter package.
- **NFR-I4.** Wallapop unofficial-API adapter validates response schema at parse time; schema drift surfaces as adapter failure (exit code 3 / operational alert), not silent acceptance.
- **NFR-I5.** Standard eBay API key + OAuth flow; renewals and rate-limit headers respected. Daily request budget tracked; breach raises operational alert and degrades to reduced poll cadence.
- **NFR-I6.** Failed Telegram sends retried with exponential backoff up to configurable ceiling (default 3 attempts over ~1 minute). Persistent failure surfaces as structured-log error; agent does not block polling on Telegram outages.

**Cost (NFR-C1–C3):**

- **NFR-C1.** Phase 1 monthly cost: ≤ €0/month on existing homelab hardware; ≤ €10/month worst case.
- **NFR-C2.** Phase 2 incremental cost: ≤ €1.00 per Phase 2 purchase even under worst-case TinyFish pricing changes.
- **NFR-C3.** LLM cache hit rate: ≥ 60% on listings re-fetched within TTL during steady state.

**Maintainability (NFR-M1–M6):**

- **NFR-M1.** **(Launch blocker)** No business-logic package directly imports Hermes, TinyFish, Wallapop SDK, eBay SDK, LLM SDK, or marketplace-specific HTML/CSS selectors. CI lint (custom import-graph rule) blocks merge.
- **NFR-M2.** Phase 2 buy-flow logic (cross-source reconciliation, fail-closed UI checks, circuit breaker, audit-log writes, receipt-vs-alert reconciliation) has integration tests against recorded marketplace fixtures. Coverage ≥ 90% line coverage at v1.0.
- **NFR-M3.** Synthetic Phase 2 smoke test (FR33) maintains a regression set that grows with every marketplace UI surprise; fixtures tracked in repo.
- **NFR-M4.** Public CLI surface (subcommand names, flag names, exit codes, JSON output schema), config schema, and audit-log SQLite schema governed by semver.
- **NFR-M5.** Total Python third-party dependency count under 30 direct dependencies at v1.
- **NFR-M6.** Steady-state maintenance budget ≤ 8 h/month after the first 6 months; rolling 3-month average > 20 h/month invokes the sustained-burden walk-away trigger.

**Privacy (NFR-PR1–PR5):**

- **NFR-PR1.** Agent stores only: wishlist YAML, config files, credentials, seen-listings dedup index, Phase 2 audit log. No other personal data.
- **NFR-PR2.** Indefinite local retention by default. The user, as data controller, owns deletion. No automated purge.
- **NFR-PR3.** No remote persistence. Architecture forbids it; schema has no field for it.
- **NFR-PR4.** Operator can delete agent state by removing `data_dir/*` and credential files.
- **NFR-PR5.** Agent processes seller-published listing data only for evaluation and audit-snapshot capture. No profiling of sellers, no cross-listing analytics.

**Observability (NFR-O1–O5):**

- **NFR-O1.** Daemon emits structured JSON Lines on stdout with standard fields `level`, `ts`, `event`, `entry`, `marketplace`, `listing_id`, `latency_ms`, `error_class`. No syslog/remote-logging integration at v1.
- **NFR-O2.** `health` command returns adapter status, Hermes scheduler status, last-poll timestamp per marketplace, last-alert timestamp, last Phase 2 event, current Phase 2 enable/disable scope.
- **NFR-O3.** `audit show` paginates the Phase 2 audit log with human-readable formatting; `audit export` produces JSONL suitable for `jq` or external analysis.
- **NFR-O4.** For any operational alert, the agent emits a structured log entry containing data necessary to root-cause the event without re-running the failing path. Operator must not need to enable debug logging to diagnose a production incident.
- **NFR-O5.** docker-compose / systemd / docker log driver owns log rotation; the agent makes no assumptions about how long logs are kept.

### Additional Requirements

**Architecture-driven implementation requirements (AR1–AR25):**

- **AR1.** **Starter template** = minimal `uv` Python scaffold via `uv init --package salvager --python 3.12`. CPython ≥ 3.12. uv-managed `pyproject.toml` + committed `uv.lock`. **This is the first implementation story** — the directory layout encodes adapter discipline (NFR-M1) and cannot be added retroactively without rework.
- **AR2.** CLI framework: `typer` ≥ 0.12.1 (type-hint-driven, built on Click; matches the 18-subcommand structure for FR39–FR48).
- **AR3.** Code quality toolchain: `ruff` (lint+format, replaces black+isort+flake8); `ty` (Astral type checker, beta as of May 2026) with `mypy` as immediate fallback if ty hits a stub it can't process — CI runs both for the first release. `pytest` + `pytest-cov` + `pytest-asyncio` + `syrupy` for tests.
- **AR4.** Schema/config: `pydantic` v2 + `pydantic-settings` (.env loading with type validation). `PyYAML` for read; `ruamel.yaml` for round-trip preservation when CLI rewrites `wishlist.yaml`.
- **AR5.** Runtime libraries: `httpx` (async-friendly HTTP); `python-telegram-bot` (Telegram); `google-genai` (default LLM provider, Gemini Flash, swappable behind `ListingEvaluator`).
- **AR6.** **Hexagonal/ports-and-adapters internal architecture**: `domain/` (pure, stdlib + pydantic only) → `interfaces/` (ABCs) → `orchestration/` (composes interfaces) → `adapters/` (the only package allowed to import external SDKs).
- **AR7.** **Custom AST-based adapter discipline lint** at `scripts/adapter_discipline_lint.py` (~50 LOC, zero external dep). Walks every `.py` file outside `src/salvager/adapters/**`; fails build on any import of a configured deny-list (`hermes_agent`, `tinyfish_*`, `google.genai`, `openai`, `anthropic`, `telegram`, marketplace SDK names). CI gate.
- **AR8.** Persistence: single SQLite database file (`salvager.db`) with WAL mode (`PRAGMA journal_mode=WAL` at first connect) for concurrent CLI reads while daemon writes. Tables: `wishlist_runtime_state`, `seen_listings`, `alert_snapshots`, `tap_events`, `transactions`, `phase2_smoke_tests`, `phase2_state`, `_meta`.
- **AR9.** **Append-only enforcement at application layer**: `Store` interface exposes only `record_*` writers for `alert_snapshots`/`tap_events`/`transactions`; no `update_*`/`delete_*` methods exist on these tables. Property test asserts the absence of mutation methods.
- **AR10.** Hand-rolled migrations: numbered `.sql` files in `src/salvager/migrations/`; `_meta.schema_version` row; applied at daemon startup; CLI `validate-config` flags drift.
- **AR11.** LLM evaluation cache hosted by Hermes Agent's built-in SQLite + FTS5 memory (separate database from `salvager.db`), keyed by listing URL. TTL 24h default; 1h for low-confidence.
- **AR12.** **`wishlist.yaml` is canonical Phase 2 source-of-truth.** `phase2 enable <entry>` and `phase2 disable <entry>` rewrite the YAML using `ruamel.yaml` (preserves comments and formatting). Daemon parses `wishlist.yaml` at the start of every poll cycle. SQLite carries no override table for Phase 2 enable/disable.
- **AR13.** Phase 2 auto-disable persistence: a global "Phase 2 lockout" row in `phase2_state` SQLite table takes runtime precedence over YAML's per-entry `enabled: true` until explicitly cleared by `phase2 enable <entry>`.
- **AR14.** Daemon ↔ CLI communication via shared filesystem + SQLite, no IPC, no HTTP control plane. Read-only CLI works whether daemon is running or not. Daemon picks up `wishlist.yaml` / `config.yaml` changes on next poll cycle (or 30-second config-rescan tick).
- **AR15.** Concurrency: async daemon (`asyncio` + `httpx`) using Hermes' subagent primitive (up to 8 concurrent workers) for parallel per-listing LLM evaluation. Sync CLI subcommands.
- **AR16.** Internal data flow: synchronous pipeline within async runtime — `poll_loop` → `PageFetcher.search` → `PageFetcher.fetch` → `Store.is_seen?` → `ListingEvaluator.evaluate` → `Store.record_seen` → `TelegramSurface.send_alert`. No event bus, no message broker.
- **AR17.** Packaging: single `Dockerfile` (`python:3.12-slim` base) building a single-service `docker-compose.yml` mounting `./data` (SQLite, audit log, cookies) and `./config` (wishlist.yaml, config.yaml, .env). `restart: on-failure` with default backoff; `stop_grace_period: 30s` to match FR50 SIGTERM drain.
- **AR18.** Image distribution: GitHub Container Registry (`ghcr.io/ifuensan/salvager`), semver-tagged (`v0.1.0`, …, `v1.0.0`). PyPI publication deferred post-launch.
- **AR19.** GitHub Actions CI on every PR + tag. Gates: `ruff check`, `ty` (with `mypy` fallback), `pytest --cov` with thresholds (≥ 90% on Phase 2 critical path), `python scripts/adapter_discipline_lint.py`, daemon smoke test. On tag push: build + push GHCR image.
- **AR20.** Telegram operational alerts share the same chat as listing alerts, distinguished by severity prefix; no separate "ops chat" at v1. The bot silently drops any inbound message from any chat ID other than `TELEGRAM_CHAT_ID`.
- **AR21.** Wallapop session cookie file in Netscape `cookies.txt` format; mode 0600. eBay OAuth refresh + access tokens in `oauth_tokens.json` (mode 0600) at `data_dir/auth/`; auto-refresh before expiry within the daemon.
- **AR22.** Permission verification at daemon startup for cookie file, OAuth token file, and `.env`; refuse to start if any is permissive (NFR-S2 enforcement).
- **AR23.** All external HTTP via httpx with default TLS 1.2+; `verify=True` always; no `verify=False` codepath exists (NFR-S3 enforcement).
- **AR24.** **Phase 1 vs Phase 2 file split**: 7 named files exist as `Phase2GuardrailTripped` stubs at v0.x: `orchestration/buy_orchestrator.py`, `orchestration/reconciler.py`, `orchestration/circuit_breaker.py`, `orchestration/smoke_test.py`, `adapters/tinyfish_browser/`, `adapters/sqlite_store/audit_writer.py` (write side; tap_events + transactions tables), `cli/phase2_cmd.py` (the `enable/disable/status/smoke-test/reconcile` subcommands). Stubs removed and full implementations land at v0.x → v1.0 boundary.
- **AR25.** Project initialization is the first implementation story (Epic 1 Story 1) per architecture handoff.

### UX Design Requirements

**Telegram message rendering surface (UX-DR1–UX-DR8):**

- **UX-DR1.** Implement six rendering functions in `src/salvager/domain/alert.py`: `render_phase1_listing_alert`, `render_phase2_listing_alert`, `render_phase2_buy_success`, `render_phase2_buy_failure`, `render_operational_alert`, `render_callback_acknowledgment`. Each consumes a domain object and returns a `RenderedAlert`. No other code path emits Telegram text.
- **UX-DR2.** Implement two CLI rendering helpers in `src/salvager/observability/styling.py`: `render_table(rows, columns) -> Table` (uses `box=MINIMAL`, no row separators, default 80-col width) and `render_prose(message, style, hint=None)` (single-record output via theme tokens). No CLI command writes to stdout directly.
- **UX-DR3.** Define `SEVERITY_TOKENS` constants module exposing the locked six-emoji palette: `operational_warn` = `⚠️ `, `operational_info` = `ℹ️ `, `phase1_listing` = `📦`, `phase2_listing` = `🟢`, `phase2_buy_success` = `✅`, `phase2_buy_failure` = `🚫`. Any other emoji forbidden in code review.
- **UX-DR4.** Define `BUTTON_LABELS` constants module exposing the locked five-button vocabulary: `view` = `👁 Ver`, `skip_phase1` = `🙅 Saltar`, `snooze` = `😴 Posponer 24h`, `buy` = `✅ Comprar`, `skip_phase2` = `❌ Saltar`. Spanish at v1; locale flag is post-launch.
- **UX-DR5.** `callback_data` format strictly `<surface>:<verb>:<id>` (three colon-segments, ≤ 64 bytes per Telegram limit). Constant in module-level config; CI lint ensures no deviation.
- **UX-DR6.** **Direction A + E hybrid Phase 1 alert anatomy**: Phase 1 alerts use 5-row baseline (severity+part+price / location+marketplace / italics LLM take / confidence row / button row). When `AlertSnapshot.is_container == True`, insert two indented rows (`↪︎ Wrapper:` and `↪︎ Extracted:`) between Row 1 and the LLM take row.
- **UX-DR7.** Phase 2 listing alert reuses Phase 1 layout with three substitutions: severity prefix `📦` → `🟢`; confidence row appended with ` · Phase 2 max: <€>`; inline keyboard `[✅ Comprar] [❌ Saltar] [👁 Ver]`. Pre-flight gating (smoke test, circuit breaker, kill-switch, entry-enabled) happens before the renderer is called; if any check fails, the orchestrator calls `render_phase1_listing_alert` instead.
- **UX-DR8.** All user-supplied content (listing title, description, seller name) escaped via a single `escape_markdown_v2()` helper before insertion into Telegram MarkdownV2 messages; pass-through is treated as a security bug.

**Phase 2 receipt + failure UX (UX-DR9–UX-DR12):**

- **UX-DR9.** Phase 2 receipt confirmation message (`render_phase2_buy_success`) requires a captured screenshot as the photo attachment. If the screenshot is missing, the orchestrator must NOT call this renderer; instead emit `render_phase2_buy_failure(reason=screenshot_missing, ctx=...)` even though the transaction succeeded.
- **UX-DR10.** Phase 2 failure message (`render_phase2_buy_failure`) must include the canonical reassurance line `La compra NO se ha ejecutado.` on every variant. Property test verifies the line is present in all `BuyFailureReason` outputs.
- **UX-DR11.** Phase 2 buy in-flight state: edit the original alert keyboard via Telegram `editMessageReplyMarkup` to a non-tappable single-button row `[🟡 Comprando…]` upon `Comprar` tap. Replaced again by success or failure message; original alert's keyboard is never re-rendered.
- **UX-DR12.** Acknowledgment row pattern after Phase 1 button taps: replace keyboard with single non-tappable row `[✓ visto]` / `[✓ saltado]` / `[✓ pospuesto 24h]` (Spanish past-participles).

**Operational alerts (UX-DR13–UX-DR15):**

- **UX-DR13.** Operational alerts (`render_operational_alert`) take a `Severity` enum (`warn`, `info`) and `EventName` enum (`phase2_disabled`, `wallapop_session_expired`, `daemon_started`, `daemon_stopped`, `circuit_open`, `smoke_test_failed`, `smoke_test_recovered`, `phase2_re_enabled`, `tinyfish_fallback_active`, `tinyfish_fallback_recovered`, `ebay_token_refresh_failed`). One variant per `EventName`; finite, grows only via PRD amendment.
- **UX-DR14.** `⚠️` variants must include a numbered next-step list with copy-paste-ready CLI commands; `ℹ️` variants must include a single CLI hint or no hint. Operational alerts carry no inline keyboard.
- **UX-DR15.** Calm-instructional tone for `⚠️` (cause + next-CLI-command in one read; specific numbers required, e.g., `API 53.00 vs HTML 0.53`); direct + minimal tone for `ℹ️`. Tone register must match severity; cushioning language ("Oops!") fails review.

**CLI styling and rendering (UX-DR16–UX-DR21):**

- **UX-DR16.** Define theme-token color map in `observability/styling.py`: `error` = `bold red`, `warn` = `bold yellow`, `success` = `bold green`, `info` = `bold blue`, `emphasis` = `bold` (no color), `secondary` = `dim` (no color), `code` = `cyan`. Color emits only when stdout is a TTY (rich auto-detection); `--no-color`, `NO_COLOR=1`, and piping disable color but preserve `bold`/`dim` semantics.
- **UX-DR17.** `rich.progress.Progress` and `rich.status.Status` are forbidden at v1. CI lint (or grep-based check) flags introductions. Long-running operations emit structured log lines / discrete prose-line events instead.
- **UX-DR18.** CLI error format (locked): `error: <one-line description, ≤ 80 chars>` (bold red) followed by `hint: <suggested next command, ≤ 120 chars>` (dim). Stack traces only with `--debug`; otherwise to structured log.
- **UX-DR19.** CLI density: adaptive — single-record commands emit prose lines (`render_prose`); multi-record commands emit `rich.table.Table` with `box=MINIMAL`, no row separators.
- **UX-DR20.** JSON output schema conventions (FR48): snake_case fields; ISO 8601 with millisecond precision and `Z` suffix; numbers as numbers (prices as decimals to two places); no envelope (flat array on stdout); errors to stderr as one-line JSON.
- **UX-DR21.** Help text format: typer + rich integration; every CLI subcommand has a usage line + ≤ 5-line description + args table + ≥ 1 example invocation. The help IS the doc.

**Form / config validation UX (UX-DR22–UX-DR23):**

- **UX-DR22.** `validate-wishlist` forbidden-field error explicitly names the (c3) scope contract and points to ROADMAP.md for the future-research repo path. Format: `error: <file>:<line>:<col>: <description>` + `hint: <fix or scope reference>`.
- **UX-DR23.** Destructive operations (`init --force`, `phase2 disable --all`) require typing-a-token interactive confirmation (e.g., `Type 'OVERWRITE' to confirm:` or `Type the number of currently enabled entries to confirm:`); never y/n prompts. In non-TTY contexts, fail.

**Empty states + health UX (UX-DR24–UX-DR25):**

- **UX-DR24.** No Telegram empty-state messages. No "still watching" pings, no daily summaries, no engagement nudges. Silence-as-success is part of the contract.
- **UX-DR25.** `health` output structure must distinguish "watching, no matches in 24h" from "stuck poller" via explicit fields: `Recent matches: 0 in last 24h (watching)` AND `Last poll: <timestamp>` AND adapter-status table. Operators must never have to ask "is the bot working?".

**Cross-surface alignment + locking (UX-DR26–UX-DR28):**

- **UX-DR26.** Every Telegram alert that names a CLI command must include an audit pointer (`salvager audit show --id <n>`) so the CLI returns output matching the alert verbatim. The audit-log row is the shared source of truth.
- **UX-DR27.** Bilingual asymmetry: Telegram surface in Spanish (Castilian); CLI / README / CONTRIBUTING / ROADMAP / code comments / log messages in English. No mixing. A `config.yaml > telegram.locale` flag for English Telegram is post-launch (OQ-tracked, NOT v1).
- **UX-DR28.** Phase 1 alert capped at 6 logical rows + button row; Phase 2 alert same cap. Top-3-rows must contain decision-critical fields (severity + part + price + location) for iOS lock-screen preview optimization.

**Testing & verification UX (UX-DR29–UX-DR33):**

- **UX-DR29.** Snapshot tests (via `syrupy`) on every Telegram renderer output assert against locked golden text. Format drift breaks the build (FR22 enforcement).
- **UX-DR30.** Property tests verify: every `BuyFailureReason` produces an output containing the reassurance line; every `EventName` matches its severity-vs-headline-style rule; every CLI subcommand exits with one of the locked exit codes (FR48); every `--format json` output is `json.loads`-parseable.
- **UX-DR31.** CLI terminal width testing at 60, 80, 100, 120, 200 cols against goldens; non-TTY (piped) output is plain text without color or boxes.
- **UX-DR32.** Telegram client variance manual-test matrix at v1 release: iOS Telegram + Android Telegram + Telegram desktop + Telegram Web; capture screenshots and visual-diff for emoji rendering consistency, MarkdownV2 fidelity, button row layout.
- **UX-DR33.** Color-blind safety + accessibility audit at v1 release: every CLI command run with `NO_COLOR=1`; Telegram screenshots reviewed via Coblis or Color Oracle (deuteranopia, protanopia, tritanopia); macOS VoiceOver tested on representative CLI commands.

### FR Coverage Map

| FR | Epic(s) | Notes |
|---|---|---|
| FR1 | Epic 2 | Wishlist YAML schema (manufacturer, model, ref, type, prices, keywords, container_keywords) |
| FR2 | Epic 2 | Per-entry Phase 2 flag + confidence threshold (schema only at this stage; Phase 2 consumption lands in Epic 5) |
| FR3 | Epic 2 | Wishlist validator with arbitrage-field scope-guard pointing to (c3) and ROADMAP |
| FR4 | Epic 2 | `(manufacturer, model, ref)` entry-key contract established and consumed by domain models |
| FR5 | Epic 2 | `max_price_in_device == nil` disables container detection for that entry |
| FR6 | Epic 3 | Wallapop two-path monitoring (unofficial API + TinyFish fallback) |
| FR7 | Epic 3 | eBay.es official API monitoring; structurally independent of Wallapop |
| FR8 | Epic 3 | Hermes scheduler integration for per-marketplace poll cadence |
| FR9 | Epic 3 | Search query builder per wishlist entry |
| FR10 | Epic 3 | Seen-listings dedup index (URL + perceptual hash + timestamps + match-fired flag) |
| FR11 | Epic 3 | Wishlist-anchored only; no good-deals surfacing path |
| FR12 | Epic 3 + Epic 4 | Detection in Epic 3 (stop polling Wallapop on 401); operational alert + recovery flow in Epic 4 |
| FR13 | Epic 3 | LLM evaluator with `(low|medium|high)` confidence |
| FR14 | Epic 3 | Standalone vs container evaluation against per-entry ceilings |
| FR15 | Epic 3 | LLM one-line take surfaced in every alert |
| FR16 | Epic 3 | LLM evaluation cache keyed by listing URL with TTL |
| FR17 | Epic 3 | No arbitrage scoring (LLM prompt + adapter contract) |
| FR18 | Epic 3 | Phase 1 alert with photo + price + location + take + confidence + entry + deeplink |
| FR19 | Epic 3 | Phase 1 inline buttons View/Skip/Snooze |
| FR20 | Epic 3 | Snooze 24h per entry (configurable) |
| FR21 | Epic 4 | Operational Telegram alerts with `⚠️`/`ℹ️` severity prefix; no inline buttons |
| FR22 | Epic 3 | Phase 1/2 alert format locked for v1; snapshot tests enforce stability (inherited by Epic 5) |
| FR23 | Epic 5 | Per-entry Phase 2 enable (default off; no global flip) |
| FR24 | Epic 5 | Phase 2 alert buttons + Buy initiates autonomous purchase flow |
| FR25 | Epic 5 | Protected payment rails only (Wallapop Pay, eBay.es checkout); CI lint deny-list |
| FR26 | Epic 5 | Per-entry max price as hard ceiling; fail-closed |
| FR27 | Epic 5 | Per-entry confidence threshold gates Phase 2 path |
| FR28 | Epic 5 | UI element fail-closed check before purchase |
| FR29 | Epic 5 | No fully-autonomous mode (structural guard) |
| FR30 | Epic 5 | Stealth browser session via TinyFish browser adapter |
| FR31 | Epic 5 | Cross-source price reconciliation |
| FR32 | Epic 5 | Receipt-vs-alert reconciliation; mismatch auto-disables Phase 2 |
| FR33 | Epic 5 | Daily synthetic Phase 2 smoke test |
| FR34 | Epic 5 | Per-purchase circuit breaker (default 3 consecutive failures) |
| FR35 | Epic 5 | Manual re-enable after auto-disable (operator action required) |
| FR36 | Epic 5 | Append-only Phase 2 audit log with three artifacts |
| FR37 | Epic 4 + Epic 5 | CLI commands `audit show`/`audit export` in Epic 4; Phase 2 writers populating the audit tables in Epic 5 |
| FR38 | Epic 5 | No telemetry on audit data |
| FR39 | Epic 1 | Single `salvager` binary with subcommand framework; daemon-default when no subcommand |
| FR40 | Epic 2 | `salvager init` scaffolds config files; refuses overwrite without `--force` |
| FR41 | Epic 2 | `login wallapop` interactive browser flow |
| FR42 | Epic 2 | `login ebay` OAuth flow |
| FR43 | Epic 4 | `test-search` dry-run command |
| FR44 | Epic 4 | `explain` one-shot LLM evaluation |
| FR45 | Epic 5 | `phase2 status` / `enable <entry>` / `disable <entry|--all>` |
| FR46 | Epic 5 | `phase2 smoke-test` + `phase2 reconcile <receipt-id>` |
| FR47 | Epic 4 | `health` command surfacing adapter + scheduler + Phase 2 state |
| FR48 | Epic 1 + applied across all CLI epics | Framework: exit-code mapping (0/1/2/3/4/5) + `--format json` contract in Epic 1; applied wherever CLI commands land |
| FR49 | Epic 1 + Epic 2 | 3-file config layout (`.env.example` / `config.example.yaml` / `wishlist.example.yaml`) in Epic 1; pydantic-settings loaders + validators in Epic 2 |
| FR50 | Epic 4 | SIGTERM graceful drain; in-flight LLM + Telegram + audit flushed within 30s |
| FR51 | Epic 1 | `Dockerfile` + `docker-compose.yml` + tracked examples |
| FR52 | Epic 1 | `CONTRIBUTING.md` with "no arbitrage PRs" rule + 3 invitation categories |
| FR53 | Epic 1 | `ROADMAP.md` with multi-marketplace / arbitrage-as-separate-repo / C&D-induced sunset |
| FR54 | Epic 1 | `README.md` positioning + legal disclaimer + no Wallapop trademarks |

Every FR has at least one epic assigned. No orphan FRs.

## Epic List

### Epic 1: Foundation — Installable Skeleton & OSS Posture

**User outcome.** An operator (or fork user) can `git clone`, `docker-compose up`, and reach a state where the daemon starts cleanly and Telegram receives an `ℹ️ Daemon ready` informational alert. The product exists as a runnable artifact published to GHCR with adapter discipline (NFR-M1 launch blocker), CI gates, and OSS posture documentation in place. No alerts yet — that's Epic 3 — but the install path works end-to-end.

**FRs covered:** FR39, FR48 (framework: exit-code mapping + `--format json` contract), FR49 (3-file config layout), FR51, FR52, FR53, FR54

**NFRs:** NFR-M1 (adapter discipline lint as merge-blocker), NFR-M4 (semver discipline), NFR-M5 (≤ 30 direct deps), NFR-O1 (structured JSON Lines on stdout), NFR-O5 (no remote logging), NFR-PR1, NFR-PR3, NFR-S7

**Architecture:** AR1 (uv scaffold), AR2 (typer), AR3 (ruff + ty/mypy + pytest), AR4 (pydantic v2 / pydantic-settings / PyYAML / ruamel.yaml — declared as deps), AR5 (httpx / python-telegram-bot / google-genai — declared as deps), AR6 (hexagonal layout encoded in directory tree), AR7 (`scripts/adapter_discipline_lint.py`), AR17 (Dockerfile + docker-compose.yml with restart policy + 30s stop_grace_period), AR18 (GHCR image distribution), AR19 (GitHub Actions CI), AR23 (TLS posture default)

**UX-DRs:** UX-DR2 (`render_table` / `render_prose` helpers in `observability/styling.py`), UX-DR16 (theme tokens), UX-DR17 (forbid `rich.progress.Progress` / `rich.status.Status`), UX-DR21 (typer + rich help text format), UX-DR27 (bilingual asymmetry — English-only policy for code/comments/docs), UX-DR31 (CLI terminal-width testing as CI gate)

### Epic 2: Wishlist Authoring, Configuration & Credentials

**User outcome.** The operator can declare what they're hunting in `wishlist.yaml`, validate it (with arbitrage fields structurally rejected pointing to (c3) and ROADMAP), authenticate Wallapop (manual browser cookie capture) and eBay.es (OAuth), and reach a state where the daemon would start polling if Phase 1 wiring existed (it doesn't yet — that's Epic 3). All credentials at mode 0600; permission verification at startup.

**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR40, FR41, FR42, FR49 (config loaders + validators)

**NFRs:** NFR-S1 (credential handling), NFR-S2 (0600 file permissions), NFR-S3 (TLS), NFR-S6 (interactive confirmation for destructive ops), NFR-PR4 (manual deletion path documented)

**Architecture:** AR4 (pydantic + ruamel.yaml round-trip), AR21 (Netscape cookies.txt + oauth_tokens.json), AR22 (permission verification at startup)

**UX-DRs:** UX-DR18 (CLI error + hint format), UX-DR19 (adaptive density), UX-DR22 (scope-contract error wording), UX-DR23 (typing-a-token destructive confirmation)

### Epic 3: Phase 1 — Continuous Marketplace Monitoring & Alerts

**User outcome.** The operator receives Telegram alerts for matched listings on Wallapop + eBay.es. Each alert contains the photo, price, location, italicized LLM one-line take, confidence level, and Phase 1 button row `[👁 Ver] [🙅 Saltar] [😴 Posponer 24h]`. Container-aware split renders when the LLM detects a wrapper listing (FR14). Snooze works per-entry. Wallapop's two-path fallback keeps alerts flowing during unofficial-API hiccups; eBay.es runs independently. **This is the heart of Phase 1.**

**FRs covered:** FR6, FR7, FR8, FR9, FR10, FR11, FR12 (detection side: stop polling Wallapop on 401), FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR22

**NFRs:** NFR-P1 (≤ 20 min p95 alert latency), NFR-P3 (≤ 5s p95 per-listing LLM eval), NFR-I1 (Hermes v0.13.x pin), NFR-I2 (TinyFish via MCP, rate-limit enforcement), NFR-I3 (`ListingEvaluator` interface; lint enforces no LLM-SDK imports outside adapter), NFR-I4 (Wallapop schema-drift surfaces as adapter failure), NFR-I5 (eBay API rate-limit handling), NFR-I6 (Telegram retry semantics), NFR-R1 (Wallapop / eBay.es runtime independence), NFR-R2 (two-path Wallapop fallback within same poll cycle), NFR-C3 (≥ 60% LLM cache hit rate target)

**Architecture:** AR6 (domain/interfaces/orchestration/adapters separation realized for the polling pipeline), AR8 (Phase 1 SQLite tables: `seen_listings`, `wishlist_runtime_state`, `alert_snapshots` Phase 1 columns, `_meta`), AR9 (`Store` interface foundation; `record_*` writers for `alert_snapshots`), AR10 (numbered SQL migrations applied at startup; Phase 1 migration creates Phase 1 tables), AR11 (Hermes SQLite + FTS5 hosts LLM evaluation cache, separate from `salvager.db`), AR15 (async daemon + Hermes subagents up to 8 concurrent for LLM eval), AR16 (synchronous internal pipeline)

**UX-DRs:** UX-DR1 (Phase 1 listing alert renderer), UX-DR3 (`SEVERITY_TOKENS` constants module), UX-DR4 (`BUTTON_LABELS` constants module), UX-DR5 (`callback_data` `<surface>:<verb>:<id>` format), UX-DR6 (Direction A + E hybrid with container split), UX-DR8 (`escape_markdown_v2()` helper), UX-DR12 (acknowledgment row after Phase 1 tap), UX-DR15 (lock-screen 3-rows decision-critical), UX-DR28 (6-row alert cap), UX-DR29 (Phase 1 renderer snapshot tests via syrupy), UX-DR30 (Phase 1 property tests for exit codes and JSON parseability)

### Epic 4: Operator Observability & Phase 1 Recovery

**User outcome.** The operator can diagnose any agent issue without reading raw logs. Operational alerts (`⚠️` high-priority, `ℹ️` informational) surface degradation with cause + next CLI command. `health` distinguishes "watching, no matches" from "stuck poller". `audit show` and `audit export` reveal Phase 1 events. `test-search` and `explain` enable dry-run inspection. SIGTERM drains in-flight work in ≤ 30s. Recovery from Wallapop session expiry, daemon crash, and adapter break is named and ergonomic.

**FRs covered:** FR12 (operational alert + recovery flow), FR21 (operational alerts in general), FR37 (CLI commands `audit show`/`audit export`), FR38 (no telemetry — applied across CLI), FR43, FR44, FR47, FR48 (exit codes + `--format json` applied to all Epic 4 commands), FR50

**NFRs:** NFR-O1 (structured JSON Lines fields), NFR-O2 (`health` surface contract), NFR-O3 (`audit show` paginated human format; `audit export` JSONL), NFR-O4 (operational alert diagnostic completeness), NFR-O5 (no log retention assumption), NFR-R3 (no silent failure), NFR-R4 (manual recovery boundaries), NFR-R5 (crash behavior + dedup consistency across restart)

**Architecture:** AR14 (daemon ↔ CLI: shared filesystem + SQLite, no IPC), AR20 (Telegram chat allowlist; silently drop unknown chat IDs)

**UX-DRs:** UX-DR13 (`render_operational_alert` for Phase 1-relevant events: `daemon_started`, `daemon_stopped`, `wallapop_session_expired`, `tinyfish_fallback_active`/`recovered`, `ebay_token_refresh_failed`), UX-DR14 (`⚠️` warn variants with numbered next-steps; `ℹ️` info variants direct + minimal), UX-DR15 (calm-instructional tone for `⚠️`; direct + minimal for `ℹ️`), UX-DR20 (JSON schema: snake_case + ISO 8601 + flat array + stderr JSON errors), UX-DR24 (no Telegram empty-state pings — silence is success), UX-DR25 (`health` distinguishes "watching, 0 matches in 24h" from "stuck poller"), UX-DR26 (audit pointer `salvager audit show --id <n>` in every alert that names a CLI command), UX-DR30 (property tests for `EventName` severity-vs-headline-style)

### Epic 5: Phase 2 — Autonomous Purchase with Safety Stack

**User outcome.** After the 4–8 week Phase 1 stabilization gate (per PRD), the operator opts entries into Phase 2 (`phase2 enable WD40EFPX`); receives Phase 2 alerts with `[✅ Comprar] [❌ Saltar] [👁 Ver]`; taps Comprar; sees the keyboard edit to `🟡 Comprando…`; receives a factual receipt with screenshot within 60s. The safety stack (cross-source price reconciliation + receipt-vs-alert reconciliation + daily synthetic smoke test + per-purchase circuit breaker) catches malformed data before any transaction; any failure auto-disables Phase 2 globally with a `⚠️` operational alert naming the cause and the `phase2 enable` command to recover. v1.0 is releasable when this epic completes; the release-gating Telegram client variance test and accessibility audit run as final stories.

**FRs covered:** FR23, FR24, FR25, FR26, FR27, FR28, FR29, FR30, FR31, FR32, FR33, FR34, FR35, FR36, FR37 (Phase 2 audit log writers populating the tables), FR45, FR46

**NFRs:** NFR-P2 (≤ 60s p95 end-to-end Phase 2 buy completion), NFR-S4 (audit log append-only at application layer; property test enforces), NFR-S5 (payment-rail enforcement + CI lint deny-list for `bizum`/`transferencia`), NFR-M2 (≥ 90% line coverage on Phase 2 critical-path modules: `buy_orchestrator`, `reconciler`, `circuit_breaker`, `smoke_test`, `audit_writer`), NFR-M3 (smoke-test regression fixture set grows with every UI surprise), NFR-R4 (manual re-enable after auto-disable)

**Architecture:** AR12 (`wishlist.yaml` canonical for Phase 2 enable/disable; ruamel.yaml round-trip on CLI mutations), AR13 (Phase 2 auto-disable lockout persisted in `phase2_state` SQLite table; cleared only by explicit `phase2 enable`), AR24 (Phase 2 file split: the 7 named files transition from `Phase2GuardrailTripped` stubs to full implementations)

**UX-DRs:** UX-DR7 (Phase 2 listing alert renderer; reuses Phase 1 layout with `🟢` prefix, `Phase 2 max:` suffix, Phase 2 keyboard), UX-DR9 (mandatory receipt screenshot — missing screenshot triggers `buy_success_without_screenshot` failure path), UX-DR10 (`La compra NO se ha ejecutado.` reassurance line on every `BuyFailureReason` variant), UX-DR11 (`🟡 Comprando…` in-flight keyboard state), UX-DR13 (Phase 2 operational events: `phase2_disabled`, `phase2_re_enabled`, `circuit_open`, `smoke_test_failed`, `smoke_test_recovered`), UX-DR23 (`--all` destructive confirmation by typing a token), UX-DR29 (Phase 2 renderer snapshot tests), UX-DR30 (property test: every `BuyFailureReason` produces the reassurance line; every `EventName` matches severity rules), UX-DR32 (Telegram client variance manual test matrix at v1.0 release gate), UX-DR33 (color-blind + accessibility audit at v1.0 release gate)

<!-- Story details elaborated below -->

## Epic 1: Foundation — Installable Skeleton & OSS Posture

**Goal.** An operator (or fork user) can `git clone`, `docker-compose up`, and reach a state where the daemon process starts cleanly, the container runs, the structured JSON logger emits `daemon_started`, and the image was built and pushed to `ghcr.io/ifuensan/salvager` by a green CI pipeline. The product exists as a runnable installable with adapter discipline (NFR-M1 launch blocker) enforced by CI, the typer CLI skeleton in place, and OSS posture documentation visible to fork users.

### Story 1.1: Bootstrap uv-managed Python package with hexagonal directory layout

As ifuensan (sole maintainer),
I want salvager initialized as a uv-managed Python 3.12 package with the full hexagonal directory tree (`domain/` / `interfaces/` / `orchestration/` / `adapters/` / `cli/` / `config/` / `observability/`) and a tracked `LICENSE` (MIT) + `.gitignore`,
So that every later story has a stable place to land code and the adapter-discipline boundary (NFR-M1) cannot be retroactively introduced.

**Acceptance Criteria:**

**Given** a fresh working directory
**When** I run `uv init --package salvager --python 3.12` followed by the dependency-add commands in architecture.md lines 188–196
**Then** `pyproject.toml` and `uv.lock` are produced
**And** the lockfile is committed
**And** `uv run python -c "import salvager"` succeeds with no error

**Given** the repository
**When** I list `src/salvager/`
**Then** the seven sibling packages `cli/` / `domain/` / `interfaces/` / `orchestration/` / `adapters/` / `config/` / `observability/` exist as empty packages with `__init__.py` files
**And** `tests/` contains `unit/` / `integration/` / `e2e/` / `fixtures/` sibling directories

**Given** the repository
**When** I inspect repository root
**Then** `LICENSE` exists (MIT, copyright ifuensan) and `.gitignore` excludes `/.env` / `/wishlist.yaml` / `/config.yaml` / `/data/` / `/.venv/` / `.ruff_cache/` / `.pytest_cache/` / `.ty_cache/` / `__pycache__/`

### Story 1.2: Establish CI quality gates with adapter discipline lint

As ifuensan,
I want a GitHub Actions workflow that runs `ruff check`, `ty` (with `mypy` fallback), `pytest --cov`, `python scripts/adapter_discipline_lint.py`, and a dependency-footprint check on every PR and tag push,
So that NFR-M1 (adapter discipline launch blocker), NFR-M5 (≤ 30 direct deps), and code-quality gates are mechanically enforced from day one.

**Acceptance Criteria:**

**Given** the repository
**When** I read `scripts/adapter_discipline_lint.py`
**Then** the script (≤ 100 LOC, zero external dep) walks every `.py` file under `src/salvager/`
**And** for files outside `src/salvager/adapters/**`, it fails on any `import` or `from … import` of a configured deny-list (`hermes_agent`, `tinyfish*`, `google.genai`, `openai`, `anthropic`, `telegram`, `httpx`, Wallapop/eBay SDK names)
**And** the script exits 0 on a clean tree and 1 on any violation with a line-numbered report

**Given** a PR opened against `main`
**When** CI runs
**Then** the workflow includes named jobs `lint` (ruff), `type-check` (ty + mypy fallback), `test` (pytest --cov), `adapter-discipline` (the AST lint), `dep-footprint` (asserts `len(uv tree | grep -c "^\S") ≤ 30 direct deps`)
**And** each job fails the workflow on non-zero exit

**Given** a PR that introduces `import httpx` in `src/salvager/domain/listing.py`
**When** CI runs
**Then** the `adapter-discipline` job fails with output naming the file and line number

### Story 1.3: Build and publish Docker image to GHCR

As a fork user,
I want a public Docker image at `ghcr.io/ifuensan/salvager:<semver>` produced automatically by CI on every tagged release,
So that I can run `docker pull ghcr.io/ifuensan/salvager:latest` without building from source.

**Acceptance Criteria:**

**Given** the repository
**When** I read `Dockerfile`
**Then** it uses `python:3.12-slim` as base
**And** it copies the uv-locked dependencies (`pyproject.toml` + `uv.lock`) and installs via `uv sync --frozen`
**And** the entrypoint is `salvager` (resolves via uv-installed console script)

**Given** the repository
**When** I read `docker-compose.yml`
**Then** it defines a single service named `salvager`
**And** the service mounts `./data:/app/data` and `./config:/app/config`
**And** `restart: on-failure` is set with default backoff
**And** `stop_grace_period: 30s` is set (FR50)

**Given** a tag `v0.1.0` pushed to `main`
**When** the release workflow runs
**Then** `ghcr.io/ifuensan/salvager:v0.1.0` and `:latest` are pushed
**And** the image is publicly pullable without authentication
**And** the workflow uses `GITHUB_TOKEN` for authentication (no manual secrets)

**Given** a pulled image
**When** I run `docker run --rm ghcr.io/ifuensan/salvager:latest --version`
**Then** the container prints the semver version and exits 0

### Story 1.4: Ship tracked example configuration files

As a fork user,
I want `.env.example`, `wishlist.example.yaml`, and `config.example.yaml` tracked in the repo with realistic placeholder content,
So that I can `cp .env.example .env` (etc.) and have a working starting point.

**Acceptance Criteria:**

**Given** the repository
**When** I list repository root
**Then** `.env.example`, `wishlist.example.yaml`, `config.example.yaml` exist and are tracked
**And** `.env`, `wishlist.yaml`, `config.yaml` are gitignored

**Given** `.env.example`
**When** I read it
**Then** it contains commented-placeholder entries for `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`, `EBAY_APP_ID`, `EBAY_CERT_ID`, `EBAY_DEV_ID`, `TINYFISH_API_KEY`
**And** each entry has a one-line comment explaining what it is and where to get it

**Given** `wishlist.example.yaml`
**When** I read it
**Then** it contains 2–3 representative entries (e.g., WD Red Plus 4TB / Crucial 16GB DDR4) with all required schema fields populated
**And** it contains zero forbidden arbitrage fields (`expected_resale_value`, `min_margin_percent`, `current_market_price`)
**And** it includes a top-of-file comment block referencing the (c3) scope contract and ROADMAP for arbitrage forks

**Given** `config.example.yaml`
**When** I read it
**Then** it contains commented-defaults for `schedule.wallapop_minutes` (15), `schedule.ebay_minutes` (30), `llm.provider` (gemini-flash), `llm.cache_ttl_hours` (24), `phase2.kill_switch_global` (false), `phase2.reconciliation_tolerance_eur` (1.00), `phase2.reconciliation_tolerance_pct` (5)

### Story 1.5: Author OSS posture documentation (README, CONTRIBUTING, ROADMAP)

As a fork user discovering the repo,
I want a README that frames salvager as a personal monitoring tool (not a "Wallapop scraper"), a CONTRIBUTING with explicit "no arbitrage PRs" policy, and a ROADMAP naming future-research repo paths and C&D-induced sunset,
So that I can decide whether the project fits my use case and how to contribute without violating the (c3) scope contract.

**Acceptance Criteria:**

**Given** the repository
**When** I read `README.md`
**Then** the first paragraph positions salvager as a personal monitoring tool, not a marketplace scraper
**And** it includes a legal disclaimer section covering Spanish ToS posture and the secondary-account recommendation
**And** it contains no Wallapop trademarks, logos, or proprietary terms in titles, package names, or domain references
**And** it includes a Quick Start showing `git clone` → `cp .env.example .env` → `cp wishlist.example.yaml wishlist.yaml` → `docker-compose up -d` → `salvager login wallapop`

**Given** the repository
**When** I read `CONTRIBUTING.md`
**Then** the document contains a top-level "No arbitrage PRs" section naming the structural rejection (FR3) and pointing to `ROADMAP.md` for the future-research repo path
**And** it names three explicit invitation categories: wishlist examples (PRs welcome), prompt improvements (PRs welcome), Wallapop selector patches (PRs welcome)
**And** it describes the dev-loop (uv install + `uv run pytest` + adapter discipline lint)

**Given** the repository
**When** I read `ROADMAP.md`
**Then** the document names: future multi-marketplace expansion, future-arbitrage-as-separate-repo, and "C&D-induced sunset" as a documented possible end state
**And** it documents the walk-away triggers from the PRD's Project Sustainability success criterion (≥ 30h/break × 3 attempts; rolling 3-month average > 20h/month maintenance)

### Story 1.6: Implement structured JSON Lines logging foundation

As an operator,
I want every daemon and CLI emission on stdout to be structured JSON Lines with the standard fields `level`, `ts`, `event`, `entry`, `marketplace`, `listing_id`, `latency_ms`, `error_class`,
So that NFR-O1 is satisfied from day one and downstream log scraping (docker-compose, journalctl, jq pipelines) works without parser hacks.

**Acceptance Criteria:**

**Given** `src/salvager/observability/logging.py`
**When** I import `get_logger(name)` from it
**Then** the returned logger emits one JSON object per line on stdout
**And** every record carries `level` (`debug`/`info`/`warn`/`error`), `ts` (ISO 8601 with millisecond precision and `Z` suffix), and `event` (snake_case event name)
**And** records can optionally carry `entry`, `marketplace`, `listing_id`, `latency_ms`, `error_class` when supplied by the caller

**Given** the logger configured via `config.yaml > logging.level`
**When** I set level to `warn`
**Then** `logger.info("foo")` produces no output and `logger.warn("bar")` produces a JSON record

**Given** a CLI invocation that pipes stdout to `jq`
**When** I run `salvager version | jq .event`
**Then** the JSON parses cleanly and yields the event name (no stderr noise mixed into stdout)

**Given** a daemon process raising an unhandled exception
**When** the global exception handler triggers
**Then** a final JSON record is emitted with `level: error`, `error_class`, the exception message, and a stack trace as a structured `stack` field
**And** the process exits with non-zero (NFR-R5)

### Story 1.7: Implement rich-based CLI rendering helpers with theme tokens

As a developer writing CLI subcommands,
I want a single source of truth for CLI output rendering in `observability/styling.py` exposing `render_table(rows, columns)` and `render_prose(message, style, hint=None)` plus the locked theme-token color map,
So that every operator command produces visually consistent output without inviting per-command `print()` calls.

**Acceptance Criteria:**

**Given** `src/salvager/observability/styling.py`
**When** I import `render_table` and `render_prose`
**Then** `render_table(rows: list[dict], columns: list[ColumnSpec]) -> rich.table.Table` produces a `rich.table.Table` with `box=MINIMAL`, header row bolded, no row separators, default 80-col width
**And** `render_prose(message: str, style: ThemeToken, hint: str | None = None) -> None` writes to stdout (or stderr for `error`/`warn`) using the locked token-to-style map: `success` (bold green + `✓ ` prefix), `error` (bold red + `error: ` prefix), `warn` (bold yellow + `warn: ` prefix), `info` (default), `secondary` (dim)

**Given** the styling module
**When** I read the `THEME` constant
**Then** it is a literal `dict` with seven entries: `error`/`warn`/`success`/`info`/`emphasis`/`secondary`/`code` mapped to the rich style strings from UX-DR16
**And** the module documents that `rich.progress.Progress` and `rich.status.Status` are forbidden at v1 (UX-DR17)

**Given** a CLI invocation with `--no-color` or `NO_COLOR=1` or piped stdout
**When** `render_prose("test", style="error")` runs
**Then** the output is plain text `error: test` with no ANSI escape codes
**And** the `error: ` prefix is preserved (color-independence per UX-DR22)

**Given** a CI test
**When** the test runs `render_table` against a fixture with 5 rows × 3 columns
**Then** the rendered text matches a tracked golden file at widths 60, 80, 100, 120 (UX-DR31)

### Story 1.8: Implement typer CLI skeleton with version subcommand

As ifuensan,
I want a `salvager` console script that exposes the typer subcommand framework, registers the placeholder subcommand groups (`init` / `login` / `validate-wishlist` / `validate-config` / `test-search` / `explain` / `phase2` / `audit` / `health` / `logs`), and ships `salvager version` working end-to-end,
So that FR39 is satisfied and every later story has a place to plug its subcommand in.

**Acceptance Criteria:**

**Given** the installed package
**When** I run `salvager --help`
**Then** the output lists usage, a one-paragraph description, and the placeholder subcommand groups
**And** the help text uses the typer + rich theme (bold cyan titles per UX-DR21)
**And** each subcommand listed has at least a one-line description

**Given** the installed package
**When** I run `salvager version`
**Then** stdout prints the semver version + git commit short SHA via `render_prose`
**And** the exit code is 0
**And** `salvager version --format json` emits a single JSON object `{"version": "0.1.0", "commit": "<sha>"}` to stdout

**Given** the installed package
**When** I run `salvager` with no subcommand
**Then** the daemon-default mode is invoked (FR39); at v0.1 this is a stub that logs `daemon_started` and `daemon_stopped` and exits cleanly (real poll loop lands in Epic 3)

**Given** the installed package
**When** I run `salvager init` (not yet implemented in Epic 1)
**Then** the command exits with code 1 and message `error: not yet implemented in this build` + `hint: see ROADMAP.md` (placeholder until Epic 2 Story 2.8)

**Given** any CLI invocation
**When** typer parses an unknown subcommand
**Then** the exit code is 2 (usage error per FR48)

**Given** any CLI invocation
**When** the command completes
**Then** the exit code is one of {0, 1, 2, 3, 4, 5} per FR48; a TODO comment names a CI gate to enforce this set as we add subcommands

## Epic 2: Wishlist Authoring, Configuration & Credentials

**Goal.** The operator can declare what they're hunting in `wishlist.yaml`, validate it (with arbitrage fields structurally rejected and the (c3) scope contract surfaced in the error), authenticate Wallapop via interactive browser cookie capture, authenticate eBay.es via OAuth, and trust that all credential files are mode-0600 with permission verification at startup. The wishlist schema, config schema, and `.env` loader are the foundation that every later epic builds on.

### Story 2.1: Define pydantic v2 schema for wishlist entries

As ifuensan,
I want `WishlistEntry` and `Wishlist` pydantic v2 models in `src/salvager/domain/wishlist.py` that enforce the FR1/FR2/FR4/FR5 field contract,
So that every later component (validator, scope-guard, poll loop, alert renderer) shares one schema source-of-truth and FR4's `(manufacturer, model, ref)` entry-key contract is mechanically defined.

**Acceptance Criteria:**

**Given** `src/salvager/domain/wishlist.py`
**When** I import `WishlistEntry`
**Then** the model declares required fields `manufacturer: str`, `model: str`, `ref: str`, `type: Literal["hdd", "ram"]`, `max_price_solo: Decimal | None`, `max_price_in_device: Decimal | None`, `keywords: list[str]`, `container_keywords: list[str]`, `phase2: Phase2Settings`, `confidence_threshold: Literal["low", "medium", "high"]`
**And** `Phase2Settings` declares `enabled: bool = False` and `max_price_eur: Decimal | None = None`
**And** the model uses pydantic v2 `model_config = ConfigDict(extra="forbid")` so unknown fields raise validation errors

**Given** `WishlistEntry`
**When** I instantiate with valid data
**Then** the `entry_key` computed property returns the tuple `(manufacturer, model, ref)` (FR4)
**And** the `display_name` computed property returns `f"{manufacturer} {model} ({ref})"`

**Given** `WishlistEntry`
**When** `max_price_in_device` is `None` (FR5)
**Then** the model accepts the value
**And** a method `container_detection_enabled() -> bool` returns `False`

**Given** `WishlistEntry`
**When** `max_price_solo` is `None` AND `max_price_in_device` is `None`
**Then** pydantic raises a `ValidationError` ("at least one of max_price_solo or max_price_in_device must be set")

**Given** a `Wishlist` model wrapping `entries: list[WishlistEntry]`
**When** two entries share the same `(manufacturer, model, ref)` tuple
**Then** pydantic raises a `ValidationError` naming both entries
**And** when the list contains > 100 entries, a `UserWarning` is emitted (soft cap per FR3)

### Story 2.2: Implement scope-guard validator with (c3)-anchored error

As ifuensan,
I want a `scope_guard.py` module that rejects any wishlist YAML containing forbidden arbitrage fields (`expected_resale_value`, `min_margin_percent`, `current_market_price`, `target_resale_margin`) with an error pointing to the (c3) scope contract and ROADMAP for the future-research repo path,
So that FR3 is enforced at the schema layer and FR17's "no arbitrage scoring" is impossible to introduce by config.

**Acceptance Criteria:**

**Given** `src/salvager/domain/scope_guard.py`
**When** I import `check_scope_violations(raw_yaml: dict) -> list[ScopeViolation]`
**Then** the function returns an empty list for compliant YAML
**And** for each occurrence of a forbidden field (case-insensitive match against `FORBIDDEN_FIELDS`), it returns a `ScopeViolation` with `path` (dotted path), `field_name`, and `line_number` (when available from ruamel.yaml CommentedMap)
**And** `FORBIDDEN_FIELDS` is a module-level constant naming exactly: `expected_resale_value`, `min_margin_percent`, `current_market_price`, `target_resale_margin`, `arbitrage_score`, `resale_target`

**Given** a wishlist with an `expected_resale_value: 80.00` entry
**When** validation runs via `validate_wishlist(path)`
**Then** the operation fails with the locked error template:
```
error: wishlist.yaml:42: forbidden field 'expected_resale_value' (entry: WD Red Plus 4TB)
hint: salvager does not support arbitrage scoring per the (c3) scope contract.
hint: See ROADMAP.md for the future-research repo path: github.com/ifuensan/salvager-research (stub).
```
**And** the exit code is 3 (validation failure per FR48)

**Given** the scope-guard module
**When** a unit test attempts to add a new forbidden field via the module API alone
**Then** the test fails (the FORBIDDEN_FIELDS constant is `Final[frozenset[str]]`)

### Story 2.3: Implement wishlist loader with ruamel.yaml round-trip preservation

As a developer writing `phase2 enable`/`phase2 disable`,
I want a `load_wishlist(path) -> Wishlist` and `save_wishlist(path, wishlist) -> None` pair in `src/salvager/config/wishlist_yaml.py` that round-trips comments and formatting via `ruamel.yaml`,
So that AR12 (wishlist canonical for Phase 2 settings; rewrites preserve user comments) holds without rewriting the user's whole file on every CLI mutation.

**Acceptance Criteria:**

**Given** a `wishlist.yaml` with inline comments and per-entry comment blocks
**When** I `load_wishlist(path)` then immediately `save_wishlist(path, wishlist)` without mutation
**Then** the file's byte content is identical (idempotent round-trip)

**Given** the loader
**When** the YAML is well-formed but a `WishlistEntry` field is invalid
**Then** pydantic raises a `ValidationError` and `load_wishlist` wraps it as `WishlistValidationError` with file path + line number + field name
**And** the scope-guard runs BEFORE pydantic validation (forbidden fields are reported as the highest-priority error)

**Given** the loader
**When** the YAML is malformed (parser error)
**Then** `load_wishlist` raises `WishlistParseError` with file path + line:col of the parser failure

**Given** a unit test
**When** I call `save_wishlist` after mutating `entries[0].phase2.enabled = True`
**Then** the saved YAML preserves all comments
**And** only the `enabled:` line under the targeted entry is changed
**And** YAML quoting style of unchanged values is preserved

### Story 2.4: Implement `salvager validate-wishlist` CLI command

As an operator,
I want `salvager validate-wishlist` to run the schema + scope-guard validation against `wishlist.yaml` and report success or precise errors,
So that FR3 is exercised on demand and FR40 (operator can validate before daemon start) is covered.

**Acceptance Criteria:**

**Given** a valid `wishlist.yaml` with 18 entries
**When** I run `salvager validate-wishlist`
**Then** the command prints `✓ wishlist.yaml is valid (18 entries; 2 with Phase 2 enabled)` via `render_prose(style="success")`
**And** the exit code is 0
**And** `salvager validate-wishlist --format json` prints `{"valid": true, "entry_count": 18, "phase2_enabled_count": 2}` on stdout

**Given** a `wishlist.yaml` with a forbidden field
**When** I run `salvager validate-wishlist`
**Then** the output matches the locked error template from Story 2.2 (Story 2.2 AC)
**And** the exit code is 3
**And** stderr (not stdout) carries the error in JSON mode

**Given** a `wishlist.yaml` with a duplicate `(manufacturer, model, ref)` tuple
**When** I run `salvager validate-wishlist`
**Then** the output names both duplicate entries with their line numbers
**And** the exit code is 3

**Given** `wishlist.yaml` not existing at the configured path
**When** I run `salvager validate-wishlist`
**Then** the output is `error: wishlist.yaml not found at <path>` + `hint: run salvager init to scaffold one`
**And** the exit code is 1

### Story 2.5: Implement config.yaml schema and loader with pydantic-settings

As ifuensan,
I want `config.yaml` parsed by a pydantic-settings model in `src/salvager/config/config_yaml.py` with explicit field contracts for `schedule.*`, `llm.*`, `phase2.*`, `telegram.*`, `logging.*`, `paths.*`,
So that FR49 (operational tunables file) is satisfied with type-safe schema and defaults documented in code.

**Acceptance Criteria:**

**Given** `src/salvager/config/config_yaml.py`
**When** I import `ConfigModel`
**Then** the pydantic-settings model declares typed sections: `schedule` (`wallapop_minutes: int`, `ebay_minutes: int`), `llm` (`provider: Literal[...]`, `cache_ttl_hours: int`, `cache_ttl_hours_low_confidence: int`), `phase2` (`kill_switch_global: bool`, `reconciliation_tolerance_eur: Decimal`, `reconciliation_tolerance_pct: Decimal`, `circuit_breaker_threshold: int`, `smoke_test_hour_utc: int`), `telegram` (`retry_max_attempts: int`, `retry_backoff_seconds: float`, `locale: Literal["es-ES"] = "es-ES"`), `logging` (`level: Literal[...]`), `paths` (`data_dir: Path`, `config_dir: Path`)
**And** every field has a documented default matching `config.example.yaml`

**Given** the loader `load_config(path) -> ConfigModel`
**When** the YAML is well-formed and all fields validate
**Then** the function returns a `ConfigModel` instance

**Given** the loader
**When** the YAML is missing a required field with no default
**Then** pydantic raises a `ValidationError` and the loader wraps it as `ConfigValidationError` with path + section + field

**Given** the loader
**When** `phase2.reconciliation_tolerance_pct` is `< 0` or `> 100`
**Then** pydantic raises a `ValidationError` (range check via `Annotated[Decimal, Field(ge=0, le=100)]`)

### Story 2.6: Implement .env loader with pydantic-settings BaseSettings

As ifuensan,
I want `src/salvager/config/env.py` to load credentials from `.env` exactly once at process start via pydantic-settings BaseSettings, with no hot-reload,
So that FR49 (`.env` once at start), NFR-S1 (credentials never logged or persisted outside cookie/token files), and FR50 (clean lifecycle) hold.

**Acceptance Criteria:**

**Given** `src/salvager/config/env.py`
**When** I import `EnvSettings`
**Then** the BaseSettings model declares required fields: `TELEGRAM_BOT_TOKEN: SecretStr`, `TELEGRAM_CHAT_ID: int`, `GEMINI_API_KEY: SecretStr`, `EBAY_APP_ID: SecretStr`, `EBAY_CERT_ID: SecretStr`, `EBAY_DEV_ID: SecretStr`, `TINYFISH_API_KEY: SecretStr`
**And** every credential uses pydantic `SecretStr` so `repr()` and `str()` mask the value

**Given** `EnvSettings` configured to read from `.env`
**When** I instantiate it with all required vars present
**Then** the model loads successfully
**And** `logger.info("env_loaded", extra={...})` emits NO credential values in its output

**Given** `EnvSettings`
**When** a required env var is missing
**Then** pydantic raises a `ValidationError` naming the missing var
**And** the daemon entry point catches this and prints `error: missing required env var: <name>` + `hint: see .env.example` to stderr with exit code 4 (auth)

**Given** the loader
**When** invoked twice in the same process
**Then** the second call returns the same cached instance (singleton; no hot-reload per FR49)

### Story 2.7: Implement `salvager validate-config` CLI command

As an operator,
I want `salvager validate-config` to load and validate `config.yaml` + `.env` and report success or precise errors,
So that I can sanity-check my configuration before starting the daemon.

**Acceptance Criteria:**

**Given** a valid `config.yaml` and `.env`
**When** I run `salvager validate-config`
**Then** the command prints `✓ config.yaml + .env are valid` via `render_prose(style="success")`
**And** the exit code is 0

**Given** a malformed `config.yaml`
**When** I run `salvager validate-config`
**Then** the output names the file, section, and field that failed validation
**And** the exit code is 3

**Given** a missing `.env` variable
**When** I run `salvager validate-config`
**Then** the output is `error: missing required env var: TELEGRAM_BOT_TOKEN` + `hint: see .env.example`
**And** the exit code is 4 (auth)

### Story 2.8: Implement `salvager init` subcommand

As a fork user (or ifuensan starting fresh),
I want `salvager init` to copy the tracked example files (`.env.example` → `.env`, `wishlist.example.yaml` → `wishlist.yaml`, `config.example.yaml` → `config.yaml`) into the configured `config_dir`,
So that FR40 is satisfied with a single command that scaffolds my starting point and refuses to overwrite without `--force`.

**Acceptance Criteria:**

**Given** an empty `config_dir`
**When** I run `salvager init`
**Then** the three target files are created from their `.example` siblings
**And** the output is a `rich.panel.Panel` (box=ROUNDED per UX-DR style) listing the three files created with their paths
**And** the exit code is 0

**Given** a `config_dir` containing an existing `wishlist.yaml`
**When** I run `salvager init` (without `--force`)
**Then** the command prints `error: wishlist.yaml already exists at <path>` + `hint: pass --force to overwrite (you'll be asked to confirm)`
**And** no files are written
**And** the exit code is 1

**Given** a `config_dir` containing an existing `wishlist.yaml`
**When** I run `salvager init --force` in a TTY
**Then** the command prompts `Type 'OVERWRITE' to confirm:` (per UX-DR23 — typing-a-token, never y/n)
**And** if the operator types anything other than `OVERWRITE`, no files are written and exit code is 1
**And** if the operator types `OVERWRITE`, all three files are overwritten and exit code is 0

**Given** a non-TTY context (e.g., `docker-compose run`)
**When** I run `salvager init --force`
**Then** the command fails immediately with `error: --force requires an interactive terminal` (per NFR-S6)
**And** the exit code is 1

### Story 2.9: Implement `salvager login wallapop` subcommand

As ifuensan,
I want `salvager login wallapop` to open a real browser, walk me through Wallapop's login + 2FA, capture the resulting session cookie in Netscape format, and persist it to `data_dir/auth/wallapop_cookies.txt` with mode 0600,
So that FR41 is satisfied with anti-bot-correct manual login and the cookie is filesystem-protected per NFR-S2 / AR21.

**Acceptance Criteria:**

**Given** a TTY context
**When** I run `salvager login wallapop`
**Then** the command opens a browser window (TinyFish Browser via Hermes MCP, or fallback to Playwright when configured) pointing at Wallapop's login page
**And** stdout prints `Opening browser for manual login...` via `render_prose(style="info")`
**And** the command waits for the operator to complete login + 2FA in the browser

**Given** a successful manual login in the browser
**When** Wallapop sets the session cookie
**Then** the command captures cookies via the browser session
**And** writes them to `data_dir/auth/wallapop_cookies.txt` in Netscape cookies.txt format
**And** sets file mode to `0600` via `os.chmod`
**And** prints `✓ Cookie captured (mode 0600 verified)` via `render_prose(style="success")`
**And** the exit code is 0

**Given** the cookie file already exists with mode 0644
**When** the command attempts to write it
**Then** the operation succeeds (the mode is enforced post-write, not pre-write)
**And** the new file is mode 0600

**Given** the operator abandons the browser session (closes window without logging in)
**When** the configured timeout (default 5 minutes) expires
**Then** the command exits with `error: login timeout: no cookie captured` + `hint: re-run salvager login wallapop when ready`
**And** the exit code is 4 (auth)
**And** no cookie file is written (no partial state)

**Given** a non-TTY context
**When** I run `salvager login wallapop`
**Then** the command fails immediately with `error: login wallapop requires an interactive terminal`
**And** the exit code is 1

### Story 2.10: Implement `salvager login ebay` subcommand

As ifuensan,
I want `salvager login ebay` to walk me through eBay's official OAuth flow and persist refresh + access tokens in `data_dir/auth/oauth_tokens.json` with mode 0600,
So that FR42 / NFR-I5 / NFR-S2 / AR21 are satisfied and the daemon can auto-refresh access tokens without further operator intervention.

**Acceptance Criteria:**

**Given** a TTY context with `EBAY_APP_ID` / `EBAY_CERT_ID` / `EBAY_DEV_ID` set
**When** I run `salvager login ebay`
**Then** the command prints the eBay OAuth consent URL via `render_prose` and opens the URL in the default browser (or instructs the operator to open it manually)
**And** the command waits for the operator to complete the consent flow and paste back the authorization code

**Given** a valid authorization code
**When** the command exchanges it for refresh + access tokens
**Then** both tokens are written to `data_dir/auth/oauth_tokens.json` with mode 0600
**And** the file structure is `{"refresh_token": "...", "access_token": "...", "expires_at": "<ISO 8601>", "scope": "..."}`
**And** the command prints `✓ OAuth tokens captured (mode 0600 verified)`
**And** the exit code is 0

**Given** an invalid authorization code
**When** the exchange fails with HTTP 400
**Then** the command prints `error: OAuth exchange failed: <eBay error message>` + `hint: re-run salvager login ebay and re-paste the code`
**And** the exit code is 4

**Given** the daemon running with valid refresh + access tokens
**When** the access token is within 5 minutes of expiry
**Then** the eBay adapter (Epic 3) auto-refreshes the access token using the refresh token
**And** the new tokens are written atomically (write to temp file → fsync → rename) preserving 0600 mode

### Story 2.11: Implement startup permission verification for credential files

As ifuensan,
I want the daemon (and every CLI command that reads credentials) to verify at startup that `.env`, `wallapop_cookies.txt`, and `oauth_tokens.json` are mode 0600 and refuse to load otherwise,
So that NFR-S2 + AR22 are enforced — a permissive permission can never be silently tolerated.

**Acceptance Criteria:**

**Given** a startup-verification helper `verify_credential_permissions() -> None` in `src/salvager/config/permissions.py`
**When** I call it with all three files at mode 0600
**Then** the function returns silently

**Given** the helper
**When** any of the three files is at mode 0644 (or any mode broader than 0600)
**Then** the function raises `CredentialPermissionsError` naming the file and its actual mode
**And** the daemon entry point catches this and prints `error: <path> has mode <observed>, expected 0600` + `hint: chmod 600 <path>` to stderr with exit code 4 (auth)
**And** the daemon exits without starting the poll loop

**Given** the helper
**When** a file does not exist
**Then** the function treats it as "missing credential" and raises `CredentialMissingError` (a separate error class) with the path
**And** the daemon prints `error: missing credential file: <path>` + `hint: run salvager login <marketplace>` and exits 4

**Given** a CI test using `pyfakefs` or `tmp_path`
**When** I create test files at modes 0600, 0640, 0644, 0755
**Then** only 0600 passes verification and all others raise `CredentialPermissionsError`
**And** the test runs on Linux + macOS CI runners (Windows skipped — out of v1 support)

## Epic 3: Phase 1 — Continuous Marketplace Monitoring & Alerts

**Goal.** The operator receives Telegram alerts for matched listings on Wallapop + eBay.es. Each alert renders with photo, price, location, italicized LLM one-line take, confidence level, and the locked Phase 1 button row `[👁 Ver] [🙅 Saltar] [😴 Posponer 24h]`. Container-aware split (Direction E) renders when the LLM identifies a wrapper listing. Snooze suppresses the entry for 24 hours. Wallapop's two-path fallback keeps alerts flowing during unofficial-API hiccups; eBay.es runs independently per NFR-R1. **This is the heart of Phase 1**; once it lands, the user can opt into Phase 1 production for the 4–8 week trust window before Phase 2 (Epic 5) becomes available.

### Story 3.1: Define domain models for listing, evaluation, alert-snapshot

As a developer writing adapters and the poll loop,
I want pure-Python pydantic v2 models in `src/salvager/domain/listing.py`, `evaluation.py`, `alert.py`, and `audit.py` (Phase 1 subset),
So that every adapter, renderer, and store shares one schema source-of-truth and AR6 (pure domain, no SDK imports) is enforced from the start.

**Acceptance Criteria:**

**Given** `src/salvager/domain/listing.py`
**When** I import `Listing`
**Then** the model has fields `listing_id: str`, `marketplace: Literal["wallapop", "ebay"]`, `url: str`, `title: str`, `description: str`, `price_eur: Decimal`, `location: str | None`, `photo_urls: list[str]`, `seller_id: str | None`, `seller_history_count: int | None`, `published_at: datetime | None`, `fetched_at: datetime`
**And** `Listing.entry_key_match: tuple[str, str, str] | None` is the matched wishlist entry-key set by the LLM evaluator (None until evaluated)

**Given** `src/salvager/domain/evaluation.py`
**When** I import `ListingEvaluation`
**Then** the model has fields `listing_id: str`, `entry_key: tuple[str, str, str]`, `confidence: Literal["low", "medium", "high"]`, `one_line_take: str`, `is_container: bool`, `wrapper_text: str | None`, `extracted_text: str | None`, `evaluated_at: datetime`, `cache_hit: bool`
**And** `ConfidenceLevel` is exposed as a re-exportable enum or Literal

**Given** `src/salvager/domain/alert.py`
**When** I import `AlertSnapshot`
**Then** the model has fields `alert_id: UUID`, `entry_key: tuple[str, str, str]`, `entry_display_name: str`, `listing: Listing`, `evaluation: ListingEvaluation`, `phase: Literal["phase1", "phase2"]`, `phase2_max_price_eur: Decimal | None`, `rendered_at: datetime`
**And** `RenderedAlert` is the data shape every renderer produces: `text: str`, `parse_mode: Literal["MarkdownV2"]`, `photo_url: str | None`, `inline_keyboard: list[list[InlineButton]] | None`
**And** `InlineButton` has `text: str` (label) and `callback_data: str` (format `<surface>:<verb>:<id>`)

**Given** `src/salvager/domain/audit.py` (Phase 1 subset)
**When** I import `AuditEntry`
**Then** the Phase 1 variants `AlertSnapshotAudit`, `CallbackAudit` are defined as pydantic discriminated unions with a `kind` field
**And** Phase 2 variants `TapEventAudit`, `TransactionAudit` are declared but raise `Phase2GuardrailTripped` if instantiated (per AR24 stub policy)

**Given** the entire `src/salvager/domain/` package
**When** the adapter-discipline lint runs
**Then** no file in `domain/` imports anything outside `stdlib` + `pydantic` + `decimal` + `uuid` + `datetime` + `typing`

### Story 3.2: Define adapter interfaces (ABCs in `interfaces/`)

As a developer composing the poll loop,
I want abstract base classes for `PageFetcher`, `ListingEvaluator`, `Scheduler`, `TelegramSurface`, `Store` in `src/salvager/interfaces/`,
So that `orchestration/` composes interfaces, never concrete adapters; the adapter-discipline boundary is mechanical.

**Acceptance Criteria:**

**Given** `src/salvager/interfaces/page_fetcher.py`
**When** I import `PageFetcher`
**Then** the ABC declares `async def search(self, query: SearchQuery) -> list[Listing]` and `async def fetch(self, listing_url: str) -> Listing`
**And** `SearchQuery` is a pydantic model in `domain/listing.py` with fields `keywords: list[str]`, `marketplace: Literal["wallapop", "ebay"]`, `max_price_eur: Decimal | None`

**Given** `src/salvager/interfaces/listing_evaluator.py`
**When** I import `ListingEvaluator`
**Then** the ABC declares `async def evaluate(self, listing: Listing, entry: WishlistEntry) -> ListingEvaluation`

**Given** `src/salvager/interfaces/scheduler.py`
**When** I import `Scheduler`
**Then** the ABC declares `async def register(self, job_name: str, cadence_minutes: int, callable: Awaitable) -> None` and `async def shutdown(self) -> None`

**Given** `src/salvager/interfaces/telegram_surface.py`
**When** I import `TelegramSurface`
**Then** the ABC declares `async def send(self, rendered: RenderedAlert) -> int` (returns Telegram message_id), `async def edit_keyboard(self, message_id: int, keyboard: list[list[InlineButton]] | None) -> None`, `async def listen_callbacks(self, handler: Callable[[CallbackEvent], Awaitable]) -> None`

**Given** `src/salvager/interfaces/store.py`
**When** I import `Store`
**Then** the ABC declares Phase 1 methods: `async def is_seen(self, listing_id: str, entry_key: tuple) -> bool`, `async def record_seen(self, listing: Listing, entry_key: tuple) -> None`, `async def record_alert_snapshot(self, snapshot: AlertSnapshot) -> int`, `async def record_callback(self, callback: CallbackAudit) -> None`, `async def get_snooze_until(self, entry_key: tuple) -> datetime | None`, `async def set_snooze(self, entry_key: tuple, until: datetime) -> None`, `async def get_alert_snapshot(self, audit_id: int) -> AlertSnapshot | None`
**And** Phase 2 methods (`record_tap_event`, `record_transaction`, etc.) are declared in the ABC but documented as Phase 2 — concrete adapters raise `Phase2GuardrailTripped` if called at v0.x (AR24)
**And** the ABC declares NO `update_*` or `delete_*` methods on any audit table (NFR-S4 enforcement)

**Given** the `interfaces/` package
**When** the adapter-discipline lint runs
**Then** no file in `interfaces/` imports anything outside `stdlib` + `pydantic` + `domain/`

### Story 3.3: Implement SQLite store with WAL mode + Phase 1 tables

As an operator,
I want a single `salvager.db` SQLite file with WAL mode and a tracked migration runner producing the Phase 1 tables (`wishlist_runtime_state`, `seen_listings`, `alert_snapshots`, `callbacks`, `_meta`),
So that AR8 / AR9 / AR10 are satisfied and concurrent CLI reads work while the daemon writes (NFR-R5).

**Acceptance Criteria:**

**Given** `src/salvager/adapters/sqlite_store/connection.py`
**When** the daemon opens its first connection
**Then** the connection executes `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`
**And** the database file lives at `data_dir/salvager.db`

**Given** `src/salvager/migrations/`
**When** I read the directory
**Then** it contains `0001_phase1_schema.sql` defining: `_meta` (key/value with `schema_version`), `wishlist_runtime_state` (entry_key columns + `snooze_until` + last-seen timestamps), `seen_listings` (listing_id + url + perceptual_photo_hash + first_seen + last_seen + entry_key + match_fired), `alert_snapshots` (audit_id PK auto-increment + alert_id UUID + entry_key + listing JSON + evaluation JSON + phase + rendered_at), `callbacks` (audit_id PK + alert_id FK + verb + raw_payload + received_at)
**And** every audit table (`alert_snapshots`, `callbacks`) has indexes on entry_key columns and timestamps for FR47 health queries

**Given** the migration runner at daemon startup
**When** `_meta.schema_version` matches the highest available migration
**Then** no migrations run

**Given** the migration runner
**When** `_meta.schema_version` is older than available migrations
**Then** missing migrations run in order, each in a transaction; `_meta.schema_version` advances after each
**And** `salvager validate-config` flags drift between code and DB

**Given** `Store` implementation `SqliteStore` in `src/salvager/adapters/sqlite_store/`
**When** I call `record_alert_snapshot(snapshot)`
**Then** a row is inserted with `audit_id` returned
**And** the table has NO `UPDATE` or `DELETE` triggers — the application layer is the only enforcement (NFR-S4)

**Given** `SqliteStore`
**When** I attempt to monkey-patch an `update_alert_snapshots` method onto the instance
**Then** a property test (NFR-S4 enforcement) detects the absence of mutation methods on `Store` ABC and fails CI if any are introduced

### Story 3.4: Implement Wallapop unofficial-API adapter

As ifuensan,
I want a `PageFetcher` implementation in `src/salvager/adapters/wallapop_api/` that queries `api.wallapop.com/api/v3/general/search` via httpx with the operator's session cookie, validates the response schema, and returns `Listing` instances,
So that FR6 (primary path) is satisfied; FR10 dedup is fed; NFR-I4 (schema drift surfaces as adapter failure) is enforced.

**Acceptance Criteria:**

**Given** `src/salvager/adapters/wallapop_api/fetcher.py`
**When** I import `WallapopApiFetcher`
**Then** the class implements `PageFetcher.search()` and `.fetch()`
**And** it loads the cookie from `wallapop_cookies.txt` via the cookie-jar helper (Netscape format)
**And** httpx is the HTTP client; `verify=True` always (NFR-S3); no `verify=False` codepath exists

**Given** the fetcher executing a search
**When** the API returns HTTP 200 with valid JSON
**Then** the response is validated against a pydantic schema (`WallapopApiSearchResponse`)
**And** each entry is converted to a domain `Listing` instance with `marketplace="wallapop"`
**And** the operation logs `wallapop_search_succeeded` with `latency_ms` and `result_count`

**Given** the fetcher
**When** the API returns HTTP 401 (session expired)
**Then** the fetcher raises `WallapopSessionExpired` (a typed exception in `domain/errors.py`)
**And** the caller (Story 3.6) decides what to do — this adapter doesn't auto-recover

**Given** the fetcher
**When** the API returns HTTP 4xx (other) or 5xx
**Then** the fetcher raises `WallapopApiError` with the status code and (when available) the response body excerpt

**Given** the fetcher
**When** the API returns HTTP 200 but the response JSON has fields missing from the pydantic schema (schema drift)
**Then** the fetcher raises `WallapopSchemaDrift` (typed exception) with the offending field path
**And** the operation logs `wallapop_schema_drift` with `error_class`

**Given** the adapter package
**When** the adapter-discipline lint runs
**Then** `wallapop_api/` is allowed to import `httpx` (it's an adapter)
**And** no other package imports `httpx` (Story 1.2 lint enforces this)

### Story 3.5: Implement Wallapop TinyFish fallback adapter

As ifuensan,
I want a second `PageFetcher` implementation in `src/salvager/adapters/wallapop_tinyfish/` that queries Wallapop via TinyFish's MCP Search and Fetch primitives (proxied through Hermes' MCP client), honoring TinyFish free-tier rate limits (5 req/min Search, 25 URLs/min Fetch),
So that NFR-R2 (two-path Wallapop fallback within same poll cycle) is satisfied and FR6's fallback path is available when the unofficial API breaks.

**Acceptance Criteria:**

**Given** `src/salvager/adapters/wallapop_tinyfish/fetcher.py`
**When** I import `WallapopTinyfishFetcher`
**Then** the class implements `PageFetcher.search()` and `.fetch()`
**And** the constructor accepts a Hermes MCP client handle (configured at startup with TinyFish endpoint + API key)
**And** the adapter never imports `tinyfish_*` SDKs directly — only the Hermes MCP client interface (NFR-I2)

**Given** the fetcher executing a search
**When** the call returns successfully
**Then** the result is parsed (HTML/JSON depending on TinyFish response shape) into domain `Listing` instances
**And** the operation logs `wallapop_tinyfish_search_succeeded` with `latency_ms` and `result_count`

**Given** the fetcher
**When** the rate limit (5 search/min) would be exceeded
**Then** the fetcher does NOT call TinyFish; it raises `RateLimitWouldExceed` immediately
**And** the local rate-limit tracker is enforced via a small in-memory sliding-window counter inside the adapter (client-side enforcement per NFR-I2 — never trust remote alone)

**Given** the fetcher
**When** TinyFish returns an error (auth, quota, infra)
**Then** the fetcher raises `WallapopTinyfishError` with the error class + (when present) error message

**Given** an integration test using a recorded TinyFish fixture
**When** the fetcher runs against the fixture
**Then** the returned `Listing` set matches the golden snapshot exactly

### Story 3.6: Implement two-path Wallapop fallback orchestration with session-expiry detection

As ifuensan,
I want the poll loop's Wallapop branch to try the unofficial-API path first, fall back to the TinyFish path within the same poll cycle on adapter failure, and emit a specific operational alert when the cookie returns 401,
So that NFR-R2 (two-path fallback) and FR12 (session-expiry alert + stop polling unofficial-API path) are satisfied.

**Acceptance Criteria:**

**Given** an orchestration helper `wallapop_two_path_fetch(query) -> list[Listing]` in `src/salvager/orchestration/wallapop_fallback.py`
**When** the unofficial-API path succeeds
**Then** the unofficial-API results are returned and the TinyFish path is NOT called
**And** the result is annotated with `source="wallapop_api"` for diagnostic logging

**Given** the orchestration helper
**When** the unofficial-API path raises `WallapopApiError` or `WallapopSchemaDrift`
**Then** the TinyFish path is attempted as fallback within the same poll cycle
**And** the result is annotated with `source="wallapop_tinyfish"` for logging
**And** an operational event `wallapop_api_degraded` is fired via the degradation reporter (Epic 4 wires the renderer; for now we just emit the structured log entry)

**Given** the orchestration helper
**When** the unofficial-API path raises `WallapopSessionExpired`
**Then** the helper marks the API path as `unhealthy` in the `health` state
**And** falls back to TinyFish for the current poll
**And** stops attempting the unofficial-API path on subsequent polls until the operator runs `salvager login wallapop` (Story 2.9) again
**And** emits a structured log entry `wallapop_session_expired` (Epic 4 wires the Telegram operational alert)

**Given** the orchestration helper
**When** BOTH paths fail
**Then** the helper returns an empty list, marks Wallapop as `down` in `health` state, and the structured log entry `wallapop_both_paths_down` fires
**And** the poll cycle continues (eBay.es is independent per NFR-R1)

**Given** the orchestration helper
**When** the operator runs `login wallapop` and re-captures the cookie
**Then** on the next poll, the unofficial-API path is re-attempted (status flips back to `healthy` on success)
**And** an operational event `wallapop_session_renewed` is emitted

### Story 3.7: Implement eBay.es official-API adapter

As ifuensan,
I want a `PageFetcher` implementation in `src/salvager/adapters/ebay_api/` that queries eBay's Finding/Search API using the OAuth tokens from `data_dir/auth/oauth_tokens.json`, auto-refreshes access tokens before expiry, tracks daily request budget, and degrades to reduced poll cadence on quota breach,
So that FR7 / NFR-I5 are satisfied and the eBay.es leg of the daemon runs independently of Wallapop (NFR-R1).

**Acceptance Criteria:**

**Given** `src/salvager/adapters/ebay_api/fetcher.py`
**When** I import `EbayApiFetcher`
**Then** the class implements `PageFetcher.search()` and `.fetch()` for `marketplace="ebay"`
**And** it loads OAuth tokens from `oauth_tokens.json` at startup and refreshes access tokens via the eBay refresh endpoint when access token is within 5 minutes of expiry
**And** atomic write (temp file → fsync → rename) preserves 0600 mode

**Given** the fetcher
**When** the search succeeds
**Then** the result is parsed into domain `Listing` instances with `marketplace="ebay"`
**And** the operation logs `ebay_search_succeeded` with `latency_ms`, `result_count`, `daily_quota_remaining`

**Given** the fetcher
**When** the daily request budget configured via `config.yaml > ebay.daily_request_quota` would be breached on the next call
**Then** the fetcher raises `EbayQuotaExceeded` with the current and budgeted counts
**And** the caller (poll loop) reduces eBay polling cadence by 2× until the next quota reset (UTC midnight)
**And** the operational event `ebay_quota_breach` fires (Epic 4 renders the operational alert)

**Given** the fetcher
**When** the refresh endpoint returns HTTP 401 (refresh token revoked)
**Then** the fetcher raises `EbayAuthFailed`
**And** the operational event `ebay_token_refresh_failed` fires
**And** the daemon stops polling eBay until the operator runs `salvager login ebay` (Story 2.10) again

**Given** an integration test using a recorded eBay fixture (`tests/fixtures/ebay_api/`)
**When** the fetcher runs against the fixture
**Then** the returned `Listing` set matches the golden snapshot exactly

### Story 3.8: Implement Hermes scheduler adapter + per-marketplace poll registration

As the daemon orchestrator,
I want a `Scheduler` implementation in `src/salvager/adapters/hermes_scheduler/` that wraps Hermes Agent's built-in scheduler primitives and registers per-marketplace poll jobs with cadences from `config.yaml`,
So that FR8 / NFR-I1 are satisfied without depending on external cron and the per-marketplace cadence is operator-tunable.

**Acceptance Criteria:**

**Given** `src/salvager/adapters/hermes_scheduler/scheduler.py`
**When** I import `HermesScheduler`
**Then** the class implements `Scheduler.register(job_name, cadence_minutes, callable)` by wrapping the Hermes scheduler primitive
**And** the adapter is the only package in the project allowed to import `hermes_agent.*`
**And** Hermes is pinned to v0.13.x in `pyproject.toml` (NFR-I1)

**Given** the daemon entry point at startup
**When** the scheduler is initialized
**Then** two jobs register: `wallapop_poll` at `config.yaml > schedule.wallapop_minutes` (default 15) and `ebay_poll` at `config.yaml > schedule.ebay_minutes` (default 30)
**And** the scheduler logs `scheduler_started` with both job names and cadences

**Given** the running daemon
**When** the operator edits `config.yaml > schedule.wallapop_minutes` from 15 to 10
**Then** on the next 30-second config-rescan tick, the daemon re-registers `wallapop_poll` with the new cadence
**And** logs `scheduler_job_re_registered` with old + new cadence

**Given** the daemon receiving SIGTERM
**When** `Scheduler.shutdown()` is invoked
**Then** in-flight jobs complete (up to FR50's 30-second budget) and no new jobs start
**And** the scheduler logs `scheduler_stopped`

### Story 3.9: Implement wishlist-anchored LLM evaluator with container detection

As ifuensan,
I want a `ListingEvaluator` implementation in `src/salvager/adapters/llm_gemini/` that takes a `Listing` + `WishlistEntry`, calls Gemini Flash with a wishlist-anchored prompt template (in `domain/prompts.py`), and returns a `ListingEvaluation` with `(low|medium|high)` confidence, a one-line take, and a container-detection signal,
So that FR13 / FR14 / FR15 / FR17 are satisfied and the LLM has NO codepath to produce arbitrage scores (FR17's "no codepath" enforcement is structural — the prompt only asks the matching question).

**Acceptance Criteria:**

**Given** `src/salvager/domain/prompts.py`
**When** I import `build_evaluation_prompt(listing, entry) -> str`
**Then** the function returns a prompt template that includes:
  - The wishlist entry's `(manufacturer, model, ref)` + display name + keywords + container_keywords + price ceilings
  - The listing's title + description + price + photo URLs + location
  - The single question: *"does this listing match this wishlist entry?"*
  - A required output schema: `{confidence: low|medium|high, one_line_take: str, is_container: bool, wrapper_text: str|null, extracted_text: str|null}`
**And** the prompt template contains NO request for resale value, margin, market price, or any arbitrage signal (FR17 enforced at the prompt layer)

**Given** `src/salvager/adapters/llm_gemini/evaluator.py`
**When** I import `GeminiFlashEvaluator`
**Then** the class implements `ListingEvaluator.evaluate(listing, entry)`
**And** the implementation uses `google.genai` (per AR5) to call Gemini Flash with the prompt
**And** it parses the response strictly via pydantic (rejects responses that don't match the schema)

**Given** the evaluator
**When** Gemini returns a valid response
**Then** the function returns a `ListingEvaluation` instance with the parsed fields
**And** `one_line_take` is required to be specific (length ≤ 120 chars; a property test in Story 3.15 asserts non-generic content via regex against banned generic phrases)
**And** `evaluated_at` is set to current UTC

**Given** the evaluator
**When** the listing's price > entry's `max_price_solo` AND > entry's `max_price_in_device`
**Then** the evaluator returns confidence `low` (above-budget guard at the eval layer; FR26's hard ceiling lands in Epic 5)
**And** `one_line_take` includes "price exceeds wishlist max"

**Given** the evaluator
**When** Gemini's response is malformed (parser error or schema violation)
**Then** the function raises `LlmEvaluationError`
**And** the caller (poll loop) skips the listing and logs `llm_eval_failed` with the listing_id and error_class
**And** the listing is NOT marked as seen (will be retried on next poll)

**Given** the evaluator
**When** Gemini hits its API rate limit
**Then** the function raises `LlmRateLimited`
**And** the caller (poll loop) gracefully degrades — defers the remaining listings to the next cycle
**And** an operational event `llm_provider_rate_limited` fires (Epic 4 wires the renderer)

**Given** the adapter
**When** the adapter-discipline lint runs
**Then** `llm_gemini/` is allowed to import `google.genai`
**And** no other package imports `google.genai` (NFR-I3 / NFR-M1)

### Story 3.10: Implement LLM evaluation cache via Hermes SQLite + FTS5

As ifuensan,
I want LLM evaluations cached per listing URL with configurable TTL (24h default, 1h for low-confidence) using Hermes Agent's built-in SQLite + FTS5 memory (separate from `salvager.db`),
So that FR16 / NFR-C3 are satisfied — re-fetched listings within TTL skip Gemini Flash entirely, cutting cost and latency.

**Acceptance Criteria:**

**Given** `src/salvager/adapters/llm_gemini/cache.py`
**When** I import `LlmEvaluationCache`
**Then** the class wraps Hermes' SQLite + FTS5 memory primitive (AR11)
**And** the cache database lives separately from `salvager.db`, at `data_dir/hermes_memory.db`
**And** keys are `(listing_url, prompt_version)` to invalidate cache on prompt changes
**And** stored values are the serialized `ListingEvaluation` + the originating prompt (for `explain` debugging via FR44)

**Given** the cache
**When** `get(listing_url, prompt_version) -> ListingEvaluation | None` is called and a value exists within TTL
**Then** the cached `ListingEvaluation` is returned with `cache_hit=True`
**And** the cache logs `llm_cache_hit` with `listing_url` and `age_seconds`

**Given** the cache
**When** the cached value has confidence `low` and is older than `config.yaml > llm.cache_ttl_hours_low_confidence` (default 1)
**Then** `get()` returns `None` (treat as miss)

**Given** the cache
**When** the cached value has confidence `medium` or `high` and is older than `config.yaml > llm.cache_ttl_hours` (default 24)
**Then** `get()` returns `None`

**Given** a steady-state CI test running the cache against a recorded fixture stream of 1000 listings with 30% re-fetch rate
**When** the test completes
**Then** the cache hit rate is ≥ 60% (NFR-C3 target)
**And** the test fails if the rate drops below 50% (regression guard with a 10pt cushion)

**Given** the evaluator (Story 3.9) wired to use the cache
**When** an evaluation is requested for an already-cached listing
**Then** the evaluator returns the cached result without calling Gemini
**And** `ListingEvaluation.cache_hit` is `True`

### Story 3.11: Implement Phase 1 alert renderer with Direction A + E hybrid

As ifuensan reading alerts on a phone,
I want `render_phase1_listing_alert(snapshot: AlertSnapshot) -> RenderedAlert` in `src/salvager/domain/alert.py` to produce the locked Direction A baseline anatomy plus the Direction E container-aware split when `snapshot.evaluation.is_container == True`, using the locked `SEVERITY_TOKENS` and `BUTTON_LABELS` constants and `escape_markdown_v2()` on all user-supplied content,
So that FR18 / FR19 / FR22 / UX-DR1 / UX-DR3 / UX-DR4 / UX-DR5 / UX-DR6 / UX-DR8 are satisfied with format stability gated by snapshot tests.

**Acceptance Criteria:**

**Given** `src/salvager/domain/alert.py`
**When** I import `SEVERITY_TOKENS`, `BUTTON_LABELS`, `CALLBACK_DATA_FORMAT`
**Then** the constants exactly match the UX-DR3/4/5 spec: `SEVERITY_TOKENS` has the 6 named entries (`operational_warn`, `operational_info`, `phase1_listing`, `phase2_listing`, `phase2_buy_success`, `phase2_buy_failure`); `BUTTON_LABELS` has the 5 named entries (`view`, `skip_phase1`, `snooze`, `buy`, `skip_phase2`); `CALLBACK_DATA_FORMAT` is the literal string `"<surface>:<verb>:<id>"` (max 64 bytes documented)
**And** all three are `Final[dict[str, str]]` (or `Final[str]`) — runtime-immutable

**Given** `escape_markdown_v2(s: str) -> str` in `domain/alert.py`
**When** I pass a string containing MarkdownV2 reserved characters (`_*[]()~\`>#+-=|{}.!`)
**Then** the function returns the string with every reserved character backslash-escaped
**And** a property test in Story 3.15 asserts no reserved chars remain unescaped for a generated string corpus

**Given** `render_phase1_listing_alert(snapshot)` with a direct (non-container) listing
**When** the renderer runs
**Then** the returned `RenderedAlert.text` matches the Direction A anatomy exactly:
  - Row 1: `📦 *<part_name>* — *<price_eur formatted ES>*`
  - Row 2: `📍 <location> · <marketplace>`
  - Row 3: `_<llm_take>_`
  - Row 4: `🔍 Confidence: <low|medium|high>`
**And** `RenderedAlert.photo_url` is the listing's first photo URL
**And** `RenderedAlert.inline_keyboard` is `[[(👁 Ver, listing:view:<id>), (🙅 Saltar, listing:skip:<id>), (😴 Posponer 24h, listing:snooze:<id>)]]`
**And** `RenderedAlert.parse_mode` is `"MarkdownV2"`

**Given** the renderer with `snapshot.evaluation.is_container == True`
**When** the renderer runs
**Then** two indented rows are inserted between Row 1 and Row 3:
  - `  ↪︎ Wrapper: <wrapper_text>`
  - `  ↪︎ Extracted: <extracted_text>`

**Given** the renderer
**When** any user-supplied content contains MarkdownV2 reserved characters
**Then** the rendered output is fully escaped (no markdown injection possible)

**Given** snapshot tests via `syrupy` in `tests/unit/test_alert_renderer.py`
**When** I run the tests against 4 fixtures (direct alert, container alert, low-confidence alert, missing-photo alert)
**Then** each render matches its golden snapshot exactly
**And** FR22 (format locked for v1) is mechanically enforced — any drift breaks the build

### Story 3.12: Implement Telegram bot adapter with retry + chat-ID allowlist

As ifuensan,
I want a `TelegramSurface` implementation in `src/salvager/adapters/telegram_bot/` using `python-telegram-bot` that sends `RenderedAlert` instances, retries failed sends with exponential backoff (default 3 attempts over ~1 min), silently drops inbound messages from chat IDs other than `TELEGRAM_CHAT_ID`,
So that FR18 dispatch / NFR-I6 retry / AR20 chat-ID allowlist are satisfied.

**Acceptance Criteria:**

**Given** `src/salvager/adapters/telegram_bot/surface.py`
**When** I import `TelegramBotSurface`
**Then** the class implements `TelegramSurface.send(rendered)` and `.edit_keyboard(message_id, keyboard)` and `.listen_callbacks(handler)`
**And** the constructor accepts `bot_token: SecretStr` and `recipient_chat_id: int` from `EnvSettings`
**And** the adapter is the only package allowed to import `telegram.*`

**Given** the surface
**When** `send(rendered)` is called for a Phase 1 alert with photo
**Then** the bot calls `sendPhoto` with the photo URL, caption text, parse_mode MarkdownV2, and inline keyboard
**And** returns the Telegram message_id
**And** the operation logs `telegram_alert_sent` with `latency_ms`

**Given** the surface
**When** Telegram returns HTTP 5xx or network error
**Then** the surface retries with exponential backoff: attempts 1, 2, 3 spaced ~5s/15s/40s by default
**And** if all retries fail, the surface logs `telegram_send_failed` with `error_class` and raises `TelegramDeliveryFailed`
**And** the caller (poll loop) continues — does NOT block polling per NFR-I6

**Given** the surface
**When** Telegram returns HTTP 4xx (invalid token, chat not found)
**Then** the surface does NOT retry; raises `TelegramConfigError` immediately and logs `telegram_config_error`

**Given** the surface listening for callbacks
**When** the bot receives an inbound message from a chat ID other than `TELEGRAM_CHAT_ID`
**Then** the message is silently dropped (no response, no log spam — just `logger.debug("telegram_inbound_unknown_chat", extra={...})`)

**Given** the surface listening for callbacks
**When** the bot receives a callback from the configured chat ID
**Then** the callback is parsed into a `CallbackEvent` with `verb`, `id` extracted from `callback_data`, plus message_id and timestamp
**And** the handler passed to `listen_callbacks` is invoked

### Story 3.13: Implement Phase 1 callback handler with acknowledgment-row keyboard edit

As ifuensan tapping a Phase 1 button,
I want the Telegram callback handler in `src/salvager/orchestration/callback_handler.py` to process `View`/`Skip`/`Snooze` callbacks, record the audit entry, mutate state where applicable (Snooze writes to `wishlist_runtime_state.snooze_until`), and replace the inline keyboard via `editMessageReplyMarkup` with the locked acknowledgment row (`✓ visto` / `✓ saltado` / `✓ pospuesto 24h`),
So that FR19 / FR20 / UX-DR12 are satisfied with end-to-end Phase 1 tap → state → visible ack in ≤ 1 second.

**Acceptance Criteria:**

**Given** a `CallbackEvent` with `verb="view"`
**When** the handler processes it
**Then** the handler records a `CallbackAudit` row in `callbacks` table (timestamp + verb + alert_id)
**And** edits the message keyboard to a single non-tappable button `[✓ visto]`
**And** the View action does NOT require a separate deeplink response — Telegram's button URL or callback handling opens the listing in-app

**Given** a `CallbackEvent` with `verb="skip"`
**When** the handler processes it
**Then** the audit row is written
**And** the keyboard becomes `[✓ saltado]`
**And** no state mutation occurs (Skip means "I don't want this one"; the entry continues being watched)

**Given** a `CallbackEvent` with `verb="snooze"`
**When** the handler processes it
**Then** the audit row is written
**And** the keyboard becomes `[✓ pospuesto 24h]`
**And** `wishlist_runtime_state.snooze_until` for the matching entry_key is set to `now + config.yaml > snooze.default_hours` (default 24)
**And** the next poll cycle's poll_loop filter (Story 3.14) suppresses alerts for that entry_key until `snooze_until`

**Given** a Phase 1 alert with all three buttons
**When** the operator taps `Posponer 24h`
**Then** the entry is snoozed for 24h
**And** any unalerted matches for that entry during the snooze window are NOT delivered (but ARE recorded in `seen_listings` so they don't re-fire later)
**And** the operational event `entry_snoozed` is logged

**Given** a `CallbackEvent` with an unknown verb (e.g., a future Phase 2 callback received in v0.x)
**When** the handler processes it
**Then** the handler logs `callback_unknown_verb` at `warn` level and ignores it
**And** the keyboard is NOT edited (so the user can retry on a real handler)

### Story 3.14: Implement poll loop orchestrator (synchronous pipeline)

As ifuensan,
I want `src/salvager/orchestration/poll_loop.py` to compose `PageFetcher → dedup_filter → snooze_filter → ListingEvaluator → record_seen → TelegramSurface.send` as a synchronous pipeline within the async runtime (using Hermes subagents up to 8 concurrent for the LLM eval step),
So that AR15 / AR16 are satisfied and FR6–FR22 (the daily Phase 1 case) is delivered end-to-end.

**Acceptance Criteria:**

**Given** `orchestration/poll_loop.py`
**When** I import `run_poll_cycle(marketplace, fetcher, store, evaluator, telegram, wishlist)`
**Then** the function executes the synchronous pipeline:
  1. For each wishlist entry, build a `SearchQuery` and call `fetcher.search(query)`
  2. For each returned `Listing`, filter out `is_seen` and `snooze_until > now`
  3. Concurrently (Hermes subagents, max 8) call `evaluator.evaluate(listing, entry)`
  4. For listings where `evaluation.confidence >= entry.confidence_threshold`, build `AlertSnapshot` and call `telegram.send(rendered)`
  5. For each sent alert, call `store.record_alert_snapshot(snapshot)` AND `store.record_seen(listing, entry_key)` (in a single transaction)
  6. For listings dropped below threshold, call `store.record_seen(listing, entry_key)` AND log `listing_dropped_below_threshold` (still seen — won't re-fire — but auditable via `--include-dropped`)

**Given** the poll loop registered with the scheduler
**When** the daemon starts via `salvager` (no subcommand)
**Then** the daemon initializes the scheduler, registers Wallapop + eBay.es poll jobs, and runs indefinitely
**And** at startup, it emits `daemon_started` operational event (Epic 4 renders the Telegram informational alert; Story 3 just logs)

**Given** the poll loop
**When** a single poll cycle for Wallapop completes with 23 listings searched / 4 new / 1 alert sent / 3 below-threshold
**Then** the structured log emits a `poll_cycle_complete` record with `marketplace`, `result_count`, `new_count`, `alerts_sent`, `dropped_count`, `latency_ms`

**Given** the poll loop
**When** an unhandled exception occurs in evaluation or dispatch
**Then** the exception is caught at the pipeline level — the listing is NOT marked as seen and the operational event `poll_cycle_error` fires
**And** the loop continues with subsequent listings (one bad listing doesn't kill the whole cycle)

**Given** an end-to-end test (`tests/e2e/test_poll_loop.py`) with all adapters mocked
**When** the test runs a full poll cycle against a fixture of 10 listings (3 matches, 7 non-matches, 1 container)
**Then** exactly 3 Telegram alerts dispatch (1 container, 2 direct) AND `seen_listings` contains 10 rows AND `alert_snapshots` contains 3 rows

### Story 3.15: Property tests + snapshot tests for Phase 1 contracts

As a future contributor,
I want a property test suite covering Phase 1 invariants (renderer format stability via syrupy, callback exit-code mapping, `--format json` parseability, `escape_markdown_v2` correctness, no-mutation-method enforcement on Store ABC),
So that UX-DR29 / UX-DR30 / NFR-S4 / FR22 are mechanically enforced and regressions break CI.

**Acceptance Criteria:**

**Given** `tests/unit/test_alert_renderer_snapshots.py` with `syrupy`
**When** the test renders Phase 1 alerts against 6 fixtures (direct, container, low-confidence, missing-photo, long-llm-take, special-chars-in-title)
**Then** each render matches its tracked golden snapshot
**And** a CI failure shows a precise text diff of the drift

**Given** `tests/unit/test_callback_exit_codes.py`
**When** the test enumerates every CLI subcommand registered with typer
**Then** every subcommand maps its exits to one of {0, 1, 2, 3, 4, 5} (FR48)
**And** any subcommand returning an out-of-set exit fails the test

**Given** `tests/unit/test_json_output_parseable.py`
**When** the test runs every `--format json`-supporting subcommand against fixtures
**Then** each output (stdout + stderr) round-trips through `json.loads` cleanly
**And** ISO 8601 timestamps parse via `datetime.fromisoformat`

**Given** `tests/unit/test_escape_markdown_v2.py` (property-based via `hypothesis`)
**When** the test generates 500 random strings containing all MarkdownV2 reserved chars
**Then** `escape_markdown_v2(s)` always produces a string where NO reserved char appears unescaped
**And** the escaped string round-trips through a reference MarkdownV2 parser without injection

**Given** `tests/unit/test_store_append_only.py`
**When** the test inspects `Store` ABC via `inspect`
**Then** no method matches `update_*` or `delete_*` on `alert_snapshots`/`tap_events`/`transactions`/`callbacks`
**And** the test fails CI if such methods are introduced (NFR-S4 mechanical enforcement)

**Given** `tests/unit/test_phase1_renderer_buttons.py`
**When** the test renders Phase 1 alerts
**Then** the inline_keyboard is always exactly `[[(👁 Ver, ...), (🙅 Saltar, ...), (😴 Posponer 24h, ...)]]` (locked vocabulary per UX-DR4)
**And** every `callback_data` matches the format `<surface>:<verb>:<id>` with ≤ 64 bytes (UX-DR5)

## Epic 4: Operator Observability & Phase 1 Recovery

**Goal.** The operator can diagnose any agent issue without reading raw logs. Operational alerts (`⚠️` high-priority, `ℹ️` informational) surface degradation in Telegram with a named cause and the exact CLI command to recover. `health` distinguishes "watching, no matches" from "stuck poller." `audit show` and `audit export` reveal Phase 1 events. `test-search` and `explain` enable dry-run inspection without state mutation. SIGTERM drains in-flight work in ≤ 30s. Recovery from Wallapop session expiry, daemon crash, and adapter break is named and ergonomic — the documented MTTR (NFR-P5/NFR-R6) is achievable from the alerts and CLI alone.

### Story 4.1: Implement operational alert renderer with EventName enum

As ifuensan getting a Telegram notification while away from my laptop,
I want `render_operational_alert(severity, event, ctx) -> RenderedAlert` in `src/salvager/domain/alert.py` covering every Phase 1 `EventName` variant with locked anatomy (`⚠️` warn: bold headline + numbered next-steps; `ℹ️` info: plain headline + optional CLI hint),
So that FR21 / UX-DR13 / UX-DR14 / UX-DR15 are satisfied and every operational alert is calm-instructional with cause + next CLI command in one read.

**Acceptance Criteria:**

**Given** `src/salvager/domain/alert.py`
**When** I import `EventName`
**Then** the enum lists every Phase 1 variant: `daemon_started`, `daemon_stopped`, `wallapop_session_expired`, `wallapop_session_renewed`, `wallapop_api_degraded`, `wallapop_both_paths_down`, `tinyfish_fallback_active`, `tinyfish_fallback_recovered`, `ebay_token_refresh_failed`, `ebay_quota_breach`, `llm_provider_rate_limited`, `entry_snoozed`, `poll_cycle_error`
**And** the enum is `Final` — adding a variant requires a PRD amendment per UX-DR13's "variant pool is finite" rule
**And** Phase 2 variants are declared as TODO comments referencing Epic 5

**Given** `render_operational_alert(severity="warn", event=EventName.wallapop_both_paths_down, ctx={...})`
**When** the renderer runs
**Then** `RenderedAlert.text` matches the locked `⚠️` anatomy:
  - Row 1: `⚠️ *<bold_headline>*`
  - Row 2+: cause line, state line, numbered next-steps block (each step is a copy-paste-ready CLI command)
**And** `RenderedAlert.inline_keyboard` is `None` (operational alerts never carry buttons per FR21)
**And** `RenderedAlert.photo_url` is `None`

**Given** `render_operational_alert(severity="info", event=EventName.wallapop_session_expired, ctx={...})`
**When** the renderer runs
**Then** `RenderedAlert.text` matches the locked `ℹ️` anatomy:
  - Row 1: `ℹ️ <plain_headline>` (no bold)
  - Row 2+: adapter/context line, optional fallback-active line, single CLI hint with "cuando puedas" softener
**And** the text contains no urgency cues
**And** all CLI commands in the text are wrapped in monospace backticks

**Given** the renderer with `event=EventName.wallapop_both_paths_down`
**When** the renderer runs
**Then** the message body includes specific values from `ctx` (consecutive failure count, last error class)
**And** the next-step list names: (1) `salvager audit show --last 5`, (2) inspection / patch action, (3) `docker-compose restart salvager` (or equivalent re-enable)

**Given** a snapshot test in `tests/unit/test_operational_alert_renderer.py`
**When** the test renders one fixture per `EventName` variant
**Then** each render matches its tracked syrupy snapshot
**And** the test fails if any new `EventName` variant lacks a corresponding fixture

**Given** a property test
**When** the test iterates over every `EventName` variant
**Then** `warn` variants always include at least one numbered next-step (`1. \``)
**And** `info` variants always include either zero or one CLI hint (not multiple)
**And** every emitted text starts with `⚠️ ` or `ℹ️ ` exactly (per the locked severity-prefix vocabulary)

### Story 4.2: Implement degradation_reporter (log + Telegram + health-state)

As any subsystem detecting a degraded condition,
I want a single `DegradationReporter` in `src/salvager/orchestration/degradation_reporter.py` exposing `report(severity, event, ctx)` that fans out to: (1) the structured logger, (2) the Telegram surface (operational alert via `render_operational_alert`), (3) the `health` state cache,
So that NFR-R3 ("no silent failure") is structurally impossible — three independent surfaces see every degradation, with NFR-O4 (diagnostic completeness) preserved on each.

**Acceptance Criteria:**

**Given** `src/salvager/orchestration/degradation_reporter.py`
**When** I import `DegradationReporter`
**Then** the class constructor accepts `logger`, `telegram_surface`, `health_state` dependencies (injected by the daemon entry point)
**And** `report(severity: Severity, event: EventName, ctx: dict) -> None` is the single public method

**Given** the reporter
**When** `report(severity="warn", event=EventName.wallapop_session_expired, ctx={"adapter": "wallapop_api"})` is called
**Then** the structured logger emits `wallapop_session_expired` with the full `ctx` (`level=warn`, all standard NFR-O1 fields)
**And** the Telegram surface dispatches the rendered operational alert (via `render_operational_alert`)
**And** the `health` state cache is updated (the adapter flagged as degraded with timestamp + event)

**Given** the reporter
**When** the Telegram dispatch raises `TelegramDeliveryFailed` (NFR-I6 exhausted retries)
**Then** the report continues — the log entry is still emitted; the `health` state still updates
**And** a secondary log entry `degradation_telegram_dispatch_failed` is emitted (so the operator sees the Telegram outage even if they can't receive it via Telegram)

**Given** a deduplication policy for repeated events within a short window
**When** the reporter receives the same `(event, ctx_fingerprint)` within `config.yaml > observability.degradation_dedup_window_seconds` (default 300)
**Then** only the first emission produces a Telegram alert; subsequent duplicates update the log + health state but don't re-Telegram
**And** the dedup window prevents alert storms during cascading failures

**Given** any subsystem that previously logged a degradation directly
**When** the codebase is searched
**Then** all degradation paths go through `DegradationReporter.report()` — no other codepath sends operational Telegram alerts
**And** a CI lint (or property test on the import graph) enforces this single-entry-point invariant

### Story 4.3: Wire Wallapop session-expiry through to operational alert + recovery

As ifuensan receiving a `ℹ️` alert that my Wallapop session expired,
I want the Wallapop two-path fallback orchestration (Story 3.6) to invoke `DegradationReporter.report()` with `EventName.wallapop_session_expired`, mark the API path as `unhealthy`, continue serving alerts via the TinyFish fallback, and emit `wallapop_session_renewed` when I re-run `salvager login wallapop`,
So that FR12 / NFR-R3 / NFR-R4 / UX-DR15 are end-to-end satisfied across Epic 3 detection + Epic 4 reporting + the operator's manual recovery.

**Acceptance Criteria:**

**Given** the daemon running with a valid Wallapop cookie
**When** the unofficial-API path returns 401
**Then** the Wallapop fallback helper (Story 3.6) catches `WallapopSessionExpired` and invokes `DegradationReporter.report(severity="info", event=EventName.wallapop_session_expired, ctx={"adapter": "wallapop_api", "fallback_path_status": "active"})`
**And** the operator receives the `ℹ️ Sesión Wallapop expirada` alert with the `cuando puedas` recovery hint (`salvager login wallapop`)
**And** the API path is marked `unhealthy` in `health` state
**And** subsequent polls use ONLY the TinyFish path until recovery

**Given** the daemon with the API path marked unhealthy
**When** the operator runs `salvager login wallapop` and the cookie is updated
**Then** the daemon detects the new cookie at the start of the next poll cycle (via cookie file mtime check or explicit re-load)
**And** the API path is re-attempted on the next Wallapop poll
**And** on success, `DegradationReporter.report(severity="info", event=EventName.wallapop_session_renewed, ctx={...})` fires
**And** the operator receives `ℹ️ Sesión Wallapop renovada`

**Given** the daemon with both Wallapop paths failing
**When** the second consecutive poll has both paths failing
**Then** `DegradationReporter.report(severity="warn", event=EventName.wallapop_both_paths_down, ctx={...})` fires
**And** the operator receives a `⚠️` operational alert with numbered next-steps (audit show, inspect parser, restart)
**And** eBay.es continues polling independently (NFR-R1 verified by an integration test)

**Given** an integration test (`tests/integration/test_wallapop_session_recovery.py`) with mocked adapters
**When** the test simulates: poll succeeds → 401 fires → fallback engages → operator re-auths → next poll succeeds
**Then** exactly two operational alerts are sent (`session_expired` then `session_renewed`)
**And** no listing alerts are lost during the fallback window (TinyFish-path alerts deliver as normal)

### Story 4.4: Implement `salvager health` CLI command

As ifuensan diagnosing a daemon problem,
I want `salvager health` to surface adapter status, scheduler status, last-poll timestamps per marketplace, last-alert timestamp, current Phase 2 state, AND distinguishably report "watching, no matches in 24h" vs "stuck poller,"
So that FR47 / NFR-O2 / UX-DR25 are satisfied — the operator never has to ask "is the bot working?".

**Acceptance Criteria:**

**Given** the daemon running with healthy adapters and no recent matches
**When** I run `salvager health`
**Then** the output uses `render_table` to display an adapter status table with columns `Adapter`, `Status` (`healthy` / `degraded` / `down`), `Last Activity` (ISO 8601 Z timestamp)
**And** a header block (using `render_prose` or a `rich.panel.Panel`) shows: daemon version, daemon uptime, PID
**And** a footer block names: `Recent matches: <N> in last 24h (watching)` (UX-DR25 disambiguation), `Last poll: <ISO timestamp> (<wallapop|ebay>)`, `Phase 2: <enabled count> entries enabled (<globally disabled? yes|no>; circuit breaker <closed|open N/M>)`

**Given** `salvager health --format json`
**When** the command runs
**Then** stdout emits a single JSON object: `{"version": ..., "uptime_seconds": ..., "pid": ..., "adapters": [{"name": ..., "status": ..., "last_activity": ...}, ...], "recent_match_count_24h": ..., "last_poll": {"wallapop": "<ts>", "ebay": "<ts>"}, "phase2": {"enabled_count": ..., "globally_disabled": ..., "circuit_breaker": {"state": ..., "consecutive_failures": ..., "threshold": ...}}}`
**And** ISO 8601 timestamps + snake_case fields per UX-DR20

**Given** the daemon with the Wallapop API path unhealthy (session expired) but TinyFish path healthy
**When** I run `salvager health`
**Then** the table shows two rows for Wallapop: `wallapop_api` as `degraded` and `wallapop_tinyfish` as `healthy`
**And** the operator can see at a glance which path is broken

**Given** the daemon down (no process)
**When** I run `salvager health`
**Then** the command does NOT require the daemon to be running — it reads from SQLite + filesystem state directly (AR14)
**And** the output shows `Daemon: not running` and reads `last_poll` from the most recent record in `_meta` or `seen_listings`
**And** the exit code is 0 (not an error condition — the daemon may be intentionally stopped)

**Given** a stuck poller (last_poll older than 2× expected cadence)
**When** I run `salvager health`
**Then** the row shows `Status: degraded`
**And** the footer line surfaces `Last poll: <timestamp> (5 hours ago, expected every 15 min)` for stale detection
**And** the exit code is 0; `--exit-on-degraded` flag (post-launch OQ) would change this

**Given** the test suite
**When** the test runs `salvager health` against a fixture daemon state
**Then** golden snapshot tests verify rendering at terminal widths 60, 80, 100, 120 (UX-DR31)

### Story 4.5: Implement `audit show` and `audit export` CLI commands

As ifuensan reviewing what the agent did,
I want `salvager audit show [--last N] [--id N] [--type EVENT] [--since ISO] [--include-dropped] [--format json]` and `salvager audit export [--format json] [--since ISO]`,
So that FR37 / NFR-O3 / UX-DR20 / UX-DR28 are satisfied and every Phase 1 event (alerts + callbacks + dropped listings + operational events) is queryable from the CLI.

**Acceptance Criteria:**

**Given** the audit log with 100+ Phase 1 records
**When** I run `salvager audit show`
**Then** the default behavior returns the 10 most recent records via `render_table` (columns: `ID`, `Type`, `Timestamp`, `Summary`)
**And** the table border is `MINIMAL`, no row separators, 80-col default

**Given** the audit log
**When** I run `salvager audit show --last 50`
**Then** the 50 most recent records are returned
**And** `--last 0` produces no output (matches the empty-state pattern from UX-DR's spec)

**Given** the audit log
**When** I run `salvager audit show --id 142`
**Then** the single record with `audit_id = 142` is returned with FULL detail (not just the summary): the full `alert_snapshot` JSON / `callback` record, plus rendered Telegram text (for alerts) and audit pointer
**And** if the ID doesn't exist, output is `error: audit id 142 not found` + `hint: salvager audit show --last 5` and exit code 1

**Given** the audit log
**When** I run `salvager audit show --type callback --since 2026-05-01`
**Then** only callback events at or after the given ISO timestamp are returned

**Given** dropped-listing log entries (listings below confidence threshold; recorded by Story 3.14)
**When** I run `salvager audit show --include-dropped --last 10`
**Then** the most recent 10 records INCLUDING dropped-below-threshold events are returned

**Given** `salvager audit show --format json`
**When** the command runs
**Then** stdout emits a flat JSON array (no envelope) of audit records
**And** each record is `json.loads`-parseable individually
**And** ISO 8601 timestamps with `Z` suffix per UX-DR20

**Given** `salvager audit export`
**When** the command runs
**Then** stdout emits JSONL (one JSON object per line), one record per audit row
**And** the format is suitable for `jq` filtering or downstream analysis
**And** `audit export --since 2026-04-01 > backup.jsonl` produces a partial export

**Given** the test suite
**When** the test inserts known Phase 1 records and runs `audit show --format json --last 3`
**Then** the JSON output matches a tracked golden file

### Story 4.6: Implement `salvager test-search` CLI command

As ifuensan tuning a new wishlist entry,
I want `salvager test-search <entry-id|query>` to perform a dry-run search against a marketplace without sending Telegram alerts, mutating SQLite state, or counting beyond actual rate-limit usage,
So that FR43 is satisfied — I can sanity-check what listings the agent would surface without polluting my audit log or chat.

**Acceptance Criteria:**

**Given** a wishlist entry `WD40EFPX`
**When** I run `salvager test-search WD40EFPX`
**Then** the command builds the search query for both Wallapop and eBay.es (same logic as Story 3.14)
**And** executes the searches
**And** renders results in a `render_table` showing columns `Marketplace`, `Listing ID`, `Title`, `Price`, `Match Probability` (a quick heuristic, not the full LLM eval)
**And** does NOT send any Telegram alert
**And** does NOT write to `seen_listings`, `alert_snapshots`, or any audit table

**Given** `salvager test-search "WD Red 4TB"` (arbitrary query, not a wishlist entry)
**When** the command runs
**Then** the query is passed verbatim to both marketplaces
**And** the output table includes a column noting "no LLM evaluation (dry-run heuristic only)"

**Given** the command
**When** `--marketplace wallapop` or `--marketplace ebay` is passed
**Then** only the specified marketplace is queried

**Given** the command
**When** `--evaluate` flag is passed
**Then** the LLM evaluator IS invoked for each result (uses cache where available; cache writes are allowed in this dry-run since the cache is read-only-effective for state purposes)
**And** the output includes full `confidence` + `one_line_take` columns

**Given** the command
**When** any rate-limit triggers (TinyFish / Gemini)
**Then** the command exits with `warn: rate limit reached during dry-run` and partial results are returned
**And** exit code is 0 (partial results are still useful)

**Given** the command
**When** `--format json` is passed
**Then** stdout emits a JSON array of `Listing` objects with the heuristic match info per UX-DR20

### Story 4.7: Implement `salvager explain <url>` CLI command

As ifuensan investigating why an alert fired (or didn't),
I want `salvager explain <listing-url>` to fetch the listing, run the full LLM evaluation against every plausible wishlist entry, and print the prompt + response + confidence + would-be-alert-body,
So that FR44 is satisfied — I can debug LLM behavior without enabling debug logging or re-running the daemon.

**Acceptance Criteria:**

**Given** a Wallapop listing URL
**When** I run `salvager explain https://es.wallapop.com/item/wd-red-4tb-...`
**Then** the command:
  1. Fetches the listing via the marketplace adapter (uses cache where present)
  2. Identifies plausible matching wishlist entries (keyword overlap)
  3. For each plausible entry, runs `ListingEvaluator.evaluate(listing, entry)`
  4. Prints a `rich.panel.Panel` per evaluation showing: matched entry display name, full prompt text, raw LLM response JSON, parsed `ListingEvaluation`, would-be-alert text (if the eval would have fired), reason for skip (if it wouldn't)

**Given** the command
**When** the URL is from eBay.es
**Then** the eBay adapter is used; otherwise identical flow

**Given** the command
**When** `--entry WD40EFPX` is passed
**Then** only the specified entry is evaluated against the listing (skips the keyword-overlap heuristic)

**Given** the command
**When** the URL is malformed or the listing 404s
**Then** the command exits with `error: failed to fetch listing: <reason>` + `hint: check the URL` and exit code 3

**Given** the command
**When** `--format json` is passed
**Then** stdout emits a JSON object: `{"listing": {...}, "evaluations": [{"entry_key": [...], "prompt": "...", "response": {...}, "would_alert": true|false, "reason_for_skip": "..."}]}`
**And** the prompt + response are included as strings (the field names are stable per FR48 / UX-DR20)

**Given** the command
**When** the listing's evaluation was cached
**Then** the output notes `(from cache, age: X seconds)` and the cached prompt + response are returned
**And** the command does NOT call Gemini

### Story 4.8: Implement SIGTERM graceful drain in daemon

As an operator running `docker-compose down`,
I want the daemon to handle SIGTERM by draining in-flight LLM evaluations, flushing the audit log writes, completing pending Telegram alerts, and exiting cleanly within 30 seconds,
So that FR50 is satisfied and no audit-log gaps or dropped alerts occur on routine restarts.

**Acceptance Criteria:**

**Given** the daemon entry point in `src/salvager/cli/daemon_cmd.py`
**When** the daemon is running and receives SIGTERM
**Then** the signal handler sets a global "shutdown initiated" flag
**And** the scheduler stops accepting new polls
**And** in-flight `evaluate()` calls are awaited (up to 8 concurrent per AR15)
**And** pending Telegram sends are awaited (up to NFR-I6 retry budget)
**And** any partial audit writes are committed in a final flush
**And** the daemon exits cleanly with exit code 0

**Given** the daemon with the shutdown flag set
**When** the drain takes longer than `stop_grace_period: 30s`
**Then** docker-compose sends SIGKILL
**And** because the audit writes use SQLite WAL mode with per-write commits, no corruption occurs (NFR-R5; verified by Story 4.9)

**Given** the daemon
**When** SIGTERM arrives mid-poll
**Then** the in-flight listings finish evaluation
**And** any listings not yet started are skipped (will be re-fetched on next start)
**And** the operational event `daemon_stopped` fires with `ctx={"reason": "sigterm", "drain_seconds": <N>}`

**Given** an integration test (`tests/integration/test_sigterm_drain.py`)
**When** the test starts a daemon, dispatches 5 mock listings into the pipeline, sends SIGTERM mid-evaluation, and waits for clean exit
**Then** the exit happens in ≤ 30 seconds
**And** all 5 listings appear in either `seen_listings` or were not yet started (no half-evaluated entries)
**And** the final `daemon_stopped` log entry appears

### Story 4.9: Verify crash/restart audit consistency

As ifuensan,
I want a property test that verifies the audit log and seen-listings dedup remain consistent across daemon crash/restart cycles, with no duplicate alerts and no missing audit rows,
So that NFR-R5 is mechanically asserted and the docker-compose `restart: on-failure` recovery model is trustworthy.

**Acceptance Criteria:**

**Given** an end-to-end test (`tests/e2e/test_crash_restart_consistency.py`)
**When** the test runs: start daemon → process 20 listings (15 matches, 8 alerts dispatched) → kill -9 (SIGKILL, simulates crash) → restart daemon → process next 20 listings (includes 5 overlap with first batch)
**Then** the 5 overlap listings produce ZERO new alerts (dedup intact)
**And** the audit log contains exactly 8 alert records (no duplicates from the partial first run, no missing from the restart)
**And** the test passes with `pytest --runslow` (e2e tests take longer, opt-in)

**Given** the test
**When** the crash happens MID-WRITE on the audit log (simulated by killing the process during a SQLite transaction)
**Then** SQLite's WAL log ensures either the full transaction commits or rolls back atomically
**And** the post-restart audit log has no partial rows

**Given** the test
**When** the crash happens after a Telegram dispatch succeeds but before the audit row is committed
**Then** on restart, the daemon may re-evaluate that listing and dispatch a second Telegram alert (acceptable trade-off: better to over-alert than under-audit)
**And** the test documents this race condition explicitly with a comment referencing the trade-off

**Given** the test
**When** WAL mode is verified at startup via `PRAGMA journal_mode`
**Then** the test asserts the response is `wal`
**And** if it isn't, the test fails (regression guard against accidental WAL disable)

## Epic 5: Phase 2 — Autonomous Purchase with Safety Stack

**Goal.** After the 4–8 week Phase 1 stabilization gate (per PRD), ifuensan opts entries into Phase 2 (`phase2 enable WD40EFPX`); receives Phase 2 alerts with `[✅ Comprar] [❌ Saltar] [👁 Ver]`; taps Comprar; sees the keyboard edit to `🟡 Comprando…`; receives a factual receipt with screenshot within 60 seconds. The safety stack (cross-source price reconciliation + receipt-vs-alert reconciliation + daily synthetic smoke test + per-purchase circuit breaker) catches malformed data before any transaction. Any failure auto-disables Phase 2 globally with a `⚠️` operational alert naming the cause and the `phase2 enable` command to recover. v1.0 is releasable when this epic completes; the release-gating Telegram client variance test and accessibility audit run as final stories before the v1.0 tag.

### Story 5.1: Schema extension — Phase 2 SQLite tables + append-only audit writer

As a developer wiring the Phase 2 audit log,
I want migration `0002_phase2_schema.sql` to add the Phase 2 tables (`tap_events`, `transactions`, `phase2_smoke_tests`, `phase2_state`), and an append-only `audit_writer.py` in `src/salvager/adapters/sqlite_store/` exposing only `record_*` methods plus a property test asserting no mutation methods exist,
So that AR8 / AR9 (append-only at application layer) / AR13 (Phase 2 lockout persistence) / NFR-S4 are satisfied — corrections to past audit rows are impossible by API.

**Acceptance Criteria:**

**Given** `src/salvager/migrations/0002_phase2_schema.sql`
**When** the migration runs against a Phase 1 database
**Then** the following tables are created:
  - `tap_events` (audit_id PK auto-increment + alert_id FK + verb + raw_payload JSON + tapped_at + ip_or_chat_id; indexed on alert_id + tapped_at)
  - `transactions` (audit_id PK + alert_id FK + price_paid_eur DECIMAL + payment_method + receipt_id + screenshot_path + total_seconds INT + committed_at; indexed on alert_id + committed_at)
  - `phase2_smoke_tests` (audit_id PK + run_at + result `pass`/`fail` + parsed_price + independent_price + delta_eur + delta_pct; indexed on run_at)
  - `phase2_state` (single-row table: `globally_disabled` BOOL + `disabled_at` TIMESTAMP + `disabled_reason` + `consecutive_failures` INT + `last_smoke_result` + `last_smoke_at`)
**And** the migration is idempotent (running twice has no effect after the first)
**And** `_meta.schema_version` advances to 2

**Given** `src/salvager/adapters/sqlite_store/audit_writer.py`
**When** I import `Phase2AuditWriter`
**Then** the class implements only `record_tap_event(tap)`, `record_transaction(txn)`, `record_smoke_test(result)`, `set_global_disable(reason)`, `clear_global_disable(entry_key)`, `increment_failure_counter()`, `reset_failure_counter()`
**And** NO method named `update_*` or `delete_*` exists on this class (verified by a property test that introspects the class via `inspect`)
**And** all writes use INSERT statements — never UPDATE/DELETE on `tap_events` / `transactions` / `phase2_smoke_tests` (verified by static analysis of the SQL strings)

**Given** an `update_*` or `delete_*` method added to `Phase2AuditWriter` in a PR
**When** CI runs
**Then** the property test `tests/unit/test_audit_writer_append_only.py` fails with a precise error naming the offending method (NFR-S4 mechanical enforcement)

**Given** the Phase 2 lockout flow
**When** `set_global_disable(reason)` is called with `reason="reconciliation_tripped"`
**Then** the `phase2_state` row updates `globally_disabled=true`, `disabled_at=<now>`, `disabled_reason=reconciliation_tripped`
**And** `clear_global_disable(entry_key)` is the ONLY method that flips `globally_disabled=false` AND requires an explicit operator-action context (per FR35; only `phase2 enable <entry>` calls this)

### Story 5.2: Implement Phase 2 listing alert renderer with pre-flight gating

As ifuensan with Phase 2 enabled for one entry,
I want `render_phase2_listing_alert(snapshot)` in `domain/alert.py` to produce the locked Phase 2 anatomy (`🟢` prefix + `Phase 2 max: <€>` confidence-row suffix + `[✅ Comprar] [❌ Saltar] [👁 Ver]` keyboard), AND the orchestrator to gate this renderer on a pre-flight check (smoke test passed in 24h + circuit breaker closed + global Phase 2 not locked + entry has `phase2.enabled=true`),
So that FR23 / FR24 / UX-DR7 are satisfied AND any pre-flight failure silently downgrades to the Phase 1 renderer (operator never sees a "broken Phase 2 alert").

**Acceptance Criteria:**

**Given** `src/salvager/domain/alert.py`
**When** I import `render_phase2_listing_alert(snapshot, phase2_max_price_eur)`
**Then** the rendered text exactly matches the Phase 1 baseline anatomy (Story 3.11) with three substitutions:
  - Severity prefix `📦` → `🟢`
  - Confidence row appended with ` · Phase 2 max: <phase2_max_price_eur formatted ES>`
  - Inline keyboard: `[[(✅ Comprar, listing:buy:<id>), (❌ Saltar, listing:skip:<id>), (👁 Ver, listing:view:<id>)]]`
**And** the container-aware split (Direction E from Story 3.11) ALSO applies when `snapshot.evaluation.is_container == True`

**Given** the poll loop preparing to dispatch an alert for a listing whose entry has `phase2.enabled=true`
**When** the pre-flight gate checks (in `orchestration/phase2_preflight.py`):
  1. `phase2_state.globally_disabled == false`
  2. `phase2_state.consecutive_failures < config.yaml > phase2.circuit_breaker_threshold` (default 3)
  3. `phase2_state.last_smoke_result == "pass"` AND `phase2_state.last_smoke_at` ≥ 24h ago
  4. The entry's `phase2.max_price_eur >= listing.price_eur` (per-entry hard ceiling per FR26)
  5. The evaluation's `confidence >= entry.confidence_threshold` (per FR27)
**Then** the pre-flight returns `Phase2EligibilityResult(eligible=True)` and the Phase 2 renderer is invoked
**And** the result reason for ANY ineligibility is logged as `phase2_alert_downgraded` with `reason` field

**Given** any pre-flight check failing
**When** the renderer is selected
**Then** the Phase 1 renderer (`render_phase1_listing_alert`) is called instead — silently (UX-DR7 "downgrade not loud failure")
**And** the operator never sees a `🟢` alert that lacks a Buy button or has wrong gating

**Given** the renderer
**When** snapshot tests run against fixtures (direct Phase 2, container Phase 2, missing-photo Phase 2)
**Then** each render matches its golden snapshot
**And** the Phase 2 max line is formatted in Spanish (`Phase 2 max: 60,00 €`)

### Story 5.3: Implement TinyFish browser adapter for Wallapop Pay + eBay.es checkout

As the buy orchestrator,
I want a `BrowserSession` adapter in `src/salvager/adapters/tinyfish_browser/` with two flow implementations (`wallapop_pay.py` + `ebay_checkout.py`) that drive the marketplace's own UI to complete a purchase via Wallapop Pay or eBay.es checkout, scoped exclusively to the protected payment rails,
So that FR25 / FR30 / NFR-S5 are satisfied — the agent has no codepath to use Bizum or transferencia (verified structurally by Story 5.14's CI lint).

**Acceptance Criteria:**

**Given** `src/salvager/interfaces/browser_session.py`
**When** I import `BrowserSession`
**Then** the ABC declares `async def execute_buy(listing: Listing, max_price_eur: Decimal) -> BuyResult`
**And** `BuyResult` is a tagged union: `BuySuccess(price_paid_eur, payment_method, receipt_id, screenshot_url, total_seconds)` OR `BuyFailure(reason: BuyFailureReason, ctx: dict)`

**Given** `BuyFailureReason` enum in `domain/errors.py`
**When** I read the enum
**Then** it lists: `reconciliation_tripped`, `ui_check_failed`, `circuit_open`, `missing_element`, `marketplace_error`, `timeout`, `screenshot_missing`, `payment_rail_unavailable`
**And** the enum is `Final`

**Given** `src/salvager/adapters/tinyfish_browser/wallapop_pay.py`
**When** I import `WallapopPayFlow`
**Then** the class implements `BrowserSession.execute_buy()` for Wallapop listings
**And** the flow uses TinyFish Browser via Hermes MCP (NFR-I2)
**And** the implementation:
  1. Navigates to the listing URL using the operator's existing Wallapop session
  2. Asserts expected UI elements are present (Buy button, payment method = Wallapop Pay, price field)
  3. If ANY expected element is missing, returns `BuyFailure(reason=missing_element, ctx={"missing": [...]})` — fail-closed per FR28
  4. Clicks the Wallapop Pay buy button
  5. Awaits the confirmation page
  6. Captures a screenshot of the confirmation page
  7. Extracts the receipt ID from the confirmation page
  8. If the screenshot capture fails, returns `BuyFailure(reason=screenshot_missing, ctx={...})` even though the buy may have succeeded (per UX-DR9)
  9. Returns `BuySuccess(...)` with the captured data

**Given** `src/salvager/adapters/tinyfish_browser/ebay_checkout.py`
**When** I import `EbayCheckoutFlow`
**Then** the class follows the same shape with eBay.es checkout (not Bizum, not bank transfer — verified by inspecting the navigated URLs and element selectors in the flow code)

**Given** the BrowserSession adapter
**When** I attempt to add a `bizum_pay.py` or `transferencia_pay.py` flow
**Then** Story 5.14's CI lint deny-list flags the import / class name and fails the build

**Given** the adapter
**When** the marketplace's UI changes (e.g., button selector renamed)
**Then** the flow logs `ui_check_failed` with the specific missing element
**And** returns `BuyFailure(reason=missing_element, ...)`
**And** the operator's audit log + Telegram alert show enough context to identify the broken selector

### Story 5.4: Implement cross-source price reconciliation + receipt-vs-alert reconciliation

As ifuensan,
I want a `Reconciler` in `src/salvager/orchestration/reconciler.py` exposing `reconcile_cross_source(listing)` (re-fetches the listing via the alternate marketplace path and compares prices against a configurable tolerance) AND `reconcile_receipt_vs_alert(alert_snapshot, transaction)` (compares alert-time price vs receipt price), with domain math in pure `domain/reconciliation.py`,
So that FR31 / FR32 are satisfied — the Q9 silent-failure scenario (malformed HTML price) is caught BEFORE checkout, and any post-checkout price discrepancy is caught immediately.

**Acceptance Criteria:**

**Given** `src/salvager/domain/reconciliation.py`
**When** I import `ReconciliationResult` and `compute_tolerance(price_a, price_b, tolerance_eur, tolerance_pct)`
**Then** the function returns a pure `ReconciliationResult(passed: bool, delta_eur: Decimal, delta_pct: Decimal, tolerance_used: Literal["eur", "pct"])`
**And** the tolerance used is `max(tolerance_eur, price_a * tolerance_pct / 100)` per PRD FR31 ("€ floor + percentage, whichever is greater")
**And** the module has zero IO imports (pure decimal math)

**Given** `src/salvager/orchestration/reconciler.py`
**When** I call `await reconciler.reconcile_cross_source(listing)` for a Wallapop listing where the API price is 53.00 €
**Then** the reconciler invokes the TinyFish fallback path to re-fetch the same listing (or vice-versa if the listing was sourced from TinyFish)
**And** parses the alternate-source price
**And** calls `compute_tolerance()` with both prices and the configured tolerance from `config.yaml > phase2.reconciliation_tolerance_eur` (default 1.00) and `reconciliation_tolerance_pct` (default 5)
**And** returns `ReconciliationResult(passed=True, ...)` if within tolerance; otherwise `passed=False`

**Given** the Q9 scenario: API returns 53.00 €, HTML returns 0.53 €
**When** the reconciler runs
**Then** the result has `passed=False`, `delta_eur=52.47`, `delta_pct=99.0` (or NaN clamped)
**And** the buy orchestrator (Story 5.7) aborts the purchase with `BuyFailure(reason=reconciliation_tripped, ctx={"api_price": 53.00, "html_price": 0.53, "tolerance_used": "eur", "tolerance_value": 1.00})`

**Given** `reconciler.reconcile_receipt_vs_alert(alert_snapshot, transaction)`
**When** the alert recorded a price of 48.00 € and the transaction's `price_paid_eur` is 56.00 €
**Then** the function returns `ReconciliationResult(passed=False, ...)`
**And** the caller (buy orchestrator) emits a `⚠️ Receipt mismatch` operational alert AND auto-disables Phase 2 globally (per FR32)
**And** the transaction record is preserved (no rollback — the purchase already happened) but flagged in the audit log

**Given** a unit test in `tests/unit/test_reconciliation.py`
**When** the test runs property-based cases (`hypothesis`)
**Then** `compute_tolerance` is commutative and respects the "whichever is greater" rule
**And** tolerance edge cases (0 €, NaN, negative) are explicitly tested and rejected

### Story 5.5: Implement per-purchase circuit breaker + Phase 2 auto-disable lockout

As ifuensan,
I want a circuit breaker in `src/salvager/orchestration/circuit_breaker.py` (with pure domain math in `domain/circuit.py`) that tracks consecutive Phase 2 failures, opens after N failures (default 3, configurable), and writes the global lockout row to `phase2_state` table that survives daemon restarts,
So that FR34 / FR35 / AR13 / NFR-R4 are satisfied — Phase 2 auto-disable is durable and only an explicit operator action can re-enable.

**Acceptance Criteria:**

**Given** `src/salvager/domain/circuit.py`
**When** I import `CircuitState` and `compute_next_state(current_state, outcome, threshold)`
**Then** the pure function transitions: `(closed, success) → closed (counter reset)`, `(closed, failure) → closed (counter +1) OR open (when counter+1 >= threshold)`, `(open, *) → open (until manual reset)`
**And** the module has zero IO imports

**Given** `src/salvager/orchestration/circuit_breaker.py`
**When** I import `CircuitBreaker`
**Then** the class wraps the pure domain function with persistence: it reads `phase2_state.consecutive_failures` at startup, increments/resets on each Phase 2 outcome, persists state changes immediately via `Phase2AuditWriter.increment_failure_counter()` / `reset_failure_counter()`
**And** when the counter reaches the threshold, calls `Phase2AuditWriter.set_global_disable(reason="circuit_breaker_open")`
**And** fires the operational event `EventName.circuit_open` via `DegradationReporter`

**Given** the breaker
**When** a Phase 2 purchase succeeds
**Then** `consecutive_failures` resets to 0
**And** if the circuit was previously open, it stays open until `clear_global_disable()` is called by `phase2 enable <entry>` (NFR-R4 — no auto-recovery)

**Given** the breaker
**When** the daemon restarts after the circuit was open
**Then** the breaker reads `phase2_state.globally_disabled=true` at startup
**And** all Phase 2 alerts downgrade to Phase 1 silently (per Story 5.2 pre-flight) until the operator runs `phase2 enable`

**Given** a unit test in `tests/unit/test_circuit_breaker.py`
**When** the test exercises 100 random sequences of success/failure outcomes via `hypothesis`
**Then** the circuit state matches the pure-function expectation
**And** the persistence layer never drifts from the in-memory state

### Story 5.6: Implement daily synthetic smoke test + regression fixture set

As ifuensan,
I want `src/salvager/orchestration/smoke_test.py` to run daily (default 06:00 UTC) against a known-price fixture, compare the parsed price to an independent reference value, and auto-disable Phase 2 globally if drift exceeds tolerance, with a growing fixture set in `tests/fixtures/price_parsers/`,
So that FR33 / NFR-M3 are satisfied — the Q9 scenario (marketplace HTML parser drift) is caught BEFORE a real buy attempt.

**Acceptance Criteria:**

**Given** `src/salvager/orchestration/smoke_test.py`
**When** I import `run_smoke_test()`
**Then** the function:
  1. Loads the smoke-test fixtures from `tests/fixtures/price_parsers/active/` (each fixture: a recorded marketplace response + an `expected_price.json` with the independently-verified price)
  2. For each fixture, runs the marketplace adapter's parser against the recorded response
  3. Compares the parsed price to the expected price via `compute_tolerance()` (reusing Story 5.4 math)
  4. Records each result via `Phase2AuditWriter.record_smoke_test(result)`
  5. If ANY fixture fails, calls `Phase2AuditWriter.set_global_disable(reason="smoke_test_failed")` and fires `EventName.smoke_test_failed` via DegradationReporter
  6. If ALL fixtures pass AND the previous run failed, fires `EventName.smoke_test_recovered`

**Given** the smoke test scheduled with Hermes
**When** the daemon starts
**Then** the smoke test is registered as a daily job at `config.yaml > phase2.smoke_test_hour_utc` (default 6)
**And** the operational event `smoke_test_started` logs at each scheduled run

**Given** `tests/fixtures/price_parsers/active/`
**When** I list the directory
**Then** it contains at least 4 fixtures at v1.0: `wallapop_api_typical.json`, `wallapop_html_typical.html`, `ebay_api_typical.json`, plus the canonical Q9 regression fixture (`wallapop_html_comma_vs_dot.html`)
**And** each fixture has a sibling `expected_price.json` with the verified price

**Given** the smoke test fixture set
**When** the operator encounters a real-world parser surprise (NFR-M3)
**Then** the documented workflow is: capture the response + verify the price independently → add `tests/fixtures/price_parsers/active/<descriptive-name>.<ext>` + `expected_price.json` → next CI run includes the fixture in smoke + regression suites

**Given** the manual trigger `salvager phase2 smoke-test` (Story 5.13)
**When** I run it on demand
**Then** `run_smoke_test()` executes and prints a table of per-fixture results (PASS/FAIL/delta) via `render_table`
**And** the exit code is 0 if all pass, 5 (Phase 2 guardrail) if any fail

### Story 5.7: Implement buy orchestrator composing pre-flight + reconcile + UI check + buy + screenshot + audit-write

As ifuensan tapping Comprar,
I want `src/salvager/orchestration/buy_orchestrator.py` to compose `Phase2Preflight + Reconciler + BrowserSession + Phase2AuditWriter + TelegramSurface + CircuitBreaker` into the single end-to-end flow: pre-flight → cross-source reconciliation → UI check (delegated to BrowserSession) → execute_buy → capture screenshot → audit-write → receipt-vs-alert reconciliation → final outcome dispatch,
So that FR24 / FR25 / FR26 / FR27 / FR28 / FR29 / FR30 are satisfied end-to-end and the buy critical path has ≥ 90% line coverage (NFR-M2).

**Acceptance Criteria:**

**Given** `src/salvager/orchestration/buy_orchestrator.py`
**When** I import `BuyOrchestrator`
**Then** the class constructor accepts `preflight`, `reconciler`, `browser`, `circuit_breaker`, `audit_writer`, `telegram_surface`, `store` dependencies
**And** the single public method `async def execute_buy_from_callback(callback_event: CallbackEvent) -> BuyOutcome` orchestrates the full flow

**Given** a `CallbackEvent(verb="buy", id=<alert_uuid>)`
**When** `execute_buy_from_callback()` runs
**Then** the orchestrator:
  1. Loads the `AlertSnapshot` for the given alert UUID from `Store.get_alert_snapshot()`
  2. Re-runs `Phase2Preflight` (state may have changed since the alert; for example, the circuit may have opened)
  3. If pre-flight fails NOW, returns `BuyOutcome.aborted(reason=...)` without touching the marketplace
  4. Runs `reconciler.reconcile_cross_source(listing)` — if `passed=False`, returns `BuyOutcome.failure(reason=reconciliation_tripped, ctx=...)` and updates the circuit breaker
  5. Calls `browser.execute_buy(listing, max_price_eur=entry.phase2.max_price_eur)` (browser handles UI check internally per Story 5.3 step 2)
  6. On `BuySuccess`: writes `tap_events` row (the Buy tap) AND `transactions` row via `audit_writer.record_transaction(...)`
  7. Runs `reconciler.reconcile_receipt_vs_alert(alert_snapshot, transaction)` — if mismatch, fires `⚠️` operational alert AND calls `audit_writer.set_global_disable(reason="receipt_mismatch")`
  8. Calls `circuit_breaker.record_success()` (or `.record_failure()` on any failure path)
  9. Dispatches the success / failure / aborted Telegram message via `telegram_surface.send()` using the appropriate renderer (Stories 5.8, 5.9)
**And** the full critical path is wrapped in a single `try/finally` so partial-failure scenarios still write whatever state was reached and emit an operational alert

**Given** the orchestrator
**When** any step raises an unexpected exception
**Then** the orchestrator emits `EventName.buy_orchestrator_error` (newly added Phase 2 variant in Story 5.11), `BuyOutcome.failure(reason=marketplace_error)`, and the circuit increments
**And** the audit log is left in a consistent state (no half-written transactions)

**Given** an integration test (`tests/integration/test_buy_orchestrator.py`) with mocked adapters at every layer
**When** the test simulates 8 scenarios (happy path, reconciliation tripped, UI check failed, marketplace error, timeout, screenshot missing, receipt mismatch, circuit already open at pre-flight)
**Then** each scenario produces the expected `BuyOutcome` value AND the expected audit-log rows AND the expected Telegram dispatch

**Given** the orchestrator's critical-path modules (`buy_orchestrator.py`, `reconciler.py`, `circuit_breaker.py`, `smoke_test.py`, `audit_writer.py`)
**When** CI runs `pytest --cov` against the Phase 2 test suite
**Then** line coverage on these modules is ≥ 90% (NFR-M2 gate)
**And** a CI threshold check fails the build below 90%

### Story 5.8: Implement Phase 2 buy success renderer with mandatory-screenshot guard

As ifuensan receiving a successful Phase 2 receipt,
I want `render_phase2_buy_success(transaction)` in `domain/alert.py` to produce the locked receipt anatomy (screenshot photo + factual receipt fields + audit pointer) AND a mandatory-screenshot guard that diverts to `render_phase2_buy_failure(reason=screenshot_missing)` if no screenshot is present,
So that FR36 / UX-DR9 are satisfied — the receipt is sacred; a transaction without a screenshot is a UX failure even if the buy succeeded.

**Acceptance Criteria:**

**Given** `src/salvager/domain/alert.py`
**When** I import `render_phase2_buy_success(transaction)`
**Then** the rendered text matches the locked anatomy:
  - Photo: the captured receipt screenshot (uploaded to Telegram via the bot adapter)
  - Row 1: `✅ *Comprado* · <price_paid_eur ES> · <payment_method>`
  - Row 2: `Receipt: \`<receipt_id>\``
  - Row 3: `Listing: <entry_display_name>`
  - Row 4: `Tiempo total: <total_seconds> s`
  - Row 5: `` `salvager audit show --id <audit_id>` for full event trail. ``
**And** `RenderedAlert.inline_keyboard` is `None` (receipts carry no buttons)

**Given** the orchestrator preparing the success message
**When** `transaction.screenshot_path` is `None` or the file doesn't exist
**Then** `render_phase2_buy_success` is NOT called — the orchestrator calls `render_phase2_buy_failure(reason=screenshot_missing, ctx={"transaction_id": ..., "note": "transaction succeeded but screenshot capture failed"})` instead (UX-DR9)
**And** the audit log still records the `transactions` row (the buy DID succeed)
**And** the operational event `phase2_screenshot_missing` fires for diagnostic purposes

**Given** snapshot tests in `tests/unit/test_phase2_renderer_snapshots.py`
**When** the test renders the success message against fixtures (happy path, large receipt, special-chars-in-receipt-id)
**Then** each render matches its golden snapshot
**And** no emoji other than `✅` appears in the message body (no celebration emoji per UX-DR-spec discipline)

**Given** the renderer
**When** called with a transaction whose `total_seconds > 60`
**Then** the rendering still succeeds but the orchestrator's outer logic logs `phase2_buy_completion_slow` for NFR-P2 tracking

### Story 5.9: Implement Phase 2 buy failure renderer with reassurance line on every variant

As ifuensan receiving a buy-aborted alert,
I want `render_phase2_buy_failure(reason, ctx)` in `domain/alert.py` to produce a variant-specific message body for each `BuyFailureReason`, with the canonical reassurance line `La compra NO se ha ejecutado.` mandatory on EVERY variant (verified by a property test),
So that FR28 / UX-DR10 / UX-DR14 are satisfied — the user can answer "did the agent buy it?" from the alert alone, with zero ambiguity.

**Acceptance Criteria:**

**Given** `src/salvager/domain/alert.py`
**When** I import `render_phase2_buy_failure(reason, ctx)`
**Then** the rendered text follows the locked anatomy:
  - Row 1: `🚫 *Compra abortada* · <entry_display_name>`
  - Row 2: `Causa: <variant-specific cause name>`
  - Row 3+: bullet list of specific values from `ctx` (varies by variant — e.g., for `reconciliation_tripped`: api_price, html_price, tolerance)
  - Penultimate row: `La compra NO se ha ejecutado.` — verbatim, mandatory
  - Last row: state-of-Phase-2 line + copy-paste CLI investigation command
**And** `RenderedAlert.inline_keyboard` is `None`

**Given** every `BuyFailureReason` variant: `reconciliation_tripped`, `ui_check_failed`, `circuit_open`, `missing_element`, `marketplace_error`, `timeout`, `screenshot_missing`, `payment_rail_unavailable`
**When** the renderer is called for each
**Then** every output text contains the EXACT string `La compra NO se ha ejecutado.` (case-sensitive, no whitespace variation)
**And** a property test in Story 5.16 enumerates all variants and asserts presence

**Given** `BuyFailureReason.screenshot_missing` (the UX-DR9 special case)
**When** the renderer runs
**Then** the message acknowledges that the transaction may have succeeded: "La compra puede haberse completado, pero no se capturó el recibo." instead of the standard reassurance line
**And** the next-step CLI command is `salvager audit show --id <transaction_id>` and `salvager phase2 reconcile <receipt_id>` (when a receipt_id was captured)
**And** the property test in Story 5.16 has an explicit exception for this variant

**Given** the renderer for `BuyFailureReason.reconciliation_tripped` with `ctx={"api_price": 53.00, "html_price": 0.53, "tolerance_eur": 1.00}`
**When** the renderer runs
**Then** the rendered body includes the bullet list:
  - `- Wallapop API: 53,00 €`
  - `- Wallapop HTML: 0,53 €`
  - `- Tolerancia: 1,00 €`
**And** the final next-step block names `salvager audit show --last 1` and "Revisa el parser HTML antes de reactivar Fase 2 con `salvager phase2 enable <entry>`"

**Given** the renderer for `BuyFailureReason.circuit_open`
**When** the renderer runs
**Then** the message names the consecutive-failure count and the threshold (e.g., "3 fallos consecutivos · circuito abierto")
**And** the next-step block names `salvager audit show --last 5` then `salvager phase2 enable <entry>`

### Story 5.10: Implement `🟡 Comprando…` in-flight keyboard edit + Buy callback handler

As ifuensan after tapping `✅ Comprar`,
I want the Telegram callback handler to immediately edit the alert's keyboard to a single non-tappable `[🟡 Comprando…]` row, kick off the BuyOrchestrator, AND replace the keyboard via the success / failure message dispatch when the orchestrator completes,
So that FR24 / UX-DR11 are satisfied — the user has visual confirmation that their tap registered and the buy is in progress, with no spinner or progress animation (UX-DR17).

**Acceptance Criteria:**

**Given** the Phase 1 callback handler (Story 3.13) extended in this story
**When** a `CallbackEvent` with `verb="buy"` arrives
**Then** the handler IMMEDIATELY (within 1s of callback receipt) calls `telegram_surface.edit_keyboard(message_id, [[InlineButton(text="🟡 Comprando…", callback_data="noop")]])`
**And** the `🟡 Comprando…` button has no callback_data (or callback_data is sent to a no-op handler that does nothing — Telegram requires SOME callback_data; we use the literal string `"noop"`)
**And** the operational event `phase2_buy_callback_received` logs

**Given** the handler with the keyboard edited
**When** `BuyOrchestrator.execute_buy_from_callback(callback)` is invoked (sync-fire-and-forget via `asyncio.create_task`)
**Then** the orchestrator runs in the background
**And** on completion, the orchestrator dispatches either `render_phase2_buy_success` (Story 5.8) or `render_phase2_buy_failure` (Story 5.9) via `telegram_surface.send()` as a NEW message (the original alert's `🟡 Comprando…` is left as-is)

**Given** the handler
**When** a `CallbackEvent` with `verb="buy"` arrives for an alert whose entry has been disabled in the meantime (or whose listing has been seen but no Phase 2 was active)
**Then** the orchestrator's pre-flight (Story 5.2) catches this and returns `BuyOutcome.aborted(reason=...)`
**And** the failure message dispatches with `reason=marketplace_error` (or a new `reason=alert_stale` variant if cleaner)

**Given** the user receiving the original alert
**When** the buy is in flight
**Then** the original message shows the photo + body + `[🟡 Comprando…]` (non-tappable status)
**And** a separate NEW message appears at completion with the receipt or failure
**And** the original alert's keyboard is NOT further updated (this preserves the visual "what happened" history)

**Given** an integration test
**When** the test simulates: alert sent → buy tap → orchestrator success → success message dispatched
**Then** Telegram sees exactly 2 outbound calls: 1 `editMessageReplyMarkup` (to `🟡 Comprando…`) and 1 `sendPhoto` (the receipt)
**And** the audit log contains: 1 `tap_events` row (the Buy tap) + 1 `transactions` row

### Story 5.11: Implement Phase 2 operational alert variants

As ifuensan getting Phase 2 lifecycle alerts,
I want every Phase 2 operational `EventName` variant — `phase2_disabled`, `phase2_re_enabled`, `circuit_open`, `smoke_test_failed`, `smoke_test_recovered`, `phase2_buy_callback_received`, `phase2_screenshot_missing`, `phase2_buy_completion_slow`, `buy_orchestrator_error` — to render via `render_operational_alert(severity, event, ctx)` with the locked anatomy from Story 4.1,
So that FR21 / UX-DR13 are extended to Phase 2 and every Phase 2 lifecycle transition is visible.

**Acceptance Criteria:**

**Given** the `EventName` enum
**When** the Phase 2 stories complete
**Then** the enum includes (in addition to the Phase 1 set from Story 4.1): `phase2_disabled`, `phase2_re_enabled`, `circuit_open`, `smoke_test_failed`, `smoke_test_recovered`, `phase2_buy_callback_received`, `phase2_screenshot_missing`, `phase2_buy_completion_slow`, `buy_orchestrator_error`

**Given** `render_operational_alert(severity="warn", event=EventName.phase2_disabled, ctx={"reason": "circuit_breaker_open", "consecutive_failures": 3, "threshold": 3, "last_affected_entry": "WD Red Plus 4TB / WD40EFPX"})`
**When** the renderer runs
**Then** the message includes the headline `⚠️ *Fase 2 desactivada globalmente*` + cause + state line + numbered next-steps (`audit show --last 5`, patch action, `phase2 enable <entry>`)

**Given** `render_operational_alert(severity="info", event=EventName.phase2_re_enabled, ctx={"entry": "WD Red Plus 4TB / WD40EFPX"})`
**When** the renderer runs
**Then** the message uses the `ℹ️` anatomy: `ℹ️ Fase 2 reactivada para WD Red Plus 4TB`

**Given** `render_operational_alert` for `EventName.smoke_test_failed`
**When** the renderer runs
**Then** the message includes the failing fixture name + parsed value + expected value + delta
**And** the next-step list names `salvager phase2 smoke-test` (manual re-trigger) and `salvager audit show --type phase2_smoke_test --last 3`

**Given** snapshot tests
**When** the test renders one fixture per new variant
**Then** each render matches its golden snapshot

### Story 5.12: Implement `phase2 enable/disable/status` CLI commands

As ifuensan managing Phase 2 entries,
I want `salvager phase2 enable <entry>`, `salvager phase2 disable <entry|--all>`, and `salvager phase2 status`,
So that FR45 / AR12 (wishlist canonical) / UX-DR23 (--all destructive confirm) are satisfied — Phase 2 enable/disable rewrites `wishlist.yaml` via ruamel and respects manual-recovery boundaries.

**Acceptance Criteria:**

**Given** `salvager phase2 enable WD40EFPX`
**When** the command runs
**Then** the command:
  1. Loads `wishlist.yaml` via the ruamel loader (Story 2.3)
  2. Locates the entry with `ref=WD40EFPX` (case-insensitive substring match also works on `model` or `display_name` for ergonomics)
  3. Sets `entry.phase2.enabled = true`
  4. If `phase2.max_price_eur` is not set, prompts interactively for it (or aborts in non-TTY context with a hint)
  5. Saves `wishlist.yaml` via the ruamel writer (round-trip preservation)
  6. If `phase2_state.globally_disabled = true`, clears it via `Phase2AuditWriter.clear_global_disable(entry_key)`
  7. Resets `consecutive_failures` to 0
  8. Prints `✓ Phase 2 enabled for WD Red Plus 4TB / WD40EFPX (max: 60,00 €; threshold: high; circuit reset)`
**And** the exit code is 0

**Given** `salvager phase2 disable WD40EFPX`
**When** the command runs
**Then** the command sets `entry.phase2.enabled = false` in `wishlist.yaml`
**And** does NOT touch the global lockout state (per-entry disable is independent)
**And** prints `✓ Phase 2 disabled for WD Red Plus 4TB / WD40EFPX`

**Given** `salvager phase2 disable --all`
**When** the command runs in a TTY
**Then** the command counts currently-enabled entries (e.g., 5)
**And** prompts `Type the number 5 to confirm:` per UX-DR23 (typing-a-token, never y/n)
**And** if the operator types anything other than `5`, no changes are made and exit code is 1
**And** if the operator types `5`, all 5 entries are disabled and the global Phase 2 kill-switch is also activated (extra safety) with reason `operator_disable_all`
**And** the operational event `phase2_disabled` fires

**Given** `salvager phase2 disable --all` in a non-TTY context
**When** the command runs
**Then** the command fails with `error: --all requires an interactive terminal` and exit code 1

**Given** `salvager phase2 status`
**When** the command runs
**Then** the output uses `render_table` showing columns `Entry`, `Phase 2 Enabled?`, `Max Price`, `Confidence Threshold`, `Last Buy Attempt`, `Outcome`
**And** a footer line shows global state: `Globally disabled: <yes|no> · Circuit: <closed|open N/M> · Last smoke: <pass|fail at timestamp>`
**And** `phase2 status --format json` emits a JSON object with the same data per UX-DR20

**Given** any of the three commands
**When** the entry-id argument doesn't match any wishlist entry
**Then** the output is `error: entry '<id>' not found in wishlist.yaml` + `hint: salvager wishlist list to see valid entry IDs`
**And** the exit code is 2 (usage error)

### Story 5.13: Implement `phase2 smoke-test` + `phase2 reconcile` CLI commands

As ifuensan diagnosing Phase 2 issues,
I want `salvager phase2 smoke-test` (manual smoke-test trigger) and `salvager phase2 reconcile <receipt-id>` (re-run reconciliation on a past receipt),
So that FR46 is satisfied — I can manually verify safety stack health and audit historical buys.

**Acceptance Criteria:**

**Given** `salvager phase2 smoke-test`
**When** the command runs
**Then** `run_smoke_test()` (Story 5.6) is invoked immediately (regardless of the daily schedule)
**And** the output uses `render_table` showing one row per fixture with columns `Fixture`, `Parsed Price`, `Expected Price`, `Delta`, `Result`
**And** a footer line shows `Overall: <pass|fail> · Smoke test completed in <N>s`
**And** if any fixture fails, the exit code is 5 (Phase 2 guardrail) and Phase 2 auto-disable fires per Story 5.6

**Given** `salvager phase2 reconcile <receipt-id>`
**When** the command runs
**Then** the command:
  1. Loads the `transactions` row matching `receipt_id` (or matching `audit_id` if the operator passed an audit-id-shaped argument)
  2. Loads the matching `alert_snapshots` row
  3. Re-runs `reconciler.reconcile_receipt_vs_alert(alert_snapshot, transaction)` (Story 5.4)
  4. Prints the reconciliation result via `render_prose` or `render_table`
**And** the command does NOT mutate state (no auto-disable from a CLI reconciliation re-run)
**And** the exit code is 0 if reconciled, 5 if mismatch detected
**And** `--format json` emits the full `ReconciliationResult` per UX-DR20

**Given** `salvager phase2 reconcile <unknown-id>`
**When** the receipt ID doesn't exist in `transactions`
**Then** the output is `error: receipt id <id> not found in audit log`
**And** the exit code is 1

### Story 5.14: Implement payment-rail enforcement CI lint

As ifuensan,
I want a CI lint script (extending or paralleling `scripts/adapter_discipline_lint.py`) that fails the build if any file in `adapters/tinyfish_browser/` (or anywhere) introduces a flow targeting Bizum, transferencia bancaria, PayPal, or any payment rail other than Wallapop Pay / eBay.es checkout,
So that FR25 / NFR-S5 are mechanically enforced — alternate-rail introductions are structurally rejected.

**Acceptance Criteria:**

**Given** `scripts/payment_rail_lint.py`
**When** the script runs
**Then** it walks `src/salvager/adapters/tinyfish_browser/**` files
**And** searches (case-insensitive AST + string match) for any of: `bizum`, `transferencia`, `paypal`, `revolut`, `bank_transfer`, `tarjeta_propia` (a configurable deny-list)
**And** fails (exit 1) with a precise line-numbered report if any match is found

**Given** the script
**When** an allowed flow (`wallapop_pay.py`, `ebay_checkout.py`) mentions `bizum` only in a code comment that explicitly says "// NOT a Bizum flow — verified by payment_rail_lint"
**Then** the script tolerates the mention because of the explicit comment marker
**And** without the marker, the build fails

**Given** a CI job
**When** `payment_rail_lint.py` is added to the workflow alongside `adapter_discipline_lint.py`
**Then** every PR runs both lints
**And** any `bizum.py` / `paypal_pay.py` / etc. file introduced fails the build

**Given** a unit test (`tests/unit/test_payment_rail_lint.py`)
**When** the test creates a temporary directory with a synthetic `bizum_pay.py` file and runs the lint
**Then** the lint exits non-zero and the test passes
**And** the test runs in CI

### Story 5.15: Verify ≥ 90% line-coverage gate on Phase 2 critical-path modules

As ifuensan,
I want a CI gate that fails the build if line coverage on `buy_orchestrator.py`, `reconciler.py`, `circuit_breaker.py`, `smoke_test.py`, `audit_writer.py` drops below 90%,
So that NFR-M2 is mechanically enforced and the Phase 2 critical path can never silently lose test coverage.

**Acceptance Criteria:**

**Given** the CI workflow extended with a Phase 2 coverage step
**When** `pytest --cov=src/salvager/orchestration/buy_orchestrator --cov=src/salvager/orchestration/reconciler --cov=src/salvager/orchestration/circuit_breaker --cov=src/salvager/orchestration/smoke_test --cov=src/salvager/adapters/sqlite_store/audit_writer --cov-fail-under=90` runs
**Then** any individual module below 90% line coverage fails the build
**And** the failure output names the module and its actual coverage

**Given** the project's `.coveragerc` (or `pyproject.toml` `tool.coverage` section)
**When** I inspect the configuration
**Then** the source list explicitly names the 5 critical-path modules with `fail_under = 90` applied per-module
**And** other modules have their own (lower) thresholds; the per-module override prevents non-critical paths from dragging the gate down or being pulled up by lucky averaging

**Given** the test suite
**When** I run it locally and view the coverage report
**Then** I can see per-module coverage stats and identify any drift before pushing

### Story 5.16: Snapshot tests for Phase 2 renderers + property tests for failure variants

As a future contributor,
I want snapshot tests for every Phase 2 renderer (`render_phase2_listing_alert`, `render_phase2_buy_success`, `render_phase2_buy_failure`, `render_operational_alert` for Phase 2 events) plus a property test asserting every `BuyFailureReason` produces the reassurance line (except `screenshot_missing`),
So that UX-DR29 / UX-DR30 are extended to Phase 2 and regressions break CI.

**Acceptance Criteria:**

**Given** `tests/unit/test_phase2_renderer_snapshots.py` using syrupy
**When** the tests run against fixtures for: Phase 2 direct alert, Phase 2 container alert, buy success (typical), buy success (long receipt-id), buy failure (one fixture per `BuyFailureReason` variant), each Phase 2 operational `EventName` variant
**Then** each render matches its tracked golden snapshot

**Given** a property test in `tests/unit/test_phase2_failure_reassurance.py`
**When** the test enumerates every `BuyFailureReason` variant (except `screenshot_missing`)
**Then** for each variant, `render_phase2_buy_failure(reason, ctx={...})` returns text containing the EXACT string `La compra NO se ha ejecutado.` (case-sensitive)
**And** for `screenshot_missing`, the test asserts the alternate reassurance line `La compra puede haberse completado, pero no se capturó el recibo.`

**Given** a property test in `tests/unit/test_phase2_operational_property.py`
**When** the test enumerates every Phase 2 `EventName` variant
**Then** `warn` variants always include at least one numbered next-step CLI command
**And** the entry name (when present in ctx) appears verbatim in the rendered body

**Given** a property test in `tests/unit/test_phase2_buttons.py`
**When** the test renders Phase 2 listing alerts
**Then** the inline_keyboard is always exactly `[[(✅ Comprar, ...), (❌ Saltar, ...), (👁 Ver, ...)]]` (locked vocabulary per UX-DR4)
**And** every `callback_data` matches `<surface>:<verb>:<id>` with ≤ 64 bytes (UX-DR5)

### Story 5.17: Pre-v1.0 release-gate manual audits (Telegram client variance + accessibility)

As ifuensan preparing the v1.0 release,
I want a documented release-gate procedure that runs Telegram client variance manual testing (iOS + Android + Telegram desktop + Telegram Web) AND a color-blind / accessibility audit (Coblis or Color Oracle + macOS VoiceOver) against the v1.0 candidate build, with results documented and any drift triaged before the v1.0 tag,
So that UX-DR32 / UX-DR33 are satisfied — the bilingual asymmetry + emoji rendering + screen-reader compatibility claims are verified, not assumed.

**Acceptance Criteria:**

**Given** the release-gate procedure documented in `docs/release-checklist.md` (or in CONTRIBUTING.md as an appendix)
**When** I read it
**Then** it names the 4 Telegram test contexts (iOS Telegram on iPhone 12+, Android Telegram on Pixel 6+, Telegram desktop on macOS or Linux, Telegram Web in Chrome and Firefox) + the 3 color-blindness simulators (deuteranopia, protanopia, tritanopia via Coblis or Color Oracle) + macOS VoiceOver on Terminal

**Given** the procedure
**When** I run it against a v1.0 candidate
**Then** I capture screenshots of every alert variant (Phase 1 direct, Phase 1 container, Phase 2 direct, Phase 2 buy success, Phase 2 buy failure, each operational `⚠️`/`ℹ️` variant) in each Telegram context
**And** I verify emoji rendering is consistent (the 6 severity emoji + 5 button-label emoji)
**And** I verify MarkdownV2 fidelity (bold + italics + monospace render correctly)
**And** I verify button row layout (no wrap onto 2 rows for the locked label vocabulary)

**Given** the color-blind audit
**When** I view the captured screenshots through the simulators
**Then** every alert remains distinguishable by SHAPE (emoji) + TEXT (severity prefix `error:` / `warn:` / `✓` / etc.), not by color alone (UX-DR22)
**And** the `🚫` red and `⚠️` yellow distinction holds in deuteranopia (verified by visual inspection)

**Given** the VoiceOver audit
**When** I run `salvager health`, `audit show --last 5`, `phase2 status` on macOS Terminal with VoiceOver
**Then** the output reads in logical sequence without box-drawing-character interference (UX-DR23)
**And** the test report names any line-reading anomalies (and either patches the renderer or documents the limitation in `docs/accessibility.md`)

**Given** the release-gate run
**When** all manual audits pass
**Then** the audit results are committed to `docs/release-audits/v1.0/` as image attachments + a written summary
**And** the v1.0 tag can proceed (Story 5.18)

**Given** the release-gate run with any anomaly
**When** the anomaly is critical (e.g., severity emoji indistinguishable in deuteranopia)
**Then** the v1.0 tag is blocked
**And** the issue tracks as a release-gating bug per the regression-fix protocol

### Story 5.18: v1.0 release — tag, GHCR push, README v1.0 update

As ifuensan completing v1.0,
I want a final release story that bumps the version to `1.0.0`, runs the full CI gate (including the Phase 2 critical-path coverage threshold from Story 5.15), pushes the `v1.0.0` tag, verifies GHCR publishes `ghcr.io/ifuensan/salvager:v1.0.0` and `:latest`, updates the README to reflect v1.0 stability,
So that NFR-M4 (semver discipline) is honored, FR51 / AR18 are satisfied at release, and the v1.0 image is the canonical install path.

**Acceptance Criteria:**

**Given** the v1.0 candidate build with all prior stories complete
**When** I bump `pyproject.toml` `version = "1.0.0"` (per NFR-M4 — first 1.0 release marks Phase 2 stable)
**Then** the change is committed with message `release: v1.0.0`
**And** `git tag v1.0.0 && git push --tags` triggers the release CI workflow

**Given** the release workflow on `v1.0.0` tag
**When** CI runs
**Then** all gates pass: ruff, ty/mypy, pytest (with all coverage thresholds including the 90% Phase 2 gate from Story 5.15), adapter discipline lint, payment-rail lint, dependency footprint (≤ 30 direct deps)
**And** the Docker image is built and pushed to `ghcr.io/ifuensan/salvager:v1.0.0` AND `ghcr.io/ifuensan/salvager:latest`
**And** the image is publicly pullable without authentication

**Given** a fork user
**When** they run `docker pull ghcr.io/ifuensan/salvager:v1.0.0 && docker run --rm ghcr.io/ifuensan/salvager:v1.0.0 --version`
**Then** the output is `1.0.0` and exit code is 0

**Given** the README update
**When** I read `README.md` after the tag
**Then** the badge / install section names `:v1.0.0` as the recommended pinned tag
**And** the changelog section is updated with the v1.0.0 release notes (highlighting Phase 2 enabled, safety stack documented, ifuensan's first successful Phase 2 purchase if it occurred during the gate window)

**Given** the v1.0.0 release published
**When** the operator runs `salvager version`
**Then** the output is `1.0.0 (commit <sha>)`

**Given** the audit log requirements for v1.0
**When** the audit log schema is inspected
**Then** the schema_version in `_meta` is 2 (Phase 1 + Phase 2 migrations applied)
**And** the schema is locked at v1.0 — future breaking changes require a major version bump per NFR-M4

**Given** the v1.0 release notes
**When** I read `ROADMAP.md`
**Then** the post-v1.0 roadmap items are documented: multi-marketplace expansion (deferred), additional LLM providers (config-only, available now), arbitrage-as-separate-repo (referenced from CONTRIBUTING)

