---
title: "PRFAQ Distillate: hardware-hunter"
type: llm-distillate
source: prfaq-hardware-hunter.md
created: "2026-05-09"
purpose: "Token-efficient context for downstream PRD creation"
---

# Project Identity

- **Concept type:** open-source scratch-your-own-itch tool. Single-developer (ifuensan). OSS release is a side benefit, NOT a go-to-market.
- **Customer:** ifuensan personally (Spanish homelabber). Open-sourced for other Spanish homelabbers who might find it useful. Adoption is a side effect, not the goal.
- **Primary marketplaces v1:** Wallapop + eBay.es ONLY. No others.
- **Stack (locked, not for PRD debate):** Hermes Agent v0.13.0 (Nous Research, MIT, 103k stars as of Apr 2026) + TinyFish via MCP. Runs on owned HPE DL160 Gen10 in Valencia colo. Telegram for alerts and approvals. LLM for listing evaluation (assumed Gemini Flash for cost reasons; not locked).
- **License:** MIT.
- **Repo:** `github.com/ifuensan/hardware-hunter` (personal GitHub, not org).
- **Project owner:** ifuensan personally. No team, no funding.

# Scope Contract (c3) — DO NOT RELITIGATE

## What v1 IS

- Personal homelab monitoring tool for ifuensan
- Reads a wishlist YAML of specific parts (HDDs, RAM)
- Watches Wallapop + eBay.es for matches against that wishlist
- Detects target component INSIDE container listings (HDD inside a NAS, RAM inside a mini-PC)
- Phase 1: alerts via Telegram, human clicks to view/buy
- Phase 2: autonomous purchase for the user's own use, with non-bypassable Telegram confirmation
- Open-sourced because other Spanish homelabbers might find it useful

## What v1 is EXPLICITLY NOT

- NOT an arbitrage / flipping tool
- NOT a business — no resale, no margin optimization, no Hacienda implications
- NOT multi-marketplace beyond Wallapop + eBay.es (multi-marketplace is **deferred** to "much later, after validating Wallapop+eBay.es first")
- Does not buy things outside the wishlist, even if the LLM thinks they're "good deals"
- The "I could flip this" temptation when alert fires is OUT OF SCOPE — goes in a future-research doc, not the roadmap
- No fully autonomous mode. No setting to bypass the Telegram tap.

## Pivot history (so it doesn't get re-relitigated)

- User initially picked "scratch own itch" then pivoted mid-conversation to "could become a flipping business" — caught and reverted to **(c3) phased**: ship homelab v1 first; arbitrage as future research direction in a SEPARATE repo, never v1 scope.
- User then picked "design marketplace-agnostic from day one" — pushed back HARD as scope explosion (5+ adapters, jurisdictions, payment rails, languages); user reverted to **Wallapop + eBay.es only for v1**, multi-marketplace deferred.

# Phased Product Definition

## Phase 1 — alerts only (ships first)

- Wishlist YAML → marketplace polling (cron) → LLM listing evaluation → Telegram alerts
- Telegram alert content: photo, price, seller location, one-line LLM take on listing authenticity, link to listing
- User reads alert and decides; agent never buys
- Container detection: hidden-component listings surface alongside direct matches
- Seen-listings dedup via SQLite store

## Phase 2 — autonomous purchase (ships ~4–8 weeks after Phase 1 stabilizes)

- Same alert flow + two extra Telegram buttons: *Buy* / *Skip*
- Tapping *Buy* → agent completes purchase via marketplace's protected payment rail
- Per-wishlist-entry opt-in (Phase 2 disabled by default)
- Per-entry max prices cap blast radius
- Confidence thresholds can require manual review for low-confidence matches
- Phase 2 enabled per entry only after the user has watched Phase 1 alerts long enough to trust them (typically several weeks)

# Requirements Signals (must land in PRD)

## Wishlist & matching

- **YAML wishlist schema:** `manufacturer`, `model`, `ref`, `max_price_solo` (€), `max_price_in_device` (€), `type` (hdd|ram), `keywords[]`, `container_keywords[]`. Lists kept under 100 entries.
- **Per-SKU two-tier pricing:** `max_price_solo` for standalone listings, `max_price_in_device` for the part hidden inside a larger item.
- **Container detection:** when a listing's title/description suggests a wrapper (NAS, mini-PC, workstation), evaluate whether the wanted SKU is inside.
- **No off-wishlist alerts.** Agent does not surface "interesting" listings the user didn't ask for.
- **No arbitrage fields.** Schema must NOT have `expected_resale_value`, `min_margin_percent`, or `current_market_price`. Adding any requires schema migration visible in code review.

## LLM evaluation

