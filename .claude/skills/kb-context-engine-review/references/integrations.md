# Integration-Specific Review Checklist

## GitHub

- **Auth**: PAT vs GitHub App — a GitHub App with installation tokens is preferred for anything multi-repo/org-scale (fine-grained perms, higher rate limits, doesn't tie to one person's account). Flag a personal PAT used in a "production" bot.
- **Webhook verification**: incoming webhooks must verify the `X-Hub-Signature-256` HMAC against the webhook secret before processing — check this isn't skipped.
- **Rate limits**: GitHub's REST API is 5000 req/hr per token (higher for Apps); check for `X-RateLimit-Remaining` handling and backoff, especially in any full-org backfill/crawl.
- **Pagination**: list endpoints (issues, PRs, commits, contents) are paginated — check the code follows `Link` headers or uses the SDK's pagination helper rather than assuming one page is everything.
- **Scopes**: token/App permissions should be least-privilege for what's actually used (e.g. don't request `repo` admin scope just to read file contents).

## Notion

- **Auth**: internal integration token vs public OAuth integration — confirm which, and that the token is scoped to only the pages/databases actually needed (Notion integrations must be explicitly shared with each page).
- **Rate limits**: ~3 requests/second average; check for backoff on 429 with `Retry-After` header respected.
- **Pagination**: `blocks.children.list`, database queries, etc. are cursor-paginated (`has_more` / `next_cursor`) — check this is followed to completion, not just the first page.
- **Block types**: Notion content is a nested block tree (not flat markdown) — confirm the sync handles nested blocks (toggles, nested lists, synced blocks, databases-within-pages) rather than only top-level blocks, or content will silently go missing.
- **Webhooks**: if using Notion's webhook/automation features, verify signature validation is implemented (Notion webhooks include a verification token on first setup — check it's checked, not just logged and ignored).

## Discord

- **Library patterns**: if using discord.py/nextcord/hikari, confirm handlers use `async`/`await` correctly throughout — a single blocking call in an event handler stalls the whole gateway connection for that shard.
- **Intents**: confirm only the Gateway Intents actually needed are requested (e.g. `message_content` intent requires verification for bots in 100+ guilds) — over-requesting intents can block bot verification/approval.
- **Interaction ack timing**: slash command / component interactions must be acknowledged (`defer()` or initial response) within 3 seconds or Discord invalidates the interaction — check any handler that calls the context engine or an external API defers first if that call could be slow.
- **Rate limits**: Discord's rate limiter is per-route with global limits too; check the library's built-in rate limit handling isn't being bypassed by raw HTTP calls elsewhere in the code.
- **Token security**: bot token should come from env/secret manager, never committed; check `.gitignore` actually covers wherever it's loaded from.

## Telegram

- **Webhook vs polling**: `getUpdates` long polling and webhook mode are mutually exclusive — check the code doesn't accidentally run both (causes missed/duplicate updates).
- **Webhook security**: Telegram webhooks should be verified either via a secret path token or the `X-Telegram-Bot-Api-Secret-Token` header (`secret_token` param on `setWebhook`) — check incoming requests validate this rather than trusting any POST to the webhook URL.
- **Update de-duplication**: Telegram can redeliver updates; check `update_id` is tracked/deduped if the handler isn't naturally idempotent.
- **Long-running handlers**: same as Discord — don't block the event loop; offload slow context-engine calls so the bot stays responsive to other chats.
- **Flood limits**: Telegram bot API has per-chat and global send-rate limits (roughly 30 msgs/sec global, 1/sec per chat) — check outbound messages (especially broadcast-style) respect this.

## Cross-integration

- If the same underlying event (e.g. "new doc") can arrive via more than one integration, confirm there's a shared normalization step so downstream ingestion code doesn't have four divergent code paths to maintain.
- Confirm each integration's credentials are isolated (compromise of the Discord token shouldn't expose the Notion token) — check they're not all loaded into one shared global config object passed everywhere unnecessarily.
