# Roundtable

This directory is the development-time representation of the shared conversation channel.

The phone implementation will own the live append-only ledger.

Participant model:
- USER/owner: full authority.
- GPT: read + append.
- CLAUDE: read + append.

Roundtable is for shared statements, findings, decisions, and handoffs. Project files remain separately protected.