- **Confidence-level prompt.** LLM returns confidence with each evaluation; borderline matches surface as low-confidence alerts.
- **Wishlist-anchored prompt.** Asks "does this listing match a wishlist entry?" not "is this a good arbitrage opportunity?"
- **One-line take in alert** on whether the listing actually matches what it claims (e.g., "photos show a real WD Red, not a green; serial visible").

## Telegram interaction

- Phase 1: skip / snooze buttons on each alert.
- Phase 2: buy / skip buttons on each alert (only when Phase 2 is enabled for that wishlist entry).
- **Non-bypassable confirmation gate.** No autonomous mode without per-purchase tap.

## Phase 2 guardrails

- **Platform-protected payment rails only** (Wallapop Pay, eBay checkout). NEVER Bizum or transferencia.
- **Fail-closed UI element checks.** Refuse to buy unless 100% of expected UI elements are present.
- **Per-purchase circuit breaker.** N consecutive Phase 2 buy failures → autonomous mode auto-disables, Telegrams the user.
- **Per-entry Phase 2 toggle.**
- **Per-entry max prices.** Hard ceiling on Phase 2 spend per entry.
- **Per-entry confidence threshold.** Low-confidence matches require manual review even when Phase 2 is enabled.
- **Cross-source price reconciliation at buy time.** Re-fetch listing via the OTHER path (TinyFish if API was used, API if TinyFish was used) and compare prices. Disagreement beyond small tolerance → fail closed, ping user.
- **Receipt-vs-alert reconciliation.** Diff alert price vs marketplace receipt price after every Phase 2 purchase. Mismatch → high-priority Telegram alert + globally auto-disable Phase 2 across all entries (note: user flagged this as potentially per-entry instead — TBD in PRD).
- **Daily Phase 2 synthetic smoke test.** Simulates Phase 2 alert against a non-existent SKU with known price; verifies parsing matches independent fetch. Drift → Phase 2 auto-disables.

## Audit log

- **Append-only SQLite log per Phase 2 purchase**, three artifacts:
  - **Alert snapshot:** listing URL, title, description, photo hashes (perceptual hash), price, wishlist entry matched, LLM evaluation + confidence level, Phase 2 settings active at the time.
  - **User tap event:** Telegram message ID, button pressed (Buy / Skip / Snooze), timestamp.
  - **Marketplace transaction:** receipt ID (Wallapop Pay reference, eBay order number), price actually paid, screenshot of confirmation page (TinyFish Browser already captures this).
- All local; no remote logging, no telemetry. User = data controller, hardware-hunter = processor.

## Architecture

- **Two-path Wallapop adapter:** unofficial API primary + TinyFish Search/Fetch fallback. Either path can carry Phase 1 alone.
- **eBay.es adapter:** official eBay API.
- **Adapter discipline (v1 LAUNCH BLOCKER).** Hermes and TinyFish wrapped behind `PageFetcher` / `BrowserSession` (or equivalent) interfaces. Direct imports from business logic = launch blocker.
- **Phase 2 integration tests** against recorded marketplace fixtures.
- **Wallapop long-lived sessions with manual re-auth.** No silent automated re-login (anti-bot risk).

## Operational

- **Single docker-compose** for installation.
- **README** with example wishlist entries for common HDD and RAM models.
- **CONTRIBUTING.md** with explicit "no arbitrage PRs" rule and pointer to future-research-repo path.
- **ROADMAP.md** explicitly mentioning future-multi-marketplace direction + future arbitrage repo as separate paths + "C&D-induced sunset" as a documented possible end state.

## Repository hygiene (legal-driven)

- No Wallapop trademarks, logos, or proprietary terms in titles, package names, or domain.
- README positions hardware-hunter as a "personal monitoring tool," NOT a "Wallapop scraper." Wording matters.
- Adapter file names use marketplace names only where strictly necessary.

# Differentiators vs Existing Tools

- **vs Tatuck/wallapop-scraper (closest competitor):** Tatuck is arbitrage-focused (LLM evaluates for resale value); hardware-hunter is personal-wishlist-focused. Different products with different scope.
- **vs other Wallapop bots (wallabot, Walla-Bot, davertor, nadiamoe, Apify):** they're keyword-alert engines without container detection, LLM evaluation, eBay.es coverage, or Phase 2.
- **vs Wallapop's own saved searches (the minimum viable alternative):** saved searches don't catch container listings, don't reason about per-SKU price ceilings, don't verify listing-vs-claim, and don't unify across marketplaces.
- **The four-bullet differentiator pitch:** specific-model wishlist with per-SKU price ceilings; container detection; opt-in Phase 2 autonomous purchase via protected payment rails; eBay.es coverage alongside Wallapop.

