# Dugout.ai

## Short Overview

Dugout.ai is an AI-assisted baseball game-day production system built for a single manager to supervise live broadcast automation that normally requires a larger crew. It coordinates music, scoreboard graphics, commentary, computer-vision enrichment, and operator alerts around official game state entered from a referee mobile app.

The project is organized as a production-oriented monorepo targeting a local stadium edge deployment with Docker Compose, LAN-first networking, and a path toward field pilots before any cloud or Kubernetes rollout.

## Problem Statement

Running a live baseball broadcast—walk-up music, on-screen graphics, play-by-play commentary, camera context, and pitch-speed overlays—typically depends on several specialists working in parallel. Small venues and pilot deployments often cannot staff that full crew, yet still need reliable, low-latency production behavior during a live game.

Manual coordination also creates risk: unofficial inputs can drift from the actual game, low-confidence automation can trigger the wrong player graphic or song, and production actions are hard to audit after the fact.

## Solution / What the Project Does

Dugout.ai separates **authoritative game state** from **enrichment and automation**:

1. The **referee mobile app** records official events—balls, strikes, outs, runs, substitutions, inning changes, and corrections.
2. The **event gateway** ingests those events, persists them append-only to PostgreSQL, publishes to NATS, reduces them into live game state, and streams updates to clients over SSE.
3. The **manager dashboard** shows live scoreboard state, alerts, production status, commentary, and manual controls.
4. The **AI orchestrator** reacts to game and CV events asynchronously, enqueuing production commands for music and graphics and generating commentary off the critical path.
5. The **cv-node** reads an RTSP camera feed and publishes jersey observations for roster validation and walk-up automation.
6. Shared **protobuf contracts** keep event, state, command, and observation shapes consistent across Go, Python, and TypeScript.

Computer vision and sensors enrich production decisions; they do not replace the referee as the source of truth in v1.

## Key Features

### Game state and operations
- Referee mobile interface for pitch results, play outcomes, inning transitions, substitutions, and explicit correction events
- Append-only event log with replayable game-state reconstruction after reconnects or service restarts
- Go game-state reducer for count, inning, outs, bases, score, batter, pitcher, and corrections
- Manager dashboard with live scoreboard, event timeline, lineup view, and production status panels

### Production automation
- Command queue with priority, cooldowns, conflict groups, and manager approval for risky actions
- Walk-up music adapter with play, stop, fade, and emergency-stop controls
- Graphics adapter for scoreboard and player overlay state
- AI commentary pipeline using local Ollama LLM generation with Piper TTS fallback to template text when LLM is unavailable
- Media asset management for walk-up audio, headshots, team logos, and commentary audio files

### Computer vision and enrichment
- RTSP ingestion from MediaMTX with a fallback contour-based jersey detector for pilot testing
- Confidence gating at 70% before walk-up music commands proceed without manager approval
- Roster and lineup validation against PostgreSQL player data
- Optional radar adapter that simulates pitch-speed readings on pitch events

### Operator workflows
- Low-confidence CV alerts with confirm/override actions in the dashboard
- Manual music and commentary controls (mute, regenerate, manual text)
- Command approval and cancellation APIs
- Offline event queue in the referee app for temporary network loss

## Tech Stack

### Frontend
- React 19 + TypeScript
- Vite 8
- Server-Sent Events (SSE) for live dashboard updates
- Browser `Audio` API for music and commentary playback

### Backend
- Go 1.23 — event gateway (HTTP ingest, SSE fan-out, reverse proxy, game-state reducer)
- Python 3.10+ — AI orchestrator (FastAPI REST API + asyncio NATS daemon)
- Python — cv-node (OpenCV, ONNX Runtime) and radar-adapter (simulated pitch speed)
- FastAPI, uvicorn, asyncpg, nats-py

### Database
- PostgreSQL 16
- SQL migrations in `infra/db/migrations/`
- Pilot seed data in `infra/db/seeds_phase3.sql`

