# hardware-hunter

> **Status:** planning phase complete; implementation has not started.
> The README, CONTRIBUTING, and ROADMAP files mandated by the PRD (FR52, FR53, FR54) will land in **Epic 1 Story 1.5**. This file is a placeholder pointing to the canonical planning artifacts.

A self-hosted personal agent that watches Wallapop and eBay.es for second-hand homelab parts (HDDs, RAM) against a YAML wishlist, with optional autonomous purchase via a non-bypassable Telegram tap.

## Scope

This is a personal monitoring tool — not a "Wallapop scraper" and not an arbitrage tool. Wallapop and eBay.es only for v1. Arbitrage / resale-margin features are explicitly out of scope and structurally prevented per the PRD's (c3) scope contract.

## Planning artifacts

The complete BMAD planning workflow has been executed. Implementation begins with **Epic 1 Story 1.1** (uv scaffold + hexagonal directory layout).

| Artifact | Path |
|---|---|
| Product Requirements Document | [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md) ([PDF](_bmad-output/planning-artifacts/prd.pdf)) |
| Architecture Decision Document | [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md) |
| UX Design Specification | [`_bmad-output/planning-artifacts/ux-design-specification.md`](_bmad-output/planning-artifacts/ux-design-specification.md) |
| Epic & Story Breakdown (5 epics, 61 stories) | [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md) |
| Implementation Readiness Report | [`_bmad-output/planning-artifacts/implementation-readiness-report-2026-05-11.md`](_bmad-output/planning-artifacts/implementation-readiness-report-2026-05-11.md) |

Supporting inputs that fed the PRD:
- [`_bmad-output/planning-artifacts/prfaq-hardware-hunter.md`](_bmad-output/planning-artifacts/prfaq-hardware-hunter.md) — Working Backwards PRFAQ
- [`_bmad-output/planning-artifacts/prfaq-hardware-hunter-distillate.md`](_bmad-output/planning-artifacts/prfaq-hardware-hunter-distillate.md) — distillate
- [`hardware-hunter-bmad-prompt.md`](hardware-hunter-bmad-prompt.md) — session kickoff

## License

MIT — see [LICENSE](LICENSE).

## Implementation status

Phase 4 (implementation) has not started. The next concrete action per the planning workflow is Epic 1 Story 1.1: bootstrap a uv-managed Python 3.12 package with the hexagonal directory layout (`domain/` / `interfaces/` / `orchestration/` / `adapters/` / `cli/` / `config/` / `observability/`) and adapter-discipline lint scaffolding.
