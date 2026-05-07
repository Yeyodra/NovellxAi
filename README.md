# NovellaxAI

AI proxy that routes OpenAI-compatible requests through CodeBuddy.ai (Tencent) with session rotation, health checks, and auto-failover.

## Architecture

```
Client (OpenCode/Cursor/etc) → NovellaxAI (:8090) → CodeBuddy /v2/chat/completions → response
```

## Components

- **proxy/** - Go HTTP proxy with sticky session rotation, SSE streaming, Bearer auth
- **auth-engine/** - Python auth engine (Camoufox + Playwright) for session farming
- **dashboard/** - React + Vite + Tailwind dashboard UI
- **start-proxy.bat** - One-click launcher

## Supported Models

| Model Name | Backend |
|---|---|
| `claude-opus-4.6` | Claude Opus 4.6 |
| `gpt-5.5` | GPT 5.5 |
| `default-model` | codewise-default-cw-api-4 |
| `default-model-lite` | codewise-default-cw-api-3 |
| `gemini-3.1-pro` | Gemini 3.1 Pro |

## Quick Start

1. Double-click `start-proxy.bat`
2. Point your client to `http://localhost:8090/v1/chat/completions`
3. Use Bearer token from `proxy/config.yaml`

## Build

```bash
cd proxy
go build -o novellaxai.exe ./cmd/proxy
```
