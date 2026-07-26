# Context Engine / Knowledge Base Review Checklist

## Ingestion

- **Source of truth & sync direction**: for each source (GitHub repo, Notion page, Discord message, Telegram message), is ingestion push (webhook-triggered) or pull (polling/cron)? Polling-only ingestion on a "real-time" KB is a common mismatch to flag.
- **Deletes/updates propagate**: when a Notion page is deleted or a GitHub file is removed, does the KB remove/update the corresponding chunks, or only ever append? Append-only ingestion silently accumulates stale/contradictory context over time — a very common and very damaging bug.
- **Dedup**: same content ingested from two sources (e.g. a doc linked from both GitHub and Notion) — is there any dedup/canonicalization, or will retrieval return duplicates?
- **Rate limits during backfill**: initial/full-repo backfills against GitHub/Notion APIs need pagination + backoff; check this isn't a naive unpaginated loop.

## Chunking

- Chunk size/overlap should be explicit and reasoned about (not a magic number with no comment) — check it's appropriate for the embedding model's context window and the retrieval use case.
- Chunking should respect natural boundaries where possible (headings, code blocks, message boundaries) rather than blind character-count splitting, especially for structured sources like Notion blocks or GitHub markdown.
- Metadata (source, URL, timestamp, author) should travel with each chunk — check it's actually stored and retrievable, not dropped during chunking.

## Embeddings & storage

- Confirm the embedding model is pinned/versioned somewhere — silently switching embedding models without re-indexing corrupts the vector space (old and new embeddings become incomparable).
- Check batch embedding calls have retry/backoff and don't fail the whole ingestion job on one bad chunk.
- Vector store: confirm there's an index/filter strategy for any access-control or source-type filtering needed at query time, not just raw top-k over everything.

## Retrieval

- Check the retrieval function used at MCP-tool-call time matches what was actually indexed (same embedding model, same distance metric).
- Look for a relevance/similarity threshold or reranking step — raw top-k with no floor will return irrelevant chunks for out-of-domain queries and degrade the calling model's output.
- Confirm retrieved chunk provenance (source, link) is surfaced back to the caller, not just raw text — needed for the model to cite sources or for the user to verify.

## Staleness / freshness

- Is there any TTL, re-sync cadence, or "last updated" tracking so the KB doesn't silently drift from the live GitHub/Notion/Discord/Telegram sources?
