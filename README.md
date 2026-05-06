# aiproxy

Personal AI proxy that routes requests through CodeBuddy.ai (Tencent) using JWT session tokens.

## Architecture

```
Client (OpenCode/etc) → aiproxy (:8090) → gzip → CodeBuddy /v2/chat/completions → response
```

## Components

- **proxy/** - Go HTTP proxy with sticky session rotation, SSE streaming, gzip compression
- **auth-engine/** - Python auth engine (Camoufox + Playwright) for session farming
- **start-proxy.bat** - One-click launcher

## Supported Models

| Model Name | Backend |
|---|---|
| `claude-opus-4.6` | Claude Opus 4.6 (hidden) |
| `gpt-5.5` | GPT 5.5 |
| `default-model-lite` | codewise-default-cw-api-3 |
| `codewise-default-cw-api-3` | Claude Haiku 4.5 |

## Quick Start

1. Double-click `start-proxy.bat`
2. Point your client to `http://localhost:8090/v1/chat/completions`
3. Use Bearer token from `proxy/config.yaml`
