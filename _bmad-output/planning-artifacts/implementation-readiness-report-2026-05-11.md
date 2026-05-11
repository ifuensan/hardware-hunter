---
date: 2026-05-11
project: hardware-hunter
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
workflowStatus: complete
documentsAssessed:
  prd: _bmad-output/planning-artifacts/prd.md
  architecture: _bmad-output/planning-artifacts/architecture.md
  epics: _bmad-output/planning-artifacts/epics.md
  ux: _bmad-output/planning-artifacts/ux-design-specification.md
supportingInputs:
  - _bmad-output/planning-artifacts/prfaq-hardware-hunter.md
  - _bmad-output/planning-artifacts/prfaq-hardware-hunter-distillate.md
  - hardware-hunter-bmad-prompt.md
priorReports:
  - _bmad-output/planning-artifacts/implementation-readiness-report-2026-05-10.md
assessmentScope: full-four-artifact
---

# Implementation Readiness Assessment Report

**Date:** 2026-05-11
**Project:** hardware-hunter

## Document Discovery

### Documents Found

| Type | Status | File | Size | Modified | Steps Completed |
|---|---|---|---|---|---|
| **PRD** | ✓ Found | `_bmad-output/planning-artifacts/prd.md` | 88 KB | 2026-05-10 | 12/12 (steps 1–12) |
| **Architecture** | ✓ Found | `_bmad-output/planning-artifacts/architecture.md` | 112 KB | 2026-05-10 | 8/8 |
| **Epics & Stories** | ✓ Found | `_bmad-output/planning-artifacts/epics.md` | 191 KB | 2026-05-11 | 4/4 (workflow complete) |
| **UX Design** | ✓ Found | `_bmad-output/planning-artifacts/ux-design-specification.md` | 160 KB | 2026-05-10 | 14/14 (visualUI: false; Telegram + CLI scope) |

### Supporting Inputs (used by PRD authoring, not assessed here)

- `_bmad-output/planning-artifacts/prfaq-hardware-hunter.md` (56 KB) — Working Backwards PRFAQ, 5 stages
- `_bmad-output/planning-artifacts/prfaq-hardware-hunter-distillate.md` (18 KB) — LLM-optimized distillate
- `hardware-hunter-bmad-prompt.md` (12 KB) — BMAD session kickoff

### Derived Artifacts (not assessed)

- `prd.html`, `prd.pdf` — rendering of `prd.md` for sharing
- `build_prd_pdf.py` — reproducible PDF build script

### Prior Readiness Report

- `_bmad-output/planning-artifacts/implementation-readiness-report-2026-05-10.md` (1.9 KB) — paused PRD-only assessment from 2026-05-10; preserved as historical record.

### Document Discovery — Issues

| Issue | Status |
|---|---|
| Duplicate document formats (whole + sharded) | None |
| Missing required documents | None |
| Unresolved version conflicts | None |

### Assessment Scope

This run is the **full four-artifact readiness check**. All four documents (PRD, Architecture, Epics & Stories, UX Design) are present, complete by their own workflow tracking, and ready for cross-artifact validation. The assessment will examine: (a) PRD internal consistency and OQ status, (b) Architecture coverage of FRs/NFRs, (c) UX Design coverage of the rendering + accessibility surface, (d) Epic+Story FR coverage, dependency flow, and acceptance-criterion testability, (e) cross-artifact traceability with explicit gap-naming if found.

## PRD Analysis

### Source

PRD: `_bmad-output/planning-artifacts/prd.md` (88 KB, 887 lines, 12 sections, frontmatter shows all 12 BMAD-create-PRD steps completed; releaseMode: phased).

The full FR/NFR text was extracted verbatim from the PRD into the Requirements Inventory section of `epics.md` (lines 12–230) during the prior bmad-create-epics-and-stories Step 1. To avoid duplication of ~30 KB of FR/NFR text, this report references the canonical extraction and assesses PRD-specific quality dimensions here.

### Functional Requirements

**Total: 54 FRs**, organized in 9 thematic areas, all numbered FR1–FR54 with no gaps and no duplicate IDs.

| Area | FR range | Count | Notes |
|---|---|---|---|
| Wishlist Management | FR1–FR5 | 5 | YAML schema, validator, entry-key contract, container-detection toggle |
| Marketplace Monitoring | FR6–FR12 | 7 | Two-path Wallapop, eBay.es, scheduler, dedup, session-expiry |
| Listing Evaluation | FR13–FR17 | 5 | Wishlist-anchored LLM, container detection, cache, "no arbitrage" |
| Alert Notifications | FR18–FR22 | 5 | Phase 1 alert anatomy, buttons, snooze, operational alerts, format lock |
| Autonomous Purchase | FR23–FR30 | 8 | Per-entry enable, payment rails, UI checks, "no autonomous mode" |
| Phase 2 Failure Defense | FR31–FR35 | 5 | Cross-source + receipt reconciliation, smoke test, circuit breaker, manual re-enable |
| Audit & Dispute Evidence | FR36–FR38 | 3 | Append-only audit log, view/export, no telemetry |
| Operator Tools | FR39–FR48 | 10 | CLI binary, 9 named subcommands, exit codes, JSON output |
| Configuration & Lifecycle | FR49–FR50 | 2 | Three-file config split, SIGTERM graceful drain |
| Project Distribution | FR51–FR54 | 4 | docker-compose, CONTRIBUTING, ROADMAP, README positioning |

**FR extraction integrity:** Numbering is sequential 1–54 with no gaps. Each FR is single-sentence-bounded with bold prefix marker `**FR<N>.**`. Every FR is testable / observable from the outside; no FR is purely internal.