### Mobile
- React Native 0.85
- Expo 56

### APIs / Services
- Protocol Buffers contracts shared across Go, Python, and TypeScript
- NATS 2.10 with JetStream
- MediaMTX for local RTSP/HLS/WebRTC test streaming
- Ollama for local LLM commentary (`llama3.2:1b`)
- Piper TTS for commentary audio synthesis

### Testing / DevTools
- Go `testing` for reducer unit tests
- pytest for orchestrator command queue, commentary, and roster validation tests
- ESLint for the dashboard
- Make-based monorepo orchestration

### Deployment / Infrastructure
- Docker Compose for PostgreSQL, NATS, and MediaMTX
- Environment template at `env.template`
- No Redis, Kubernetes, OpenTelemetry, Prometheus, or Grafana in the current implementation

## Architecture Overview

At runtime, clients talk primarily to the **event gateway** on port `8080`. The referee app posts protobuf-JSON `GameEvent` payloads to `POST /api/v1/events`. The dashboard opens an SSE stream at `GET /api/v1/games/stream?game_id=<id>` and receives replayed history plus live frames for game state, music, graphics, commentary, and command status.

The gateway writes events to PostgreSQL, publishes to NATS subjects such as `dugout.game.{gameId}.events`, and maintains in-memory reduced game state. Most orchestrator REST routes are reverse-proxied through the gateway so the dashboard can use a single API origin.

The **AI orchestrator** runs as two processes:
- `main.py` — FastAPI service on port `8000` for roster, media, lineup, command, and control endpoints
- `orchestrator.py` — background daemon that subscribes to NATS, enqueues production commands, and triggers commentary generation asynchronously

The **cv-node** reads `rtsp://localhost:8554/homeplatecam` from MediaMTX, detects jersey numbers, and publishes observations to NATS. Observations below the 70% confidence threshold require manager approval before walk-up music is queued.

```text
Referee Mobile App ---> Event Gateway (Go) ---> PostgreSQL
                              |
                              +---> NATS ---> AI Orchestrator daemon
                              |                    |
                              |                    +--> Music / Graphics adapters
                              |                    +--> Commentary (Ollama + Piper)
                              |
CV Node (RTSP) -------------> NATS
                              |
Manager Dashboard <--- SSE + proxied REST --- Event Gateway
```

For deeper design notes, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/backend/BACKEND_OVERVIEW.md`](docs/backend/BACKEND_OVERVIEW.md), and [`PROJECT_PLAN.md`](PROJECT_PLAN.md).

## Project Structure

```text
Dugout/
  apps/
    dashboard/           # React manager control center
    referee-mobile/      # Expo referee scoring app
  services/
    event-gateway/       # Go HTTP ingest, SSE, reducer, NATS integration
    ai-orchestrator/     # FastAPI API, NATS daemon, production adapters
    cv-node/             # RTSP camera worker and jersey observation publisher
    radar-adapter/       # Simulated pitch-speed publisher
  packages/
    contracts/           # Protobuf schemas and generated Go/Python/TypeScript clients
  infra/
    compose/             # Docker Compose for Postgres, NATS, MediaMTX
    db/                  # SQL migrations and pilot seed data
  media/                 # Walk-up audio, headshots, logos, commentary output
  docs/                  # Architecture, backend, frontend, database, and testing docs
  Makefile               # setup, infra, contracts, build, test, lint
  env.template           # Environment variable reference
  RUN.md                 # Detailed local runbook
  PROJECT_PLAN.md        # Product vision and phased roadmap
  CLAUDE.md              # Implementation rules for contributors and agents
