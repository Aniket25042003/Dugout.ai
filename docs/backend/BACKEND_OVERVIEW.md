# Backend Overview

**One-liner:** Three services — Go gateway, Python orchestrator, Python cv-node.

## Why it exists

Latency-sensitive event routing stays in Go. Production automation (music, graphics, commentary) lives in Python where LLM/TTS libraries are available. CV runs as a separate edge process reading RTSP streams.

## How it works

### Service map

| Service | Language | Port | Entry | Role |
|---------|----------|------|-------|------|
| event-gateway | Go | 8080 | `cmd/main.go` | HTTP ingest, SSE, reverse-proxy |
| ai-orchestrator API | Python/FastAPI | 8000 | `main.py` | REST for roster, media, commands |
| ai-orchestrator daemon | Python/asyncio | — | `orchestrator.py` | NATS subscriber, production automation |
| cv-node | Python | — | `main.py` | RTSP → jersey detection → NATS |

### Directory structure

```
services/
├── event-gateway/
│   ├── cmd/main.go              # HTTP server entry
│   └── internal/
│       ├── db/db.go             # Event persistence
│       ├── reducer/reducer.go   # Game-state reducer
│       └── server/
│           ├── server.go        # Ingest, NATS, SSE
│           └── sse.go           # SSE broker
├── ai-orchestrator/
│   ├── main.py                  # FastAPI REST API
│   ├── orchestrator.py          # Background daemon
│   ├── command_queue.py         # Production command queue
│   ├── music_adapter.py         # Walk-up music
│   ├── graphics_adapter.py      # Scoreboard/overlays
│   ├── commentary_engine.py     # LLM + TTS commentary
│   ├── llm_client.py            # Ollama HTTP client
│   ├── tts_client.py            # Piper TTS
│   ├── db_client.py             # asyncpg queries
│   ├── media_manager.py         # Asset resolution/upload
│   └── tests/                   # pytest unit tests
└── cv-node/
    └── main.py                  # RTSP reader + NATS publisher
```

### Infrastructure (`infra/`)

| Path | Role |
|------|------|
| `compose/docker-compose.yml` | Postgres 16, NATS 2.10 (-js), MediaMTX |
| `db/migrations/` | SQL schema up/down |
| `db/seeds_phase3.sql` | Pilot roster, walk-up assets, lineups |

### Environment variables

From [`env.template`](../env.template):

| Variable | Default | Configures |
|----------|---------|------------|
| `DATABASE_URL` | `postgres://dugout_admin:...@localhost:5432/dugout` | All DB connections |
| `NATS_URL` | `nats://localhost:4222` | NATS pub/sub |
| `EVENT_GATEWAY_PORT` | `8080` | Gateway HTTP port |
| `AI_ORCHESTRATOR_URL` | `http://localhost:8000` | Gateway reverse-proxy target |
| `AI_ORCHESTRATOR_PORT` | `8000` | FastAPI port |
| `CV_NODE_CAMERA_RTSP_STREAM` | `rtsp://localhost:8554/home_plate_cam` | cv-node RTSP source |
| `CV_CONFIDENCE_THRESHOLD` | `0.70` | Orchestrator CV gate (in code, not env.template) |
| `MEDIA_BASE_PATH` | `../../media` | Orchestrator static file mount |
| `JWT_SECRET` | placeholder | **Not implemented** |
| `REFEREE_AUTH_TOKEN` | placeholder | **Not implemented** |

### Local dev startup order

1. `make infra-up` — Postgres, NATS, MediaMTX
2. Apply migrations + `seeds_phase3.sql`
3. `go run cmd/main.go` in event-gateway
4. `uvicorn main:app` in ai-orchestrator
5. `python orchestrator.py` in ai-orchestrator (separate terminal)
6. `python main.py` in cv-node (optional)
7. Ollama running locally for LLM commentary (optional; template fallback works)

## Architecture diagram

```mermaid
flowchart TD
  subgraph gateway [event-gateway Go]
    HTTP[HTTP routes]
    SSEBroker[SSE broker]
    Reducer[reducer.go]
    DBGo[db.go]
  end

  subgraph orch [ai-orchestrator Python]
    FastAPI[main.py API]
    Daemon[orchestrator.py]
    CmdQ[command_queue.py]
    Music[music_adapter.py]
    Graphics[graphics_adapter.py]
    Commentary[commentary_engine.py]
  end

  subgraph cv [cv-node Python]
    RTSP[RTSP reader]
    Detector[FallbackVisualDetector]
  end

  HTTP --> DBGo
  HTTP --> SSEBroker
  Daemon --> CmdQ
  CmdQ --> Music
  CmdQ --> Graphics
  Daemon --> Commentary
  RTSP --> Detector
```

## Key code callouts

- [`services/event-gateway/cmd/main.go`](../services/event-gateway/cmd/main.go) — service wiring and proxy routes
- [`services/ai-orchestrator/orchestrator.py`](../services/ai-orchestrator/orchestrator.py) — `OrchestratorDaemon.start()`
- [`services/ai-orchestrator/main.py`](../services/ai-orchestrator/main.py) — FastAPI lifecycle and all REST endpoints
- [`packages/contracts/`](../packages/contracts/) — shared protobuf source of truth

## Tech decisions

1. **Two orchestrator processes** — FastAPI handles HTTP; daemon handles NATS without blocking API requests.
2. **Gateway reverse-proxy** — dashboard talks to one port (8080) for both SSE and REST.
3. **Contracts package** — protobuf generates Go, Python, and TypeScript clients from single `.proto` files.

## Talking points

- Makefile `build` compiles gateway and dashboard but does not start orchestrator daemon automatically.
- `piper` package used by `tts_client.py` is not listed in `requirements.txt`.
- No Redis, Celery, or Kubernetes in v1 — Docker Compose only.
