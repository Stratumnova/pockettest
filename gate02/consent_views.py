"""Development-only consent views. Not registered on the public deny-all app."""
import html
import time
from starlette.responses import HTMLResponse, JSONResponse

CSP = "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
HEADERS = {"Cache-Control": "no-store", "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def _transaction(store, txn_id):
    with store.connect() as db:
        row = db.execute("""SELECT t.txn_id,t.match_code,t.scopes,t.status,t.expires_at,
                                   c.platform_hint
                            FROM pending_txns t JOIN connections c USING(client_id)
                            WHERE t.txn_id=?""", (txn_id,)).fetchone()
    return dict(row) if row is not None else None


def _status(row, now):
    if row["status"] == "pending" and row["expires_at"] <= now:
        return "expired"
    if row["status"] == "approved" and row["expires_at"] <= now:
        return "expired"
    return row["status"]


def consent_page(store, txn_id, now=None):
    now = int(time.time()) if now is None else int(now)
    row = _transaction(store, txn_id)
    if row is None:
        return HTMLResponse("Not found", status_code=404, headers=HEADERS)
    status = _status(row, now)
    # Never expose the match code once the request is no longer pending.
    match = html.escape(row["match_code"]) if status == "pending" else "Unavailable"
    platform = html.escape(row["platform_hint"])
    scopes = html.escape(row["scopes"])
    page = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<title>Authorization waiting</title></head><body>"
            "<h1>Awaiting local owner approval</h1>"
            f"<p>Platform: {platform}</p><p>Scopes: {scopes}</p>"
            f"<p>Match code: {match}</p><p>Status: {html.escape(status)}</p>"
            "<p>Approve only through the local owner terminal.</p>"
            "</body></html>")
    return HTMLResponse(page, headers=HEADERS)


def consent_status(store, txn_id, now=None):
    now = int(time.time()) if now is None else int(now)
    row = _transaction(store, txn_id)
    if row is None:
        return JSONResponse({"status": "not_found"}, status_code=404, headers=HEADERS)
    return JSONResponse({"status": _status(row, now)}, headers=HEADERS)


def dev_consent_routes(store):
    """Call only from the isolated development app, never public server.py."""
    from starlette.routing import Route

    async def page(request):
        return consent_page(store, request.path_params["txn_id"])

    async def status(request):
        return consent_status(store, request.path_params["txn_id"])

    return [
        Route("/consent/{txn_id}", page, methods=["GET"]),
        Route("/consent/{txn_id}/status", status, methods=["GET"]),
    ]
