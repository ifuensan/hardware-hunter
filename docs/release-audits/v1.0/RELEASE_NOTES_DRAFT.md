# v1.0.0 release execution — draft

Prepared in advance of the Story 5.17 audit sign-off so the actual
release step (Story 5.18) is a quick sequence of "apply these prepared
edits + tag + push" actions.

**Trigger gate**: `docs/release-audits/v1.0/SUMMARY.md` flipped to
`RESULT: PASS`. Do NOT execute any step below until that gate is met.

---

## Step 1 — Bump version

`pyproject.toml`:

```diff
 [project]
 name = "hardware-hunter"
-version = "0.1.0"
+version = "1.0.0"
```

The `hardware-hunter version` command reads from the installed package
metadata, so the bump propagates automatically; no code changes needed.

---

## Step 2 — Apply README updates

Three localised edits.

### 2a. Status block (lines ~13)

Replace the current `> **Status (May 2026)...** ` blockquote with:

```markdown
> **Status:** `v1.0.0` released — Phase 2 (autonomous purchase) is
> stable behind the safety stack and the non-bypassable Telegram tap.
> Pinned tag: `ghcr.io/ifuensan/hardware-hunter:v1.0.0` (recommended).
> See [CHANGELOG.md](CHANGELOG.md) for the full release notes and
> [ROADMAP.md](ROADMAP.md) for post-v1 deferred work.
```

### 2b. Quick start — pinned tag

Add a one-liner near the top of `## Quick start` referencing the
pinned image:

```diff
 ## Quick start

-Prerequisites: Docker + docker-compose, a Telegram bot, a Google
-Gemini API key, an eBay developer account, and a running Hermes
-Agent service the daemon can reach (Hermes is operated separately;
-typical deployment is a Proxmox VM on the operator's host).
+Prerequisites: Docker + docker-compose, a Telegram bot, a Google
+Gemini API key, an eBay developer account, a TinyFish API key (Phase 2),
+and a Wallapop / eBay.es account dedicated to the agent (see Legal
+disclaimer below).
+
+The recommended image tag is `ghcr.io/ifuensan/hardware-hunter:v1.0.0`
+(latest stable). `:latest` follows the newest release; pin to `:v1.0.0`
+for reproducible deploys.
```

Note: the Hermes mention is stale — Hermes was dropped per the
2026-05-13 design pivot. Remove that paragraph entirely (or update if
Hermes is brought back post-v1).

### 2c. Drop the Hermes paragraph from "Architecture"

Lines ~88. Hermes is no longer a dependency. Replace:

```markdown
Hermes Agent runs as a remote service (typically on a Proxmox VM)
providing the scheduler, memory, and MCP routing (including TinyFish).
The daemon connects via HTTP/MCP at the `HERMES_URL` configured in
`.env`.
```

with:

```markdown
Scheduler runs in-process (asyncio-based, `adapters/asyncio_scheduler/`).
TinyFish is reached directly via the official SDK from
`adapters/wallapop_tinyfish/` (Phase 1 fallback) and
`adapters/tinyfish_browser/` (Phase 2 buy flows). No remote
agent-orchestration service is required.
```

---

## Step 3 — Apply ROADMAP updates

### 3a. Flip "Where we are"

Replace the entire `## Where we are (May 2026)` section with:

```markdown
## Where we are

**`v1.0.0` shipped.** Both phases of the agent are in production:

- **Phase 1** — alerts only. Daemon polls Wallapop + eBay.es,
  evaluates listings against the wishlist via Gemini Flash, dispatches
  Telegram alerts with `[👁 Ver] [🙅 Saltar] [😴 Posponer 24h]` buttons.
  Shipped across Epics 2-4.
- **Phase 2** — autonomous purchase. Opt entries into Phase 2 via
  `hardware-hunter phase2 enable <entry>`; the safety stack
  (cross-source price reconciliation + receipt-vs-alert reconciliation
  + daily synthetic smoke test + per-purchase circuit breaker) catches
  malformed data before any transaction. Phase 2 alerts carry
  `[✅ Comprar] [❌ Saltar] [👁 Ver]` buttons; the autonomous buy
  drives Wallapop Pay or eBay.es checkout via TinyFish. Shipped in
  Epic 5.

See [CHANGELOG.md](CHANGELOG.md) for the full v1.0.0 release notes
and the full epic + story breakdown in
[`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md).
```

### 3b. Replace "Near-term: Phase 1 and Phase 2"

The phased-rollout text is now historical. Replace the entire section
with a "Post-v1.0 — open questions" subsection:

```markdown
## Post-v1.0 — open questions

