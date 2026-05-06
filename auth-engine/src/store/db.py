"""SQLite store - shared with Go proxy."""
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from .config import settings


class DB:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA busy_timeout = 5000")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def insert_account(self, email: str, enterprise_id: str = "") -> str:
        account_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT OR IGNORE INTO accounts (id, email, enterprise_id) VALUES (?, ?, ?)",
            (account_id, email, enterprise_id),
        )
        self.conn.commit()
        # Return existing id if already existed
        row = self.conn.execute("SELECT id FROM accounts WHERE email = ?", (email,)).fetchone()
        return row["id"] if row else account_id

    def insert_key(self, api_key: str, account_id: str, email: str, enterprise_id: str = ""):
        self.conn.execute(
            "INSERT OR IGNORE INTO keys (api_key, account_id, email, enterprise_id) VALUES (?, ?, ?, ?)",
            (api_key, account_id, email, enterprise_id),
        )
        self.conn.commit()

    def update_account_enterprise(self, email: str, enterprise_id: str):
        self.conn.execute(
            "UPDATE accounts SET enterprise_id = ? WHERE email = ?",
            (enterprise_id, email),
        )
        self.conn.commit()

    def update_account_login(self, email: str):
        self.conn.execute(
            "UPDATE accounts SET last_login_at = datetime('now') WHERE email = ?",
            (email,),
        )
        self.conn.commit()

    def get_account_by_email(self, email: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

    def count_active_keys(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM keys WHERE status = 'active'").fetchone()
        return row["cnt"]

    def count_keys_for_account(self, account_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM keys WHERE account_id = ?", (account_id,)
        ).fetchone()
        return row["cnt"]
