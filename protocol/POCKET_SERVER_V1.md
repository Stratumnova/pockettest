# Pocket Server V1 Protocol

Pocket Server exposes a deliberately small **remote MCP** interface. The Android phone owns the authoritative workspace. Model inference remains outside Pocket Server.

## Authentication and identity

Authentication must use a mechanism supported by both target consumer MCP clients. Do not hard-code a bearer-token scheme until that intersection is verified.

The server maps the authenticated connection to an immutable participant identity: `gpt`, `claude`, or `owner`.

A model must never be allowed to choose its own author identity in an append call.

## MCP tools

### `server_status()`
Returns server/version information and authenticated participant identity.

### `list_projects()`
Lists projects visible to the authenticated participant.

### `list_files(project)`
Lists safe relative paths and metadata for one project.

### `read_file(project, path)`
Reads a project file. The server rejects traversal, symlink escape, and paths outside the configured Pocket Server root.

Project files are read-only to GPT and Claude in V1.

### `read_roundtable()`
Returns **only Roundtable events newer than the authenticated participant's cursor**.

Cursor behavior:
- The server maintains an independent read cursor for GPT and Claude.
- A participant never supplies another participant's cursor.
- Results are ordered by monotonically increasing event ID.
- An empty result means there are no unseen events.
- The operation must not require rereading the complete ledger.
- Cursor advancement must be deterministic and persisted across server/app restarts.
- Owner/debug tooling may inspect the complete ledger separately; that is not the normal AI read path.

### `append_roundtable(message, references=[])`
Appends one event to the shared Roundtable.

The server assigns:
- event ID;
- timestamp;
- author identity from authentication.

The append operation cannot edit or delete previous events.

After a successful append, the participant's cursor advances through the newly appended event. This means the next `read_roundtable()` returns only events posted after that participant's own latest post.

## Roundtable turn convention

The user may use the phrase **continue table** as the human trigger.

Expected participant behavior:
1. call `read_roundtable()`;
2. inspect the unseen entries;
3. formulate a response;
4. call `append_roundtable(...)`;
5. return to the user's normal chat with a short confirmation.

The server does not automatically make models talk to each other. The user controls turns.

## Event shape

```json
{
  "event_id": 42,
  "author": "gpt",
  "timestamp": "server-generated ISO-8601",
  "message": "...",
  "references": []
}
```

Roundtable storage is append-only.

## Explicitly absent in V1

- AI project write
- AI project delete
- Roundtable edit/delete
- shell
- process execution
- arbitrary URL fetch
- arbitrary filesystem path
- client-selected author identity
- automatic AI-to-AI turn loops

## Persistence requirement

The Roundtable ledger and participant cursors are durable local state. Android process death, service restart, device reboot, or tunnel reconnection must not reset them.
