import httpx
import time
import json
from datetime import datetime, timezone
import nats
import asyncio

NATS_URL = "nats://localhost:4222"
GAME_ID = "game_2026_ashland_vs_opponent"

async def main():
    nc = await nats.connect(NATS_URL)
    print("Connected to NATS for CV simulation...")

    # 1. Send low confidence observation (55%) for jersey #17 (Marcus Rivera)
    low_conf_obs = {
        "observationId": f"obs_low_{int(time.time())}",
        "gameId": GAME_ID,
        "cameraId": "cam_home_plate",
        "observedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "observationType": "jersey_number",
        "jerseyNumber": {
            "jerseyNumber": 17
        },
        "confidence": 0.55,
        "modelName": "yolov8-jersey",
        "modelVersion": "1.0.0",
        "modelRuntime": "onnxruntime"
    }
    
    print("Publishing low confidence observation to NATS...")
    await nc.publish(f"dugout.game.{GAME_ID}.observations", json.dumps(low_conf_obs).encode())
    
    await asyncio.sleep(4)

    # 2. Send high confidence observation (92%) for jersey #1 (Alex Johnson)
    high_conf_obs = {
        "observationId": f"obs_high_{int(time.time())}",
        "gameId": GAME_ID,
        "cameraId": "cam_home_plate",
        "observedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "observationType": "jersey_number",
        "jerseyNumber": {
            "jerseyNumber": 1
        },
        "confidence": 0.92,
        "modelName": "yolov8-jersey",
        "modelVersion": "1.0.0",
        "modelRuntime": "onnxruntime"
    }

    print("Publishing high confidence observation to NATS...")
    await nc.publish(f"dugout.game.{GAME_ID}.observations", json.dumps(high_conf_obs).encode())

    await nc.close()
    print("CV Simulation complete.")

if __name__ == "__main__":
    asyncio.run(main())
