# Dugout.ai Project Plan

## 1. Product Vision

Dugout.ai is an AI-assisted baseball game-day production system that reduces a large production crew to one manager/operator by automating the major live-production tasks around a baseball game:

- Music playback, including player-specific walk-up music.
- Scoreboard graphics, player graphics, lower thirds, and game-state visuals.
- Live commentary for online audiences.
- Camera tracking and clip/context capture.
- Pitch speed and sensor logging.
- Confidence monitoring, anomaly alerts, and manual override workflows.

The system is designed for a real field pilot first. The v1 deployment should run on a single local stadium edge server with GPU acceleration, Docker Compose, local LAN networking, and a clear path to Kubernetes once the pilot proves the workflow.

## 2. Core Operating Model

Dugout.ai uses automation where it is reliable and human authority where accuracy matters most.

- The referee mobile app is the authoritative source for official game-state events in v1: balls, strikes, outs, scoring, substitutions, inning transitions, and timer controls.
- Computer vision and sensors provide enrichment: player identity suggestions, camera tracking, pitch speed, object tracking, and production context.
- The manager dashboard is the operational control center: live feeds, confidence scores, current game state, alerts, audit history, and manual overrides.
- Automated production actions are always traceable through an audit log: what triggered the action, which service made the decision, confidence level, source event IDs, and whether a human confirmed or overrode it.

## 3. Primary Users

- Manager/operator: supervises the whole production, resolves low-confidence cases, manually overrides incorrect automation, and keeps the game-day show running.
- Referee/umpire input user: submits official game-state events through a fast mobile interface.
- Online audience: receives synchronized commentary, scoreboard context, and camera/video presentation.
- Venue production team: configures rosters, music, scoreboard templates, camera feeds, and venue-specific integrations before the game.

## 4. Feature Set

### 4.1 Game-State Automation

- Referee app buttons for ball, strike, foul, out, hit, walk, run scored, home run, substitution, inning transition, timer start/stop/reset, and correction.
- Canonical game-state reducer that converts event streams into current count, inning, outs, bases, score, batter, pitcher, lineup position, and game clock.
- Replayable event history to reconstruct game state after service restarts or network drops.
- Manual correction events instead of destructive edits.

### 4.2 Music Automation

- Player-specific walk-up music triggered by confirmed batter identity and lineup position.
- Music command queue with cooldowns, fade-in/fade-out, volume targets, and emergency stop.
- Manager override for wrong player, inappropriate timing, or venue interruption.
- Support for fallback music when the player track is unavailable.

### 4.3 Scoreboard Graphics Automation

- Dynamic player graphics driven by roster, batting order, jersey recognition, and official game state.
- Scoreboard templates for batter intro, pitcher intro, count, score, inning, speed, lower-third player card, replay cue, and sponsor-safe interstitials.
- Confidence-based approval for player graphics when CV confidence is below threshold.
- Output adapter boundary so the system can later integrate with Daktronics, OBS, CasparCG, or venue-specific scoreboard controllers.

### 4.4 Commentary Automation

- Structured commentary context generated from official game-state events, roster metadata, CV observations, and pitch/speed logs.
- AI commentary service that produces short play-by-play lines first, with optional TTS audio output after text quality is validated.
- Commentary guardrails:
  - Do not invent player stats or outcomes.
  - Treat referee events as truth.
  - Label CV-derived context internally as unconfirmed unless validated.
  - Keep latency-sensitive production actions independent from LLM/TTS latency.
- Manager can mute, approve, regenerate, or switch to manual commentary mode.

### 4.5 CV, Camera, And Sensor Automation

- RTSP camera ingestion from fixed or PTZ cameras.
- Jersey/player detection and tracking for walk-up music, scoreboard graphics, and commentary context.
- Active roster validation to reject staff, water runners, irrelevant players, and false positives.
- Camera tracking observations for framing suggestions or future PTZ automation.
- Pitch speed integration from radar gun, scoreboard feed, or manual/referee input where direct hardware integration is not available.

### 4.6 Alerts And Manual Override

- Low-confidence alert when CV recognition confidence falls below 70%.
- Manager verification workflow targeted at 3 to 5 seconds.
- Alert types:
  - Low CV confidence.
  - Player not on active roster.
  - Duplicate/contradictory official event.
  - Missing media asset.
  - Network delay or disconnected client.
  - Production command failure.
