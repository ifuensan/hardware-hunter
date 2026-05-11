---
title: "PRFAQ: hardware-hunter"
status: "complete"
created: "2026-05-09"
updated: "2026-05-09"
stage: "5-verdict"
inputs:
  - hardware-hunter-bmad-prompt.md
  - "web research (Tom's Hardware RAM index 2026, IDC memory shortage 2026, Wallapop ToS rev. Apr 2026, ACES / arXiv 2508.02630, Hermes Agent v0.10, TinyFish, competitive scrapers: Tatuck/wallabot/Walla-Bot/davertor/Apify/ScrapingBee)"
---

# hardware-hunter: an open-source agent that finds the exact second-hand homelab parts you want — even when they're hidden inside someone else's listing.

## Catches the listings you'd buy if you saw them in time.

**Valencia, [Launch Date]** — Good second-hand listings on Wallapop and eBay.es vanish in about four hours, which means a homelabber hunting for a specific HDD or RAM kit either checks every twenty minutes or accepts that the best deals will always be gone. **hardware-hunter**, released today as an open-source project, watches both marketplaces continuously and sends a Telegram alert the moment a real match against a wishlist appears — including the listings where the part you want is hiding inside something else.

Twenty minutes of every day, gone — refreshing the same searches on the same two sites, watching for the WD Red at a fair price or the ECC RAM kit that doesn't list for double its real value. By the time a good listing surfaces, ten other people have already messaged the seller. The worst losses aren't even visible: a "NAS Synology DS220 con discos" gets sold for the price of the empty enclosure because the seller doesn't realize the drives inside are worth more, and a homelabber who would have happily paid twice that price never even saw it.

With hardware-hunter running, the manual refresh disappears. A short YAML describes the parts a homelabber wants — manufacturer, model, max price — and the agent takes over the watch on Wallapop and eBay.es. When a match appears, a Telegram message arrives within minutes with the photo, the price, a one-line take on whether the listing is real, and a link straight to the seller. The hidden-component listings — the underpriced NAS, the mini-PC with the right RAM inside — surface alongside the obvious ones. Once you've trusted the alerts for a while, an opt-in mode lets the agent itself make the purchase on your approval, so you don't lose a deal because you were in a meeting when it appeared.

> "I missed one too many deals because I was at work — and one too many because the part I wanted was buried in someone else's listing. The fix turned out to be small enough to share."
> — ifuensan, Creator

### How It Works

Setup is a single repository clone and a configuration file. A homelabber installs hardware-hunter on a box they already run — a NAS, a homelab server, a small VPS — and creates a Telegram bot in a couple of minutes.

The wishlist lives in a small YAML file. Each entry names the part (manufacturer, model, reference) and two ceilings: the maximum price worth a buy as a standalone listing, and the maximum price worth a buy when the part is hidden inside a larger item like a NAS or mini-PC. Twenty entries cover most homelab refresh cycles.

From there, the workflow is passive. The agent watches Wallapop and eBay.es continuously. When a listing matches a wishlist entry — directly or as a hidden component — a Telegram message arrives with the photo, price, seller location, a one-line note on whether the listing matches what it promises, and a link straight to the seller. With autonomous-purchase mode enabled, the same alert offers a *Buy* button that completes the purchase via the marketplace's own payment rail. Nothing is ever bought without an explicit tap — there is no fully autonomous mode.

### How to Participate

hardware-hunter is released under the **MIT** license at **github.com/ifuensan/hardware-hunter**. Installation is documented in the README: clone the repository, copy `.env.example`, fill in a Telegram bot token and the marketplace credentials, write a YAML wishlist (the repository ships with example entries for common HDD and RAM models), and start the agent with a single docker-compose command. A first alert typically arrives within hours of the first wishlist entry being added.

Phase 2 — autonomous purchase with Telegram confirmation — is disabled by default and is enabled per wishlist entry once a homelabber has watched the alerts long enough to trust them.

Contributions are welcome: example wishlist entries for common homelab parts, prompt improvements for the listing-evaluation step, and bug reports against Wallapop's anti-bot evolution all live as standard GitHub pull requests and issues. The roadmap, including a future research direction on adapting hardware-hunter to non-Spanish marketplaces, is published at **github.com/ifuensan/hardware-hunter/blob/main/ROADMAP.md**.

---

## Customer FAQ

### Q: How is this actually different from Tatuck's wallapop-scraper or the half-dozen existing Wallapop monitoring bots on GitHub? They've been around for years.

A: The existing Wallapop bots — wallabot, Walla-Bot, davertor's scraper, and the rest — are alert engines for keyword searches: they ping when a new listing matches "WD Red" or "DDR4 32GB," and the user decides. They work, and for many people they're enough. Tatuck's wallapop-scraper is the closest in spirit — it uses Gemini to estimate resale value — but it's an arbitrage tool aimed at flippers, not a personal wishlist tool. None of them combine the four things hardware-hunter does:

1. **A specific-model wishlist with per-SKU price ceilings.** The YAML names exact references (manufacturer, model, ref) and a "buy below" price for each — so the alerts are *the part you actually want at the price you'd actually pay*, not a generic keyword match.
2. **Container detection.** A second price ceiling for "this part hidden inside a larger item" lets the agent flag the NAS, mini-PC, or workstation listing where the seller has underpriced what's inside. None of the existing bots do this.
3. **Phase 2: opt-in autonomous purchase via the marketplace's protected payment rail**, gated by Telegram confirmation. None of the existing tools cross the line from alert to purchase.
4. **Coverage of eBay.es alongside Wallapop.** Most existing bots are Wallapop-only — but eBay.es often surfaces server-class hardware that never appears on Wallapop, and missing one doubles the blind spots a homelabber accepts.

If a homelabber's needs are covered by keyword alerts on saved searches, the existing tools are fine. The case for hardware-hunter is wishlist precision, container detection, two-marketplace coverage, and not losing a deal because you were in a meeting.

### Q: Wallapop already has saved searches with push notifications, and eBay has saved-search alerts too. Why do I need a whole self-hosted agent for this?

A: Saved searches work great for "ping me when 'WD Red' shows up under €X" and a homelabber whose hunt fits that pattern should keep using them. They don't, however, do three things hardware-hunter does:

- **Match listings where the part is hidden inside something else.** A saved search for "WD Red 4TB" never sees "Synology DS220 con discos" — but that's often where the real deal is.
- **Reason about price *per specific model*.** Saved searches filter by a price range; they don't know that 60€ for an HGST He10 14TB is a steal but normal for a WD Red 4TB. A YAML wishlist with per-SKU ceilings does.
- **Verify the listing matches its claim.** The one-line take — *"photos show a real WD Red, not a green; serial visible"* — saves a homelabber from chasing a listing whose photo turns out to be a stock catalog image.

