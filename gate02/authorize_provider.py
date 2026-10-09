"""C3 development-only OAuth authorize adapter; not mounted on public server."""
from mcp.server.auth.provider import AuthorizeError
from client_registration import C2ClientRegistration

CONSENT_ORIGIN = "https://roundtable.rodsrcpark.com"


class C3AuthorizeProvider(C2ClientRegistration):
    """Only authorize() is implemented; token issuance is deliberately absent."""

    async def authorize(self, client, params):
        state = getattr(params, "state", None)
        if not isinstance(state, str) or not state:
            raise AuthorizeError(error="invalid_request", error_description="Nonempty state required")

        redirect_uri = str(params.redirect_uri)
        explicitly = params.redirect_uri_provided_explicitly
        if not isinstance(explicitly, bool):
            raise AuthorizeError(error="invalid_request", error_description="Invalid redirect flag")

        try:
            txn_id, _match_code = self.auth_store.create_pending(
                client_id=client.client_id,
                redirect_uri=redirect_uri,
                state=state,
                code_challenge=params.code_challenge,
                scopes=params.scopes,
                resource=params.resource,
                redirect_uri_provided_explicitly=explicitly,
            )
        except (ValueError, TypeError) as exc:
            raise AuthorizeError(error="invalid_request", error_description="Authorization rejected") from exc
        return f"{CONSENT_ORIGIN}/consent/{txn_id}"