- Manual override events are first-class events and must be written to the audit log.

## 5. Architecture

### 5.1 High-Level Flow

```text
Referee Mobile App ---> Event Gateway --------+
                                              |
CV Nodes -------------> Event Gateway --------+--> NATS/JetStream --> Game-State Service
                                              |                         |
Radar/Speed Feed -----> Event Gateway --------+                         |
                                                                        v
                                                            AI Orchestrator
                                                                  |
                         +----------------------------------------+--------------------------------+
                         |                                        |                                |
                  Music Adapter                         Graphics Adapter                  Commentary Service
                         |                                        |                                |
                         v                                        v                                v
                Venue Audio System                       Scoreboard/OBS                 Text/TTS Stream

Manager Dashboard <---------------- WebSocket/SSE API <---------------- Event Gateway + Game State
```

### 5.2 Service Boundaries

- `apps/dashboard`: React + TypeScript manager dashboard.
- `apps/referee-mobile`: React Native + Expo mobile app for official inputs.
- `services/event-gateway`: Go service for WebSocket/SSE ingestion, auth, validation, fan-out, and low-latency event routing.
- `services/ai-orchestrator`: Python/FastAPI service for production decisioning, commentary context creation, AI commentary, and production command routing.
- `services/cv-node`: edge CV worker for camera ingest, detection, tracking, confidence scoring, and observation publishing.
- `packages/contracts`: shared schemas for events, observations, commands, game state, API DTOs, and generated clients.
- `infra`: Docker Compose, environment templates, local NATS/Postgres/Redis/MediaMTX config, and later Kubernetes manifests.
- `docs`: implementation notes, venue setup guides, pilot checklists, data collection guidance, and runbooks.

### 5.3 Recommended Repo Structure

```text
Dugout/
  apps/
    dashboard/
    referee-mobile/
  services/
    event-gateway/
    ai-orchestrator/
    cv-node/
  packages/
    contracts/
    config/
    test-fixtures/
  infra/
    docker/
    compose/
    k8s/
    mediamtx/
    observability/
  docs/
    architecture/
    runbooks/
    pilots/
    data/
  scripts/
  PROJECT_PLAN.md
  CLAUDE.md
```

## 6. Technology Stack

### 6.1 Edge CV And Inference

- OpenCV for image processing and tracking utilities.
- GStreamer or FFmpeg for RTSP camera ingestion and frame extraction.
- YOLO-family detector benchmarking instead of locking one model prematurely.
- ONNX Runtime for portable inference.
- TensorRT for NVIDIA GPU optimization in the stadium edge server.
- Python for early model experiments and dataset tooling.
- C++ for latency-critical production inference if Python prototype latency is insufficient.

### 6.2 Backend And Realtime

- Go for the event gateway and high-concurrency realtime transport.
- WebSocket for bidirectional dashboard/referee communication where needed.
- Server-Sent Events for read-only live event streams where simpler transport is enough.
- Python/FastAPI for AI orchestration, commentary generation, TTS integration, and non-realtime orchestration APIs.
- NATS with JetStream for low-latency pub/sub and replayable event streams.

### 6.3 Frontend And Mobile

- React + TypeScript for the manager dashboard.
- React Native + Expo for the referee mobile app.
- Shared generated types from `packages/contracts`.
- Dashboard UI should be dense, operational, and reliable: live state first, alerts clear, manual controls always reachable.

### 6.4 Data And Persistence

- PostgreSQL for teams, rosters, players, games, lineups, media assets, audit logs, event metadata, and configuration.
- Redis optional for hot state, transient locks, and short-lived command deduplication.
- Object storage later for clips, generated media, training data, and long-term archives.

### 6.5 Video And Production Integrations

- MediaMTX or equivalent RTSP/WebRTC bridge for local video routing.
- OBS, CasparCG, or scoreboard-specific adapters for graphics output.
- Audio adapter layer for local playback, Dante/virtual audio routing, or venue audio system integration.

### 6.6 Deployment And Observability

- Docker Compose for v1 single-edge-server deployment.
- Kubernetes after field pilot validation and multi-node requirements.
- OpenTelemetry for traces and structured telemetry.
- Prometheus and Grafana for metrics.
- Structured JSON logs across all services.
- Health checks for event broker, database, CV nodes, dashboard API, mobile clients, and production adapters.