Phase 2 then crosses the line saved searches don't: with explicit Telegram approval per buy, the agent makes the purchase, so a four-hour deal isn't lost because nobody was awake to tap.

### Q: Wallapop's terms of service forbid scraping and bots. Realistically, will my account get banned for running this?

A: The ToS forbids automated access. The realistic risk is platform-side account termination (not legal action — Spanish courts have generally permitted scraping of public data). hardware-hunter mitigates by polling at human-volume rates, running listing fetches through stealth Chromium when the unofficial API is blocked, and never doing mass scraping or unattended purchases. Recommended: run with a Wallapop account you'd be willing to lose, not your primary trading account.

### Q: This is a one-person, scratch-your-own-itch OSS project. If you stop using it next year, what happens to my homelab's monitoring?

A: hardware-hunter is self-hosted, MIT-licensed, and has no remote backend that can disappear — installs keep working as long as the marketplaces don't break compatibility. If active maintenance stops, the realistic failure mode is "Wallapop or eBay.es changes something and nobody patches the adapter." Three things mitigate that:

- **MIT + small codebase.** Anyone can fork and patch a marketplace adapter; the code is small enough to read in an afternoon.
- **Marketplace fragility is community-surface, not single-developer-surface.** Whoever uses this will need to keep the adapters working — that's a normal OSS contribution path.
- **Saved searches and the existing alert bots remain as fallback.** A homelabber whose install dies isn't worse off than they were before installing.

Honest answer: this can become unmaintained. The trade-off is that "self-hosted, MIT, no SaaS lock-in" is the cleanest one-person-project risk profile you can get. If long-term continuity matters more than wishlist precision and container detection, hardware-hunter isn't the right tool.

### Q: Wallapop's unofficial API breaks every few months and they're tightening anti-bot. What's my realistic experience running this six months from now?

A: The unofficial API does break — historically every few months when Wallapop ships changes. The realistic six-month experience:

- **Two-path fetching.** Primary path: the unofficial API. Fallback path: TinyFish's free Search/Fetch endpoints against the public web pages. Either path can carry Phase 1 alone.
- **eBay.es is independent.** A Wallapop break doesn't kill eBay.es monitoring; the official eBay API is stable. Half-degraded is still useful.
- **Open risk:** if both Wallapop paths break simultaneously, monitoring degrades or stops on Wallapop until the adapter is patched — days to weeks depending on the break.

Honest answer: expect a couple of break/patch cycles a year, expect Phase 2 buy flows to be the most fragile part (UI selectors change), and expect eBay.es to be more stable than Wallapop. If you can't tolerate any downtime, hardware-hunter isn't the right fit.

### Q: What does this actually cost to run per month — LLM tokens, hosting, TinyFish credits, everything?

A: Phase 1 monthly cost is dominated by hosting, not by LLM tokens. Concrete breakdown:

- **Hosting:** €0 if running on an existing homelab box; ~€3–5/month on a small VPS.
- **LLM tokens:** A wishlist of ~50 entries with ~10 candidate listings/day at ~500 tokens per evaluation is ~3M tokens/month — well under €1/month with Gemini Flash, a few euros with a more expensive model.
- **TinyFish:** Search/Fetch are free at Phase 1 volumes. TinyFish Browser (Phase 2 only) is credit-based and bills per actual purchase, not per alert.
- **Telegram and marketplaces:** free.

Realistic total: **€3–6/month for Phase 1 on a VPS, effectively free on existing hardware.** Phase 2 adds cents per purchase. The first fair deal caught usually covers a year of running costs.

### Q: The "hidden-component" detection is your headline feature. How often does the LLM get it wrong — flagging a NAS as "has WD Reds inside" when it doesn't, or missing one that does?

A: Honest answer: we don't have real-world numbers yet — hardware-hunter is launching, not running with users for a year. What we can say:

