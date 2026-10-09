"""Local-only Gate-02A C1 administrative CLI. No HTTP listener."""
import argparse
import os
from pathlib import Path
from auth_store import AuthStore

def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Pocket Server auth administration")
    parser.add_argument("--db", default=os.environ.get("POCKET_AUTH_DB", str(Path(__file__).with_name("auth.sqlite3"))))
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("pending")
    create = sub.add_parser("create-profile")
    create.add_argument("human")
    create.add_argument("platform")
    approve = sub.add_parser("approve")
    approve.add_argument("txn")
    approve.add_argument("--profile", required=True)
    deny = sub.add_parser("deny")
    deny.add_argument("txn")
    revoke = sub.add_parser("revoke")
    revoke.add_argument("client_id")
    revoke_profile = sub.add_parser("revoke-profile")
    revoke_profile.add_argument("profile")
    args = parser.parse_args(argv)
    store = AuthStore(args.db)
    if args.action == "pending":
        for txn in store.pending():
            print(f"{txn['txn_id']}  {txn['match_code']}  {txn['platform_hint']}  {txn['client_name']}  {txn['created_at']}")
    elif args.action == "create-profile":
        print(store.create_profile(args.human,args.platform))
    elif args.action == "approve":
        print("APPROVED" if store.approve(store.resolve_pending_code(args.txn) if len(args.txn)==4 and args.txn.isdigit() else args.txn,args.profile) else "NOT APPROVED")
    elif args.action == "deny":
        print("DENIED" if store.deny(store.resolve_pending_code(args.txn) if len(args.txn)==4 and args.txn.isdigit() else args.txn) else "NOT DENIED")
    elif args.action == "revoke":
        print("REVOKED" if store.revoke_connection(args.client_id) else "NOT REVOKED")
    elif args.action == "revoke-profile":
        print("REVOKED" if store.revoke_profile(args.profile) else "NOT REVOKED")

if __name__ == "__main__":
    main()