## 7. Public Interfaces

All services must use shared contracts from `packages/contracts`. Do not invent per-service payload shapes.

### 7.1 Canonical Game Event

```json
{
  "event_id": "evt_01H...",
  "game_id": "game_2026_ashland_vs_opponent",
  "source": "referee_app",
  "source_device_id": "ref_phone_1",
  "event_type": "pitch_result",
  "occurred_at": "2026-05-25T19:03:21.125Z",
  "received_at": "2026-05-25T19:03:21.180Z",
  "sequence": 1024,
  "payload": {
    "result": "strike",
    "batter_id": "player_17",
    "pitcher_id": "player_22"
  },
  "confidence": 1.0,
  "authority": "official",
  "correlation_id": "corr_01H..."
}
```

Required behavior:

- Referee app events are authoritative in v1.
- Corrections must be appended as new events.
- Duplicate sequence numbers must be detected and handled idempotently.
- Every event must be replayable.

### 7.2 CV Observation

```json
{
  "observation_id": "obs_01H...",
  "game_id": "game_2026_ashland_vs_opponent",
  "camera_id": "home_plate_cam",
  "observed_at": "2026-05-25T19:03:19.840Z",
  "observation_type": "jersey_number",
  "payload": {
    "jersey_number": "12",
    "team_side": "home",
    "bbox": {
      "x": 0.42,
      "y": 0.18,
      "width": 0.11,
      "height": 0.24
    },
    "track_id": "track_8891"
  },
  "confidence": 0.83,
  "model": {
    "name": "jersey-detector",
    "version": "pilot-001",
    "runtime": "onnxruntime-tensorrt"
  }
}
```

Required behavior:

- CV observations are enrichment unless promoted through validation or manager confirmation.
- Observations below 70% confidence must create an alert if they are needed for a production action.
- Observed jersey numbers must be cross-validated against active roster and lineup context.

### 7.3 Production Command

```json
{
  "command_id": "cmd_01H...",
  "game_id": "game_2026_ashland_vs_opponent",
  "command_type": "play_walkup_music",
  "target": "music_adapter",
  "created_at": "2026-05-25T19:03:21.240Z",
  "source_event_ids": ["evt_01H...", "obs_01H..."],
  "payload": {
    "player_id": "player_17",
    "asset_id": "asset_walkup_17",
    "fade_in_ms": 250,
    "max_duration_ms": 20000
  },
  "requires_manager_confirmation": false,
  "status": "queued"
}
```

Required behavior:

- Commands must be idempotent.
- Commands must have source event IDs for auditability.
- Production adapters must report accepted, started, completed, failed, or cancelled status.
- Risky or low-confidence commands must require manager confirmation.

### 7.4 Manual Override Event

```json
{
  "event_id": "evt_override_01H...",
  "game_id": "game_2026_ashland_vs_opponent",
  "source": "manager_dashboard",
  "event_type": "manual_override",
  "occurred_at": "2026-05-25T19:03:24.000Z",
  "payload": {
    "override_type": "confirm_player_identity",
    "original_observation_id": "obs_01H...",
    "selected_player_id": "player_17",
    "reason": "manager_confirmed_low_confidence_cv"
  },
  "authority": "manager"
}
```

Required behavior:

- Overrides must never mutate history silently.
- Override reason and operator identity are required.
- Overrides must be visible in replay mode.

## 8. Implementation Roadmap

### Phase 0: Foundation And Repo Setup

Goal: create a professional monorepo foundation that prevents messy implementation later.

- Create the repo structure listed above.
- Add shared contracts before building service-specific payloads.
- Add local Docker Compose with NATS, PostgreSQL, Redis, and service placeholders.
- Add environment templates and documented required variables.
- Add linting, formatting, tests, and CI checks per language.
- Define game-state reducer rules and fixtures before building the dashboard.
- Define roster, team, player, game, lineup, media asset, and audit log models.

Deliverables:

- Clean monorepo structure.
- Shared contract package.
- Local development setup.
- Initial event fixtures and reducer test cases.

### Phase 1: Simulation MVP For Field-Pilot Readiness

