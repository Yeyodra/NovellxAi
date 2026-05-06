"""CLI for managing aiproxy sessions — add, remove, list, refresh JWT tokens."""
import sys
import json
import logging
from pathlib import Path

from .config import STORE_PATH
from .store.db import Store
from .codebuddy.auth import refresh_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def cmd_add(args):
    """Add a session from JWT token."""
    store = Store(STORE_PATH)

    if len(args) < 2:
        print("Usage: python -m src.main add <email> <jwt_token> [refresh_token]")
        print("")
        print("  jwt_token: The full Bearer token (with or without 'Bearer ' prefix)")
        print("  refresh_token: Optional, for automatic token refresh")
        print("")
        print("How to get JWT token:")
        print("  1. Open HTTP Toolkit or browser DevTools")
        print("  2. Use CodeBuddy CLI or extension")
        print("  3. Find request to /v2/chat/completions")
        print("  4. Copy the Authorization header value")
        sys.exit(1)

    email = args[0]
    jwt_token = args[1]
    refresh_tok = args[2] if len(args) > 2 else ""

    session_id = store.add_session(email, jwt_token, user_id="", refresh_token=refresh_tok)
    active = store.count_active()
    print(f"Added session #{session_id} for {email} (pool: {active} active)")


def cmd_add_from_har(args):
    """Add session(s) from HAR file — auto-extracts JWT tokens."""
    store = Store(STORE_PATH)

    if len(args) < 1:
        print("Usage: python -m src.main add-har <path-to-har-file> [email-label]")
        sys.exit(1)

    har_path = args[0]
    email_label = args[1] if len(args) > 1 else "har-import"

    if not Path(har_path).exists():
        print(f"File not found: {har_path}")
        sys.exit(1)

    har = json.loads(Path(har_path).read_text(encoding="utf-8"))
    entries = har.get("log", {}).get("entries", [])

    # Find chat completions requests to extract tokens
    found = 0
    for entry in entries:
        url = entry.get("request", {}).get("url", "")
        status = entry.get("response", {}).get("status", 0)

        if "v2/chat/completions" in url and status == 200:
            headers = entry["request"].get("headers", [])
            auth = next((h["value"] for h in headers if h["name"] == "Authorization"), "")
            user_id = next((h["value"] for h in headers if h["name"] == "X-User-Id"), "")

            if auth and user_id:
                # Find refresh token from same session
                refresh_tok = ""
                for e2 in entries:
                    if "auth/token/refresh" in e2.get("request", {}).get("url", ""):
                        rh = e2["request"].get("headers", [])
                        rt = next((h["value"] for h in rh if h["name"] == "X-Refresh-Token"), "")
                        if rt:
                            refresh_tok = rt
                            break

                label = f"{email_label}-{found + 1}" if found > 0 else email_label
                session_id = store.add_session(label, auth, user_id, refresh_tok)
                found += 1
                print(f"Extracted session #{session_id} (user: {user_id[:20]}..., refresh: {'yes' if refresh_tok else 'no'})")
                break  # Only need 1 token per HAR (they share same session)

    if found == 0:
        print("No valid tokens found in HAR file")
        sys.exit(1)

    active = store.count_active()
    print(f"Total active sessions: {active}")


def cmd_remove(args):
    """Remove a session by email."""
    store = Store(STORE_PATH)
    if len(args) < 1:
        print("Usage: python -m src.main remove <email>")
        sys.exit(1)

    if store.remove_session(args[0]):
        print(f"Removed {args[0]}")
    else:
        print(f"Not found: {args[0]}")


def cmd_list(_args):
    """List all sessions."""
    store = Store(STORE_PATH)
    sessions = store.list_sessions()

    if not sessions:
        print("No sessions. Use 'add' or 'add-har' to add tokens.")
        return

    print(f"{'ID':>4}  {'Status':<10}  {'Current':<8}  {'Email':<30}  {'Expires':<20}  {'User ID':<20}")
    print("-" * 100)
    for s in sessions:
        current = "*" if s.get("is_current") else ""
        user_short = s.get("user_id", "")[:18] + ".." if len(s.get("user_id", "")) > 18 else s.get("user_id", "")
        exp = s.get("expires_at", "")[:19] if s.get("expires_at") else "unknown"
        print(f"{s['id']:>4}  {s['status']:<10}  {current:<8}  {s['email']:<30}  {exp:<20}  {user_short:<20}")

    active = store.count_active()
    print(f"\nActive: {active}/{len(sessions)}")


def cmd_refresh(args):
    """Refresh JWT tokens for all active sessions that have refresh tokens."""
    store = Store(STORE_PATH)
    sessions = store.list_sessions()

    refreshed = 0
    failed = 0

    for s in sessions:
        if s["status"] != "active":
            continue
        if not s.get("refresh_token"):
            log.info(f"Skipping {s['email']} — no refresh token")
            continue

        log.info(f"Refreshing {s['email']}...")
        result = refresh_token(s["jwt_token"], s["refresh_token"], s["user_id"])

        if result:
            new_jwt = f"Bearer {result['accessToken']}"
            new_refresh = result.get("refreshToken", s["refresh_token"])
            store.add_session(s["email"], new_jwt, s["user_id"], new_refresh)
            refreshed += 1
            log.info(f"Refreshed {s['email']}")
        else:
            failed += 1
            log.error(f"Failed to refresh {s['email']}")

    print(f"Refreshed: {refreshed}, Failed: {failed}")


def cmd_help(_args):
    print("""
aiproxy auth-engine — Session Manager

Commands:
  add <email> <jwt_token> [refresh_token]   Add a session manually
  add-har <har_file> [email_label]          Extract session from HAR file
  remove <email>                             Remove a session
  list                                       List all sessions
  refresh                                    Refresh all JWT tokens
  help                                       Show this help

Examples:
  python -m src.main add user@gmail.com "Bearer eyJhbG..."
  python -m src.main add-har ~/Downloads/HTTPToolkit.har account1
  python -m src.main list
  python -m src.main refresh
""")


def main():
    if len(sys.argv) < 2:
        cmd_help([])
        sys.exit(1)

    commands = {
        "add": cmd_add,
        "add-har": cmd_add_from_har,
        "remove": cmd_remove,
        "list": cmd_list,
        "refresh": cmd_refresh,
        "help": cmd_help,
    }

    cmd = sys.argv[1]
    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        cmd_help([])
        sys.exit(1)

    commands[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
