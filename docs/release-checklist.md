# Pre-v1.0 release-gate manual audits

Story 5.17 / UX-DR22, UX-DR23, UX-DR32, UX-DR33.

This is the **release-gating** manual procedure that runs against a
v1.0 candidate build before [Story 5.18](../ROADMAP.md) tags `v1.0.0`.
Snapshot tests, mypy and the coverage gate verify *code* invariants;
they cannot verify that Telegram on iPhone renders `🚫` distinguishably
from `⚠️` for a deuteranope, or that VoiceOver reads the `audit show`
table without box-drawing-character interference. That is what this
procedure exists for.

Every section ends with a recorded outcome. The whole run is committed
to `docs/release-audits/v1.0/` (image attachments + a written summary).
Any **critical** anomaly blocks the v1.0 tag.

---

## 0. Prerequisites

- A v1.0 candidate build deployed against a throwaway Telegram chat
  (so we can fire every alert variant without polluting the operator's
  real chat).
- The bot configured against that chat in `config.yaml`.
- A controlled wishlist with one entry that will reliably produce
  Phase 1 + Phase 2 listing alerts (or fixture replays via
  `salvager audit replay <id>` when that lands).
- The 22 operational `EventName` variants are reachable from
  `salvager dev emit-alert <event>` (or by replaying recorded
  fixtures from `tests/unit/__snapshots__/`).

---

## 1. Telegram client variance — 4 contexts (UX-DR32)

Capture every alert variant in every context. The matrix is small but
non-negotiable: emoji rendering and MarkdownV2 fidelity drift silently
between Telegram clients, and the v1.0 promise is that the operator
gets the same alert anatomy regardless of where they read it.

### Contexts to cover

| # | Platform | Specifics |
|---|----------|-----------|
| 1 | iOS Telegram | iPhone 12 or newer, latest stable Telegram |
| 2 | Android Telegram | Pixel 6 or newer, latest stable Telegram |
| 3 | Telegram Desktop | macOS or Linux, latest stable |
| 4 | Telegram Web | Chrome **and** Firefox (count as one context — capture both browsers) |

### Alert variants to fire and screenshot

**Listing surface (Phase 1 + Phase 2):**

- Phase 1 direct match
- Phase 1 container (Direction E — wrapper + extracted rows)
- Phase 2 direct match (`🟢` severity + locked `[✅ Comprar · ❌ Saltar · 👁 Ver]` row)
- Phase 2 buy success (`✅` receipt with screenshot attachment)
- Phase 2 buy failure — **all 8 `BuyFailureReason` variants**:
  - `reconciliation_tripped`
  - `ui_check_failed`
  - `circuit_open`
  - `missing_element`
  - `marketplace_error`
  - `timeout`
  - `screenshot_missing` (alternate reassurance line)
  - `payment_rail_unavailable`

**Operational surface — all 22 `EventName` variants:**

`daemon_started`, `daemon_stopped`, `wallapop_session_expired`,
`wallapop_session_renewed`, `wallapop_api_degraded`,
`wallapop_both_paths_down`, `tinyfish_fallback_active`,
`tinyfish_fallback_recovered`, `ebay_token_refresh_failed`,
`ebay_quota_breach`, `llm_provider_rate_limited`, `entry_snoozed`,
`poll_cycle_error`, `circuit_open`, `smoke_test_failed`,
`smoke_test_recovered`, `phase2_disabled`, `phase2_re_enabled`,
`phase2_buy_callback_received`, `phase2_screenshot_missing`,
`phase2_buy_completion_slow`, `buy_orchestrator_error`.

### What to verify in each capture

- **Severity emoji fidelity** — the 6 surface emoji render identically
  across contexts: `⚠️` (warn), `ℹ️` (info), `📦` (Phase 1 listing),
  `🟢` (Phase 2 listing), `✅` (buy success), `🚫` (buy failure).
- **Button-label emoji fidelity** — the 5 button-row emoji render
  identically: `👁` (Ver), `🙅` (Saltar — Phase 1), `😴` (Posponer 24h),
  `✅` (Comprar), `❌` (Saltar — Phase 2).
- **MarkdownV2 fidelity** — bold headlines (`*Compra abortada*`) render
  bold; italic one-line takes render italic; backtick `monospace`
  renders as monospace and is one-tap copyable.
- **Button row layout** — `[Comprar · Saltar · Ver]` (Phase 2) and
  `[Ver · Saltar · Posponer]` (Phase 1) sit on a single row at every
  reasonable viewport. No wrap onto two rows for the locked label
  vocabulary.
- **Receipt screenshot** — Phase 2 buy-success photo attaches and
  renders inline (not as a downloadable file).

### Recording

For each (context, variant) pair, save a PNG to:

```
docs/release-audits/v1.0/telegram/<context>/<variant>.png
```

…where `<context>` is one of `ios | android | desktop | web-chrome |
web-firefox` and `<variant>` is the lowercase event name or
`phase{1,2}_<kind>` for listings.

---

## 2. Color-blind audit — 3 simulators (UX-DR22)

