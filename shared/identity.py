"""Stage 2 identity configuration for Shared Space (no remote owner endpoint).

This module does not grant execution permissions or alter Gate-01 history.
Secret path values are supplied only by the phone's runtime environment.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from hmac import compare_digest
from typing import Mapping

ACTORS = ("gpt", "claude")
_SECRET_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z", re.ASCII)


class IdentityConfigurationError(ValueError):
    """A credential is absent, weak, or ambiguous."""


@dataclass(frozen=True)
class IdentityConfig:
    """Immutable mapping of remote actors to distinct private path segments."""

    gpt_path: str
    claude_path: str

    def path_for(self, actor: str) -> str:
        if actor == "gpt":
            return self.gpt_path
        if actor == "claude":
            return self.claude_path
        raise IdentityConfigurationError("unknown remote actor")

    def identify(self, path: str) -> str | None:
        """Constant-time compare; no prefix, query, or substring matching."""
        if not isinstance(path, str) or not path.isascii():
            return None
        gpt = compare_digest(path, self.gpt_path)
        claude = compare_digest(path, self.claude_path)
        if gpt:
            return "gpt"
        if claude:
            return "claude"
        return None


def _parse_secret(value: str | None, name: str) -> str:
    if value is None or not _SECRET_PATTERN.fullmatch(value):
        raise IdentityConfigurationError(
            f"{name} must be a 32-128 character URL-safe random path segment"
        )
    if "CHANGE-ME" in value.upper() or "PLACEHOLDER" in value.upper():
        raise IdentityConfigurationError(f"{name} contains a placeholder")
    return "/" + value


def load_identities(env: Mapping[str, str] | None = None) -> IdentityConfig:
    """Fail closed; do not generate, print, or persist credentials."""
    source = os.environ if env is None else env
    gpt = _parse_secret(source.get("A25_SHARED_GPT_PATH"), "A25_SHARED_GPT_PATH")
    claude = _parse_secret(source.get("A25_SHARED_CLAUDE_PATH"), "A25_SHARED_CLAUDE_PATH")
    if compare_digest(gpt, claude):
        raise IdentityConfigurationError("GPT and Claude credentials must differ")
    return IdentityConfig(gpt_path=gpt, claude_path=claude)
