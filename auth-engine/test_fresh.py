"""Test fresh API key against CodeBuddy."""
import sys, os, gzip, json, uuid, secrets
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from store.db import Store
from config import STORE_PATH
import httpx

s = Store(STORE_PATH)
sessions = [x for x in s.list_sessions() if x["email"] == "rerollcursorke1@gmail.com"]
if not sessions:
    print("Account not found")
    sys.exit(1)

sess = sessions[0]
api_key = sess["jwt_token"]
print(f"Account: {sess['email']}")
print(f"Key: {api_key[:40]}...")
print(f"Status: {sess['status']}")
print()

body = json.dumps({
    "model": "claude-opus-4-6",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Say hello in exactly 3 words"}],
    "stream": True,
}).encode()

compressed = gzip.compress(body)

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

print("Sending to /v2/chat/completions (stream=true)...")
with httpx.stream(
    "POST",
    "https://www.codebuddy.ai/v2/chat/completions",
    content=compressed,
    headers=headers,
    timeout=30,
    verify=False,
) as resp:
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print("STREAMING RESPONSE:")
        for line in resp.iter_lines():
            if line:
                print(f"  {line[:200]}")
    else:
        print(f"Body: {resp.read().decode()[:500]}")
