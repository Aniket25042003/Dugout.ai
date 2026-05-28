# CLAUDE.md

This file gives future coding agents project context and implementation rules for Dugout.ai.

## Project Summary

Dugout.ai is an AI-assisted baseball game-day production system. It automates music, scoreboard graphics, commentary, camera/sensor context, alerts, and operator workflows so a single manager can supervise a baseball production that normally requires a larger crew.

The first target is a real field pilot, not just a toy demo. The v1 system should run on one local stadium edge server with GPU support, Docker Compose, and LAN-first communication. Kubernetes and cloud sync come later after pilot validation.

## Non-Negotiable Product Rules

- The referee mobile app is the authoritative source for official v1 game state: balls, strikes, outs, runs, scoring, inning changes, substitutions, and timer controls.
- CV and sensor data are enrichment unless validated by roster/lineup rules or confirmed by the manager.
- Low-confidence CV recognition below 70% must create a manager-visible alert before it drives a production action.
- Manager overrides must be appended as events and written to the audit log. Never silently mutate history.
- Every automated production command must include source event IDs and enough metadata to explain why it happened.
- Latency-sensitive event routing must not depend on LLM or TTS calls.
- Emergency stop and manual override controls must remain easy to reach in manager workflows.

## Preferred Repository Structure

Use a production-ready monorepo layout:

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

Do not scatter service code, schemas, scripts, and configs at the root. Root files should be limited to project-level docs, workspace configuration, lockfiles, and top-level build/test orchestration.

## Tech Stack Defaults

- Dashboard: React + TypeScript.
- Referee mobile app: React Native + Expo.
- Event gateway: Go.
- AI orchestration/commentary: Python + FastAPI.
- CV node: Python prototype first, C++ for latency-critical production paths if needed.
- CV/video tooling: OpenCV, GStreamer or FFmpeg, RTSP/WebRTC bridge through MediaMTX or equivalent.
- Model runtime: benchmark YOLO-family models, export to ONNX, optimize with ONNX Runtime and TensorRT where available.
- Messaging: NATS with JetStream.
- Database: PostgreSQL.
- Hot state/cache: Redis only if the implementation has a clear need.
- Deployment: Docker Compose for v1; Kubernetes after pilot.
- Observability: OpenTelemetry, Prometheus, Grafana, structured JSON logs.

## Architecture Rules

- Keep contracts centralized in `packages/contracts`.
- Generate or share typed clients from contracts instead of copying payload shapes between services.
- Keep the event gateway small, fast, and boring: validation, auth, sequencing, fan-out, and broker publishing.
- Keep AI commentary and TTS in separate orchestration paths so slow generation cannot block official game state or production safety controls.
- Treat production adapters as boundaries. Music, graphics, scoreboard, OBS, CasparCG, TTS, and venue-specific systems should be replaceable.
- Prefer append-only event flows over mutable state changes.
- Make replay mode possible from the beginning by preserving event order, event IDs, timestamps, source IDs, and correction events.

## Event And Data Rules

Canonical event fields should include:

- Stable event ID.
- Game ID.
- Source and source device ID.
- Event type.
- Occurred timestamp and received timestamp.
- Sequence number when available.
- Payload.
- Confidence.
- Authority level.
- Correlation ID.

CV observations should include:

- Stable observation ID.
- Game ID.
- Camera ID.
- Observation timestamp.
- Observation type.
- Bounding box or tracking metadata when relevant.
- Confidence.
- Model name, version, and runtime.

Production commands should include:

- Stable command ID.
- Game ID.
- Command type.
- Target adapter.
- Created timestamp.
- Source event IDs.
- Payload.
- Manager confirmation requirement.
- Status.

Audit records are required for:

- Official referee events.
- Manual corrections and overrides.
- Automated production commands.
- Command status updates.
- Low-confidence alerts.
- Failed integrations.
- Emergency stop actions.

## Coding Standards

