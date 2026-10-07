# Decisions

- D001: Keep the authoritative project files owner-controlled.
- D002: GPT and Claude receive read-only access to project files for V1.
- D003: Roundtable is the only AI-writable shared area and is append-only.
- D004: GPT and Claude use different credentials.
- D005: Identity is derived from the credential; clients cannot submit an arbitrary author identity.
- D006: Do not expose the Android device filesystem generally. Expose only the configured Pocket Server root.
- D007: Do not expose a shell, arbitrary execution, delete, or rename to AI clients in V1.
- D008: Keep model inference outside Pocket Server. No OpenAI/Anthropic model API is required.
- D009: Use pockettest as the proving ground before building a large Android interface.
- D010: Shared operational context is intentionally readable by both GPT and Claude.
