# Changelog

All notable changes to **hardware-hunter** land here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project
honours [Semantic Versioning](https://semver.org/spec/v2.0.0.html) per
NFR-M4.

## [Unreleased]

Nothing on the wire today. Post-v1 work is described in
[ROADMAP.md](ROADMAP.md) under "Post-launch (deferred)".

---

## [1.0.0] — _pending Story 5.17 release-audit sign-off_

**Phase 2 stable.** The autonomous-purchase loop ships behind the
safety stack and the non-bypassable Telegram tap. The Phase 1 →
Phase 2 stabilisation gate has been passed; entries opted in via
`hardware-hunter phase2 enable <entry>` can complete a buy through
Wallapop Pay or eBay.es checkout without operator intervention beyond
the initial tap.

Tag: `v1.0.0` → GHCR `ghcr.io/ifuensan/hardware-hunter:v1.0.0`,
`:1.0`, `:latest` (semver auto-tagging from
`.github/workflows/release.yml`).

### Added

- **Phase 2 autonomous-purchase critical path** (Epic 5):
  - SQLite schema v2 with append-only `tap_events`, `transactions`,
    `phase2_smoke_tests` + single-row mutable `phase2_state` (Story 5.1).
  - Phase 2 listing alert renderer + preflight gate — five checks
    (per-entry enabled, max-price ceiling, listing under ceiling,
    confidence ≥ threshold, global lockout / circuit / smoke freshness)
    consulted at alert dispatch AND on every Buy tap (Story 5.2).
  - `BrowserSession` port + `WallapopPayFlow` / `EbayCheckoutFlow`
    TinyFish-driven adapters with a 9-step buy contract and
    fail-closed mapping of every SDK error → typed `BuyFailure`
    (Story 5.3).
  - Cross-source price reconciliation (FR31) + receipt-vs-alert
    reconciliation (FR32) gating the buy on both sides of the
    checkout (Story 5.4).
  - Per-purchase circuit breaker + auto-disable lockout (FR34 /
    FR35) — three consecutive failures opens the breaker, only
    `phase2 enable` clears it (Story 5.5).
  - Daily synthetic smoke test against a fixture set under
    `tests/fixtures/price_parsers/active/` (Story 5.6).
  - `BuyOrchestrator` composing preflight + reconcile + UI check +
    buy + screenshot + audit-write + receipt reconciliation + circuit
    record + Telegram dispatch in a single
    `execute_buy_from_callback` call returning a typed `BuyOutcome`
    discriminated union (Story 5.7).
  - Phase 2 buy success renderer with mandatory-screenshot guard
    (UX-DR9 — Story 5.8) and buy failure renderer with the locked
    reassurance line on every variant (UX-DR10 — Story 5.9).
  - `[🟡 Comprando…]` in-flight keyboard edit + Buy callback handler
    extending the Phase 1 `CallbackDispatcher` (Story 5.10).
  - Six new operational `EventName` variants for the Phase 2 surface
    (`phase2_disabled`, `phase2_re_enabled`,
    `phase2_buy_callback_received`, `phase2_screenshot_missing`,
    `phase2_buy_completion_slow`, `buy_orchestrator_error` — Story 5.11).
  - `hardware-hunter phase2 enable / disable / status` CLI commands
    with TTY-gated typing-a-number confirm on `--all` (Story 5.12).
  - `hardware-hunter phase2 smoke-test` + `phase2 reconcile` CLI
    commands for operator-driven safety-stack triage (Story 5.13).

- **Release-blocking CI gates**:
  - **Payment-rail enforcement** — AST + per-line lint walks
    `adapters/tinyfish_browser/` and rejects any reference to Bizum,
    transferencia, PayPal, Revolut, bank_transfer or tarjeta_propia
    that is not annotated `verified by payment_rail_lint`
    (Story 5.14, FR25 / NFR-S5).
  - **Per-module 90% line-coverage gate** on the Phase 2 critical
    path (`buy_orchestrator`, `reconciler`, `circuit_breaker`,
    `smoke_test`, `audit_writer`) — fails the build below 90%
    (Story 5.15, NFR-M2).
  - **Snapshot tests + property tests** for every Phase 2 renderer
    and every `BuyFailureReason` variant; reassurance line invariant
    is asserted on every non-`screenshot_missing` failure (Story
    5.16, UX-DR10).

- **Release-audit tooling** (Story 5.17):
  - `hardware-hunter dev emit-alert <variant>` fires any of the 37
    locked alert variants against the configured Telegram chat
    (--dry-run prints rendered MarkdownV2 to stdout for inspection).
  - `scripts/dump_audit_snapshots.py` writes one reference `.txt`
    per variant under `docs/release-audits/v1.0/reference-text/`
    for client-variance diffing.
  - `docs/release-checklist.md` documents the 4 Telegram contexts,
    3 colour-blind simulators and macOS VoiceOver pass that gate
    the v1.0 tag.
  - `docs/release-audits/v1.0/SETUP.md` walks through the
    throwaway-bot + audit-chat setup so the production wiring stays
    untouched during the audit window.

### Changed

- `version` in `pyproject.toml` bumped `0.1.0` → `1.0.0`. The
  `hardware-hunter version` CLI command surfaces the new value alongside
  the git short SHA.
- README badge + install instructions recommend `:v1.0.0` as the
  pinned tag for new deployments (`:latest` continues to track the
  newest stable release).

### Security

- Payment-rail boundary structurally enforced: the only payment rails
  the agent can reach are Wallapop Pay and eBay.es checkout. The CI
  lint trips any drift before merge (NFR-S5).
- Mandatory-screenshot guard on Phase 2 buys (UX-DR9): a buy that
  completes without a captured receipt surfaces as
  `BuyFailure(reason=screenshot_missing)` with the alternate
  reassurance line, never as a silent success.

### Project notes

- Schema locked at v2 — future schema-breaking changes require a major
  version bump per NFR-M4.
- Post-v1.0 deferred items (multi-marketplace expansion, additional
  LLM providers as config-only, the arbitrage-as-separate-repo
  path) live in [ROADMAP.md](ROADMAP.md).

---

## [0.1.0] — 2026-04-XX

Foundation release. Installable skeleton + OSS posture; no marketplace
polling yet. Published to GHCR as `ghcr.io/ifuensan/hardware-hunter:0.1.0`.

### Added

- uv-managed Python 3.12+ package with hexagonal directory layout
  (`domain/`, `interfaces/`, `orchestration/`, `adapters/`, `cli/`,
  `config/`, `observability/`).
- CI quality gates: `ruff check`, `ruff format --check`, `ty` + `mypy`
  strict, `pytest`, custom adapter-discipline lint enforcing NFR-M1
  (only `adapters/` may import marketplace SDKs / TinyFish / Hermes /
  python-telegram-bot / httpx).
- Docker image + GHCR release workflow on `v*` tag push.
- Tracked example configuration files (`.env.example`,
  `wishlist.example.yaml`, `config.example.yaml`).
- OSS posture documentation (README, CONTRIBUTING, ROADMAP, LICENSE).
- Structured JSON Lines logging foundation (NFR-O1 / NFR-R5).
- rich-based CLI rendering helpers + locked theme tokens (UX-DR16).
- typer CLI skeleton with the `hardware-hunter version` subcommand
  (FR39 / FR48).

---

[Unreleased]: https://github.com/ifuensan/hardware-hunter/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ifuensan/hardware-hunter/releases/tag/v1.0.0
[0.1.0]: https://github.com/ifuensan/hardware-hunter/releases/tag/v0.1.0
