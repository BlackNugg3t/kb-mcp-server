# MCP Server Review Checklist

## Protocol/implementation correctness

- **Transport**: stdio, SSE, or streamable HTTP — confirm the transport matches how clients (Claude Code, Claude Desktop, etc.) will actually connect. A common bug: writing debug output to stdout when using stdio transport, which corrupts the JSON-RPC stream. All logging in a stdio server must go to stderr, never stdout.
- **Tool schemas**: every `@tool`/`call_tool` definition should have a complete JSON schema (types, required fields, descriptions). Missing `description` fields on tools/params are the top cause of the model calling tools wrong or not at all.
- **Tool naming/descriptions are pushy enough**: vague tool descriptions ("gets data") lead to under-triggering. Each tool description should say what it does AND when to use it.
- **Error handling**: tool handlers should catch exceptions and return them as MCP tool errors (isError: true + message), not let the process crash or return an unhandled traceback as the result content.
- **Resources vs tools**: check that read-only data exposure uses `resources` (or a `list_resources`/`read_resource` pattern) rather than modeling everything as tools when it doesn't need side effects — keeps the tool list smaller and clearer.
- **Statelessness / concurrency**: if the server holds in-memory state (session, cache) across tool calls, confirm it's safe under concurrent calls (async lock, or confirm single-client assumption is actually true).
- **Input validation**: don't trust tool arguments blindly — especially anything that becomes a file path, shell command, or SQL/query fragment. Path traversal via a `file_path` argument is a common finding.
- **Long-running tools**: does the server support/emit progress notifications for slow tools (e.g., a full KB re-index), or will the client just hang/timeout?

## Security

- No tool should allow arbitrary code execution or shell command construction from unsanitized model/user input unless that is explicitly the tool's declared purpose and sandboxed.
- If the MCP server proxies to the context engine's retrieval, confirm it isn't leaking documents/chunks the requesting user/context shouldn't have access to (multi-tenant KBs especially).
- Confirm the server doesn't expose secrets (API keys for GitHub/Notion/etc.) back to the model through tool outputs, logs, or error messages.

## Config

- Server startup should fail fast and loudly if required env vars (API keys, DB URL) are missing, not fail silently on first tool call.
- Check `mcp.json` / server registration config matches the actual entrypoint and required env vars are documented.
