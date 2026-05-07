"""Test if API key works against CodeBuddy chat completions endpoint."""
import sys
import os
import gzip
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from store.db import Store
from config import STORE_PATH

import httpx

s = Store(STORE_PATH)
sessions = [x for x in s.list_sessions() if x["status"] == "active" and "ck_" in x.get("jwt_token", "")]
if not sessions:
    print("No API key sessions found")
    sys.exit(1)

sess = sessions[-1]  # Try last one
api_key = sess["jwt_token"]  # Already has 'Bearer ' prefix
print(f"Testing with: {sess['email']} (key: {api_key[7:30]}...)")

# Test request to CodeBuddy (model uses dashes, not dots)
body = json.dumps({
    "model": "claude-opus-4-6",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Say hi in 3 words"}],
    "stream": True,
}).encode()

compressed = gzip.compress(body)

import uuid, secrets

headers = {
    "Content-Type": "application/json",
    "Content-Encoding": "gzip",
    "Accept": "application/json",
    "Authorization": api_key,
    "X-Domain": "www.codebuddy.ai",
    "X-Product": "SaaS",
    "X-IDE-Type": "CLI",
    "X-IDE-Name": "CLI",
    "X-IDE-Version": "2.95.0",
    "X-Requested-With": "XMLHttpRequest",
    "X-Agent-Intent": "craft",
    "X-Agent-Purpose": "conversation",
    "X-Conversation-ID": str(uuid.uuid4()),
    "X-Conversation-Message-ID": secrets.token_hex(16),
    "X-Conversation-Request-ID": "",
    "X-Request-ID": secrets.token_hex(16),
    "User-Agent": "CLI/2.95.0 CodeBuddy/2.95.0",
    "Origin": "https://www.codebuddy.ai",
    "Referer": "https://www.codebuddy.ai/",
}

# Also try the first account (8282mabarga) which returned 429 = auth works
sess2 = sessions[0]
print(f"Also testing: {sess2['email']} (key: {sess2['jwt_token'][7:30]}...)")

print("\nSending request to CodeBuddy /v2/chat/completions...")
print(f"Body: {body.decode()[:200]}")
resp = httpx.post(
    "https://www.codebuddy.ai/v2/chat/completions",
    content=compressed,
    headers=headers,
    timeout=30,
    verify=False,
)
print(f"Account {sess['email']}: Status={resp.status_code}")
print(f"Body: {resp.text[:300]}")

# Now test with first account
headers["Authorization"] = sess2["jwt_token"]
compressed2 = gzip.compress(body)
resp2 = httpx.post(
    "https://www.codebuddy.ai/v2/chat/completions",
    content=compressed2,
    headers=headers,
    timeout=30,
    verify=False,
)
print(f"Status: {resp.status_code}")
print(f"Body: {resp.text[:500]}")