Goal: prove the whole operational loop without real cameras or scoreboard hardware.

- Build referee mobile app with official event buttons and correction flow.
- Build Go event gateway for ingesting referee events and broadcasting state.
- Build game-state reducer and replay mechanism.
- Build manager dashboard with:
  - Current inning, score, count, outs, base state, batter, pitcher.
  - Event timeline.
  - Confidence alerts.
  - Manual override controls.
  - Simulated camera/CV feed panel.
- Build mocked CV publisher for jersey observations and low-confidence scenarios.
- Build AI orchestration skeleton for commentary text and production command creation.
- Build simulated production adapters for music, graphics, and commentary.

Deliverables:

- End-to-end simulated inning.
- Event replay after restart.
- Low-confidence alert workflow.
- Manual override written to audit log.

### Phase 2: Real Field Ingestion

Goal: connect the system to real camera and sensor inputs.

- Add RTSP camera ingestion through MediaMTX/GStreamer/FFmpeg.
- Collect field footage across lighting, angles, home/away uniforms, dugout movement, and crowd occlusion.
- Benchmark YOLO-family models against:
  - Jersey-number accuracy.
  - Player/person localization.
  - Inference latency.
  - False positives from staff/non-players.
  - GPU and CPU utilization.
- Export best candidate to ONNX and optimize with TensorRT when available.
- Implement active-roster and lineup validation.
- Add pitch/speed input adapter from radar, scoreboard feed, or manual entry.
- Add camera tracking logs for commentary and future PTZ automation.

Deliverables:

- Real camera observations published into NATS.
- CV confidence and roster validation visible in dashboard.
- Benchmark report with recommended model/runtime.
- Speed observations available to commentary context.

### Phase 3: Production Automation

Goal: trigger real production outputs safely.

- Implement music adapter for walk-up music, stop/fade, fallback track, and emergency stop.
- Implement graphics adapter boundary for scoreboard/OBS/CasparCG integration.
- Implement commentary generation with structured prompts and optional TTS.
- Add command queueing, cooldowns, cancellation, and conflict resolution.
- Require manager approval for commands based on unconfirmed CV or risky state.
- Add media asset management for player music, headshots, team branding, and graphics templates.

Deliverables:

- Music automation in a controlled venue test.
- Graphics automation in a simulated or OBS-based output.
- Commentary text stream generated from official game events.
- Command status and failures visible in dashboard.

### Phase 4: Pilot Hardening

Goal: make the system reliable enough for a live field pilot with one manager.

- Add offline mode for referee app when network drops, with ordered sync on reconnect.
- Add replay mode for debugging and post-game review.
- Add operator runbook and pre-game checklist.
- Add production kill switch.
- Add service health panel to dashboard.
- Add latency metrics and alerts.
- Add structured logs and trace IDs across event, command, and adapter flows.
- Run simulated full-game tests and field rehearsals.

Deliverables:

- Full-game rehearsal pass.
- Operator runbook.
- Observability dashboard.
- Deployment checklist.
- Field-pilot acceptance report.

### Phase 5: Kubernetes And Cloud Upgrade

Goal: scale beyond one field and one edge server after the pilot.

- Move from Docker Compose to Kubernetes manifests or Helm charts.
- Split CV nodes across multiple edge devices if needed.
- Add cloud sync for historical games, analytics, and asset management.
- Add multi-venue configuration.
- Add secure remote monitoring and update workflow.
- Add long-term data warehouse for player/game analytics and model improvement.

Deliverables:

- Kubernetes deployment path.
- Multi-venue configuration model.
- Cloud sync architecture.
- Long-term analytics plan.

## 9. Data Model Overview

Core entities:

- `Venue`: stadium configuration, network details, camera locations, scoreboard/audio integration settings.
- `Team`: team identity, colors, logos, roster relationship.
- `Player`: name, jersey number, team, position, media assets, walk-up track, pronunciation, commentary notes.
- `Game`: teams, date, venue, status, inning state, official event stream.
- `Lineup`: active batting order, substitutions, pitcher assignments.
- `GameEvent`: authoritative or enrichment event.
- `CvObservation`: model-generated observation with confidence and source camera.
- `ProductionCommand`: output command sent to music, graphics, commentary, or alert systems.
- `AuditLog`: immutable trail of automated decisions, manual overrides, command statuses, and operator actions.
- `MediaAsset`: music, headshots, graphics templates, sponsor-safe visuals, generated clips.

