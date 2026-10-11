"""Stage 2 identity and permission-boundary tests."""
import pytest

from identity import IdentityConfigurationError, load_identities, require_local_owner

GPT = "A" * 32
CLAUDE = "B" * 32


def valid_env():
    return {"POCKET_GPT_PATH": GPT, "POCKET_CLAUDE_PATH": CLAUDE}


def test_valid_distinct_identities():
    identities = load_identities(valid_env())
    assert identities.path_for("gpt") == "/" + GPT
    assert identities.path_for("claude") == "/" + CLAUDE
    assert identities.identify("/" + GPT) == "gpt"
    assert identities.identify("/" + CLAUDE) == "claude"


@pytest.mark.parametrize("actor", ["owner", "GPT", "", "other"])
def test_unknown_remote_actor_denied(actor):
    with pytest.raises(IdentityConfigurationError):
        load_identities(valid_env()).path_for(actor)


@pytest.mark.parametrize("value", [
    "", "short", "CHANGE-ME" + "A" * 40,
    "PLACEHOLDER" + "A" * 40, "a/b" + "A" * 32,
    "../" + "A" * 32, "A" * 129, "a b" + "A" * 32,
    "ü" * 32, "/" + "A" * 32,
])
def test_bad_secrets_fail_closed(value):
    env = valid_env()
    env["POCKET_GPT_PATH"] = value
    with pytest.raises(IdentityConfigurationError):
        load_identities(env)


def test_missing_secret_fails_closed():
    with pytest.raises(IdentityConfigurationError):
        load_identities({"POCKET_GPT_PATH": GPT})


def test_duplicate_secrets_fails_closed():
    with pytest.raises(IdentityConfigurationError):
        load_identities({"POCKET_GPT_PATH": GPT, "POCKET_CLAUDE_PATH": GPT})


@pytest.mark.parametrize("path", [
    GPT, "/" + GPT + "/", "/" + GPT + "/mcp", "/" + GPT + "?x=1",
    "/" + GPT.lower(), "/" + CLAUDE + "/mcp", "", "/owner",
])
def test_no_prefix_or_substring_auth(path):
    assert load_identities(valid_env()).identify(path) is None


@pytest.mark.parametrize("actor,loopback,allowed", [
    ("owner", True, True), ("owner", False, False),
    ("gpt", True, False), ("claude", True, False),
    ("owner", None, False),
])
def test_owner_cli_boundary(actor, loopback, allowed):
    if allowed:
        assert require_local_owner(peer_is_loopback=loopback, actor=actor) is None
    else:
        with pytest.raises(PermissionError):
            require_local_owner(peer_is_loopback=loopback, actor=actor)