```

The repo is modular by design. Component-level documentation lives under `docs/`, including:

- [`docs/FRONTEND.md`](docs/FRONTEND.md) and `docs/frontend/` for dashboard and referee app behavior
- [`docs/backend/`](docs/backend/) for gateway, orchestrator, CV, commentary, and API routes
- [`docs/DATABASE.md`](docs/DATABASE.md) for schema and entity relationships
- [`docs/TESTING.md`](docs/TESTING.md) for current test coverage and gaps
- [`docs/GAME_STATE_AND_EVENTS.md`](docs/GAME_STATE_AND_EVENTS.md) for reducer and event semantics

## Setup and Installation

### Prerequisites

- Go 1.23+
- Node.js 18+ or 20+ with npm
- Python 3.10+ or 3.11+
- Docker and Docker Compose
- `protoc` (optional; only needed if you modify protobuf contracts)

### Initial setup

```bash
# Clone the repository and enter it
cd Dugout

# Create local environment file
cp env.template .env

# Install Go modules, Python virtual environments, and npm workspaces
make setup

# Generate Go, Python, and TypeScript types from protobuf contracts
make contracts-gen

# Start PostgreSQL, NATS, and MediaMTX
make infra-up
```

### Database migrations and seed data

Apply migrations after the Postgres container is healthy:

```bash
docker exec -i dugout-postgres psql -U dugout_admin -d dugout < infra/db/migrations/000001_init_schema.up.sql
docker exec -i dugout-postgres psql -U dugout_admin -d dugout < infra/db/migrations/000002_phase3_schema.up.sql
docker exec -i dugout-postgres psql -U dugout_admin -d dugout < infra/db/seeds_phase3.sql
```

Default database credentials are defined in `env.template` (`dugout_admin` / `dugout_secret`, database `dugout`).

### Environment variables

Key variables from `env.template`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgres://dugout_admin:dugout_secret@localhost:5432/dugout?sslmode=disable` | Database connections |
| `NATS_URL` | `nats://localhost:4222` | Messaging |
| `EVENT_GATEWAY_PORT` | `8080` | Gateway HTTP port |
| `AI_ORCHESTRATOR_URL` | `http://localhost:8000` | Orchestrator API and gateway proxy target |
| `CV_NODE_CAMERA_RTSP_STREAM` | `rtsp://localhost:8554/home_plate_cam` | CV RTSP source |
| `MEDIA_BASE_PATH` | `../../media` | Static media mount for orchestrator |

JWT and referee auth tokens exist in `env.template` as placeholders; authentication middleware is not yet implemented.

## Running the Project

Run each service in its own terminal during development.

### 1. Infrastructure

```bash
make infra-up
# Optional: follow logs
make infra-logs
```

Infrastructure ports:

- PostgreSQL: `5432`
- NATS client: `4222`, monitoring: `8222`
- MediaMTX RTSP: `8554`, HLS: `8888`, WebRTC: `8889`

### 2. Event gateway

```bash
cd services/event-gateway
go run cmd/main.go
```

Health check: `GET http://localhost:8080/health`

### 3. AI orchestrator API and daemon

```bash
cd services/ai-orchestrator
source .venv/bin/activate
uvicorn main:app --port 8000 --reload
```

In a second terminal:

```bash
cd services/ai-orchestrator
source .venv/bin/activate
python orchestrator.py
```

Optional for commentary generation:

```bash
# Run Ollama locally and pull the model used by the orchestrator
ollama pull llama3.2:1b
```

Health check: `GET http://localhost:8000/health`

### 4. CV node (optional)

```bash
cd services/cv-node
source .venv/bin/activate
python main.py
```

The current cv-node uses a fallback contour detector against the MediaMTX test stream and alternates high/low confidence observations for alert testing.

### 5. Manager dashboard

From the repo root:

```bash
npm run dashboard:dev
```

Open `http://localhost:5173`. The dashboard connects to the gateway SSE stream and shows `● LIVE` when connected.

### 6. Referee mobile app

From the repo root:

```bash
npm run referee:start
```

Use Expo web mode (`w`) for quick desktop testing, or scan the QR code with Expo Go on a device.

### Quick verification