The v1.0 release does not retire these:

- **OQ3 — measured per-purchase TinyFish Browser cost.** NFR-C2 caps
  it at ≤ €1.00 worst-case; the gate fixture asserts the contract but
  the empirical cost on the operator's first 5 Phase 2 buys is the
  only honest validation. Track in `docs/release-audits/v1.0/` or a
  follow-up.
- **OQ6 — language-register bias.** The Telegram surface is Castilian
  Spanish per UX-DR27; structured-log audit for Catalan / regional
  Spanish / Basque is pending for any non-maintainer user.
- **OQ8 — agentskills.io publication.** Decision deferred until the
  v1.0 deployment hits its empirical success criteria.
```

### 3c. Post-launch deferred — confirm wording

The existing `## Post-launch (deferred)` section already lists
multi-marketplace, additional LLM providers (config-only), the
future-research repo path, and the bilingual-asymmetry CI lint.
**No edit needed** — it survives v1.0 verbatim. Sanity-check on the
day of release.

---

## Step 4 — Commit, tag, push

Once §1-3 are applied:

```bash
git add pyproject.toml README.md ROADMAP.md CHANGELOG.md docs/release-audits/v1.0/SUMMARY.md
git commit -m "$(cat <<'EOF'
release: v1.0.0

Phase 2 (autonomous purchase) stable behind the safety stack and the
non-bypassable Telegram tap. Release-audit sign-off recorded in
docs/release-audits/v1.0/SUMMARY.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push
git tag v1.0.0
git push origin v1.0.0
```

The `v1.0.0` tag push triggers `.github/workflows/release.yml` which
builds + pushes the Docker image to GHCR with the semver tags
`1.0.0` / `1.0` / `latest`.

---

## Step 5 — Verify the release

Once the release workflow completes (~5 minutes):

```bash
# 1. CI gates pass on the tag.
gh run list --workflow Release --limit 1

# 2. Image pulls cleanly without auth.
docker pull ghcr.io/ifuensan/hardware-hunter:v1.0.0
docker run --rm ghcr.io/ifuensan/hardware-hunter:v1.0.0 version
#    → expected: hardware-hunter 1.0.0 (commit <sha>)

# 3. `:latest` tracks the new release.
docker pull ghcr.io/ifuensan/hardware-hunter:latest
docker inspect ghcr.io/ifuensan/hardware-hunter:latest \
  --format '{{.RepoTags}}'
#    → should include both 1.0.0 and latest

# 4. The GHCR package page shows the v1.0.0 tag publicly.
xdg-open 'https://github.com/ifuensan/hardware-hunter/pkgs/container/hardware-hunter'
```

---

## Step 6 — Update the "currently running" world

After GHCR is happy:

1. **Operator's own deploy**: pull the new image
   (`docker-compose pull && docker-compose up -d`) on the production
   homelab host.
2. **Sanity check**: `docker-compose logs hardware-hunter | head -50`
   to confirm `daemon_started` lands and the version line matches.
3. **Smoke test the safety stack**: `hardware-hunter phase2 smoke-test`
   should return `RESULT: pass` against the bundled fixture set.

---

## Rollback plan

If §5 surfaces a regression before §6 is done:

```bash
# Delete the tag (local + remote) — the release workflow's image is
# still in GHCR but no operator follows ":latest" to it because §6
# has not run.
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0
```

If §6 has already run and a regression surfaces in production:

```bash
# Pin back to v0.1.0 — the last stable foundation tag.
sed -i 's/:latest/:v0.1.0/' docker-compose.yml
docker-compose pull && docker-compose up -d
```

…and open a v1.0.1 hotfix immediately. Do NOT delete the v1.0.0 tag
once it's been pulled by anyone outside the maintainer; semver
contract says a published tag is permanent.

---

## After v1.0.0 is live

- [ ] Update [CHANGELOG.md](../../../CHANGELOG.md): move the
  `## [1.0.0] — _pending..._` heading to a real date and remove the
  "pending audit sign-off" line.
- [ ] Confirm `docs/release-audits/v1.0/SUMMARY.md` is committed in
  the same release commit (the audit artefact ships with the release).
- [ ] Optionally close any GitHub issues filed against Phase 2 stories
  that the release fully addresses.
