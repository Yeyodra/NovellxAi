"""Batch runner for automated Google OAuth login across multiple accounts."""
import asyncio
import logging
import time
from pathlib import Path

from .google_login import GoogleOAuth
from ..store.db import Store

log = logging.getLogger(__name__)


class BatchRunner:
    def __init__(self, accounts_file: str, config, store: Store):
        self.accounts_file = accounts_file
        self.config = config
        self.store = store

    async def run(self, concurrency: int = 3, delay_between: float = 10.0):
        """
        Process all accounts from accounts file:
        1. Read accounts (email:password per line, skip # comments)
        2. Filter out accounts already active in store
        3. Process with semaphore-limited concurrency
        4. Per account: login -> store JWT -> log result
        5. Print summary
        """
        accounts = self._load_accounts()
        if not accounts:
            log.error(f"No accounts found in {self.accounts_file}")
            return

        # Filter out already active accounts
        active_emails = {
            s["email"] for s in self.store.list_sessions() if s["status"] == "active"
        }
        to_process = [(e, p) for e, p in accounts if e not in active_emails]
        skipped = len(accounts) - len(to_process)

        if skipped > 0:
            log.info(f"Skipping {skipped} already-active accounts")

        if not to_process:
            print("All accounts already active. Nothing to do.")
            return

        total = len(to_process)
        print(f"Processing {total} accounts (concurrency={concurrency}, delay={delay_between}s)")
        print(f"Skipped: {skipped} (already active)")
        print("-" * 60)

        semaphore = asyncio.Semaphore(concurrency)
        results = {"success": 0, "failed": 0, "skipped": skipped}
        failed_accounts = []

        async def process_account(index: int, email: str, password: str):
            async with semaphore:
                log.info(f"[{index}/{total}] Logging in {email}...")
                oauth = GoogleOAuth(email, password, self.config)
                result = await oauth.login()

                if result["success"]:
                    jwt_token = result["jwt_token"]
                    # Ensure Bearer prefix for store
                    if not jwt_token.startswith("Bearer "):
                        jwt_token = f"Bearer {jwt_token}"

                    self.store.add_session(
                        email=email,
                        jwt_token=jwt_token,
                        user_id=result.get("user_id", ""),
                        refresh_token=result.get("refresh_token", ""),
                    )
                    results["success"] += 1
                    log.info(f"[{index}/{total}] SUCCESS: {email}")
                else:
                    results["failed"] += 1
                    error = result.get("error", "unknown")
                    failed_accounts.append(f"{email}:{password} # {error}")
                    log.error(f"[{index}/{total}] FAILED: {email} — {error}")

        # Process accounts with staggered starts
        tasks = []
        for i, (email, password) in enumerate(to_process, 1):
            task = asyncio.create_task(process_account(i, email, password))
            tasks.append(task)
            # Stagger starts to avoid rate limiting
            if i < total:
                await asyncio.sleep(delay_between)

        # Wait for all remaining tasks
        await asyncio.gather(*tasks, return_exceptions=True)

        # Write failed accounts
        if failed_accounts:
            failed_path = Path(self.accounts_file).parent / "failed_accounts.txt"
            failed_path.write_text(
                f"# Failed accounts — {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                + "\n".join(failed_accounts) + "\n",
                encoding="utf-8",
            )
            log.info(f"Failed accounts written to {failed_path}")

        # Summary
        print("\n" + "=" * 60)
        print(f"BATCH LOGIN COMPLETE")
        print(f"  Success: {results['success']}")
        print(f"  Failed:  {results['failed']}")
        print(f"  Skipped: {results['skipped']}")
        print(f"  Total:   {total + skipped}")
        print("=" * 60)

    def _load_accounts(self) -> list[tuple[str, str]]:
        """Load accounts from file. Format: email:password per line."""
        path = Path(self.accounts_file)
        if not path.exists():
            log.error(f"Accounts file not found: {self.accounts_file}")
            return []

        accounts = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":", 1)
            if len(parts) == 2:
                email, password = parts[0].strip(), parts[1].strip()
                if email and password:
                    accounts.append((email, password))
            else:
                log.warning(f"Skipping malformed line: {line[:30]}...")

        return accounts