1. Start infrastructure, migrations, gateway, dashboard, and referee app.
2. In the referee app, tap **BALL** or **STRIKE**.
3. Confirm the dashboard scoreboard updates in real time.
4. Start `cv-node` and watch low-confidence alerts appear in the dashboard alerts panel.

See [`RUN.md`](RUN.md) for a fuller step-by-step runbook.

## Testing

Run the monorepo test suite:

```bash
make test
```

This runs:

1. **Go tests** — `services/event-gateway`, including reducer coverage for balls, strikes, fouls, play outcomes, inning transitions, corrections, and substitutions
2. **Python tests** — `services/ai-orchestrator/tests/` for command queue behavior, commentary state updates, and roster validation
3. **Dashboard tests** — none are configured yet; `make test` reports that gracefully

Individual commands:

```bash
cd services/event-gateway && go test ./... -v
cd services/ai-orchestrator && .venv/bin/pytest
cd apps/dashboard && npm run lint
```

Current gaps: no frontend unit tests, no cv-node tests, no HTTP/SSE integration tests, and no end-to-end referee-to-dashboard automation. See [`docs/TESTING.md`](docs/TESTING.md) for the full coverage map.

## Future Improvements / Roadmap

Planned work is documented in [`PROJECT_PLAN.md`](PROJECT_PLAN.md). Near-term items grounded in the current codebase and docs include:

- **Field ingestion hardening** — real camera benchmarking with YOLO-family models, ONNX export, and TensorRT optimization
- **Production adapter integration** — OBS, CasparCG, Daktronics, and venue audio systems behind the existing adapter boundaries
- **Auth and device registration** — enforce JWT/referee tokens currently present only in `env.template`
- **Audit log wiring** — persist overrides, command lifecycle changes, and failed integrations to `audit_logs`
- **CV observation persistence** — write NATS observations to the existing `cv_observations` table
- **Frontend and integration tests** — dashboard/referee coverage plus referee reconnect, duplicate event, and emergency-stop scenarios listed in `CLAUDE.md`
- **Observability** — OpenTelemetry, Prometheus, Grafana, and structured trace IDs across services
- **Kubernetes and multi-venue deployment** — after the Docker Compose field pilot is validated

## Key Implementation Notes

- **Referee authority** — official game state comes from the referee app. CV observations are enrichment unless validated against roster/lineup rules or confirmed by the manager.
- **Latency-sensitive path** — game-state ingest, persistence, reduction, and SSE delivery stay in Go. LLM and TTS commentary run asynchronously and must not block official state updates.
- **Append-only events** — corrections are new events, not silent mutations. Game state is rebuilt from the event stream.
- **Confidence gate** — CV confidence below 0.70 triggers manager-visible approval before walk-up music commands proceed automatically.
- **Dual reducers** — Go owns canonical live state; Python maintains a separate in-memory reducer for commentary context. Keep both in sync when changing game-state rules.
- **Single-game pilot defaults** — both apps currently use `game_2026_ashland_vs_opponent` with seed data from `infra/db/seeds_phase3.sql`.
- **Gateway as API hub** — dashboard SSE and most REST calls go through port `8080`; orchestrator media files are served from port `8000`.
- **Pilot limitations** — no Redis cache, no implemented auth middleware, no root-level license file, and observability stack not yet integrated.

## Contributing

1. Read [`CLAUDE.md`](CLAUDE.md) for project rules around event authority, auditability, contracts, and implementation order.
2. Prefer changes that start from `packages/contracts` when event or command shapes evolve.
3. Add or update tests for reducer behavior, command queue logic, and contract-sensitive paths before expanding UI around new behavior.
4. Use `make lint` and `make test` before opening a pull request.
5. Keep venue-specific values in configuration and seed data, not hardcoded in application logic.

For service-specific details, start with the docs under [`docs/`](docs/) and the runbook in [`RUN.md`](RUN.md).

## License

No project-level license file is present in this repository. The referee mobile app directory includes the Expo MIT license for Expo-related tooling; that license does not apply to the full monorepo unless separately stated by the project owners.
