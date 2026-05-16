# Accessibility — known limitations + workarounds

This document captures accessibility limitations that the v1.0 release-
gate audit (Story 5.17 / UX-DR23 / UX-DR33) surfaced and explicitly
chose to document rather than patch before v1.0.

The release audit is recorded in
[`release-audits/v1.0/SUMMARY.md`](release-audits/v1.0/SUMMARY.md);
the procedure is in
[`release-checklist.md`](release-checklist.md).

---

## macOS Terminal + VoiceOver — limited compatibility with Rich tabular output

### Symptom

When `hardware-hunter health`, `audit show --last 5`, or `phase2 status`
are run inside Apple Terminal.app on macOS with VoiceOver enabled
(`Cmd + F5`), VoiceOver does **not** announce the contents of the
rendered tables. The visual output is correct and readable, but
VoiceOver only emits whitespace / prompt sounds when asked to read
the output (`VO + A`, `VO + Cmd + A`, etc.).

Verified during the v1.0 release-gate audit on 2026-05-16: the SSH'd
session showed the expected populated tables (3 wishlist entries on
`phase2 status`, three adapter rows on `health`, "no audit records
found" on `audit show`), but VoiceOver did not surface any of that
content.

### Root cause (working hypothesis)

The CLI surface uses Rich-rendered tables that emit Unicode
box-drawing characters (`│ ─ ┼ ├ ┤`) interleaved with ANSI colour
codes. macOS Terminal.app's accessibility hook does not always
expose these to VoiceOver as semantic table rows; the result is that
VoiceOver reads whitespace where structured data was rendered.

This is a long-standing limitation of Apple Terminal specifically and
not a regression introduced by hardware-hunter. iTerm2, Alacritty,
Kitty and other terminal emulators each handle accessibility
differently — UX-DR32's release-gate audit explicitly scopes to Apple
Terminal because it is the macOS default. iTerm2 + VoiceOver is known
to be more accessible but is out of audit scope at v1.0.

### Workaround for screen-reader users

The three primary commands all support a `--format json` flag (FR48 /
NFR-O2) that emits machine-readable, single-line JSON instead of
the Rich table. VoiceOver reads JSON cleanly because it is plain text
without box-drawing characters. The workaround is to pipe through
`jq` (or any JSON-aware tool) for human-friendly extraction:

```bash
# Daemon liveness + adapter status — one event line per adapter.
hardware-hunter health --format json \
  | jq -r '.adapters[] | "\(.name): \(.status), last activity \(.last_activity // "never")"'

# Recent audit log — one line per record.
hardware-hunter audit show --last 5 --format json \
  | jq -r '.records[]? | "[\(.audit_id)] \(.type) \(.occurred_at): \(.summary // .verb // "")"'

# Phase 2 enablement — one line per wishlist entry.
hardware-hunter phase2 status --format json \
  | jq -r '.entries[]? | "\(.display_name): enabled=\(.phase2_enabled), max=\(.max_price_eur // "-")"'
```

Each line is short, dense, and read by VoiceOver without interference.
The output above produces strictly accessible text that mirrors what
the Rich-table view shows visually.

### Why this is not a v1.0 blocker

UX-DR23 stipulates the screen-reader audit on Apple Terminal but
provides an explicit escape clause: "either patch the renderer or
document the limitation in `docs/accessibility.md`". The v1.0 candidate
exercises the second branch. The trade-off:

- **Cost of patching at v1.0**: rewriting the entire `observability/
  styling.py` surface — every table renderer, every panel, every
  styled line — to emit ARIA-friendly plain-text fallback when stdout
  is not a TTY (or when an `ACCESSIBLE=1` env var is set). Affects
  every visible CLI surface and risks regressions in the visual
  output. Estimated >1 week of focused work.
- **Cost of documenting**: 0 — the `--format json | jq` workflow
  already works and is documented above.
- **Affected user population**: at v1.0 the project ships as a
  single-operator tool (the project's c3 scope contract). The
  maintainer-operator does not depend on a screen reader. A future
  forker who is a screen-reader user has the JSON workflow available
  out of the box and can open a feature-request issue requesting a
  native `--plain` mode.

### Roadmap

Tracked in [`ROADMAP.md`](../ROADMAP.md) under "Post-launch (deferred)"
as a follow-up if forker demand surfaces. Possible directions:

- An `--plain` flag (or an `ACCESSIBLE=1` env-var trigger) that
  re-renders every Rich table as a sequence of
  `label: value` lines, one per cell. Estimated 1-2 days for the
  three audited commands; longer to cover every CLI surface.
- A documented `iTerm2 + VoiceOver` audit path post-v1.0 that opens
  the testing matrix beyond Apple Terminal.
- A `hardware-hunter dev a11y-smoketest` command that fires each
  table renderer with synthetic populated data and writes the JSON
  equivalent for screen-reader validation — useful for regressions
  on the JSON contract specifically.

None of these is committed; they are placeholders for if the issue
becomes load-bearing for any user.

---

## Other notes (none at v1.0)

This section will grow if future audits surface additional limitations.
At v1.0 only the macOS Terminal + VoiceOver limitation is documented.
