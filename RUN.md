# Running Dugout.ai

This document provides detailed, step-by-step instructions on setting up, configuring, running, and verifying each layer of the **Dugout.ai** system.

---

## 🛠 Prerequisites

Ensure you have the following installed on your local development machine:

- **Go**: Version `1.23+` (used for the Event Gateway)
- **Node.js**: Version `18+` or `20+` & `npm` (used for Dashboard, Referee App, and Contracts generation)
- **Python**: Version `3.10+` or `3.11+` & `venv` (used for AI Orchestrator and CV Node)
- **Docker & Docker Compose**: For local infrastructure (PostgreSQL, NATS, MediaMTX)
- **Protobuf Compiler (`protoc`)**: For regenerating contract types (optional, if modified)

---

## ⚙️ Environment Setup

1. Copy the global environment template to create a local `.env` file at the root:
   ```bash
   cp env.template .env
   ```

2. Open the `.env` file and review the default configuration. By default, all services are pre-configured to communicate seamlessly on `localhost`.

---

## 🚀 Quick Start (Monorepo orchestration)

The project includes a top-level `Makefile` to orchestrate common setup and runtime tasks.

### 1. Install & Set Up Dependencies
Run the setup target to configure all package managers, virtual environments, and Node modules:
```bash
make setup
```
*This command runs `go mod tidy` in the Event Gateway, initializes Python virtual environments (`.venv`) for `ai-orchestrator` and `cv-node` with updated `pip` and package installations, and runs `npm install` at the root workspace.*

### 2. Generate Protocol Buffer Contracts
Build the type definitions for Go, Python, and TypeScript from the shared definitions in `packages/contracts`:
```bash
make contracts-gen
```

### 3. Spin Up Infrastructure
Start NATS, PostgreSQL, and MediaMTX in detached mode:
```bash
make infra-up
```
*You can follow the logs of the infrastructure containers at any time with:*
```bash
make infra-logs
```

### 4. Run Database Migrations
Once the database container is healthy, apply the database schema. You can execute the migration script using the running PostgreSQL container:
```bash
docker exec -i dugout-postgres psql -U dugout_admin -d dugout < infra/db/migrations/000001_init_schema.up.sql
```

---

## 🖥 Running Individual Layers

For debugging or active development, you should run each component in its own terminal pane/window.

### 1. Database & Infrastructure
If not using `make`, spin up using docker-compose directly:
```bash
docker compose -f infra/compose/docker-compose.yml up -d
```
- **Postgres Database**: Port `5432` (`database: dugout`, `user: dugout_admin`, `password: dugout_secret`)
- **NATS Broker**: Port `4222` (client connection), Port `8222` (HTTP monitoring console)
- **MediaMTX Video Streamer**: Port `8554` (RTSP), Port `1935` (RTMP), Port `8888` (HLS), Port `8889` (WebRTC)

---

### 2. Backend: Go Event-Gateway
The gateway ingests official referee actions and CV observations, runs the game-state reducer, writes to the database audit logs, and streams live state updates to the dashboards via SSE.

```bash
cd services/event-gateway
go run cmd/main.go
```
- **Port**: `8080`
- **Endpoints**:
  - `GET /health` (Health check)
  - `POST /api/v1/events` (Event ingestion endpoint)
  - `GET /api/v1/games/stream?game_id=<id>` (SSE Stream for dashboard client)

---

### 3. Backend: Python AI Orchestrator
The AI Orchestrator handles LLM commentary, context-building, and automated venue adapters (such as music and TTS triggers) reacting to NATS events.

```bash
cd services/ai-orchestrator
source .venv/bin/activate
uvicorn main:app --port 8000 --reload
```
- **Port**: `8000`
- **Endpoints**:
  - `GET /health` (Health check and protobuf contract loading status)

---

### 4. Models & CV Layer: Python CV Edge Node
The CV Edge Node monitors the camera feed (simulated RTSP stream) and runs YOLO inference.

#### Running the CV Node Daemon:
```bash
cd services/cv-node
source .venv/bin/activate
python main.py
```
- **Stream Target**: Ingests RTSP feeds from MediaMTX (default stream: `rtsp://localhost:8554/home_plate_cam`).

#### Simulating Model Detections (Mock CV Publisher):
You can simulate computer vision models publishing jersey number observations to NATS to test alerts, validation, and dashboard overrides:
```bash
cd services/cv-node
source .venv/bin/activate

# Publish a mixed stream of high-confidence and low-confidence detections (Recommended for testing)
python mock_publisher.py mixed

# Publish only high-confidence detections (>70%, automatically processed)
python mock_publisher.py high

# Publish only low-confidence detections (<70%, requires operator confirmation)
python mock_publisher.py low
```

---

### 5. Frontend: Manager Dashboard (Web UI)
The Control Center Dashboard displays real-time game-day metrics, active field observations, low-confidence alerts, overrides, and camera feeds.

Run the dashboard from the workspace root:
```bash
npm run dashboard:dev
```
Or navigate and run directly:
```bash
cd apps/dashboard
npm run dev
```
- **URL**: `http://localhost:5173`
- *The dashboard will automatically establish a Server-Sent Events (SSE) connection to the Go Event Gateway.*

---

### 6. Frontend: Referee Mobile App (Expo / React Native)
The referee app is the official source of truth for the game state, used to input balls, strikes, outs, runs, and inning changes.

Run the referee app from the workspace root:
```bash
npm run referee:start
```
Or navigate and run directly:
```bash
cd apps/referee-mobile
npm run start
```
- **Running Options**:
  - Press `w` to run in the local web browser (ideal for quick desktop testing).
  - Install the **Expo Go** app on your iOS/Android device, and scan the QR code displayed in the terminal to run it on your mobile device.

---

## 🧪 Testing & Verification Workflow

Verify the entire monorepo flow is working end-to-end:

### 1. Verification Checklist
1. Ensure NATS and Postgres are running (`docker ps`).
2. Start the Event-Gateway Go server.
3. Start the Manager Dashboard and open `http://localhost:5173`. You should see `● LIVE` in the top header, indicating a successful SSE connection.
4. Start the Referee Mobile App in Web mode (`w`) and open the provided URL.
5. In the Referee app, click **BALL** or **STRIKE** button.
6. **Observe the Dashboard**: The count (Balls, Strikes) should update in real-time (< 250ms latency) on the dashboard scoreboard.

### 2. Testing CV Alerts & Overrides
1. Run the mock CV publisher in mixed mode:
   ```bash
   cd services/cv-node && source .venv/bin/activate && python mock_publisher.py mixed
   ```
2. You will see high-confidence observations processed, while low-confidence observations (confidence < 0.70) trigger a prominent alert on the Manager Dashboard.
3. In the Dashboard under **Alerts & Overrides**, press **Confirm** or **Override** to test manager interventions.

### 3. Automated Test Suites
To execute unit tests across all directories, run:
```bash
make test
```
*Individual test runs:*
- **Event Gateway**: `cd services/event-gateway && go test ./...`
- **AI Orchestrator**: `cd services/ai-orchestrator && .venv/bin/pytest`
- **Dashboard**: `cd apps/dashboard && npm run lint` (or workspace tests if configured)