### Non-Functional Requirements

**Total: 37 NFRs**, organized in 8 categories using a 2-letter prefix scheme (P/S/R/I/C/M/PR/O).

| Category | NFR range | Count | Driving concern |
|---|---|---|---|
| Performance | NFR-P1–P5 | 5 | Alert latency, Phase 2 completion, LLM eval, CLI responsiveness, daemon startup |
| Security | NFR-S1–S7 | 7 | Credentials, file modes, TLS, audit append-only, payment rails, destructive ops, local data plane |
| Reliability | NFR-R1–R6 | 6 | Marketplace independence, fallback, no silent failure, manual recovery, crash, marketplace-break target |
| Integration | NFR-I1–I6 | 6 | Hermes pin, TinyFish via MCP, LLM provider abstraction, schema drift, eBay API, Telegram retry |
| Cost | NFR-C1–C3 | 3 | Phase 1 monthly, Phase 2 per-purchase, LLM cache hit rate |
| Maintainability | NFR-M1–M6 | 6 | Adapter discipline (launch blocker), Phase 2 coverage, smoke regression set, semver, dep footprint, solo-maintainer budget |
| Privacy | NFR-PR1–PR5 | 5 | Data classes, retention, no remote persistence, deletion path, listing data scope |
| Observability | NFR-O1–O5 | 5 | Structured logs, health surface, audit readability, diagnostic completeness, no mandatory retention |

**NFR extraction integrity:** Each NFR has a unique category-numeric ID; no duplicates. NFR-M1 is explicitly flagged as a **launch-blocker** (adapter discipline). NFR-M2 sets a hard 90% coverage gate on named Phase 2 critical-path modules.

### Additional Requirements

The PRD's `Domain-Specific Requirements` (lines 289–355) and `Innovation & Novel Patterns` (lines 356–438) sections contain prose that informs but does not introduce additional numbered requirements. The Project Scoping section (lines 635–714) introduces the **phased delivery model** (Phase 1 alerts only → 4–8 week stabilization gate → Phase 2 autonomous purchase) which is operationally an architecture / epics concern; epics.md reflects this as the Epic 4 → Epic 5 boundary.

The **(c3) scope contract** ("personal homelab tool; Wallapop + eBay.es only for v1; arbitrage explicitly out of scope and structurally prevented") is referenced from FR3 / FR11 / FR17 / FR52 / FR53 and is enforced both at the schema layer (FR3) and at the prompt layer (FR17). This is a cross-cutting constraint, not a single requirement.

### Open Questions (OQs)

The PRD documents **8 Open Questions** with explicit defaults, resolution paths, owners, and blocking status:

| # | Question | v1 default | Blocking? |
|---|---|---|---|
| OQ1 | Receipt-vs-alert auto-disable scope (global vs per-entry) | Global | No |
| OQ2 | Container detection: strict ceiling vs LLM "vale la pena" | Strict ceiling + confidence gate | No |
| OQ3 | Per-purchase TinyFish Browser cost (cents vs ≤ €1.00) | ≤ €1.00 worst-case (NFR-C2) | **Yes — gates public Phase 2 docs** |
| OQ4 | Wishlist scale assumptions | ~50 entries × ~10 candidates/day | No |
| OQ5 | Per-marketplace adapter break frequency | 2–4/year | No |
| OQ6 | Language-register bias on LLM evaluation (Castilian vs other) | Best-effort, disclosed in README | **Yes — gates Phase 2 enable for non-Castilian users** |
| OQ7 | Phase 2 fallback when TinyFish Browser unavailable mid-buy | Fail closed + operational alert | No |
| OQ8 | agentskills.io publication for Hermes ecosystem visibility | Deferred to Vision | No |

**OQ status assessment:** 2 OQs (OQ3, OQ6) are flagged as blocking. Both block Phase 2 readiness, not Phase 1; both have explicit empirical-measurement resolution paths owned by ifuensan. Each blocking OQ should be tracked in the Phase 1 → Phase 2 gate checklist of `epics.md` (Epic 5 — Phase 2 enablement).

### PRD Completeness Assessment

| Dimension | Status | Notes |
|---|---|---|
| Sectional completeness | ✓ Complete | All 12 BMAD-PRD steps marked in frontmatter; sections 1–12 present |
| FR numbering integrity | ✓ Complete | No gaps, no duplicates, sequential FR1–FR54 |
| NFR taxonomy | ✓ Complete | 8 categories, 37 NFRs, no orphans |
| Testability | ✓ High | Each FR/NFR is single-sentence, externally observable, has measurable acceptance criteria embedded in the prose |
| Launch-blocker flagging | ✓ Explicit | NFR-M1 (adapter discipline) flagged; PRD Innovation section lists it as the v1 launch blocker |
| Scope clarity | ✓ Strong | (c3) contract appears 8+ times across sections; arbitrage exclusion is named in FR3, FR17, FR52, CONTRIBUTING |
| Open Question discipline | ✓ Complete | All 8 OQs have defaults, owners, resolution paths, and blocking-status flags |
| Phased delivery boundary | ✓ Crisp | Phase 1 / Phase 2 / stabilization gate / release criteria all documented in Project Scoping section |
| Internal cross-references | ✓ Consistent | FR ↔ NFR cross-references resolve (e.g., FR35 references NFR-R4; FR3 references FR17 via "(c3) scope contract") |
| Legal posture | ✓ Documented | FR54 mandates README legal disclaimer; Spanish ToS posture + secondary-account recommendation named; no Wallapop trademarks |

**Assessment: PRD is implementation-ready.** No internal inconsistencies, no missing sections, no requirement gaps that would propagate downstream. The 2 blocking OQs are correctly scoped to Phase 2 gating, not Phase 1 implementation start.

