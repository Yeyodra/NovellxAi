"""Main CLI entry point for auth engine."""
import asyncio
import logging
import sys
from pathlib import Path

import click

from .config import settings
from .store.db import DB
from .oauth.google_login import GoogleOAuth
from .codebuddy.auth import CodeBuddyAuth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def load_accounts(path: str) -> list[tuple[str, str]]:
    """Load email:password pairs from accounts file."""
    accounts = []
    p = Path(path)
    if not p.exists():
        log.warning(f"Accounts file not found: {path}")
        return accounts

    for line in p.read_text().strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Support email:password or email|password
        sep = "|" if "|" in line else ":"
        parts = line.split(sep, 1)
        if len(parts) == 2:
            accounts.append((parts[0].strip(), parts[1].strip()))
    return accounts


async def farm_single_account(email: str, password: str, db: DB) -> bool:
    """Full pipeline: OAuth -> region setup -> create API key -> store in DB."""
    log.info(f"=== Farming: {email} ===")

    # Step 1: Get auth state from CodeBuddy
    try:
        auth_data = CodeBuddyAuth.get_auth_state()
        auth_url = auth_data.get("authUrl", "")
        if not auth_url:
            log.error(f"No auth URL returned for {email}")
            return False
    except Exception as e:
        log.error(f"Failed to get auth state: {e}")
        return False

    # Step 2: Browser OAuth login
    oauth = GoogleOAuth(email, password)
    result = await oauth.login(auth_url)

    if not result.get("success"):
        log.error(f"OAuth failed for {email}: {result.get('error', 'unknown')}")
        return False

    cookies = result["cookies"]
    if not cookies:
        log.error(f"No cookies obtained for {email}")
        return False

    # Step 3-5: CodeBuddy API interactions
    cb = CodeBuddyAuth(cookies)
    try:
        # Setup region
        cb.setup_region()

        # Get enterprise ID
        enterprise_id = cb.get_enterprise_id()
        if not enterprise_id:
            log.error(f"No enterprise ID for {email}")
            return False

        # Register + activate trial
        cb.register_user(enterprise_id)
        cb.activate_trial()

        # Create API key
        api_key = cb.create_api_key(enterprise_id)
        if not api_key:
            log.error(f"Failed to create API key for {email}")
            return False

        # Claim gift credits
        cb.claim_gift()

        # Store in shared SQLite
        account_id = db.insert_account(email, enterprise_id)
        db.insert_key(api_key, account_id, email, enterprise_id)
        db.update_account_login(email)

        active = db.count_active_keys()
        log.info(f"SUCCESS: {email} -> {api_key[:15]}... (pool: {active} active keys)")
        return True

    except Exception as e:
        log.error(f"CodeBuddy API error for {email}: {e}")
        return False
    finally:
        cb.close()


@click.group()
def cli():
    """AI Proxy Auth Engine - CodeBuddy key farmer."""
    pass


@cli.command()
@click.option("--count", default=0, help="Max accounts to process (0 = all)")
@click.option("--accounts-file", default=settings.ACCOUNTS_FILE, help="Path to accounts.txt")
def farm(count: int, accounts_file: str):
    """Farm API keys from CodeBuddy accounts."""
    db = DB()
    accounts = load_accounts(accounts_file)

    if not accounts:
        log.error("No accounts found. Create accounts.txt with email:password lines.")
        sys.exit(1)

    if count > 0:
        accounts = accounts[:count]

    log.info(f"Farming {len(accounts)} accounts...")

    success = 0
    failed = 0

    for email, password in accounts:
        try:
            ok = asyncio.run(farm_single_account(email, password, db))
            if ok:
                success += 1
            else:
                failed += 1
        except Exception as e:
            log.error(f"Unexpected error for {email}: {e}")
            failed += 1

    log.info(f"Done: {success} success, {failed} failed")
    active = db.count_active_keys()
    log.info(f"Total active keys in pool: {active}")
    db.close()


@cli.command()
@click.option("--accounts-file", default=settings.ACCOUNTS_FILE)
def claim_credits(accounts_file: str):
    """Claim daily gift credits for all accounts."""
    db = DB()
    accounts = load_accounts(accounts_file)
    claimed = 0

    for email, password in accounts:
        try:
            # Need to login first to get session cookies
            ok = asyncio.run(_claim_for_account(email, password))
            if ok:
                claimed += 1
        except Exception as e:
            log.error(f"Claim failed for {email}: {e}")

    log.info(f"Credits claimed for {claimed}/{len(accounts)} accounts")
    db.close()


async def _claim_for_account(email: str, password: str) -> bool:
    """Login and claim credits for one account."""
    auth_data = CodeBuddyAuth.get_auth_state()
    auth_url = auth_data.get("authUrl", "")
    if not auth_url:
        return False

    oauth = GoogleOAuth(email, password)
    result = await oauth.login(auth_url)
    if not result.get("success"):
        return False

    cb = CodeBuddyAuth(result["cookies"])
    try:
        return cb.claim_gift()
    finally:
        cb.close()


@cli.command()
def status():
    """Show current key pool status."""
    db = DB()
    active = db.count_active_keys()
    print(f"Active keys: {active}")
    db.close()


@cli.command()
@click.argument("api_key")
@click.option("--email", default="manual", help="Account email")
def add_key(api_key: str, email: str):
    """Manually add an API key to the pool."""
    db = DB()
    account_id = db.insert_account(email)
    db.insert_key(api_key, account_id, email)
    active = db.count_active_keys()
    print(f"Key added. Active keys: {active}")
    db.close()


if __name__ == "__main__":
    cli()
