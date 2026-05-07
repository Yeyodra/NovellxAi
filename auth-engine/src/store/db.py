"""Shared JSON store — same format as Go proxy reads."""
import json
import os
import time
import base64
from pathlib import Path
from typing import Optional


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.data = {"sessions": [], "accounts": [], "request_log": []}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            raw = open(self.path, "r", encoding="utf-8").read()
            # Strip BOM
            if raw.startswith("\ufeff"):
                raw = raw[1:]
            if raw.strip():
                self.data = json.loads(raw)

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def _next_id(self) -> int:
        ids = [s["id"] for s in self.data["sessions"]]
        return max(ids, default=0) + 1

    def add_session(self, email: str, jwt_token: str, user_id: str, refresh_token: str = "", api_key: str = ""):
        """Add or update a session. If email exists, update token."""
        # Guard: if a ck_ API key was accidentally passed as jwt_token, move it to api_key
        if jwt_token and jwt_token.startswith("ck_"):
            api_key = jwt_token
            jwt_token = ""

        # Ensure jwt_token has Bearer prefix
        if jwt_token and not jwt_token.startswith("Bearer "):
            jwt_token = f"Bearer {jwt_token}"

        # Auto-detect user_id from JWT if not provided
        if not user_id and jwt_token:
            user_id = self._extract_sub_from_jwt(jwt_token)

        # Auto-detect expiry from JWT
        expires_at = self._extract_exp_from_jwt(jwt_token) if jwt_token else ""

        for i, s in enumerate(self.data["sessions"]):
            if s["email"] == email:
                if jwt_token:
                    self.data["sessions"][i]["jwt_token"] = jwt_token
                if user_id:
                    self.data["sessions"][i]["user_id"] = user_id
                if refresh_token:
                    self.data["sessions"][i]["refresh_token"] = refresh_token
                if api_key:
                    self.data["sessions"][i]["api_key"] = api_key
                self.data["sessions"][i]["status"] = "active"
                if expires_at:
                    self.data["sessions"][i]["expires_at"] = expires_at
                self._save()
                return self.data["sessions"][i]["id"]

        session = {
            "id": self._next_id(),
            "email": email,
            "account_id": email,
            "jwt_token": jwt_token,
            "api_key": api_key,
            "user_id": user_id,
            "refresh_token": refresh_token,
            "status": "active",
            "is_current": len(self.data["sessions"]) == 0,  # First one becomes current
            "remaining_quota": 0,
            "last_used_at": "",
            "expires_at": expires_at,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        self.data["sessions"].append(session)

        # Also add account entry
        emails = [a["email"] for a in self.data["accounts"]]
        if email not in emails:
            self.data["accounts"].append({
                "id": email,
                "email": email,
                "enterprise_id": "",
                "status": "active",
                "last_login_at": "",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            })

        self._save()
        return session["id"]

    def remove_session(self, email: str) -> bool:
        before = len(self.data["sessions"])
        self.data["sessions"] = [s for s in self.data["sessions"] if s["email"] != email]
        if len(self.data["sessions"]) < before:
            self._save()
            return True
        return False

    def list_sessions(self) -> list[dict]:
        return self.data["sessions"]

    def count_active(self) -> int:
        return sum(1 for s in self.data["sessions"] if s["status"] == "active")

    def _extract_sub_from_jwt(self, jwt_token: str) -> str:
        """Extract 'sub' (user ID) from JWT payload."""
        try:
            token = jwt_token.replace("Bearer ", "")
            payload_b64 = token.split(".")[1]
            # Add padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload.get("sub", "")
        except Exception:
            return ""

    def _extract_exp_from_jwt(self, jwt_token: str) -> str:
        """Extract expiry from JWT payload."""
        try:
            token = jwt_token.replace("Bearer ", "")
            payload_b64 = token.split(".")[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get("exp", 0)
            if exp:
                return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(exp))
        except Exception:
            pass
        return ""