UX-DR22 commits that every alert is distinguishable by **shape**
(emoji glyph) **and** by **text** (severity prefix in the headline or
the `Causa:` row), never by color alone. Telegram colorizes severity
emoji in a way that drops out under deuteranopia, so we verify the
shape + text fallback holds.

### Simulators

| Condition | Tool |
|-----------|------|
| Deuteranopia (most common) | [Coblis](https://www.color-blindness.com/coblis-color-blindness-simulator/) **or** [Color Oracle](https://colororacle.org/) |
| Protanopia | Same |
| Tritanopia | Same |

### Procedure

For each of the **Section 1** screenshots, view the image through the
three simulators. Verify:

- The `🚫` (failure) and `⚠️` (warn) emoji remain visually
  distinguishable by shape under deuteranopia. (They differ in color
  *and* shape; the color drop-out must leave the shape difference
  intact.)
- The `🟢` Phase 2 prefix is distinguishable from the `📦` Phase 1
  prefix — same color-vs-shape test.
- The severity text is present and readable: `*Compra abortada*`,
  `⚠️ *Wallapop sin servicio*`, `ℹ️ Daemon iniciado`. Color can be
  ignored entirely; the prefix word carries the signal.
- Button-row labels: `✅ Comprar` vs `❌ Saltar` distinguishable even
  if the green / red colorization flattens. The emoji + word combo is
  what carries the affirmative-vs-negative meaning.

### Recording

Save a written note per simulator-screenshot pair where the
distinguishability is **borderline**. A pass is a quiet pass — record
only anomalies. Save the (simulated) PNGs that demonstrate any anomaly
to:

```
docs/release-audits/v1.0/colorblind/<simulator>/<variant>.png
```

---

## 3. VoiceOver audit on Terminal (UX-DR23, UX-DR33)

UX-DR23 promises the CLI is usable with a screen reader. We verify on
macOS VoiceOver because it is the dominant accessibility stack on the
operator's platform; ORCA / NVDA are out of scope for v1.0.

### Setup

- macOS with VoiceOver enabled (`Cmd + F5`).
- Terminal.app (Apple Terminal — not iTerm; iTerm has its own
  accessibility implementation that we don't validate at v1.0).
- The candidate build installed and configured.

### Commands to read

Run each in sequence and listen to the VoiceOver readout end-to-end:

1. `salvager health` — the table is read row by row, label →
   value, without VoiceOver getting stuck on box-drawing characters.
2. `salvager audit show --last 5` — the 5 most recent audit
   entries read in chronological order, with each row's fields
   identifiable.
3. `salvager phase2 status` — the Phase 2 state table reads
   cleanly; the "global disabled" / "per-entry disabled" sections are
   announced as distinct.

### What to verify

- VoiceOver reads each row as one logical unit. The box-drawing
  characters (`├ ┤ │ ─`) used by Rich's tables are *spoken as*
  individual glyphs by default — verify that the renderer either
  (a) emits an accessible mode under `--no-color` / `--plain` that
  drops box-drawing, or (b) the default rendering is acceptable.
- The Spanish text reads correctly with the system voice (the operator
  speaks Spanish — `es-ES` voice is the canonical one).
- Numeric columns (price, duration, count) are not run-together; the
  reader pauses between cells.

### Recording

For any line-reading anomaly:

- If the renderer can be patched, file it as a release-gating bug per
  the regression-fix protocol and patch before tagging.
- If the limitation is structural (a Rich behaviour we can't reach
  without an architecture change), document the workaround in
  `docs/accessibility.md` (e.g. "for VoiceOver users, prefer
  `salvager ... --json | jq` for tabular output").

---

## 4. Sign-off

Once all three sections complete cleanly (or every anomaly is either
patched or documented):

1. Create `docs/release-audits/v1.0/SUMMARY.md` with the run date,
   build SHA, contexts covered, any anomalies + their disposition, and
   a one-line `RESULT: PASS` / `RESULT: BLOCKED — <reason>`.
2. Commit the audit folder (`docs/release-audits/v1.0/`).
3. If `RESULT: PASS`, proceed to [Story 5.18](#) — tag `v1.0.0`.

### Blocking criteria

The v1.0 tag is blocked if any of the following holds:

- **Critical color-blind failure** — a severity emoji is
  indistinguishable from another severity emoji under any simulator
  (e.g. `🚫` and `⚠️` collapse to the same glyph + same color), and
  the severity *text* alone is insufficient context. This violates
  UX-DR22.
- **Critical VoiceOver failure** — a primary command
  (`health`, `audit show`, `phase2 status`) cannot be navigated to the
  point where the operator can answer "what is the system doing right
  now?". This violates UX-DR23 / UX-DR33.
- **Telegram emoji corruption** — a severity emoji renders as the
  replacement glyph (□ or �) on any of the 4 contexts. Indicates a
  Telegram client / Unicode regression we have to either patch around
  (different glyph) or wait out (Telegram client update). This
  violates UX-DR32.

Non-critical anomalies (e.g. a single info-tier emoji renders slightly
differently across iOS and Android but remains identifiable) are
documented in the summary and do not block the tag.