# Cost Model

- **Hosting:** €0 if running on existing homelab box; ~€3–5/month on a small VPS.
- **LLM tokens (Phase 1):** ~50 wishlist entries × ~10 candidates/day × ~500 tokens/eval = ~3M tokens/month. Gemini Flash ~$0.075/M input ≈ <€1/month. GPT-4o ≈ a few €/month.
- **TinyFish:** Search/Fetch are free at Phase 1 volumes (5 req/min, 25 URLs/min). Browser is credit-based (Phase 2 only) — estimated cents per purchase, not measured.
- **Telegram:** free.
- **Total Phase 1:** €3–6/month VPS, free on existing hardware.
- **Phase 2:** adds cents per actual purchase, not per alert.
- **Worst case if TinyFish free tier disappears:** ~€10/month Phase 1; €0.50–1/purchase Phase 2.

# Competitive Intelligence

- **Tatuck/wallapop-scraper:** Python + unofficial Wallapop API + Gemini 2.0 Flash for resale valuation. Closest competitor in spirit; different framing (arbitrage). Still on GitHub as of May 2026.
- **ZebraBot (zebrabot.es):** commercial Wallapop automation service in Spain, has run for years openly. Not OSS. Useful as a precedent that platforms enforce via account ban, not legal escalation.
- **Existing OSS Wallapop bots** (wallabot, Walla-Bot/miqueasmd, davertor's scraper, nadiamoe/wallabot): all alert-only, no LLM evaluation, no eBay.es coverage, no autonomous purchase, no container detection.
- **Apify Wallapop Scraper, ScrapingBee:** SaaS scraping APIs. No domain-specific evaluation; pay-per-call.
- **Wallapop saved searches:** the real "minimum viable alternative." Free, native, but no container detection / per-SKU pricing / cross-claim verification / cross-marketplace.

# Market Context (verified as of May 2026)

- DDR4 32GB kits jumped from $60–90 (Oct 2025) to $150–180+ (Q1 2026). Tom's Hardware RAM index.
- DDR5-6000 32GB rose ~$120 to ~$410 May–Dec 2025.
- Q2 2026 DRAM +63% / NAND +75% on top of Q1 ~95% jumps. Samsung "no stock." (IDC, Team Group GM)
- DRAM/NAND shortages projected through Q4 2027.
- Spanish second-hand market = rational sourcing channel for homelabbers.

# Legal Posture

- **Wallapop ToS (rev. Apr 2026)** explicitly forbids scraping/bots. Realistic enforcement is account ban, not legal action.
- **Customer FAQ position:** acknowledge ToS forbids it, recommend "use a Wallapop account you'd be willing to lose," recommend secondary account dedicated to monitoring + approved purchases.
- **C&D contingency:** comply, don't fight. Solo maintainer can't litigate. Read carefully, assess scope, comply with reasonable scope (rename, archive, code removal). MIT-licensed forks survive any takedown.
- **Spanish courts have generally permitted scraping of public data** (cited generically in customer FAQ; STS 572/2012 was kept in Stage 2 coaching notes but dropped from final FAQ for fact-check safety).
- **RGPD posture:** all data local, no telemetry. User = data controller. Sellers' publicly posted data processed only for the transaction.
- **Hacienda / tax integration:** out of scope. Personal use only by (c3).

# Walk-Away Triggers (for maintainer planning)

- **Personal-use trigger:** ifuensan stops using hardware-hunter for 3+ consecutive months for own homelab.
- **Technical-debt trigger:** 3 consecutive failed patch attempts on a marketplace break (~10 hours each, ~30 hours sunk).
- **Sustained burden trigger:** average > 20 hours/month for 3+ consecutive months.
- **Legal trigger:** any cease-and-desist arrives → comply, archive, allow forks.
- **Stack trigger:** Hermes or TinyFish breaking change whose migration cost exceeds remaining personal value.
- **Walk-away ≠ silent abandonment:** final commit pinning deps to known-working versions, README addendum saying "actively unmaintained as of [date], forks welcome," repo archived with pointer to any fork carrying on.

# Maintenance Burden Estimate

- **Steady state:** ~4–8 hours/month (deps, version bumps, occasional bugs, log monitoring, prompt revision).
- **Spike:** 15–30 hours per marketplace break. Historical pattern: 2–4 breaks/year.
- **First 6 months post-launch:** ~2× steady state.

# Stack Risk Contingencies

## Hermes Agent (MIT, v0.10 Apr 2026)

- Critical bug → pin to last known-good version; ship release with the pin.
- Breaking API change → migrate if a single-dev evening absorbs it; otherwise stay pinned, fork-with-patch for security only.
- Stagnation → fine, we use core agent + cron + memory + clarify primitives; pinned operation is sustainable.
- Project abandonment by Nous Research → MIT, fork.

## TinyFish (commercial, free Search/Fetch + paid Browser)

- Free tier disappears or tightens → Phase 1 cost ~€0 → ~€10/month worst case.
- Pricing change on Browser → Phase 2 cents → maybe €0.50–€1/purchase. Trivial vs deal value.
- API change or service shutdown → swap behind `PageFetcher` / `BrowserSession` interfaces to Playwright self-hosted, Browserbase, or Apify. Days, not weeks.
- Aggressive deplatforming → Playwright self-hosted is the bare-metal fallback, runs on the user's existing box.

# Open Questions / Unknowns

- **Wallapop session persistence strategy** — flagged in kickoff doc, escalated by Q1 internal. Cookie strategy + re-auth UX needs concrete design.
- **Realistic per-purchase TinyFish Browser cost** — estimated "cents," not measured. Verify before Phase 2 docs go public.
- **Wishlist scale assumptions** (~50 entries, ~10 candidates/day, ~3M tokens/month) — guessed. Validate with first month of personal use.
- **Per-marketplace adapter break frequency** (estimated 2–4/year) — could be higher if anti-bot tightens.
- **Language-register bias** (formal Castilian vs Catalan/regional Spanish/Basque) — empirically unknown. Could systematically affect non-Castilian sellers. Defer to accuracy dashboard.
- **Receipt-vs-alert reconciliation: global Phase 2 auto-disable vs per-entry?** Currently captured as global; user flagged option to make per-entry. TBD in PRD.
- **Container "worth it" decision criterion** — open kickoff question.
- **Web backend choice** (Firecrawl vs SearXNG) — open kickoff question.
- **agentskills.io publication** for Hermes ecosystem visibility — open kickoff question.

# Resource & Timeline Estimates

- **Phase 1 (alerts only):** ~3–5 weeks of evening engineering (single experienced developer). Doesn't include Wallapop unofficial-API discovery (could add a week).
- **Phase 2 (autonomous purchase with all guardrails):** ~4–8 additional weeks.
- **Total to ship everything the customer FAQ promised:** ~3 months of solid evening work. Lower bound slips ~50% in practice if Phase 2 buy flow stability is as hard as Q1 stated.
- **What we say no to in v1:** any side-project consuming the same evening hours, multi-marketplace expansion, polish, dashboards, web UI, accuracy reporting (all wait until after the first real Phase 2 purchase).

# Verdict — Actionable Items for PRD

## Forged in steel (use as-is in PRD)

- (c3) scope contract; press release narrative; container detection differentiator; Phase 2 guardrail stack; legal posture; adapter discipline; honest framing throughout.

## Needs more heat (PRD must develop further)

- Real-world accuracy data path → accuracy dashboard plan
- LLM bias empirical audit (esp. language register for Spain)
- Wallapop session persistence: concrete cookie + re-auth UX
- Wishlist scale assumptions: validate with first month of personal use
- TinyFish Browser per-purchase cost: measure before docs are public
- ROADMAP.md and CONTRIBUTING.md: WRITE before v1 ships, not just promise

## Cracks (PRD must address explicitly, not skip)

- **Silent Phase 2 misbehavior** (Q9): unique downside of automating purchases. Wrong-but-internally-consistent values bypass structural guardrails. Three mitigations committed (cross-source reconciliation, receipt-vs-alert diff, daily smoke test). **PRD recommendation:** dedicated section for "silent failure modes," not a sub-bullet of Phase 2 testing.
- **Wallapop ToS exposure:** project lives at platform's pleasure; single C&D could end public release. **PRD recommendation:** ROADMAP.md should explicitly name "C&D-induced sunset" as documented end state.
- **Hidden-component detection structurally unverified at launch:** headline differentiator with no real-world data. **PRD recommendation:** accuracy dashboard is a launch-week priority, NOT a fast-follow.
- **Solo-maintainer sustainability:** small contributor pool (Spanish dev homelabbers). **PRD recommendation:** make contribution paths absurdly low-friction; CONTRIBUTING.md names three explicit invitation categories (example wishlists, prompt improvements, Wallapop selector patches).

## PRD priority order (verdict recommendation)

1. **Phase 2 silent-failure-mode design** (own section, not sub-bullet).
2. **Accuracy dashboard as launch-week priority**, not fast-follow.
3. **Wallapop session persistence strategy** (concrete cookie + re-auth UX).
4. **ROADMAP.md and CONTRIBUTING.md as launch artifacts**, not nice-to-haves.
5. **Empirical LLM bias audit** before Phase 2 enables for any user.
