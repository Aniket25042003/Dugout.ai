# CV Node

**One-liner:** Edge Python worker detecting jersey numbers from RTSP camera feed.

## Why it exists

Walk-up music and player graphics need batter identity from camera input. cv-node runs at the stadium edge, reads the home-plate camera stream, and publishes observations to NATS for the orchestrator to validate against roster data.

## How it works

1. **Startup** (`main.py`): Connect to NATS, log configuration (`NATS_URL`, `CV_NODE_CAMERA_RTSP_STREAM`, `GAME_ID`).
2. **RTSP loop** (`process_rtsp_stream`):
   - Open `cv2.VideoCapture(CAMERA_RTSP_STREAM)` with reconnect on failure (5s retry)
   - Read frames in a loop; process every 5th frame (~6 fps at 30fps source)
3. **Detection** (`FallbackVisualDetector.detect`):
   - Convert frame to grayscale, threshold bright white text (MediaMTX test pattern)
   - Find contours matching jersey-number bounding box size/aspect ratio
   - Return detections with jersey number, team side, confidence, normalized bbox
   - Alternates confidence 0.63 (low) and 0.95 (high) every 15 seconds for testing alert workflow
4. **Publish** observation JSON to `dugout.game.{GAME_ID}.observations`:
   - Fields: `observationId`, `gameId`, `cameraId`, `confidence`, `model`, `jerseyNumber`
   - Model metadata: `contour-jersey-sim` v1.0, runtime `fallback-contour`
5. **Orchestrator** receives observation, resolves player, applies 0.70 confidence threshold

### Environment variables

| Variable | Default |
|----------|---------|
| `NATS_URL` | `nats://localhost:4222` |
| `CV_NODE_CAMERA_RTSP_STREAM` | `rtsp://localhost:8554/homeplatecam` |
| `GAME_ID` | `game_2026_ashland_vs_opponent` |
| `CV_MODEL_PATH` | `""` (unused — fallback detector only) |

## Architecture diagram

```mermaid
flowchart LR
  MediaMTX[MediaMTX RTSP] -->|homeplatecam| CVNode[cv-node main.py]
  CVNode --> Detector[FallbackVisualDetector]
  Detector --> NATS["dugout.game.*.observations"]
  NATS --> Orch[orchestrator.py handle_cv_observation]
  Orch --> CmdQ[CommandQueue play_walkup_music]
```

## Key code callouts

| Class/Function | File |
|----------------|------|
| `FallbackVisualDetector` | `services/cv-node/main.py` |
| `process_rtsp_stream()` | `services/cv-node/main.py` |
| `handle_cv_observation()` | `services/ai-orchestrator/orchestrator.py` |

## Tech decisions

1. **Fallback contour detector over YOLO** — pilot uses MediaMTX test pattern; C++ YOLO planned for production latency.
2. **Frame sampling (every 5th)** — controls CPU usage on edge hardware.
3. **NATS-only output** — observations not persisted to `cv_observations` table yet.

## Talking points

- Confidence alternation (0.63/0.95) is intentional for testing manager approval workflow.
- Jersey number hardcoded as `"17"` in fallback detector — not real CV yet.
- `mock_publisher.py` and `benchmark.py` were removed in Phase 1 cleanup as unused dev utilities.
- MediaMTX provides synthetic RTSP at `rtsp://localhost:8554/homeplatecam` via Docker Compose.
