"""Test device auth flow to get JWT token (not API key)."""
import sys, os, json, asyncio, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import aiohttp

CODEBUDDY_BASE_URL = "https://www.codebuddy.ai"
CLI_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "CLI/2.54.0 CodeBuddy/2.54.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


async def main():
    # Step 1: Get auth state
    print("Step 1: POST /v2/plugin/auth/state...")
    async with aiohttp.ClientSession(headers=CLI_HEADERS) as client:
        async with client.post(f"{CODEBUDDY_BASE_URL}/v2/plugin/auth/state?platform=IDE", json={}) as resp:
            print(f"  Status: {resp.status}")
            data = await resp.json()
            print(f"  Code: {data.get('code')}")
            state_data = data.get("data", {})
            state = state_data.get("state", "")
            auth_url = state_data.get("authUrl", "")
            print(f"  State: {state[:30]}...")
            print(f"  AuthUrl: {auth_url[:80]}...")

    if not state or not auth_url:
        print("FAILED: No state/authUrl returned")
        return

    # Step 2: Open browser for OAuth (using enowxai's adapter)
    print(f"\nStep 2: Opening browser for OAuth...")
    os.environ["BATCHER_ENABLE_CAMOUFOX"] = "true"
    os.environ["BATCHER_CAMOUFOX_HEADLESS"] = "false"

    from app.providers.codebuddy import CodeBuddyProviderAdapter
    from app.providers.base import NormalizedAccount

    adapter = CodeBuddyProviderAdapter()
    account = NormalizedAccount(
        provider="codebuddy",
        identifier="akuncursorke8@gmail.com",
        secret="bintang088",
        raw="akuncursorke8@gmail.com:bintang088",
    )

    # Bootstrap creates browser + navigates to authUrl
    session = await adapter.bootstrap_session(account)
    print(f"  Browser ready, session state: {session.get('state', '')[:30]}...")

    # Authenticate (handles Google OAuth)
    auth_state = await adapter.authenticate(account, session)
    print(f"  Authenticated: {auth_state.get('authenticated')}")

    # Use the ORIGINAL state from Step 1 (not adapter's internal state)
    actual_state = state
    print(f"  Using original state for polling: {actual_state[:30]}...")

    # Step 3: Poll for JWT token (GET, not POST — matching CLIProxyAPIPlus)
    print(f"\nStep 3: Polling /v2/plugin/auth/token with state={actual_state[:30]}...")
    poll_url = f"{CODEBUDDY_BASE_URL}/v2/plugin/auth/token"

    async with aiohttp.ClientSession(headers=CLI_HEADERS) as client:
        for attempt in range(30):  # Poll for up to 60 seconds
            # GET with state as query param (like CLIProxyAPIPlus does)
            async with client.get(f"{poll_url}?state={actual_state}") as resp:
                status = resp.status
                try:
                    body = await resp.json()
                except Exception:
                    text = await resp.text()
                    print(f"  Non-JSON response: status={status} body={text[:200]}")
                    await asyncio.sleep(2)
                    continue
                code = body.get("code", -1)

                if status == 200 and code == 0:
                    token_data = body.get("data", {})
                    access_token = token_data.get("accessToken", "")
                    refresh_token = token_data.get("refreshToken", "")
                    print(f"  SUCCESS! Got JWT (length={len(access_token)})")
                    print(f"  Access token: {access_token[:50]}...")
                    print(f"  Refresh token: {refresh_token[:30]}...")

                    # Now test this JWT against /v2/chat/completions
                    print(f"\nStep 4: Testing JWT against /v2/chat/completions...")
                    import gzip, uuid, secrets as sec
                    test_body = json.dumps({
                        "model": "claude-opus-4-6",
                        "max_tokens": 50,
                        "messages": [{"role": "user", "content": "Say hi"}],
                        "stream": True,
                    }).encode()
                    compressed = gzip.compress(test_body)

                    # Parse user_id from JWT
                    import base64
                    jwt_payload = access_token.split(".")[1]
                    padding = 4 - len(jwt_payload) % 4
                    if padding != 4:
                        jwt_payload += "=" * padding
                    claims = json.loads(base64.urlsafe_b64decode(jwt_payload))
                    user_id = claims.get("sub", "")
                    print(f"  User ID from JWT: {user_id}")

                    test_headers = {
                        "Content-Type": "application/json",
                        "Content-Encoding": "gzip",
                        "Accept": "application/json",
                        "Authorization": f"Bearer {access_token}",
                        "X-User-Id": user_id,
                        "X-Domain": "www.codebuddy.ai",
                        "X-Product": "SaaS",
                        "X-IDE-Type": "CLI",
                        "X-IDE-Name": "CLI",
                        "X-IDE-Version": "2.95.0",
                        "X-Requested-With": "XMLHttpRequest",
                        "X-Agent-Intent": "craft",
                        "X-Agent-Purpose": "conversation",
                        "X-Conversation-ID": str(uuid.uuid4()),
                        "X-Conversation-Message-ID": sec.token_hex(16),
                        "X-Request-ID": sec.token_hex(16),
                        "User-Agent": "CLI/2.95.0 CodeBuddy/2.95.0",
                    }

                    async with client.post(
                        f"{CODEBUDDY_BASE_URL}/v2/chat/completions",
                        data=compressed,
                        headers=test_headers,
                    ) as chat_resp:
                        print(f"  Chat Status: {chat_resp.status}")
                        chat_body = await chat_resp.text()
                        print(f"  Response: {chat_body[:300]}")

                    # Cleanup
                    try:
                        await adapter.cleanup_session(session)
                    except Exception:
                        pass
                    return

                elif code == 14001:  # Not yet authenticated
                    if attempt % 5 == 0:
                        print(f"  Polling... (attempt {attempt+1}, waiting for auth)")
                    await asyncio.sleep(2)
                else:
                    print(f"  Poll response: status={status} code={code} msg={body.get('msg','')}")
                    await asyncio.sleep(2)

    print("TIMEOUT: Token polling failed after 60s")
    try:
        await adapter.cleanup_session(session)
    except Exception:
        pass


asyncio.run(main())