## Epic Coverage Validation

### Source

Epics: `_bmad-output/planning-artifacts/epics.md` (191 KB, 2,497 lines, workflowStatus: complete; 5 epics, 61 stories).

The document includes an explicit **FR Coverage Map** (lines 235–291 of epics.md) mapping every PRD FR to one or more epics, with story-level pointers in each epic body. Cross-check below.

### Coverage Matrix (54 PRD FRs vs Epic Coverage Map)

| FR | PRD area | Epic Coverage (per epics.md) | Story-level pointers | Status |
|---|---|---|---|---|
| FR1 | Wishlist | Epic 2 | 2.1 (schema) | ✓ Covered |
| FR2 | Wishlist | Epic 2 | 2.1 (Phase 2 + confidence fields) | ✓ Covered |
| FR3 | Wishlist | Epic 2 | 2.2 (scope-guard), 2.4 (validate-wishlist CLI) | ✓ Covered |
| FR4 | Wishlist | Epic 2 | 2.1 (entry_key) | ✓ Covered |
| FR5 | Wishlist | Epic 2 | 2.1 (nil disables container detection) | ✓ Covered |
| FR6 | Marketplace | Epic 3 | 3.4 (API), 3.5 (TinyFish), 3.6 (orchestration) | ✓ Covered |
| FR7 | Marketplace | Epic 3 | 3.7 (eBay.es API) | ✓ Covered |
| FR8 | Marketplace | Epic 3 | 3.8 (Hermes scheduler) | ✓ Covered |
| FR9 | Marketplace | Epic 3 | 3.14 (query builder in poll loop) | ✓ Covered |
| FR10 | Marketplace | Epic 3 | 3.3 (seen_listings table), 3.14 (dedup filter) | ✓ Covered |
| FR11 | Marketplace | Epic 3 | 3.14 (only wishlist-anchored matches surface) | ✓ Covered |
| FR12 | Marketplace | Epic 3 + Epic 4 | 3.6 (detection), 4.3 (operational alert + recovery) | ✓ Covered (split) |
| FR13 | Evaluation | Epic 3 | 3.9 (LLM evaluator with confidence levels) | ✓ Covered |
| FR14 | Evaluation | Epic 3 | 3.9 (container detection vs per-entry ceilings) | ✓ Covered |
| FR15 | Evaluation | Epic 3 | 3.9 (one_line_take), 3.11 (rendered in alert) | ✓ Covered |
| FR16 | Evaluation | Epic 3 | 3.10 (LLM cache with TTL) | ✓ Covered |
| FR17 | Evaluation | Epic 3 | 3.9 (prompt has no arbitrage codepath) | ✓ Covered |
| FR18 | Alerts | Epic 3 | 3.11 (renderer), 3.12 (dispatcher) | ✓ Covered |
| FR19 | Alerts | Epic 3 | 3.11 (Phase 1 buttons), 3.13 (callback handler) | ✓ Covered |
| FR20 | Alerts | Epic 3 | 3.13 (snooze handling) | ✓ Covered |
| FR21 | Alerts | Epic 4 + Epic 5 | 4.1 (Phase 1 operational variants), 5.11 (Phase 2 variants) | ✓ Covered (split) |
| FR22 | Alerts | Epic 3 + Epic 5 | 3.11 (Phase 1 snapshot tests), 5.16 (Phase 2 snapshot tests) | ✓ Covered |
| FR23 | Phase 2 | Epic 5 | 5.2 (pre-flight check), 5.12 (enable CLI) | ✓ Covered |
| FR24 | Phase 2 | Epic 5 | 5.2 (Phase 2 alert), 5.10 (Comprar callback) | ✓ Covered |
| FR25 | Phase 2 | Epic 5 | 5.3 (TinyFish browser scoped to protected rails), 5.14 (CI lint deny-list) | ✓ Covered |
| FR26 | Phase 2 | Epic 5 | 5.2 (pre-flight max price check) | ✓ Covered |
| FR27 | Phase 2 | Epic 5 | 5.2 (pre-flight confidence threshold) | ✓ Covered |
| FR28 | Phase 2 | Epic 5 | 5.3 (UI element check inside execute_buy), 5.7 (orchestrator wiring) | ✓ Covered |
| FR29 | Phase 2 | Epic 5 | 5.7 (orchestrator API only accepts CallbackEvent; no autonomous entry point) | ✓ Covered |
| FR30 | Phase 2 | Epic 5 | 5.3 (stealth browser via TinyFish) | ✓ Covered |
| FR31 | Phase 2 Defense | Epic 5 | 5.4 (cross-source reconciliation) | ✓ Covered |
| FR32 | Phase 2 Defense | Epic 5 | 5.4 (receipt-vs-alert reconciliation) | ✓ Covered |
| FR33 | Phase 2 Defense | Epic 5 | 5.6 (daily smoke test) | ✓ Covered |
| FR34 | Phase 2 Defense | Epic 5 | 5.5 (circuit breaker) | ✓ Covered |
| FR35 | Phase 2 Defense | Epic 5 | 5.5 (no auto-recovery), 5.12 (phase2 enable command) | ✓ Covered |
| FR36 | Audit | Epic 5 | 5.1 (Phase 2 schema), 5.7 (audit log writes) | ✓ Covered |
| FR37 | Audit | Epic 4 + Epic 5 | 4.5 (audit show + audit export CLI), 5.1/5.7 (Phase 2 writers populate the tables) | ✓ Covered (split) |
| FR38 | Audit | Epic 5 + Epic 1 | NFR-S7 applied cross-cutting; no telemetry guard everywhere | ✓ Covered (cross-cutting) |
| FR39 | Operator | Epic 1 | 1.8 (typer CLI skeleton + daemon-default) | ✓ Covered |
| FR40 | Operator | Epic 2 | 2.8 (init scaffold) | ✓ Covered |
| FR41 | Operator | Epic 2 | 2.9 (login wallapop) | ✓ Covered |
| FR42 | Operator | Epic 2 | 2.10 (login ebay) | ✓ Covered |
| FR43 | Operator | Epic 4 | 4.6 (test-search) | ✓ Covered |
| FR44 | Operator | Epic 4 | 4.7 (explain) | ✓ Covered |
| FR45 | Operator | Epic 5 | 5.12 (phase2 enable/disable/status) | ✓ Covered |
| FR46 | Operator | Epic 5 | 5.13 (phase2 smoke-test + reconcile) | ✓ Covered |
| FR47 | Operator | Epic 4 | 4.4 (health) | ✓ Covered |
| FR48 | Operator | Epic 1 + Epic 4 | 1.6 (structured logs), 1.8 (exit codes), 4.5 (--format json on audit), 3.15 (property tests) | ✓ Covered |
| FR49 | Config | Epic 1 + Epic 2 | 1.4 (example configs), 2.5 (config.yaml loader), 2.6 (.env loader) | ✓ Covered |
| FR50 | Lifecycle | Epic 4 | 4.8 (SIGTERM drain) | ✓ Covered |
| FR51 | Distribution | Epic 1 | 1.3 (Docker), 1.4 (example configs) | ✓ Covered |
| FR52 | Distribution | Epic 1 | 1.5 (CONTRIBUTING with no-arbitrage rule) | ✓ Covered |
| FR53 | Distribution | Epic 1 | 1.5 (ROADMAP) | ✓ Covered |
| FR54 | Distribution | Epic 1 | 1.5 (README positioning + legal disclaimer) | ✓ Covered |

