"""
Mock CV Publisher for Dugout.ai Phase 1 Simulation.

Publishes simulated CvObservation messages to NATS JetStream,
including both high-confidence and low-confidence jersey recognitions
to test the alert and override workflow.
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from typing import Optional

import nats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock-cv-publisher")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
GAME_ID = os.getenv("GAME_ID", "game_2026_ashland_vs_opponent")


def build_observation(
    jersey_number: str,
    team_side: str,
    confidence: float,
    camera_id: str = "home_plate_cam",
    model_name: str = "jersey-detector",
    model_version: str = "pilot-001",
) -> dict:
    """Build a CvObservation-compatible JSON payload."""
    return {
        "observationId": f"obs_{uuid.uuid4().hex[:12]}",
        "gameId": GAME_ID,
        "cameraId": camera_id,
        "observedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "observationType": "jersey_number",
        "confidence": confidence,
        "model": {
            "name": model_name,
            "version": model_version,
            "runtime": "onnxruntime-cpu",
        },
        "jerseyNumber": {
            "jerseyNumber": jersey_number,
            "teamSide": team_side,
            "bbox": {
                "x": round(0.3 + 0.2 * (hash(jersey_number) % 5) / 5, 2),
                "y": round(0.15 + 0.1 * (hash(jersey_number) % 3) / 3, 2),
                "width": 0.11,
                "height": 0.24,
            },
            "trackId": f"track_{hash(jersey_number) % 10000}",
        },
    }


async def publish_observation(nc, observation: dict) -> None:
    """Publish a single observation to NATS."""
    subject = f"dugout.game.{observation['gameId']}.observations"
    data = json.dumps(observation).encode()
    await nc.publish(subject, data)
    logger.info(
        "Published observation: jersey=%s confidence=%.2f subject=%s",
        observation["jerseyNumber"]["jerseyNumber"],
        observation["confidence"],
        subject,
    )


async def run_scenario_high_confidence(nc) -> None:
    """Simulate a sequence of high-confidence jersey detections."""
    jerseys = [
        ("17", "TEAM_SIDE_HOME", 0.95),
        ("22", "TEAM_SIDE_AWAY", 0.91),
        ("5", "TEAM_SIDE_HOME", 0.88),
    ]
    for number, side, conf in jerseys:
        obs = build_observation(number, side, conf)
        await publish_observation(nc, obs)
        await asyncio.sleep(1.5)


async def run_scenario_low_confidence(nc) -> None:
    """Simulate low-confidence detections that should trigger manager alerts."""
    low_conf_jerseys = [
        ("12", "TEAM_SIDE_HOME", 0.63),
        ("8", "TEAM_SIDE_AWAY", 0.55),
        ("99", "TEAM_SIDE_HOME", 0.42),
    ]
    for number, side, conf in low_conf_jerseys:
        obs = build_observation(number, side, conf)
        await publish_observation(nc, obs)
        await asyncio.sleep(2.0)


async def run_scenario_mixed(nc) -> None:
    """Run a realistic mixed scenario with both high and low confidence."""
    observations = [
        ("17", "TEAM_SIDE_HOME", 0.95),
        ("22", "TEAM_SIDE_AWAY", 0.91),
        ("12", "TEAM_SIDE_HOME", 0.63),  # Should trigger alert
        ("5", "TEAM_SIDE_HOME", 0.88),
        ("8", "TEAM_SIDE_AWAY", 0.55),   # Should trigger alert
        ("17", "TEAM_SIDE_HOME", 0.97),
    ]
    for number, side, conf in observations:
        obs = build_observation(number, side, conf)
        await publish_observation(nc, obs)
        await asyncio.sleep(2.0)


async def main():
    scenario = sys.argv[1] if len(sys.argv) > 1 else "mixed"

    logger.info("Connecting to NATS at %s...", NATS_URL)
    nc = await nats.connect(NATS_URL)
    logger.info("Connected to NATS.")

    scenarios = {
        "high": run_scenario_high_confidence,
        "low": run_scenario_low_confidence,
        "mixed": run_scenario_mixed,
    }

    runner = scenarios.get(scenario, run_scenario_mixed)
    logger.info("Running scenario: %s", scenario)
    await runner(nc)

    await nc.flush()
    await nc.close()
    logger.info("Mock CV publisher finished.")


if __name__ == "__main__":
    asyncio.run(main())
