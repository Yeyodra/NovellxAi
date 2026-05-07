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
    """Add a session from API key or JWT token."""
    store = Store(STORE_PATH)

    if len(args) < 2:
        print("Usage: python -m src.main add <email> <api_key_or_jwt> [refresh_token]")
        print("")
        print("  api_key: CodeBuddy API key (ck_...) — preferred")
        print("  jwt_token: Bearer token (fallback)")
        print("")
        print("How to get API key:")
        print("  1. Go to https://www.codebuddy.ai/profile/keys")
        print("  2. Create new API key")
        print("  3. Copy the ck_... value")
        print("")
        print("Or use batch-login to auto-generate keys for multiple accounts")
        sys.exit(1)

    email = args[0]
    credential = args[1]
    refresh_tok = args[2] if len(args) > 2 else ""

    # Auto-detect: API key starts with ck_, otherwise treat as JWT
    if credential.startswith("ck_"):
        session_id = store.add_session(email, jwt_token="", user_id="", refresh_token="", api_key=credential)
    else:
        session_id = store.add_session(email, jwt_token=credential, user_id="", refresh_token=refresh_tok)

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
        print("No sessions. Use 'add' or 'batch-login' to add API keys.")
        return

    print(f"{'ID':>4}  {'Status':<10}  {'Cur':<4}  {'Auth':<8}  {'Email':<30}  {'Credential':<20}")
    print("-" * 85)
    for s in sessions:
        current = "*" if s.get("is_current") else ""
        api_key = s.get("api_key", "")
        jwt = s.get("jwt_token", "")
        if api_key:
            auth_type = "apikey"
            cred = api_key[:15] + "..." if len(api_key) > 15 else api_key
        elif jwt:
            auth_type = "jwt"
            cred = jwt[:15] + "..."
        else:
            auth_type = "none"
            cred = "-"
        print(f"{s['id']:>4}  {s['status']:<10}  {current:<4}  {auth_type:<8}  {s['email']:<30}  {cred:<20}")

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
        # API-key sessions don't need JWT refresh
        if s.get("api_key") and not s.get("jwt_token"):
            log.info(f"Skipping {s['email']} — uses API key (no JWT refresh needed)")
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


def cmd_batch_login(args):
    """Batch login via enowxai CodeBuddy adapter (Camoufox + Google OAuth)."""
    import subprocess
    src_dir = Path(__file__).parent

    # Build command: python batch_login.py [accounts_file] [flags]
    cmd = [sys.executable, str(src_dir / "batch_login.py")] + args
    subprocess.run(cmd, cwd=str(src_dir))


def cmd_help(_args):
    print("""
aiproxy auth-engine — Session Manager

Commands:
  add <email> <api_key_or_jwt>              Add session (auto-detects ck_ vs JWT)
  add-har <har_file> [email_label]          Extract session from HAR file
  remove <email>                             Remove a session
  list                                       List all sessions
  refresh                                    Refresh all JWT tokens
  batch-login [accounts_file] [options]      Batch login via Google OAuth → API key
  help                                       Show this help

Auth Flow:
  batch-login → Camoufox Google OAuth → generate API key (ck_...) → store
  Proxy reads api_key → hits CodeBuddy /v2/chat/completions with X-API-Key header

Batch Login Options:
  --concurrency <n>    Max parallel browsers (default: 3)
  --delay <seconds>    Delay between account starts (default: 10)
  --headless           Run browsers headless (default)
  --visible            Show browser windows

Examples:
  python -m src.main add user@gmail.com "ck_fl9e98b4d98g.xxxxx"
  python -m src.main add user@gmail.com "Bearer eyJhbG..."
  python -m src.main list
  python -m src.main batch-login accounts.txt --concurrency 5 --visible
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
        "batch-login": cmd_batch_login,
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