### Missing Requirements

**None.** All 54 PRD FRs are covered by at least one story in the epic structure.

### Reverse Check — FRs in epics not in PRD

The epics.md FR Coverage Map references FR1–FR54 exclusively. No FR55+ or non-PRD-derived FRs were introduced during epic decomposition. Reverse-coverage is clean.

### Coverage Statistics

- **Total PRD FRs:** 54
- **FRs covered in epics:** 54
- **Coverage percentage:** **100%**
- **FRs split across multiple epics (intentional):** 6 (FR12, FR21, FR22, FR37, FR48, FR49) — each split documented with rationale in the FR Coverage Map
- **FRs without explicit story-level mapping:** 0
- **Orphan stories (no FR/NFR/AR/UX-DR reference):** 0 (every story's body names its driving requirements)

### Phase boundary integrity check

Epic 5 (Phase 2) cleanly inherits the architecture's Phase 1 vs Phase 2 file split (AR24): the 7 named files exist as `Phase2GuardrailTripped` stubs after Epic 3 (Story 3.1's domain definitions) and become full implementations in Epic 5 (Story 5.1 + downstream). Stories that touch Phase 2 work are all in Epic 5; no Phase 2 work bleeds into Epic 3 or Epic 4.

**Assessment: Epic coverage is complete.** Zero gaps. The 6 multi-epic FR splits are intentional and rationally documented (e.g., FR12 detection in Epic 3, operational alerting in Epic 4 — different code paths for the same lifecycle event).

## UX Alignment Assessment

### UX Document Status

**Found.** `_bmad-output/planning-artifacts/ux-design-specification.md` (160 KB, 14 workflow steps complete).

The UX workflow was explicitly reframed for the no-GUI product (`visualUI: false` in frontmatter; scope note in the document: "hardware-hunter has no graphical UI; user surfaces are a Telegram bot and an operator CLI"). The reframe is structural — every UX step that the standard skill would have produced for a GUI was rewritten to address Telegram message rendering and CLI ergonomics instead. No phantom GUI specification leaked in.

### UX ↔ PRD Alignment

| Dimension | Alignment | Notes |
|---|---|---|
| User surfaces | ✓ Aligned | UX scope (Telegram + CLI) exactly matches PRD surfaces (FR18, FR21, FR39, FR41–FR48) |
| User journeys | ✓ Aligned | UX Step 10 specifies 6 journeys (setup, first alert, Phase 2 enable, auto-disable recovery, session expiry, wishlist edit). All 6 trace to PRD User Journeys section (lines 175–288) or are direct extensions for operational recovery |
| Phase 1 alert anatomy | ✓ Aligned | UX-DR6 (Direction A + E hybrid) is the locked instantiation of FR18 + FR19 (alert + buttons); FR22 (format frozen) is mechanically enforced via UX-DR29 snapshot tests |
| Phase 2 alert anatomy | ✓ Aligned | UX-DR7 instantiates FR23 + FR24 (Phase 2 enable per entry + Comprar button); pre-flight gating downgrades to Phase 1 alert when conditions fail |
| Operational alert distinction | ✓ Aligned | UX-DR13/14/15 implement FR21's `⚠️`/`ℹ️` severity-prefix distinction with calm-instructional vs direct-minimal tone registers |
| Manual-recovery boundaries | ✓ Aligned | UX-DR23 (typing-a-token destructive confirmation) implements NFR-S6; UX journeys 4 + 5 (Phase 2 auto-disable + session expiry) honor NFR-R4 |
| Mandatory receipt screenshot | ✓ Aligned | UX-DR9 instantiates FR36's "screenshot path" audit log artifact; UX adds the failure-redirect when screenshot is absent — a UX refinement of the PRD's intent |
| Scope contract (c3) | ✓ Aligned | UX-DR22 surfaces (c3) in `validate-wishlist` error wording, matching FR3 and FR52 + FR53 |
| Language posture | ✓ Aligned with addition | UX-DR27 introduces explicit bilingual asymmetry (Spanish Telegram + English CLI/code/docs). PRD doesn't mandate language; UX adds this constraint, consistent with FR54 (Spanish-positioning README) and the (c3) Spanish-homelabber audience. **No conflict.** |
| OQ scope | ✓ Aligned | UX explicitly defers `config.yaml > telegram.locale` flag to post-launch (OQ-tracked), matching PRD's "personal homelab tool" framing |