- Write clean, modular, production-quality code. Do not add throwaway logic to "just make it run."
- Start with contracts, reducers, and tests before building UI around unstable behavior.
- Prefer explicit domain types over loose maps/dictionaries.
- Keep functions small and named around baseball/production concepts.
- Avoid hardcoded teams, players, venue paths, IPs, ports, API keys, asset paths, and credentials.
- Use configuration files and environment variables for deployment-specific values.
- Keep logs structured and include correlation IDs where available.
- Use idempotency keys for event ingestion and production commands.
- Fail closed for risky production actions when confidence, roster validation, or command target status is uncertain.
- Add comments only when they clarify non-obvious decisions or domain rules.

## Frontend And UX Rules

- The dashboard is an operational tool, not a marketing page.
- Prioritize dense, readable, real-time information: game state, active batter/pitcher, alerts, live feeds, event timeline, command status, and manual controls.
- Keep alert states unmistakable and actionable.
- Do not hide emergency stop, override, or confirmation controls deep in menus.
- Use stable layout dimensions so live updates do not shift critical controls.
- Design for a manager making decisions in seconds during a live game.

## Mobile App Rules

- The referee app should be fast, simple, and hard to misuse.
- Official event buttons must be large and unambiguous.
- Corrections must be explicit correction events.
- Support reconnect behavior and ordered sync after temporary network loss.
- Do not put heavy processing on the phone in v1.

## CV And Model Rules

- Do not lock the project to one YOLO version without a benchmark.
- Record model name, version, runtime, camera, and confidence for every observation.
- Validate jersey observations against active roster and lineup context before triggering player-specific production.
- Treat staff, water runners, non-active players, and crowd occlusion as expected false-positive cases to handle.
- Keep dataset notes and benchmark results in docs so future agents do not repeat experiments blindly.

## Testing Expectations

At minimum, add or preserve tests for:

- Game-state reducer behavior.
- Event ordering and idempotency.
- Referee event contract validation.
- CV observation contract validation.
- Roster validation.
- Low-confidence alert creation.
- Manual override event creation.
- Production command idempotency and status transitions.
- Commentary context building without invented facts.

Integration scenarios should include:

- Normal half inning.
- Batter walk-up from validated player identity.
- Low-confidence CV alert and manager confirmation.
- Duplicate referee event.
- Network reconnect from referee app.
- Service restart and event replay.
- Missing music asset fallback.
- Manual score correction.
- Emergency stop.

## Performance Targets

Use these as pilot acceptance targets unless the product owner changes them:

- Referee event to dashboard update under 250 ms on LAN.
- Production command dispatch under 500 ms after authoritative event.
- Manager low-confidence alert immediately when CV confidence drops below 70%.
- Manager confirmation/override workflow designed for 3 to 5 seconds.
- AI commentary may be slower, but must not block official game state or production safety.

## Implementation Order

Recommended order for future agents:

1. Create monorepo structure and shared contract package.
2. Define event, observation, command, game-state, and audit schemas.
3. Implement game-state reducer with fixtures and tests.
4. Implement event gateway with NATS/JetStream and replay support.
5. Implement referee app official event flow.
6. Implement dashboard live state, alerts, and override flow.
7. Add mocked CV publisher and simulated production adapters.
8. Add AI orchestration and commentary context.
9. Add real camera ingestion and CV benchmarking.
10. Add real production adapters and field-pilot hardening.

## Things To Avoid

- Do not build UI before event contracts and reducer behavior are clear.
- Do not make CV the source of truth for official game state in v1.
- Do not bypass audit logs for convenience.
- Do not let LLM calls sit in the path between referee input and dashboard/game-state updates.
- Do not create hidden mutable state that cannot be reconstructed from events.
- Do not hardcode one venue's camera URLs, team roster, or media paths in application code.
- Do not introduce Kubernetes complexity before the Docker Compose pilot is working.

