# A25 Document Format and Storage Policy

Status: Zed-authorized working rule, 2026-10-16 (exact message time not verified).

## Storage
- GitHub `a25-training/A25_gpt_transcripts/` is the default durable location for GPT-authored A25 transcripts, reports, records and requested archives.
- Markdown (`.md`) or other GitHub-compatible text is the complete editable source of record, not an abridged summary.
- PDFs are generated for Zed's local reading and download **when requested**, from the matching source text. PDF download is not a prerequisite for repository storage.
- Future Claude sessions and builders should read the repository source directly, using a commit-pinned raw link and a manifest where appropriate.

## Fidelity
- Preserve tables, headings, evidence references, attribution, disagreements, open findings, and document scope in the Markdown.
- Identify source and PDF rendering version and any intentional visual-only differences. Do not claim byte equality across different formats.
- A PDF supplied by Zed for conversion should be transcribed or extracted into a complete Markdown source to the extent supported by the PDF; identify unreadable, image-only, or omitted content explicitly.
- Full transcript labels require complete source coverage; otherwise label a reconstruction or partial extract.
- Corrections are separate and traceable; do not silently overwrite original evidence.

## Security and permissions
The public repository must not contain credentials, secret paths, canary details, or personal documents. GPT writes; Claude independently reviews when available; Zed decides. This policy does not certify implementation of automatic Pocket Server synchronization.