**UX requirements not in PRD:** 33 UX-DRs add specificity to the PRD's user-experience direction. These are *refinements*, not *contradictions* — each UX-DR can be traced to a PRD intent (e.g., UX-DR10 reassurance line refines FR21's "operational alerts surface degradation with cause"; UX-DR9 receipt screenshot guard refines FR36's audit log).

**PRD UX requirements not in UX:** None. Every PRD UX-relevant requirement (alert anatomy, operational alert distinction, CLI ergonomics, JSON output, etc.) has a corresponding UX-DR specification.

### UX ↔ Architecture Alignment

| Architecture decision | UX requirement | Alignment |
|---|---|---|
| AR6 (hexagonal layout: domain pure + interfaces ABCs + adapters SDK-bound) | UX-DR1 places renderers in `domain/alert.py` (pure pydantic); UX-DR2 places CLI helpers in `observability/styling.py` (uses rich) | ✓ Aligned — renderers produce pure `RenderedAlert` consumed by Telegram adapter |
| AR7 (custom AST-based adapter discipline lint) | UX-DR1 renderers depend only on `domain/` + pydantic; UX-DR2 CLI helpers are observability-package (allowed to import rich since observability is the renderer location, not domain) | ✓ Aligned — lint will pass |
| AR8/AR9 (SQLite tables + append-only `Store` interface) | UX-DR9 (mandatory receipt screenshot) maps to `transactions.screenshot_path` column; UX-DR26 (audit pointer in alerts) maps to `audit show --id <n>` returning the canonical row | ✓ Aligned — schema supports the UX contract |
| AR12 (wishlist canonical for Phase 2; ruamel round-trip) | UX-DR23 (`phase2 disable --all` typing-a-token confirmation) consumes the same `wishlist.yaml` rewrite path; UX-DR22 (validate-wishlist error) consumes the scope-guard at the schema layer | ✓ Aligned |
| AR14 (daemon ↔ CLI: shared filesystem + SQLite, no IPC) | UX-DR25 (`health` distinguishes states) reads SQLite + filesystem directly; works whether daemon is running | ✓ Aligned |
| AR17 (Dockerfile + docker-compose with restart on-failure) | UX journeys 1 + 4 (install + Phase 2 recovery) assume `docker-compose restart` is the supported recovery model | ✓ Aligned |
| AR20 (Telegram chat allowlist) | UX `render_callback_acknowledgment` (UX-DR12) is silent for non-allowlisted chats (UX inherits architecture's silent-drop behavior) | ✓ Aligned |
| AR24 (Phase 1 vs Phase 2 file split: stubs at v0.x) | UX-DR7 (Phase 2 alert renderer) + UX-DR9 + UX-DR10 are all Phase 2; epics.md Story 5.1 unblocks them from `Phase2GuardrailTripped` stubs | ✓ Aligned |
| AR15 (async daemon + Hermes subagents) / AR16 (sync pipeline) | UX-DR17 (forbid `rich.progress.Progress` / `rich.status.Status`) is consistent with the architecture's "silence-is-success" posture — async work isn't surfaced as animation | ✓ Aligned |
| Decision Impact "implementation sequence" (architecture lines 452–477) | UX gates `UX-DR32` + `UX-DR33` (Telegram client variance + accessibility audits) before v1.0 release; matches architecture sequence step 14 ("v1.0 release") | ✓ Aligned |

**Architecture decisions UX depends on but doesn't add to:** Phase 2 file split (AR24), append-only audit log (AR9), wishlist as canonical Phase 2 source (AR12) — UX consumes all three without modification.

**Architecture decisions UX extends:** AR17 (Docker) is extended by UX-DR31's CLI terminal width testing as a CI gate (60/80/100/120 cols). Architecture didn't specify CI test breadth at that granularity; UX makes it concrete. No conflict.

### Alignment Issues

**None identified.** No misalignments between UX, PRD, and Architecture. The (`visualUI: false`) framing was applied consistently throughout the UX workflow, preventing the most common failure mode (specifying a GUI for a no-GUI product).

### Warnings

**Soft warning — UX-DR coverage in epics:** All 33 UX-DRs are addressed by at least one story in `epics.md`. Spot-checked:
- UX-DR1 (renderers) → Stories 3.11, 5.2, 5.8, 5.9, 4.1, 5.11, 3.13
- UX-DR9 (mandatory screenshot) → Story 5.8
- UX-DR22 (scope-contract error) → Story 2.2 + 2.4
- UX-DR23 (typing-a-token confirmation) → Stories 2.8 + 5.12
- UX-DR27 (bilingual asymmetry) → implicit cross-cutting; no single story enforces it, relies on code-review discipline. **Recommendation:** add a CI lint check (or property test) that asserts Telegram-bound strings are Spanish and English-bound strings (logs, CLI prose) are English. This is an enhancement, not a blocker.
- UX-DR32 / UX-DR33 (release-gate manual audits) → Story 5.17

**Soft warning — UX language enforcement:** The bilingual asymmetry (UX-DR27) is a UX decision but not mechanically enforceable at v1. Drift risk exists if future contributors mix Spanish into CLI output or English into Telegram strings. Mitigation: add `docs/contributing-language.md` referenced from CONTRIBUTING.md (Story 1.5), and consider a future-research story for a CI lint. **Not a v1 blocker** — single-maintainer project, code review catches drift.

**Assessment: UX alignment is implementation-ready.** No misalignments, no missing UX surfaces, no contradictions with Architecture. Two soft warnings about future-enforcement discipline noted; neither blocks Phase 1 implementation start.

## Epic Quality Review

### Per-epic structural validation

#### Epic 1: Foundation — Installable Skeleton & OSS Posture

| Check | Result | Notes |
|---|---|---|
| Epic title is user-centric | ✓ | "Installable Skeleton & OSS Posture" — frames the operator-can-install outcome, not the technical setup |
| Epic goal describes user outcome | ✓ | "Operator (or fork user) can git clone, docker-compose up, and reach a state where the daemon starts cleanly..." |
| Standalone-valuable | ✓ | Produces a runnable Docker image on GHCR even without alerts — fork users can install + verify the install path |
| Anti-pattern check: "infrastructure setup" disguised as user value | ⚠ Borderline → ✓ Acceptable | Risk: 8 stories that look like CI/Docker/scaffolding could read as technical milestones. **Mitigation:** the architecture's AR1/AR25 explicitly mandates "project initialization is the first implementation story" — this work MUST happen first; the user-value framing (installable artifact + OSS-ready docs) is the correct lens |
| Story sizing | ✓ | 8 stories, each sized for a single dev-session; no story spans more than 2 modules |
| Forward dependencies | ✓ None | 1.1 → others; 1.7 → 1.8; rest parallel |
| Database/entity creation | N/A | No tables in Epic 1; correct — tables land in Epic 3 (Story 3.3) when first needed |
| Starter template story | ✓ | Story 1.1 IS the starter-template bootstrap (uv init + hexagonal layout); satisfies AR1/AR25 |
| AC quality (Given/When/Then) | ✓ | Every story has structured ACs |

#### Epic 2: Wishlist Authoring, Configuration & Credentials

| Check | Result | Notes |
|---|---|---|
| Epic title user-centric | ✓ | "Operator can declare what they're hunting" — clear value |
| Epic goal user outcome | ✓ | Operator authors wishlist, authenticates marketplaces |
| Standalone-valuable | ✓ | After Epic 2, operator can `validate-wishlist` + `login wallapop` + `login ebay` even before alerts work |
| Story sizing | ✓ | 11 stories; each focused on one schema/loader/CLI command |
| Forward dependencies | ✓ None | 2.1 → 2.2 → 2.3 → 2.4 (wishlist track); 2.5/2.6 parallel after 2.1; 2.7 after 2.5/2.6; 2.8 standalone; 2.9/2.10 parallel; 2.11 after 2.9/2.10. **Verified no forward refs.** |
| AC quality | ✓ | Comprehensive; covers happy path + error paths + edge cases (e.g., 2.8 tests TTY + non-TTY contexts) |
| File overlap with Epic 1 | ✓ Minimal | Epic 2 touches `domain/wishlist.py`, `domain/scope_guard.py`, `config/`, `cli/init_cmd.py`, etc. — distinct from Epic 1's surface |

#### Epic 3: Phase 1 — Continuous Marketplace Monitoring & Alerts

| Check | Result | Notes |
|---|---|---|
| Epic title user-centric | ✓ | Operator receives Telegram alerts — the daily case |
| Epic goal user outcome | ✓ | "Operator receives Telegram alerts ... container-aware split renders when LLM detects wrapper listing" |
| Standalone-valuable | ✓ | After Epic 3, Phase 1 alerts work end-to-end; user can opt into 4–8 week stabilization run |
| Story sizing | ⚠ → ✓ | 15 stories — largest epic. Each focused; no single story is too large. The size reflects Phase 1 actually being the largest deliverable surface. **Acceptable.** |
| Forward dependencies | ✓ None | 3.1 → 3.2 → 3.3; 3.4/3.5/3.7 parallel; 3.6 after 3.4+3.5; 3.8 standalone; 3.9 → 3.10; 3.11 → 3.12 → 3.13; 3.14 ties all together; 3.15 last |
| Database/entity creation timing | ✓ | Story 3.3 creates the Phase 1 tables (seen_listings, alert_snapshots, callbacks, wishlist_runtime_state, _meta) — exactly when first needed. **NO "create all tables upfront" anti-pattern.** Phase 2 tables deferred to Story 5.1 |
| AC quality | ✓ | Comprehensive; e.g., Story 3.11 has 6 AC blocks covering Direction A baseline, Direction E container split, escape correctness, markdown injection prevention, snapshot tests, and FR22 format-lock enforcement |
| Pure-domain enforcement | ✓ | Story 3.1 AC explicitly asserts `domain/` package imports nothing outside stdlib + pydantic + decimal + uuid + datetime + typing — exercised by adapter discipline lint (Story 1.2) |
| Adapter discipline | ✓ | Each adapter story (3.4, 3.5, 3.7, 3.9, 3.12) explicitly states which SDK it's allowed to import and asserts no other package imports it |

#### Epic 4: Operator Observability & Phase 1 Recovery

| Check | Result | Notes |
|---|---|---|
| Epic title user-centric | ✓ | "Operator can diagnose any issue without reading raw logs" |
| Epic goal user outcome | ✓ | NFR-P5/NFR-R6 MTTR is achievable from alerts + CLI alone |
| Standalone-valuable | ✓ | After Epic 4, Phase 1 is production-ready (recovery + observability complete) |
| Story sizing | ✓ | 9 stories; each focused on one CLI command or one lifecycle path |
| Forward dependencies | ✓ None | 4.1 → 4.2 → 4.3; 4.4/4.5/4.6/4.7 parallel; 4.8 standalone → 4.9 |
| AC quality | ✓ | Story 4.9 (crash/restart consistency) has explicit e2e test with kill -9 + audit-row count assertions |

#### Epic 5: Phase 2 — Autonomous Purchase with Safety Stack

| Check | Result | Notes |
|---|---|---|
| Epic title user-centric | ✓ | "Autonomous Purchase with Safety Stack" — frames the user outcome |
| Epic goal user outcome | ✓ | Operator opts entries into Phase 2 → receives Phase 2 alerts → taps Comprar → receives factual receipt with screenshot |
| Standalone-valuable | ✓ | After Epic 5, Phase 2 is releasable as v1.0; gates the Phase 2 trust transfer |
| Story sizing | ⚠ → ✓ | 18 stories — largest epic. Justified by Phase 2 being the safety-stack + autonomous-purchase deliverable, which is intrinsically more complex than Phase 1 (PRD's 12 FRs in FR23–34 + 4 NFRs in NFR-P2/NFR-S4/NFR-S5/NFR-M2/NFR-M3). Each story remains focused. **Acceptable.** |
| Forward dependencies | ✓ None | 5.1 → 5.2; 5.3 standalone; 5.4/5.5/5.6 after 5.1; 5.7 after 5.2–5.6; 5.8/5.9 after 5.7; 5.10 after 5.8/5.9; 5.11 after 4.1 (operational alert renderer foundation); 5.12/5.13 after 5.5; 5.14 standalone; 5.15 after 5.7; 5.16 after 5.8/5.9; 5.17 after 5.10/5.16; 5.18 after 5.17. **Verified.** |
| Database/entity creation timing | ✓ | Story 5.1 creates Phase 2 tables (`tap_events`, `transactions`, `phase2_smoke_tests`, `phase2_state`) just-in-time. **No upfront over-engineering.** |
| AC quality | ✓ | Story 5.7 (buy orchestrator composition) has 5 AC blocks covering 8 distinct failure scenarios including reconciliation tripped, UI check failed, marketplace error, timeout, screenshot missing, receipt mismatch, circuit already open at pre-flight |
| NFR enforcement gates | ✓ | Story 5.15 explicitly bakes the ≥ 90% coverage gate (NFR-M2) into CI; Story 5.14 wires the payment-rail lint (NFR-S5); Story 5.1 wires the append-only property test (NFR-S4) |
| Release-gate stories | ✓ | Story 5.17 (Telegram client variance + accessibility manual audits) and Story 5.18 (v1.0 tag + GHCR push) are explicit release gates before v1.0 |

### Epic Independence Validation

| Epic | Standalone after which epics? | Verified |
|---|---|---|
| Epic 1 | After itself | ✓ Delivers installable artifact + CI green |
| Epic 2 | After Epic 1 | ✓ Delivers wishlist authoring + auth flows |
| Epic 3 | After Epic 1+2 | ✓ Delivers Phase 1 alerts end-to-end |
| Epic 4 | After Epic 1+2+3 | ✓ Delivers operability for Phase 1 production |
| Epic 5 | After Epic 1+2+3+4 | ✓ Delivers Phase 2 + v1.0 release |

**No epic requires a later epic to function.** Each epic's user outcome is achievable using only its own work plus prior epics.

### Quality Assessment Documentation

#### 🔴 Critical Violations

**None.** No technical-milestone-disguised-as-user-value epics. No forward dependencies. No epic-sized stories that cannot be completed in a single dev session.

#### 🟠 Major Issues

**None.** All acceptance criteria use Given/When/Then format. All stories reference specific FRs/NFRs/ARs/UX-DRs. Database creation is just-in-time. No story depends on a future story.

#### 🟡 Minor Concerns

1. **Epic 1 thematic risk.** 6 of 8 stories in Epic 1 are infrastructure-shaped (uv scaffold, CI gates, Docker, configs, logging, CLI skeleton, rendering helpers, version subcommand). The user-value framing (installable artifact + GHCR image + OSS-ready docs) holds, but Epic 1's "user" is necessarily a developer/operator persona, not an end-user-running-the-product persona. This is a function of the architecture's constraint that project initialization is the first story (AR1/AR25). **Mitigation:** epics.md frames Story 1.5 (README/CONTRIBUTING/ROADMAP) as fork-user-facing value; Story 1.3 (GHCR image) is `docker pull`-able. **Not blocking; documented as a known shape.**

2. **Epic 3 size.** 15 stories — the largest single epic. Each story is focused but the cognitive load of tracking all Phase 1 dependencies is highest here. **Mitigation:** the within-epic dependency map (3.1 → 3.2 → 3.3 → adapters in parallel → 3.14 ties together → 3.15 tests) is straightforward; no story exceeds single-dev-session scope. **Not blocking.**

3. **Epic 5 size.** 18 stories — second largest. Justified by Phase 2's intrinsic complexity (safety stack + autonomous purchase + audit log + release gates). Each story is focused. **Not blocking.**

4. **Soft warning (already noted in UX section):** UX-DR27 (bilingual asymmetry) lacks a mechanical enforcement mechanism — relies on code review. **Not blocking.** Future-research story for a CI lint is reasonable post-v1.

5. **Some FR splits across epics are intentional but increase coordination surface.** 6 FRs (FR12, FR21, FR22, FR37, FR48, FR49) are split. Each split is documented with rationale in the FR Coverage Map. **Not blocking.**

### Best Practices Compliance Checklist (per epic)

| Epic | User value | Standalone | Story sizing | No forward deps | DB just-in-time | AC quality | FR traceability |
|---|---|---|---|---|---|---|---|
| Epic 1 | ✓ | ✓ | ✓ | ✓ | N/A | ✓ | ✓ |
| Epic 2 | ✓ | ✓ | ✓ | ✓ | N/A | ✓ | ✓ |
| Epic 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Epic 4 | ✓ | ✓ | ✓ | ✓ | N/A | ✓ | ✓ |
| Epic 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

**All 5 epics pass all 7 quality checks.**

**Assessment: Epic quality is implementation-ready.** Zero critical or major violations. Five minor concerns documented; none block implementation start. The epic structure correctly reflects the architecture's phased delivery + starter-template-first constraints without lapsing into technical-milestone anti-patterns.

## Summary and Recommendations

### Overall Readiness Status

# ✅ **READY FOR IMPLEMENTATION**

All four planning artifacts (PRD, Architecture, Epics & Stories, UX Design Specification) are present, complete by their own workflow validation, and mutually consistent. Cross-artifact traceability is 100% — every PRD FR is covered by at least one epic story; every UX-DR aligns with PRD intent and Architecture decisions; every Architecture decision has a corresponding implementation home in the epic structure. Implementation can begin immediately with Epic 1 Story 1.1.

### Findings Summary

| Severity | Count | Items |
|---|---|---|
| 🔴 Critical | **0** | None |
| 🟠 Major | **0** | None |
| 🟡 Minor | **5** | Epic 1 thematic shape (infrastructure-flavored stories); Epic 3 size (15 stories); Epic 5 size (18 stories); UX-DR27 bilingual asymmetry lacks mechanical enforcement; 6 FRs intentionally split across multiple epics |
| 📋 Blocking Open Questions | **0 for Phase 1 / 2 for Phase 2** | OQ3 (per-purchase TinyFish cost) + OQ6 (LLM language-register bias) — both block PHASE 2 enablement, not Phase 1 implementation start |

### Critical Issues Requiring Immediate Action

**None.** Zero critical issues. Zero major issues. The five minor concerns are documented but do not block implementation start.

### Recommended Next Steps

1. **Begin Epic 1 Story 1.1 — uv scaffold + hexagonal directory layout.** This is the architecture's explicit "first implementation story" (AR1/AR25). The adapter-discipline boundary (NFR-M1 launch blocker) is encoded in the directory layout and cannot be retroactively added. All subsequent work depends on this story being completed first.

2. **Track 2 Phase-2-blocking OQs as Epic 5 gating checklist items:**
   - **OQ3** (per-purchase TinyFish Browser cost) — measure on first 5 Phase 2 purchases; update NFR-C2 and customer-FAQ cost numbers before Phase 2 docs go public.
   - **OQ6** (LLM language-register bias for non-Castilian Spanish) — empirical audit on a fixed corpus before Phase 2 enables for any user beyond ifuensan.

   Neither blocks Phase 1 implementation. Both should be picked up during Epic 5's Phase 2 enablement window (per epics.md Epic 5 goal statement).

3. **Add 2 post-launch backlog items (not v1 blockers):**
   - **Future-research story:** CI lint for UX-DR27 bilingual asymmetry enforcement (asserts Telegram-bound strings are Spanish, English-bound strings are English). Currently relies on code review; mechanical enforcement is a post-launch enhancement.
   - **`config.yaml > telegram.locale` flag** for fork users wanting English Telegram strings. Already OQ-tracked in UX-DR27; not v1.

4. **Optional: produce a shareable PDF of `epics.md`** following the same template as `build_prd_pdf.py`. Useful if the project moves toward multiple contributors or fork-runner adoption.

### Pre-implementation Checklist

Before Epic 1 Story 1.1 begins, verify:

- [ ] **Tool availability.** `uv` ≥ latest, `python` ≥ 3.12, `docker` + `docker-compose`, `git`, GitHub account with GHCR write access (`ghcr.io/ifuensan/hardware-hunter`).
- [ ] **Secrets ready.** Gemini API key obtained, eBay developer credentials (App ID + Cert ID + Dev ID), Telegram bot created via @BotFather + chat ID captured. (These are needed for Epic 2 Story 2.6 and Epic 3 onwards; Epic 1 itself doesn't need them but blocking them at Epic 1 avoids stalls.)
- [ ] **GitHub Actions configured.** Workflow file scaffolding planned, `GITHUB_TOKEN` permissions confirmed for GHCR write.
- [ ] **Confidence in OQ defaults.** OQ1 (global auto-disable), OQ2 (strict ceiling for container detection), OQ4 (wishlist scale assumptions) — accept defaults for v1; revisit post-launch.

### Final Note

This assessment identified **0 critical issues, 0 major issues, and 5 documented minor concerns** across the four planning artifacts and their cross-artifact traceability. All minor concerns are inherent shape characteristics of the project (Phase 1 vs Phase 2 split, no-GUI scope, starter-template constraint) rather than gaps in planning. The planning phase is complete; implementation can begin.

The two blocking Open Questions (OQ3 + OQ6) gate Phase 2 enablement specifically — not Phase 1 implementation start. They're correctly scoped in `epics.md` as Epic 5 release-gate concerns and in the PRD's Open Questions register with explicit measurement-based resolution paths.

---

**Assessor:** Implementation Readiness skill (BMAD method, 2026-05-11)
**Project:** hardware-hunter
**Verdict:** ✅ READY FOR IMPLEMENTATION (Phase 4 — start with Epic 1 Story 1.1)
