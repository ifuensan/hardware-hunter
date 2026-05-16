# Throwaway test-chat setup for the v1.0 release audit

Story 5.17 needs to fire every alert variant against a real Telegram
client, in every variant + every context (iOS / Android / Desktop /
Web). Doing that against your production bot pollutes the real
operator chat with dozens of debug messages and (worse) sends fake
`✅ Compra` receipts to the chat you might trust.

This guide walks through standing up a **second, throwaway**
Telegram bot pointed at a **second, throwaway** chat — separate from
production — and routing the candidate build at that pair via
`config/.env.audit` instead of the production `config/.env`.

It assumes you already have the production setup running.

---

## 1. Create the audit bot via BotFather

In Telegram, open a chat with [@BotFather](https://t.me/BotFather) and:

```
/newbot
```

When prompted:

- **Name** — e.g. `Salvager — audit v1.0` (display name; can change later).
- **Username** — must end in `_bot`; e.g. `salvager_audit_v10_bot`. Once
  taken, it's yours forever, but you can `/deletebot` it after the audit.

BotFather replies with the bot token. **Keep it** — this is the
`TELEGRAM_BOT_TOKEN` for the audit run. Treat it like any other secret.

While you're there:

```
/setjoingroups   → enable for the new bot   (so you can add it to the audit chat)
/setprivacy      → DISABLE for the new bot   (so it sees every message in the chat)
```

---

## 2. Create the audit chat

The simplest option: a private 1-on-1 chat with yourself + the bot.
You only need it visible from every device you'll audit on (iOS phone,
Android phone, Desktop, Web in both browsers). Steps:

1. In Telegram, open the audit bot you just created.
2. Tap `/start`. The bot now has your `chat_id` registered.
3. Get the chat_id:

   ```sh
   curl -s "https://api.telegram.org/bot<AUDIT_BOT_TOKEN>/getUpdates" \
     | jq '.result[].message.chat.id' | head -1
   ```

   The number that comes back is your `TELEGRAM_CHAT_ID` for the
   audit. (For a private 1-on-1 chat it's your personal Telegram user
   ID; for a group chat it's a negative number.)

If you prefer a group chat (so the audit messages don't mix with your
existing 1-on-1):

1. Create a new group, name it e.g. `Salvager — audit v1.0`.
2. Add the audit bot as a member.
3. Run the same `getUpdates` call; the group's chat_id surfaces under
   `.result[].my_chat_member.chat.id`. It's a negative integer.

---

## 3. Wire a separate `.env.audit`

Don't edit `config/.env` — that's the production wiring. Instead:

```sh
cp config/.env config/.env.audit
```

Then in `config/.env.audit`, replace **only**:

```env
TELEGRAM_BOT_TOKEN=<audit bot token from §1>
TELEGRAM_CHAT_ID=<audit chat_id from §2>
```

…leaving everything else (TinyFish key, eBay credentials, Wallapop
cookie path, etc.) untouched. The audit bot needs the same upstream
adapters as production — it only diverges at the Telegram leg.

Hardware-hunter loads `.env` by default; for audit runs override the
path:

```sh
salvager --env-path config/.env.audit dev emit-alert <variant>
```

(or symlink `config/.env` → `config/.env.audit` for the audit window
and symlink back when done.)

---

## 4. Sanity check

From the candidate build, fire one harmless variant:

```sh
salvager --env-path config/.env.audit dev emit-alert daemon_started
```

Within ~1 s your audit chat should show:

```
ℹ️ Daemon iniciado

Versión: 0.1.0 · jobs: wallapop_poll, ebay_poll
```

If you see this on every device you'll audit on, the wiring is good
and you can start the full §1 capture matrix in
[`SUMMARY.md`](SUMMARY.md).

If you see **nothing**:

- Verify `TELEGRAM_CHAT_ID` is correct (a negative int for a group
  chat, your personal user-id for a 1-on-1).
- Verify the bot has been `/start`-ed in the chat at least once.
- Verify `TELEGRAM_BOT_TOKEN` matches what BotFather gave you (no
  trailing whitespace).
- Check `docker-compose logs salvager` (or `journalctl -u …`)
  for an HTTP error from the Telegram API — `401` means bad token,
  `400 chat not found` means bad chat_id.

---

## 5. Cleanup after the audit

When `SUMMARY.md` reads `RESULT: PASS` and you've moved on to Story 5.18:

1. `rm config/.env.audit` — keep prod's `.env` untouched.
2. (Optional) `/deletebot` the audit bot in BotFather — frees the
   username for a future audit and removes another exposed token.
3. (Optional) Delete or archive the audit chat — keeps your Telegram
   sidebar tidy.

The reference-text + screenshot folders under
`docs/release-audits/v1.0/` stay committed as the release-gate
artefact.