- **Two failure modes:** false positives (alert on a wrapper that doesn't contain the part) cost a dismissive tap; false negatives (miss a wrapper that does) are invisible and the more painful.
- **What the LLM sees:** title, description, photos, sometimes a spec list. It can be wrong when photos don't match the description, when sellers don't disclose contents accurately, or when the part is described generically.
- **Mitigations:** the evaluation prompt asks the LLM to return a confidence level and surfaces borderline matches as low-confidence alerts. Repeated alerts on the same listing are deduped.
- **Baseline:** saved searches catch 0% of hidden-component listings by definition. The bar isn't "perfect" — it's "better than nothing."

Plan: publish a community-collected accuracy dashboard once there's enough usage to compute it honestly. Until then, treat the feature as best-effort, not a guarantee.

### Q: Phase 2 buys things autonomously after one tap. What happens if the agent spends 200€ on a NAS and the drives inside turn out to be junk, missing, or different from what the listing showed? Who eats the loss?

A: The user eats the loss — hardware-hunter offers no insurance. What stands between the user and that loss:

- **Platform-protected payment rails only.** Phase 2 uses Wallapop Pay and eBay checkout — both with buyer protection for items that arrive empty, broken, or materially misrepresented. The agent never uses Bizum, transferencia, or any rail without dispute resolution.
- **The user's tap is still the decision.** The Telegram alert shows the photo, listing text, one-line LLM take, and price. The agent doesn't bypass judgment — it executes a buy the user already authorized with the same information a human buyer would have.
- **Configurable guardrails.** Per-entry max prices cap the blast radius. Confidence thresholds can require manual review for low-confidence matches. Phase 2 can be disabled per-entry where ambiguity risk is high.

Honest answer: enabling Phase 2 is taking the same risk as a fast manual purchase from your phone — except faster. The agent doesn't add risk; it removes the "I was at work" friction. If you wouldn't trust your own snap judgment on a 90-second purchase, don't enable Phase 2 for that entry.



---

## Internal FAQ

### Q: What's the hardest technical problem in v1 — and what's your contingency if it doesn't work?

A: The hardest problem in v1 is **Phase 2 buy flow stability across Wallapop and eBay.es**. Listings can be read with two-path resilience (unofficial API → TinyFish fetch fallback). But buying drives the actual checkout UI — selectors change, login flows change — and a regression is real money in the wrong place.

- **Wallapop's chat → buy flow** is the harder of the two: the seller has to be messaged, response timing varies, the "Reserved" mechanic interacts with the buy click. *Fail-closed* (refuse to buy unless 100% of expected UI elements are present) is mandatory.
- **eBay.es** *Cómpralo ya* is more structured but eBay's browser anti-bot is more sophisticated.
- **Contingency:** Phase 1 ships first and runs 4–8 weeks before Phase 2 is enabled. Phase 2 ships with integration tests against recorded fixtures, fail-closed defaults, and a per-purchase circuit breaker (N consecutive buy failures → autonomous mode auto-disables, Telegrams the user). If selector breakage outpaces patch cycles, Phase 1 stays the steady state. Honest trade-off, not failure.

Close second: **Wallapop session persistence** (open kickoff question). Mitigation: long-lived sessions with manual re-auth, not silent automated re-login.

### Q: Externally we tell users "use a Wallapop account you'd be willing to lose." Internally: what's our actual posture if Wallapop sends a cease-and-desist letter to the GitHub maintainer? Do we take the repo down, defend, or rename?

A: Realistic posture: **comply, don't fight.** A solo OSS maintainer can't litigate a Spanish marketplace, and the project's value isn't worth the legal exposure of pretending otherwise.

- **Most likely outcome: no letter at all.** Wallapop's normal enforcement is account ban, not legal action. Tatuck's wallapop-scraper remains publicly on GitHub; ZebraBot has run as a commercial Wallapop automation service in Spain for years — neither has faced public escalation. Probability of a C&D is low but non-zero.
- **If a C&D arrives:** read carefully, don't reply same-day, assess what's actually demanded (repo takedown, code removal, name change, trademark). Comply with reasonable scope. MIT-licensed forks already exist or appear within hours of an archive — the codebase doesn't die.
- **What we don't do:** publicly fight, name Wallapop in litigation, or bait them. The README positions hardware-hunter as a personal monitoring tool, not a "Wallapop scraper." Wording matters.
- **Repository hygiene:** no Wallapop trademarks, logos, or proprietary terms in titles, package names, or domain. Adapter file names use marketplace names only where strictly necessary. Reduces both the trademark complaint surface and the cost of a forced rename.

Honest answer: if a real letter arrives at a personal GitHub account, the project will comply and rebrand before it defends. Not heroic, but correct given the resource asymmetry.

### Q: Phase 2 executes purchases on the user's behalf. Under Spanish consumer law and RGPD, what evidence do we keep to defend against an "I never authorized this purchase" claim — from the user, from the seller, or from the platform?

A: Three pieces of evidence are persisted for every Phase 2 purchase, locally on the user's machine, in a timestamped append-only SQLite log:

- **The alert:** listing URL, snapshot (title, description, photo hashes, price), wishlist entry matched, LLM output + confidence level, Phase 2 settings active at the time.
- **The user's tap event:** Telegram message ID, button pressed (Buy / Skip / Snooze), timestamp. Telegram's own audit trail is a corroborating second source.
- **The marketplace transaction:** receipt ID (Wallapop Pay reference, eBay order number), price actually paid, screenshot of the confirmation page.

Defends against:

- **"I never authorized this" (from the user):** the alert + tap chain shows the exact authorization with the same listing data the user saw.
- **"You bought the wrong thing" (vs the seller):** the listing snapshot at purchase time is preserved even if the seller later edits or deletes it.
- **Platform dispute resolution:** the marketplace's own logs are primary; the local trail corroborates if the platform's logs are contested.

RGPD posture: the log lives entirely on the user's machine. No remote logging, no telemetry. Sellers' publicly posted data is processed only for the duration of the transaction; no profiling, no third-party sharing. The user is the data controller for their own log; hardware-hunter is the processor.

Out of scope for v1: tax/accounting integration (Hacienda) — personal-use purchases don't require it; commercial-volume use would be a (c3) scope violation.

### Q: Every alert that fires shows the user a listing they could flip for profit. (c3) said arbitrage is out of scope. What concretely stops the project from drifting there — code-level, not just intent?

A: Code-level mechanisms that prevent the shipped codebase from becoming an arbitrage tool:

- **Wishlist schema is structurally personal-use.** Fields: `manufacturer`, `model`, `ref`, `max_price_solo`, `max_price_in_device`, `keywords`, `container_keywords`. No `expected_resale_value`, `min_margin_percent`, or `current_market_price`. Adding any requires a schema migration visible in code review.
- **LLM evaluation prompt is wishlist-anchored.** "Does this listing match a wishlist entry?" not "is this a good arbitrage opportunity?" No codepath scores off-wishlist listings or ranks by margin.
- **No off-wishlist alerts.** The agent doesn't surface "interesting" listings the user didn't ask for.
- **Roadmap + CONTRIBUTING.md make arbitrage out-of-scope explicit.** PRs adding margin-based scoring or off-wishlist surfacing get closed with a pointer to the future-research repo. Arbitrage forks are welcome — under a different name.

What can't be prevented:

- **The maintainer personally flipping a caught listing.** Personal discipline, not product. The agent surfaced a fair-priced WD Red because the user wanted one; downstream behavior isn't enforceable.
- **Users forking and adding arbitrage.** MIT license — their right. Documented as the separate-repo path so projects stay differentiated.

Honest answer: the shipped product is structurally personal-wishlist by design. Drift requires a deliberate schema/prompt/code change visible in git history. (c3) is enforced by design, not promises.

### Q: The kickoff doc called this a weekend project. Walking through it honestly: how many engineering days to a working Phase 1, and how many more to Phase 2 with all the guardrails the customer FAQ committed to (confidence thresholds, per-entry max prices, per-entry Phase 2 toggle, dispute-evidence storage)?

A: The "weekend project" estimate was order-of-magnitude wrong. Realistic timelines for a single experienced developer working evenings/weekends:

- **Phase 1 (alerts only): ~3–5 weeks.** Wallapop unofficial-API adapter + TinyFish fetch fallback, eBay.es official-API adapter, YAML wishlist schema + parser, LLM evaluation with confidence levels, container-detection logic, Telegram bot with skip/snooze, SQLite seen-listings dedup, cron, docker, README + example wishlists. Doesn't include the time to make the Wallapop unofficial API behave consistently — could add a week.
- **Phase 2 (autonomous purchase with all customer-FAQ guardrails): ~4–8 additional weeks.** Wallapop chat-to-buy + Wallapop Pay (TinyFish Browser), eBay.es Cómpralo-ya, fail-closed UI checks, per-purchase circuit breaker, append-only SQLite audit log (alert + tap + transaction + photo hashes), Telegram Buy/Skip UI, per-entry Phase 2 toggle + max prices + confidence thresholds, integration tests against recorded fixtures, manual smoke tests with real small purchases.

Realistic total to ship everything the customer FAQ promised: **~3 months of solid evening work.** If Phase 2 buy flow stability is actually the hardest problem (per Q1), expect the lower bound to slip by ~50% in practice.

What we say no to: any side-project consuming the same evening hours, multi-marketplace expansion (deferred per (c3)), and any feature work outside customer-FAQ commitments before v1 ships. Polish, dashboards, web UI, and accuracy reporting all wait until after the first real Phase 2 purchase.

### Q: Realistically, how many hours/month to keep this alive once shipped? And what's the concrete trigger — not vibes, a trigger — that means you walk away from maintenance?

A: Realistic maintenance burden once Phase 2 has shipped and stabilized:

- **Steady state: ~4–8 hours/month.** Dependency updates, Hermes/TinyFish version bumps, one or two bug fixes, monitoring the audit log, occasional LLM prompt revision as listing patterns drift.
- **Spike: 15–30 hours when a marketplace breaks compatibility.** Historical pattern: 2–4 such breaks per year.
- **First 6 months post-launch: roughly double the steady-state.** Nothing is stable yet, contributor PRs flow, Phase 2 corner cases surface.

Concrete walk-away triggers (not vibes):

- **Personal-use trigger:** I stop using hardware-hunter for 3+ consecutive months for my own homelab.
- **Technical-debt trigger:** 3 consecutive failed patch attempts on a marketplace break (~10 hours each, ~30 hours sunk).
- **Sustained burden trigger:** average > 20 hours/month for 3+ consecutive months.
- **Legal trigger:** any C&D arrives. Per Q2: comply, archive, allow forks.
- **Stack trigger:** Hermes Agent or TinyFish ship a breaking change whose migration cost exceeds the project's remaining personal value.

What "walk away" means: final commit pinning dependencies to known-working versions, README addendum ("actively unmaintained as of [date], forks welcome"), repo archived with pointer to any fork carrying on. Not silent abandonment.

### Q: ACES research (WebConf 2026) showed VLM shopping agents have systemic position and sponsored bias. We claimed the deterministic-wishlist design sidesteps that. Is that actually true, or are there hidden bias surfaces in the listing-evaluation prompt that we haven't audited?

A: The deterministic-wishlist design sidesteps the **main** ACES biases — but not all bias surfaces. Honest audit:

**What the design eliminates structurally:**

- **Position bias.** The agent evaluates each listing in isolation against the wishlist; there's no "first result wins."
- **Sponsored content bias.** Wallapop and eBay.es don't have sponsored-listing slots like the ACES marketplaces did.
- **Open-ended price sensitivity.** Per-SKU `max_price_solo` and `max_price_in_device` ceilings come from the user, not the LLM.

**What it does NOT eliminate (unaudited surfaces):**

- **Photo-quality bias** — cleaner photos may get higher confidence than grainy ones for the same part.
- **Description-length bias** — verbose descriptions may signal "trustworthy" more than terse ones.
- **Language-register bias** — formal Castilian may be judged more "real" than informal Spanish or Catalan. Matters for a Spain tool.
- **Confidence-level calibration** — the LLM may be systematically over/under-confident in particular conditions.

**What bounds the blast radius:**

- User reviews every Phase 1 alert; explicit Telegram tap on every Phase 2 buy.
- Per-entry max prices cap any LLM mispricing.
- The customer-FAQ accuracy dashboard is the long-term audit instrument; until it exists, residual bias is best-effort.

Honest answer: structural claim sound (wishlist eliminates the biggest ACES biases). Empirical claim ("our prompt has no measurable bias") is currently unfounded — we haven't audited. Residual surfaces are known unknowns; the accuracy dashboard is the path to closing them.

### Q: Hermes Agent v0.10 dropped in April 2026 — 103k stars, MIT, but production-readiness for autonomous-purchase use cases isn't proven at scale. TinyFish's free tier could change tomorrow. What's the contingency if either has a critical bug, breaks the API, or stagnates?

A: Two stack dependencies, two contingency plans:

**Hermes Agent (MIT, v0.10 Apr 2026):**

- **Critical bug:** pin to last known-good version, raise upstream issue, ship a release with the pin. Steady-state hardware-hunter doesn't depend on cutting-edge Hermes.
- **Breaking API change:** if a single-dev evening absorbs it, migrate. If not, stay pinned; fork-with-patch for security updates only.
- **Stagnation:** fine. We use core agent + cron + memory + clarify primitives — pinned-version operation is sustainable.
- **Project abandonment:** MIT license. Fork is the answer; the codebase is small enough for small communities.

**TinyFish (commercial, free Search/Fetch + paid Browser):**

- **Free tier disappears or tightens:** Phase 1 cost ~€0 → ~€10/month worst case. Still cheap.
- **Pricing change on Browser:** Phase 2 cents-per-purchase → maybe €0.50–€1/purchase. Trivial vs deal value.
- **API change:** marketplace adapters wrap TinyFish behind `PageFetcher` / `BrowserSession` interfaces. Swap to Playwright self-hosted / Browserbase / Apify costs days, not weeks.
- **Service shutdown or aggressive deplatforming:** same swap path. Playwright self-hosted is the bare-metal fallback.

**What this means:**

- **Adapter discipline is mandatory.** Hermes and TinyFish are wrapped behind interfaces, never imported from business logic. Direct imports anywhere = v1 launch blocker.
- **User owns portable data.** Wishlist YAML, audit log SQLite, config — all standard formats, all on the user's machine. Stack swaps don't lose state.
- **Contingency, not paralysis.** Both deps are de-risked enough to not kill the project. Honest worry is timeline cost (swap = evenings) and momentum cost (no feature work that month), not feasibility.

### Q: What's the scenario you're most afraid of that we haven't talked about yet?

A: The scenario I'm most afraid of, that hasn't surfaced before: **a silent Phase 2 misbehavior — wrong price, wrong quantity, wrong listing — in a system nobody is watching closely.**

Mechanism: Wallapop or eBay.es ships a UI change that breaks an assumption at the *value* level, not the structural level. Example: the displayed price formatter changes from "1.234,56 €" to "1234.56 €" and the parser silently reads the second as 1.23 €. The alert shows the wrong price; the user taps Yes; the agent buys at the real price. The audit log is consistent.

Why it scares me: it's silent (all the guardrails assume the code knows when something is wrong); it scales badly (weeks of erroneous purchases before anyone notices); it blames the user (they tapped Yes; from the defensive-evidence perspective in Q3, they authorized it); it's the failure mode of an unmaintained project drifting silently incorrect while the maintainer is paying attention to other things.

Mitigations that actually address it:

- **Cross-source price reconciliation at buy time.** Before the agent fires checkout, re-fetch the listing via the *other* path (TinyFish if the API was used, API if TinyFish was used) and compare prices. Disagreement beyond small tolerance → fail closed, ping user.
- **Receipt-vs-alert reconciliation.** After every Phase 2 purchase, automatically diff the alert price against the marketplace receipt price. Mismatch → high-priority Telegram alert + auto-disable Phase 2 across all entries.
- **Daily Phase 2 smoke test.** A synthetic run against a non-existent SKU with a known price that verifies the agent's price parsing matches an independent fetch. Drift → Phase 2 auto-disables.

Honest answer: this is the scenario where the audit log defends the project legally but the user lost real money anyway. It's the unique downside of automating actual purchases — and it's why Phase 2 has more guardrails than any other part of the system.

---

## The Verdict

hardware-hunter survived the gauntlet. Honest assessment:

### Forged in steel

- **The (c3) scope contract** — personal-wishlist tool, scratch-own-itch, multi-marketplace deferred, arbitrage explicitly out of scope. Held through every internal pressure test. Structurally enforced (YAML schema has no arbitrage fields, LLM prompt is wishlist-anchored, no off-wishlist alerts), not promise-based.
- **Container detection as the differentiator.** Concrete, novel, easy to explain to a homelabber, structurally absent from every competing tool surveyed. The press release lands on this in three places without feeling repetitive.
- **The Phase 2 guardrail stack.** HITL Telegram tap, platform-protected payment rails only (Wallapop Pay / eBay checkout, never Bizum or transferencia), per-entry max prices, per-entry Phase 2 toggle, fail-closed UI checks, per-purchase circuit breaker, append-only audit log, cross-source price reconciliation, receipt-vs-alert reconciliation, daily synthetic smoke test. Comprehensive, defensible, and proportional to the blast radius.
- **The legal posture.** Comply-don't-fight, repository hygiene, secondary-account recommendation, ToS-honest framing in the customer FAQ. Pragmatic given solo-maintainer resource asymmetry.
- **Adapter discipline as architectural commitment.** Hermes and TinyFish wrapped behind `PageFetcher` / `BrowserSession` interfaces; never imported from business logic. Direct imports = v1 launch blocker. De-risks stack swaps and turns "what if X dies?" into days-not-weeks of work.
- **Honest framing throughout.** The customer FAQ tells some readers "use the existing simpler tools instead." The internal FAQ admits the empirical bias claim is unfounded. The "weekend project" estimate is openly called wrong. None of this is heroic — all of it is correct.

### Needs more heat

- **Real-world accuracy data for hidden-component detection.** No users yet, so structurally unverified at launch. The community accuracy dashboard is the long-term path; until then, the headline differentiator is best-effort. Build the dashboard early.
- **LLM bias empirical audit.** Structural claim sound; empirical claim openly deferred. Four residual surfaces flagged (photo quality, description length, language register, confidence calibration). Language-register bias matters specifically for a Spain tool — could systematically affect Catalan/regional Spanish/Basque sellers. Worth a focused audit before Phase 2 enables.
- **Wallapop session persistence strategy.** Flagged in the kickoff doc, escalated by Q1 ("close second" hardest problem), but never specified concretely. Cookie strategy + re-auth UX needs design before Phase 1 ships.
- **Wishlist scale assumptions.** ~50 entries, ~10 candidates/day, ~3M LLM tokens/month — all guessed. Validate with the first month of personal use before committing to the cost numbers in the customer FAQ.
- **TinyFish Browser per-purchase cost.** Estimated as "cents" but not measured. Confirm before Phase 2 documentation goes public.
- **ROADMAP.md and CONTRIBUTING.md.** Committed in Q4 (scope discipline) and Q8 (stack risk) — must be written, not just promised, before v1 ships. They're the visible enforcement of the (c3) contract.

### Cracks in the foundation

- **Silent Phase 2 misbehavior.** The Q9 scenario is the unique downside of automating actual purchases — wrong-but-internally-consistent values bypass every structural guardrail (the price-formatter example is real and exactly the kind of bug Spanish marketplaces would ship). Three mitigations committed (cross-source reconciliation, receipt-vs-alert diff, daily smoke test) — but the failure class is fundamental to Phase 2. **Recommendation:** dedicated PRD section for "silent failure modes," not just a sub-bullet of Phase 2 testing.
- **Wallapop ToS exposure is real.** The comply-don't-fight plan is correct but means the project lives at Wallapop's pleasure. A single C&D could end the public release. Forks survive (MIT) but momentum dies. **Recommendation:** the secondary-account recommendation in the customer FAQ is the right protective gesture; the ROADMAP.md should explicitly name "C&D-induced sunset" as a documented end state, not a surprise.
- **Hidden-component detection is structurally unverified at launch.** This is both the headline differentiator AND the feature with no real-world data. If accuracy is poor when users start running it, the "better than saved searches" pitch weakens fast. **Recommendation:** the accuracy dashboard isn't a fast-follow — it's a launch-week priority. Without it, the differentiator is a claim, not a fact.
- **Solo-maintainer sustainability over a multi-year horizon.** The walk-away plan is honest, but realistic OSS community formation around a Spanish-market personal tool is uncertain. The pool of potential contributors is small (Spanish dev homelabbers who want to contribute to a tool they personally use). **Recommendation:** make contribution paths absurdly low-friction — example wishlist contributions, prompt improvements, and Wallapop selector patches as the three explicit invitation categories in CONTRIBUTING.md.

### Recommendation

**Move forward.** The concept is structurally sound, the scope is disciplined, the legal posture is pragmatic, and the technical risks are managed. The "needs more heat" items are normal pre-PRD work, not blockers. The "cracks" are real but not deal-breakers — they're known risks that the PRD should address explicitly rather than skip past.

The PRD should focus, in priority order, on:

1. **Phase 2 silent-failure-mode design** (own section, not a sub-bullet of testing).
2. **Accuracy dashboard as a launch-week priority**, not a fast-follow.
3. **Wallapop session persistence strategy** (concrete cookie + re-auth UX).
4. **ROADMAP.md and CONTRIBUTING.md as launch artifacts**, not nice-to-haves.
5. **Empirical LLM bias audit** before Phase 2 enables for any user.

---

<!-- coaching-notes-stage-4 -->

## Stage 4 — Coaching Notes (internal, not part of the PRFAQ proper)

### Choices made
- All 9 internal questions: user picked option (A) on every single question. Pattern: (A) was consistently the cleanest 3-block structure (e.g., "what's eliminated / what's not / what bounds blast radius"). User confirmed architecture facts inline (Q5 eBay.es official API + Wallapop two-path; Q2 ZebraBot is commercial not OSS).
- Q1 (hardest tech problem): Phase 2 buy flow stability is the #1; Wallapop session persistence is close second. Contingency: 4–8 weeks of Phase 1 running before Phase 2 enabled, fail-closed defaults, per-purchase circuit breaker.
- Q2 (legal — C&D scenario): comply, don't fight. Repository hygiene (no Wallapop trademarks/logos in titles, package names, or domain). README positions tool as "personal monitoring," not "Wallapop scraper." If letter arrives: comply and rebrand before defend.
- Q3 (RGPD/consumer law evidence): three artifacts persisted locally per Phase 2 purchase (alert snapshot, tap event, marketplace transaction). Append-only SQLite log. User = data controller; hardware-hunter = processor.
- Q4 (scope discipline / arbitrage): YAML schema has no fields for arbitrage; LLM prompt is wishlist-anchored; no off-wishlist alerts; CONTRIBUTING.md/ROADMAP.md make arbitrage out-of-scope explicit. (c3) enforced by design, not promises.
- Q5 (timeline reality): Phase 1 ~3–5 weeks; Phase 2 ~4–8 additional weeks; total ~3 months evening work. Lower bound slips ~50% in practice.
- Q6 (maintenance burden): steady state ~4–8 hours/month, spike 15–30 hours per marketplace break (~2–4/year), first 6 months ~2x. Five concrete walk-away triggers (3-month personal-use stop, 30-hour technical-debt sink on a single break, sustained >20 hours/month for 3+ months, any C&D, breaking stack change). Walk-away ≠ silent abandonment.
- Q7 (LLM bias / ACES audit): structural elimination of position/sponsored/open-ended-pricing biases acknowledged. Four unaudited residual surfaces (photo quality, description length, language register esp. Castilian vs Catalan, confidence calibration). Empirical claim deferred to accuracy dashboard.
- Q8 (stack risk Hermes/TinyFish): two contingency plans. Adapter discipline (`PageFetcher` / `BrowserSession` interfaces wrapping TinyFish; never direct imports from business logic) is a v1 launch blocker. Worst-case TinyFish costs still cheap (~€10/month Phase 1, €0.50–1/purchase Phase 2). Self-hosted Playwright is the bare-metal fallback.
- Q9 (the question avoided): silent Phase 2 misbehavior — wrong-but-internally-consistent values bypass all structural guardrails (e.g., price formatter "1.234,56 €" → "1234.56 €" parsed as 1.23 €). Three new mitigations committed.

### Requirements signals surfaced (must land in PRD — additive to Stage 3 list)

- **Per-purchase circuit breaker:** N consecutive Phase 2 buy failures → autonomous mode auto-disables, Telegrams the user (Q1).
- **Fail-closed UI element checks:** Phase 2 refuses to buy unless 100% of expected UI elements are present (Q1).
- **Wallapop long-lived session strategy with manual re-auth** (no silent automated re-login) (Q1).
- **Repository hygiene rules:** no Wallapop trademarks, logos, or proprietary terms in titles/package names/domain. README positioning as "personal monitoring tool," not "Wallapop scraper" (Q2).
- **CONTRIBUTING.md** with explicit "no arbitrage PRs" rule and pointer to future-research-repo path (Q4).
- **ROADMAP.md** explicitly mentioning future-multi-marketplace direction + future arbitrage repo as separate paths (Q4).
- **Adapter discipline as a v1 launch blocker:** `PageFetcher` and `BrowserSession` (or equivalent) interfaces wrap Hermes and TinyFish; no direct imports from business logic (Q8).
- **Cross-source price reconciliation at buy time** (Q9).
- **Receipt-vs-alert reconciliation with global Phase 2 auto-disable on mismatch** (Q9).
- **Daily Phase 2 synthetic smoke test** (Q9).

### Trade-off decisions made
- **"Comply and rebrand before defend"** (Q2): accepted given solo-maintainer resource asymmetry. Not heroic, but correct.
- **Tax/accounting (Hacienda) integration** (Q3): out of scope. Personal use only by (c3) contract.
- **Phase 2 enabled only after 4–8 weeks of Phase 1 running** (Q1): adoption-friction trade-off accepted in exchange for stability.
- **Globally agressive Phase 2 auto-disable on a single mismatch** (Q9): aggressive but defensible. User flagged option to make it per-entry instead — currently captured as global; revisit if per-entry seems less drastic in practice.
- **Empirical bias audit deferred** (Q7): structural claims sound, empirical claims unfounded. Accuracy dashboard is the path.

### Honest unknowns flagged
- **Wallapop unofficial API behavior under stress** (Q5 acknowledged): could add a week to Phase 1 timeline.
- **Realistic per-purchase TinyFish Browser cost** (estimated "cents" but not measured) — committed to verify before Phase 2 docs are final.
- **Per-marketplace adapter break frequency** (estimated 2–4/year, historical pattern). Could be higher if anti-bot tightens.
- **Whether language-register bias** (formal Castilian vs Catalan/regional Spanish) actually affects LLM evaluation — empirically unknown, deferred to accuracy dashboard.

### Strategic positioning decisions
- The (c3) personal-wishlist framing is **not just a scope contract — it's a structural defense** against ACES-style biases AND against arbitrage drift AND against community backlash that flippers face. Used as positive product positioning, not just a constraint.
- Adapter discipline (Q8) doubles as defense against stack abandonment AND against marketplace lock-in.
- Self-hosting + MIT + portable user data is the durability story across every "what if X dies?" question.

### What this stage proved about the concept
- **Feasibility:** YES, with realistic ~3-month timeline. Not a weekend project.
- **Legal posture:** clear and pragmatic. Not heroic, but correct.
- **Scope discipline:** structurally enforced, not promise-based. (c3) holds.
- **Stack risk:** managed via adapter discipline. Both deps swappable in days, not weeks.
- **The fear that survives:** silent Phase 2 misbehavior — addressable via three concrete mitigations, but the failure class is unique to autonomous purchase and deserves its own PRD section.

<!-- coaching-notes-stage-3 -->

## Stage 3 — Coaching Notes (internal, not part of the PRFAQ proper)

### Choices made
- **Q1 (vs existing scrapers):** picked option (B) — 4-bullet differentiator list including eBay.es coverage. Calls out Tatuck by name as the closest competitor (arbitrage tool, not personal wishlist).
- **Q2 (vs saved searches):** picked option (A) — 3-bullet, drops cross-marketplace dedup (already covered in Q1). Closing line on Phase 2 four-hour deal half-life.
- **Q3 (Wallapop ToS / account ban):** picked option (B) — most concise. Soft legal mention ("Spanish courts have generally permitted"), no specific case citation. Includes the "use a Wallapop account you'd be willing to lose" recommendation.
- **Q4 (one-person OSS sustainability):** picked option (A) — distinguishes "developer abandons" from "marketplace breaks compatibility." Honest closing: "if long-term continuity matters more than wishlist precision, hardware-hunter isn't the right tool."
- **Q5 (technical fragility / 6-month experience):** picked option (A) — three bullets: two-path fetching, eBay.es independence, open risk. User CONFIRMED architecture: Wallapop = unofficial API + TinyFish Search/Fetch fallback; eBay.es = official eBay API.
- **Q6 (monthly cost):** picked option (A) — €3–6/month VPS, free on existing hardware. Numbers assume Gemini Flash for LLM evaluation.
- **Q7 (LLM accuracy):** picked option (A) — honest "no real-world numbers yet," 4 bullets including baseline-vs-saved-searches reframe. Confidence-level prompt mentioned as mitigation. **REQUIREMENT SIGNAL:** confidence-level prompt is now a PRFAQ commitment.
- **Q8 (Phase 2 blast radius):** picked option (A) — leads with "user eats the loss," 3 bullets on platform-protected rails / user's tap is decision / configurable guardrails. **REQUIREMENT SIGNALS:** confidence thresholds + per-entry Phase 2 disable + per-entry max prices are now PRFAQ commitments.

### Requirements signals surfaced (must land in PRD)
- **Confidence-level prompt** in LLM evaluation (committed in Q7 + Q8 answers).
- **Per-entry max price** as a hard ceiling on Phase 2 spend (committed in Q8).
- **Per-entry Phase 2 enable/disable** toggle (committed in Q8).
- **Confidence-threshold** that pushes low-confidence matches back to manual approval even with Phase 2 enabled (committed in Q8).
- **seen-listings dedup store** (committed in Q7).
- **Two-path Wallapop adapter** (unofficial API + TinyFish Search/Fetch fallback) — committed in Q5, confirmed by user.
- **eBay.es adapter via official eBay API** (committed in Q5).
- **Phase 2 only on Wallapop Pay / eBay checkout, never Bizum or transferencia** (committed in Q8).
- **Accuracy dashboard for hidden-component detection** (community-collected, post-launch roadmap item — committed in Q7).
- **ROADMAP.md** referenced in Q4 + Q7 + How to Participate. Must include: future-multi-marketplace direction, accuracy dashboard plan.

### Trade-off decisions made
- **"Use a Wallapop account you'd be willing to lose" recommendation:** kept in PRFAQ (Q3). Adoption friction accepted in exchange for honesty + user protection. **NOT a launch blocker.**
- **No legal-citation specificity** in Q3: STS 572/2012 + ZebraBot precedent dropped from PRFAQ in favor of generic "Spanish courts have generally permitted." Reduces fact-check exposure. **NOT a launch blocker.**
- **No real-world accuracy data** for hidden-component detection (Q7): explicitly acknowledged as best-effort. Accuracy dashboard is a fast-follow, not a launch blocker.
- **One-person sustainability risk** (Q4): explicitly acknowledged. Mitigation is structural (MIT + self-hosted + small codebase), not a maintenance commitment. **Accepted trade-off.**

### Competitive intelligence surfaced
- **Tatuck/wallapop-scraper** repeatedly invoked as the closest competitor. Different framing (arbitrage vs personal wishlist) is the moat, not the technology stack.
- **Existing Wallapop bots (wallabot, Walla-Bot, davertor, nadiamoe)** all keyword-alert engines without container detection, LLM evaluation, or eBay.es coverage.
- **Wallapop's own saved searches** explicitly named as the minimum viable alternative — answer to Q2 explicitly tells some readers to use them instead.

### Gaps revealed
- **No real-world data for any accuracy claim.** This is a launch reality, not a flaw. Accuracy dashboard plan is the honest path forward.
- **TinyFish Browser per-purchase cost is estimated** ("cents") but not measured. Should be tested before Phase 2 documentation is final.
- **Wallapop session persistence strategy** (open kickoff-doc question) becomes more pointed after Q3 — if the secondary-account recommendation is taken seriously, persistence has to survive cookie expiry without re-login that triggers anti-bot.
- **Phase 2 buy flow is the most fragile part of the system** (called out in Q5). Should be the first place a smoke-test harness lives.

### Themes for Stage 4 (Internal FAQ) to revisit
- Wallapop ToS deeper dive (already in pre-loaded internal FAQ topics).
- Spanish consumer law / RGPD evidence-of-consent for Phase 2 purchases.
- ACES / VLM-bias evidence and how the deterministic-wishlist design avoids it.
- How the project resists drifting into arbitrage when alerts surface flippable listings.
- Maintenance commitment over time (related to Q4 customer answer).
- Stack risk: Hermes Agent v0.10 production-readiness, TinyFish free-tier limits at scale.

<!-- coaching-notes-stage-2 -->

## Stage 2 — Coaching Notes (internal, not part of the PRFAQ proper)

### Choices made
- **Headline:** picked option (A) — leads with "open-source agent" + container-detection differentiator. Audience-agnostic phrasing (no "Spanish").
- **Subheadline:** picked option (B) — *"Catches the listings you'd buy if you saw them in time."* — 9-word emotional gut-punch.
- **Opening paragraph:** picked option (A) — customer-pain-first ("vanish in about four hours"), not market-context-first.
- **Problem paragraph:** picked option (B) — visceral first-person voice, keeps the hidden-component story (NAS DS220 wrapper).
- **Solution paragraph:** picked option (B) — includes Phase 2 tease with explicit opt-in / per-entry / no-bypass framing.
- **Founder quote:** picked option (B) — origin-story-only, 35 words, "the fix turned out to be small enough to share."
- **User quote:** picked option (i) — SKIPPED entirely. Founder quote already carries user voice; second ifuensan quote would be redundant.
- **How It Works:** picked option (A) — 3-paragraph compression with install detail, two-tier YAML pricing, Phase 2 with no-bypass guarantee.
- **How to Participate:** picked my draft + MIT license + personal GitHub (`ifuensan/hardware-hunter`). Roadmap reference includes future-multi-marketplace direction.

### Major scope-discipline events
- **Multi-marketplace pivot caught and reversed.** User initially picked option (2) — "design hardware-hunter to be marketplace-agnostic from day one." After hard pushback laying out the cost (per-marketplace adapter complexity, scope explosion, breaking the scratch-own-itch motivation, killing the (c3) contract), user reverted to (1) — Wallapop + eBay.es only for v1. Multi-marketplace explicitly deferred to "much later, after validating Wallapop + eBay.es first." Captured as future research direction in the ROADMAP, not in v1 scope. **DO NOT relitigate this without this context.**

### Rejected framings worth remembering
- Headline alt: market-crisis-anchored ("In the worst RAM market in a decade...") — rejected as too long; the why-now data lives in the opening paragraph instead.
- Headline alt: consumer-marketing-voice ("Stop refreshing Wallapop at 2 a.m...") — rejected; the "underpriced NAS" phrasing leaned subtly toward arbitrage framing.
- Subheadline alt: timing-anchored ("In a memory market where 32GB of DDR4 doubled in seven months...") — rejected as too long, headline already sets timing context.
- Solution alt without Phase 2 tease — rejected; burying Phase 2 to the FAQ understates the ambition.
- Founder quote alt: aspirational vision ("I want my homelab to keep itself supplied...") — rejected in favor of origin-story-only.
- User quote: a fabricated-catch version (WD Red inside DS218 at 90€) was drafted but rejected as embellishment; honest pre-launch path chosen instead, and then the section dropped entirely.

### Honesty / data points used in the press release
- "32GB of DDR4 has more than doubled in seven months" — verified against Tom's Hardware May 2026 RAM index.
- "Shortages projected through 2027" — verified against IDC global memory shortage 2026 + WCCFTech (Q4 2027 outlook).
- "Good listings vanish in about four hours" — user's stated experience, used in the opening and problem paragraphs.
- "Twenty minutes a day" / "twenty entries cover most homelab refresh cycles" — user's stated experience and the kickoff doc's "lists kept under 100 entries each" upper bound.
- Synology RS818+ — user's actual NAS, captured in coaching notes for grounding even though the user quote was ultimately dropped.

### Out-of-scope details captured (don't put in PRFAQ proper, useful for PRD distillate / FAQ)
- Stack: Hermes Agent v0.13.0 + TinyFish via MCP, on owned HPE DL160 Gen10 in Valencia colo. ~5€/month infra cost target.
- Phase 2 payment rails: only platform-protected (Wallapop Pay, eBay checkout). Bizum / direct transferencia rejected.
- Cron-based polling (not literally streaming) — press release uses "around the clock" / "continuously" as honest euphemisms.
- Wallapop ToS (rev. Apr 2026) explicitly forbids scraping/bots — must be addressed in Stage 4 Internal FAQ.
- ACES paper bias evidence (arXiv 2508.02630) — supports the deterministic-wishlist design choice; could surface in Customer FAQ.
- Open kickoff-doc questions still unresolved: project name (assumed final = "hardware-hunter"), session persistence strategy, browser-failure fallback, rate-limiting per execution, container "worth it" decision criterion, web-backend choice (Firecrawl vs SearXNG), API vs Google index, agentskills.io publication.

<!-- coaching-notes-stage-1 -->

## Stage 1 — Coaching Notes (internal, not part of the PRFAQ proper)

### Concept type
**Open-source scratch-your-own-itch tool**, single-developer (ifuensan). Open-sourcing is a side benefit, not a go-to-market. This calibrates Stages 3–4: no "first 100 customers," no monetization, no GTM. Instead: does this save *me* time/money, is the maintenance burden worth it, is the OSS release a real commitment.

### Customer choice and pivot caught
- User initially picked **(c) scratch own itch** but pivoted mid-Q2 to "if this works I can create a business buying goods and selling it after." This is a flipping/arbitrage product, not a homelab tool. They are very different products with different scope, blast radius, competitor (Tatuck), and legal posture.
- After hard pushback comparing the two product framings, user chose **(c3) phased**: ship homelab v1 first, evaluate arbitrage as a future research direction (separate repo/tool), explicit anti-scope-creep contract for v1.
- This locks the PRFAQ framing as personal homelab tool. Arbitrage is OUT of scope and will be flagged if it reappears in later stages.

### Key assumptions challenged
- "Just an LLM scraper" → forced articulation of customer + problem + stakes before we let the user describe the technology.
- "Tech stack as the product" (Hermes/TinyFish) → reframed as implementation detail; press release will not name the stack.
- Implicit "users = anyone in Spain" → narrowed to ifuensan personally with OSS as side effect.

### Subagent findings that shaped the framing
- **Memory crisis is more severe than the kickoff doc claims** (Tom's Hardware May 2026, IDC, Team Group GM): DRAM Q2 2026 +63%, NAND +75%, on top of Q1 ~95% jumps, shortage projected through Q4 2027. Strengthens timing argument.
- **ACES (Columbia/Yale, WebConf 2026)** shows VLM shopping agents have systemic position/sponsored bias. The deterministic-wishlist design sidesteps this — making "narrow YAML match" a *positive* product story, not a limitation.
- **Wallapop ToS (rev. Apr 2026)** explicitly forbids scraping and bots; community sentiment is hostile to flipper bots (Tatuck-style). Personal-use framing is both ethically and tactically the right shield. Internal FAQ will address.
- **Hermes Agent v0.10 (Apr 2026), MIT, 103k stars + TinyFish free Search/Fetch tier** make ~5€/month total infra cost realistic. Stack viability confirmed.
- **Competitor scan**: 5+ Wallapop scrapers exist, none combine personal wishlist YAML + container-detection + LLM + autonomous-purchase-with-HITL + Spanish marketplace focus. Whitespace confirmed.

### User context captured (not part of PRFAQ proper)
- **Time tax:** ~20 min/day manual scanning.
- **Listing half-life:** good listings vanish in ~4 hours.
- **Market premium avoided:** ~2x retail vs second-hand.
- **Frequency of need:** "not every day," but recurring (homelab maintenance cycles).
- **Stack (locked, not for PRFAQ debate):** Hermes Agent v0.13.0 on owned HPE DL160 Gen10 in Valencia colo + TinyFish via MCP.
- **Phase 2 financial guardrails:** Bizum/transferencia rejected; only platform-protected payment rails (Wallapop Pay, eBay checkout). Telegram confirmation is non-bypassable by design.
- **Differentiator the user cares about:** YAML schema with `max_price_solo` AND `max_price_in_device` enabling detection of target component *inside* container listings (HDDs in NAS, RAM in mini-PC).
