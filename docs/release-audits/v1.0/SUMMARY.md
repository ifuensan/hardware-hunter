# v1.0 release-audit summary

| Field | Value |
|---|---|
| Run date | _YYYY-MM-DD_ |
| Build SHA | _git rev-parse --short HEAD_ |
| Auditor | ifuensan |
| Result | `RESULT: PENDING` _(→ `PASS` / `BLOCKED — <reason>` at sign-off)_ |

Procedure: [`docs/release-checklist.md`](../../release-checklist.md). Test-chat
setup: [`SETUP.md`](SETUP.md). Reference MarkdownV2 text per variant:
[`reference-text/`](reference-text/).

Mark each cell **`✓`** (clean), **`!`** (anomaly — drop a note + a PNG
into the per-section folder), or leave **blank** if not yet captured.
Critical anomalies (per the blocking-criteria section of the
checklist) flip the run to `BLOCKED`.

---

## §1 — Telegram client variance (UX-DR32)

Capture every (variant, context) cell as a PNG under
`telegram/<context>/<variant>.png`. Compare each capture against
`reference-text/<section>/<variant>.txt`. Verify the 4 invariants the
checklist names (emoji fidelity · MarkdownV2 fidelity · button-row
single-line · receipt photo inline).

### Listing surface

| Variant | iOS | Android | Desktop | Web Chrome | Web Firefox |
|---|:-:|:-:|:-:|:-:|:-:|
| `phase1_listing_direct`         |  |  |  |  |  |
| `phase1_listing_container`      |  |  |  |  |  |
| `phase1_listing_missing_photo`  |  |  |  |  |  |
| `phase2_listing_direct`         |  |  |  |  |  |
| `phase2_listing_container`      |  |  |  |  |  |
| `phase2_listing_missing_photo`  |  |  |  |  |  |

### Phase 2 buy surface (receipt + 8 failure variants)

| Variant | iOS | Android | Desktop | Web Chrome | Web Firefox |
|---|:-:|:-:|:-:|:-:|:-:|
| `buy_success`                       |  |  |  |  |  |
| `failure_reconciliation_tripped`    |  |  |  |  |  |
| `failure_ui_check_failed`           |  |  |  |  |  |
| `failure_circuit_open`              |  |  |  |  |  |
| `failure_missing_element`           |  |  |  |  |  |
| `failure_marketplace_error`         |  |  |  |  |  |
| `failure_timeout`                   |  |  |  |  |  |
| `failure_screenshot_missing`        |  |  |  |  |  |
| `failure_payment_rail_unavailable`  |  |  |  |  |  |

### Operational surface (22 EventName variants)

| Variant | iOS | Android | Desktop | Web Chrome | Web Firefox |
|---|:-:|:-:|:-:|:-:|:-:|
| `daemon_started`                    |  |  |  |  |  |
| `daemon_stopped`                    |  |  |  |  |  |
| `wallapop_session_expired`          |  |  |  |  |  |
| `wallapop_session_renewed`          |  |  |  |  |  |
| `wallapop_api_degraded`             |  |  |  |  |  |
| `wallapop_both_paths_down`          |  |  |  |  |  |
| `tinyfish_fallback_active`          |  |  |  |  |  |
| `tinyfish_fallback_recovered`       |  |  |  |  |  |
| `ebay_token_refresh_failed`         |  |  |  |  |  |
| `ebay_quota_breach`                 |  |  |  |  |  |
| `llm_provider_rate_limited`         |  |  |  |  |  |
| `entry_snoozed`                     |  |  |  |  |  |
| `poll_cycle_error`                  |  |  |  |  |  |
| `circuit_open`                      |  |  |  |  |  |
| `smoke_test_failed`                 |  |  |  |  |  |
| `smoke_test_recovered`              |  |  |  |  |  |
| `phase2_disabled`                   |  |  |  |  |  |
| `phase2_re_enabled`                 |  |  |  |  |  |
| `phase2_buy_callback_received`      |  |  |  |  |  |
| `phase2_screenshot_missing`         |  |  |  |  |  |
| `phase2_buy_completion_slow`        |  |  |  |  |  |
| `buy_orchestrator_error`            |  |  |  |  |  |

### §1 anomaly log

_Empty when clean. Drop one bullet per anomaly with the cell coords,
the symptom, and the captured PNG path._

- _(none)_

---

## §2 — Color-blind audit (UX-DR22)

For each simulator, view the **iOS** captures (the most colour-saturated
of the four contexts) and check that severity emoji + button labels
remain distinguishable by **shape + text**, never colour alone.

| Simulator | Severity emoji pass? | Button labels pass? | Anomaly PNGs |
|---|:-:|:-:|---|
| Deuteranopia (Coblis / Color Oracle) |  |  |  |
| Protanopia (Coblis / Color Oracle)   |  |  |  |
| Tritanopia (Coblis / Color Oracle)   |  |  |  |

### §2 anomaly log

_Empty when clean. Anomaly PNGs land under `colorblind/<simulator>/`._

- _(none)_

---

## §3 — VoiceOver on Terminal (UX-DR23 / UX-DR33)

Drive each command on macOS Terminal with VoiceOver running. Score the
readout end-to-end.

| Command | Reads in logical order? | Box-drawing interference? | Notes |
|---|:-:|:-:|---|
| `hardware-hunter health`          |  |  |  |
| `hardware-hunter audit show --last 5` |  |  |  |
| `hardware-hunter phase2 status`   |  |  |  |

### §3 anomaly log

_Empty when clean. If a structural limitation is documented (rather
than patched), link to `docs/accessibility.md`._

- _(none)_

---

## Sign-off

When every section is clean (or every anomaly is patched / documented):

1. Flip the `RESULT:` field above to `PASS`.
2. Commit this file + the `telegram/`, `colorblind/`, `reference-text/` folders.
3. Proceed to Story 5.18 (tag `v1.0.0`).

If any **critical** anomaly per the checklist (emoji collapse under
simulator · primary command unnavigable in VoiceOver · severity emoji
corruption on a Telegram client), flip to `BLOCKED — <one-line reason>`
and open a release-gating bug.
