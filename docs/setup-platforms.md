# Platform setup

For installation, file permissions, networking, costs, and the full Discord procedure, read the
[README](../README.md#discord-setup-in-five-steps).
Credentials and sessions must be entered by the operator, never in agent transcripts.
Collection requires consent and an explicit allowlist; discovering a channel does not authorize reading it.

## Discord

Follow [Discord: setup in five steps](../README.md#discord-setup-in-five-steps): create the bot
with **Message Content Intent**, save the token and an AI key, invite it with the dashboard
button, then choose exclusions, digest channel, frequency and language per server. Servers are
registered automatically when the bot joins them.

Hand-picked channels remain available when **Read every channel** is off:

```toml
[[discord]]
channel_id = "YOUR_CHANNEL_ID"
name = "homelab"
workspace = "Server A"
topics = ["Linux", "backup"]
```

`/ask` and `/digest` still require roles allowed for the server in the dashboard; `/gnosis`
commands are open to every member and use each member's own key.

## Telegram

1. Obtain `api_id` and `api_hash` at <https://my.telegram.org>.
2. Set `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in `.env` or the dashboard.
3. Recreate web/worker to reload credentials: `docker compose up -d --force-recreate web worker`.
4. Stop the worker and create the session once:

   ```bash
   docker compose stop worker
   docker compose run --rm worker gnosis telegram-login
   docker compose up -d worker
   ```

5. Select only accessible, authorized chats on the Telegram page, then restart the worker.

The session is in `telegram-data`: protect it like a password; collection uses your account
and does not bypass group visibility. Do not read or copy the session with an agent without
specific consent. The code may request a phone number, login code, and 2FA: the user enters them.

### Interactive bot (`/ask`, `/digest`)

This is a tool for the **global operator**, not members of the various Discord servers.

1. Create a bot with [@BotFather](https://t.me/BotFather) and save `TELEGRAM_BOT_TOKEN`.
2. Configure `GNOSIS_TELEGRAM_ALLOWED_USERS` with numeric IDs of operators allowed to see all
   sources. Without an allowlist, the bot does not start.
3. The same `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are required. The bot session is separate
   from the personal session. Recreate worker after saving the values.
4. Use commands in private conversations. Groups are ignored even for authorized users.

`GNOSIS_DIGEST_TELEGRAM_CHAT_ID` is a global destination only in installations without workspaces.
Configuring push means sending content to that chat: explicitly approve the destination and its
audience. Do not use a broad group as an admin destination.

## Interactive languages

Discord and Telegram bot responses support English (`en`), Italian (`it`), Spanish (`es`),
Russian (`ru`), and Chinese (`zh`). The interaction/user locale selects a supported language,
with English as fallback; the request locale controls RAG answer generation. The dashboard
uses browser negotiation and a saved language preference. Operator CLI/installer output is
English-only. Archived digests are shown in their original generation language, not translated
on request: existing Italian digests remain, and new scheduled digests are generated in English.

## Reddit

Create an OAuth app approved for your intended use. Set `REDDIT_CLIENT_ID`,
`REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT`, configure authorized subreddits, and recreate worker.
Access, quotas, pricing, and terms may change: check Reddit's current requirements;
there is no promise of free access or bypassing limits.

## Applying changes

- Credentials in `.env`: `docker compose up -d --force-recreate web worker` (not just restart).
- Channels/chats/subreddits in the allowlist: `docker compose restart worker`.
- Workspace mappings and roles: from the DB on the next command, without restart.

See [operations](operations.md) for status, backups, and deletion handling.