## 10. Security And Safety

- Local LAN-first operation for v1.
- Role-based access:
  - Referee app can submit official game events.
  - Manager can override, approve, cancel, and configure game operations.
  - Viewer roles are read-only.
- Device registration for referee phones and production machines.
- No hardcoded credentials, API keys, team data, media paths, or venue addresses.
- Audit every official event, automated command, manual override, and failed integration.
- Keep emergency stop controls available from the dashboard at all times.

## 11. Testing Strategy

### 11.1 Unit Tests

- Game-state reducer for balls, strikes, outs, runs, innings, substitutions, corrections, and edge cases.
- Roster validation and false-positive filtering.
- Confidence threshold logic and alert creation.
- Production command idempotency and status transitions.
- Commentary context builder and prompt input sanitation.

### 11.2 Contract Tests

- Referee app to event gateway event schema.
- CV node to event gateway observation schema.
- Event gateway to dashboard realtime schema.
- Orchestrator to production adapter command schema.
- Audit log write requirements for commands and overrides.

### 11.3 Integration Tests

- Simulated half inning with normal pitch events.
- Batter walk-up sequence with CV recognition and roster validation.
- Low-confidence jersey observation requiring manager confirmation.
- Duplicate referee event handling.
- Network drop and reconnect from referee app.
- Service restart and replay from JetStream.
- Missing music asset fallback.
- Score correction after mistaken referee input.

### 11.4 Field-Pilot Acceptance Targets

- Referee event to dashboard state update under 250 ms on LAN.
- Production command dispatch under 500 ms after authoritative event.
- Low-confidence CV alert shown immediately when confidence drops below 70%.
- Manager can confirm or override CV identity within the 3 to 5 second workflow.
- Replay logs reconstruct game state and production actions accurately.
- System remains usable if AI commentary service is slow or unavailable.
- Emergency stop cancels queued and active production commands.

## 12. Deployment Plan

### 12.1 V1 Edge Server

Recommended local pilot hardware:

- NVIDIA GPU-capable workstation or edge server.
- Wired network connection to cameras, scoreboard/audio interfaces, and manager station.
- Local Docker Engine with Compose.
- Local PostgreSQL, NATS/JetStream, Redis, MediaMTX, event gateway, AI orchestrator, and dashboard.

### 12.2 Local Network

- Keep referee app, dashboard, cameras, and server on a dedicated venue LAN where possible.
- Prefer wired links for cameras and production output machines.
- Use device IDs and service health checks to detect disconnected clients quickly.

### 12.3 Migration To Kubernetes

Move to Kubernetes only after the pilot proves:

- Multiple CV nodes are required.
- Multi-field or multi-venue deployment is needed.
- Service-level scaling is necessary.
- Operations team can support cluster monitoring and upgrades.

## 13. Pilot Checklist

Before a field test:

- Import teams, players, roster, jersey numbers, lineup, and media assets.
- Verify walk-up music asset paths and fallback tracks.
- Verify scoreboard/graphics output adapter in test mode.
- Verify referee app device registration.
- Verify camera stream availability and time sync.
- Run simulated inning test.
- Run low-confidence override test.
- Run emergency stop test.
- Confirm operator runbook is available.

During the field test:

- Log every automated action and override.
- Track latency from referee input to dashboard, command generation, and output adapter response.
- Track CV confidence by camera and lighting condition.
- Mark false positives and missed recognitions for dataset improvement.

After the field test:

- Replay event log.
- Review command failures and manual overrides.
- Update CV dataset and model benchmark notes.
- Revise operator workflow based on actual timing pressure.

## 14. External References

- Ultralytics YOLOv10: https://docs.ultralytics.com/models/yolov10/
- Ultralytics YOLO11: https://docs.ultralytics.com/models/yolo11/
- ONNX Runtime TensorRT Execution Provider: https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html
- NVIDIA TensorRT documentation: https://docs.nvidia.com/deeplearning/tensorrt/latest/index.html
- Expo documentation: https://docs.expo.dev/
- NATS JetStream documentation: https://docs.nats.io/nats-concepts/jetstream

