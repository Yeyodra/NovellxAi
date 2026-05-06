#!/usr/bin/env python3
"""Batch login using enowxai's CodeBuddy provider adapter."""
import argparse
import asyncio
import os
import sys
import time
import logging
from pathlib import Path

# Ensure 'app' package resolves from src/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.providers.codebuddy import CodeBuddyProviderAdapter
from app.providers.base import NormalizedAccount
from app.errors.exceptions import BatcherError
from store.db import Store
from config import STORE_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 2.0


def load_accounts(path: str) -> list[tuple[str, str]]:
    accounts = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":", 1)
        if len(parts) == 2:
            accounts.append((parts[0].strip(), parts[1].strip()))
    return accounts


async def login_single(adapter: CodeBuddyProviderAdapter, email: str, password: str, store: Store) -> bool:
    account = NormalizedAccount(
        provider="codebuddy",
        identifier=email,
        secret=password,
        raw=f"{email}:{password}",
    )

    session = None
    try:
        session = await adapter.bootstrap_session(account)
        log.info(f"[{email}] Browser session ready")

        auth_state = await adapter.authenticate(account, session)
        log.info(f"[{email}] Authenticated")

        tokens = await adapter.fetch_tokens(account, auth_state, session)
        log.info(f"[{email}] Tokens obtained")

        api_key = tokens.get("api_key", "")
        if api_key:
            store.add_session(
                email=email,
                jwt_token="",
                user_id="",
                refresh_token="",
                api_key=api_key,
            )
            log.info(f"[{email}] API key stored (ck_...{api_key[-8:]})")
            return True
        else:
            log.error(f"[{email}] No API key in tokens: {tokens}")
            return False

    except BatcherError as e:
        log.error(f"[{email}] {e.code}: {e.message}")
        return False
    except Exception as e:
        log.error(f"[{email}] Unexpected error: {e}")
        return False
    finally:
        if session and isinstance(session, dict) and not session.get("stub"):
            try:
                await adapter.cleanup_session(session)
            except Exception:
                pass


async def run_batch(accounts_file: str, concurrency: int, delay: float):
    accounts = load_accounts(accounts_file)
    if not accounts:
        log.error(f"No accounts found in {accounts_file}")
        return

    store = Store(STORE_PATH)

    # Filter already active
    active_emails = {s["email"] for s in store.list_sessions() if s["status"] == "active"}
    to_process = [(e, p) for e, p in accounts if e not in active_emails]
    skipped = len(accounts) - len(to_process)

    if skipped:
        log.info(f"Skipping {skipped} already-active accounts")
    if not to_process:
        print("All accounts already active.")
        return

    total = len(to_process)
    print(f"Processing {total} accounts (concurrency={concurrency}, delay={delay}s)")
    print("-" * 60)

    semaphore = asyncio.Semaphore(concurrency)
    success = 0
    failed = 0
    failed_list = []

    adapter = CodeBuddyProviderAdapter()

    async def process(idx: int, email: str, password: str):
        nonlocal success, failed
        async with semaphore:
            log.info(f"[{idx}/{total}] Logging in {email}...")
            ok = await login_single(adapter, email, password, store)
            if ok:
                success += 1
                log.info(f"[{idx}/{total}] SUCCESS: {email}")
            else:
                failed += 1
                failed_list.append(f"{email}:{password}")
                log.error(f"[{idx}/{total}] FAILED: {email}")

    tasks = []
    for i, (email, password) in enumerate(to_process, 1):
        tasks.append(asyncio.create_task(process(i, email, password)))
        if i < total:
            await asyncio.sleep(delay)

    await asyncio.gather(*tasks, return_exceptions=True)

    # Write failed
    if failed_list:
        failed_path = Path(accounts_file).parent / "failed_accounts.txt"
        failed_path.write_text("\n".join(failed_list) + "\n", encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"BATCH COMPLETE: {success} success, {failed} failed, {skipped} skipped")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Batch login via CodeBuddy OAuth")
    parser.add_argument("accounts_file", nargs="?", default=str(Path(__file__).parent.parent / "accounts.txt"))
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    if args.visible:
        os.environ["BATCHER_CAMOUFOX_HEADLESS"] = "false"
        os.environ["BATCHER_ENABLE_CAMOUFOX"] = "true"
    elif args.headless:
        os.environ["BATCHER_CAMOUFOX_HEADLESS"] = "true"
        os.environ["BATCHER_ENABLE_CAMOUFOX"] = "true"
    else:
        os.environ["BATCHER_ENABLE_CAMOUFOX"] = "true"

    asyncio.run(run_batch(args.accounts_file, args.concurrency, args.delay))


if __name__ == "__main__":
    main()
