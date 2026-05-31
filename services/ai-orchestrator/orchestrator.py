"""
AI Orchestrator for Dugout.ai Phase 1.

Subscribes to NATS game events and CV observations.
Dispatches production commands (walkup music, scoreboard updates, commentary)
and generates alerts for low-confidence CV detections.
"""

import asyncio
import json
import logging
import os
import time
import uuid

import nats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-orchestrator")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
CV_CONFIDENCE_THRESHOLD = float(os.getenv("CV_CONFIDENCE_THRESHOLD", "0.70"))

# Simulated roster for Phase 1
ROSTER = {
    "17": {"name": "Alex Johnson", "team": "home", "walkup_asset": "asset_walkup_17"},
    "5":  {"name": "Mike Turner", "team": "home", "walkup_asset": "asset_walkup_5"},
    "22": {"name": "Chris Davis", "team": "away", "walkup_asset": "asset_walkup_22"},
    "12": {"name": "Jordan Lee", "team": "home", "walkup_asset": "asset_walkup_12"},
    "8":  {"name": "Sam Wilson", "team": "away", "walkup_asset": "asset_walkup_8"},
}


def generate_command_id() -> str:
    return f"cmd_{uuid.uuid4().hex[:12]}"


def build_production_command(
    game_id: str,
    command_type: str,
    target: str,
    source_event_ids: list,
    payload: dict,
    requires_confirmation: bool = False,
) -> dict:
    return {
        "commandId": generate_command_id(),
        "gameId": game_id,
        "commandType": command_type,
        "target": target,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "sourceEventIds": source_event_ids,
        "requiresManagerConfirmation": requires_confirmation,
        "status": "COMMAND_STATUS_QUEUED",
        "payload": payload,
    }


async def handle_game_event(nc, msg):
    """Process official game events from the referee app."""
    try:
        data = json.loads(msg.data.decode())
    except json.JSONDecodeError:
        logger.warning("Failed to decode game event JSON")
        return

    event_id = data.get("eventId", "unknown")
    game_id = data.get("gameId", "unknown")
    logger.info("Received game event: %s (game: %s)", event_id, game_id)

    # Generate commentary text for the event
    commentary = generate_commentary(data)
    if commentary:
        cmd = build_production_command(
            game_id=game_id,
            command_type="generate_commentary",
            target="commentary_adapter",
            source_event_ids=[event_id],
            payload={"text": commentary, "playAudio": False},
        )
        subject = f"dugout.game.{game_id}.commands"
        await nc.publish(subject, json.dumps(cmd).encode())
        logger.info("Commentary command dispatched: %s", commentary[:60])

    # Generate scoreboard update command
    scoreboard_cmd = build_production_command(
        game_id=game_id,
        command_type="update_scoreboard",
        target="graphics_adapter",
        source_event_ids=[event_id],
        payload={"displayTemplate": "count", "sourceEvent": event_id},
    )
    subject = f"dugout.game.{game_id}.commands"
    await nc.publish(subject, json.dumps(scoreboard_cmd).encode())
    logger.info("Scoreboard update dispatched for event %s", event_id)


async def handle_cv_observation(nc, msg):
    """Process CV observations and dispatch production actions or alerts."""
    try:
        data = json.loads(msg.data.decode())
    except json.JSONDecodeError:
        logger.warning("Failed to decode CV observation JSON")
        return

    obs_id = data.get("observationId", "unknown")
    game_id = data.get("gameId", "unknown")
    confidence = data.get("confidence", 0.0)
    jersey_data = data.get("jerseyNumber", {})
    jersey_number = jersey_data.get("jerseyNumber", "?")

    logger.info(
        "CV observation: jersey=%s confidence=%.2f obs_id=%s",
        jersey_number, confidence, obs_id,
    )

    # Check confidence threshold
    if confidence < CV_CONFIDENCE_THRESHOLD:
        # Dispatch alert command for manager review
        alert_cmd = build_production_command(
            game_id=game_id,
            command_type="trigger_alert",
            target="alert_adapter",
            source_event_ids=[obs_id],
            payload={
                "alertType": "low_cv_confidence",
                "message": f"Low confidence jersey detection: #{jersey_number} ({confidence:.0%})",
                "confidence": confidence,
                "entityId": obs_id,
            },
            requires_confirmation=True,
        )
        subject = f"dugout.game.{game_id}.alerts"
        await nc.publish(subject, json.dumps(alert_cmd).encode())
        logger.warning(
            "LOW CONFIDENCE ALERT: jersey #%s at %.0f%% - requires manager confirmation",
            jersey_number, confidence * 100,
        )
        return

    # High confidence — validate against roster
    player = ROSTER.get(jersey_number)
    if not player:
        logger.warning("Jersey #%s not found in active roster, skipping", jersey_number)
        return

    # Dispatch walkup music command
    music_cmd = build_production_command(
        game_id=game_id,
        command_type="play_walkup_music",
        target="music_adapter",
        source_event_ids=[obs_id],
        payload={
            "playerId": f"player_{jersey_number}",
            "assetId": player["walkup_asset"],
            "fadeInMs": 250,
            "maxDurationMs": 20000,
        },
    )
    subject = f"dugout.game.{game_id}.commands"
    await nc.publish(subject, json.dumps(music_cmd).encode())
    logger.info(
        "Walk-up music dispatched for %s (#%s) via %s",
        player["name"], jersey_number, player["walkup_asset"],
    )


async def handle_production_command(nc, msg):
    """Simulated production adapter — logs received commands."""
    try:
        data = json.loads(msg.data.decode())
    except json.JSONDecodeError:
        return

    cmd_id = data.get("commandId", "unknown")
    cmd_type = data.get("commandType", "unknown")
    target = data.get("target", "unknown")

    logger.info(
        "[ADAPTER:%s] Received command %s (type=%s) — simulating execution...",
        target, cmd_id, cmd_type,
    )

    # Simulate execution delay
    await asyncio.sleep(0.1)

    # Publish status update
    status_update = {
        "commandId": cmd_id,
        "status": "COMMAND_STATUS_COMPLETED",
        "completedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }
    status_subject = f"dugout.commands.status"
    await nc.publish(status_subject, json.dumps(status_update).encode())
    logger.info("[ADAPTER:%s] Command %s completed.", target, cmd_id)


def generate_commentary(event_data: dict) -> str:
    """Generate play-by-play commentary text from a game event."""
    pitch = event_data.get("pitchResult")
    play = event_data.get("playOutcome")

    if pitch:
        result = pitch.get("result", "")
        if "BALL" in result:
            return "Ball. The count changes."
        elif "STRIKE_LOOKING" in result:
            return "Strike called, looking. The batter didn't swing."
        elif "STRIKE_SWINGING" in result:
            return "Swing and a miss! Strike."
        elif "FOUL" in result:
            return "Fouled off. Still alive at the plate."
        elif "HIT_BY_PITCH" in result:
            return "Hit by pitch! The batter takes first base."

    if play:
        outcome = play.get("type", "")
        if "SINGLE" in outcome:
            return "Base hit! A single into the outfield."
        elif "DOUBLE" in outcome:
            return "A double! The ball finds the gap."
        elif "TRIPLE" in outcome:
            return "A triple! The batter rounds second and slides into third."
        elif "HOME_RUN" in outcome:
            return "It's outta here! Home run!"
        elif "OUT" in outcome:
            return "That's an out. The defense makes the play."
        elif "WALK" in outcome:
            return "Ball four. The batter takes first on a walk."

    inning = event_data.get("inningTransition")
    if inning:
        num = inning.get("inningNumber", 1)
        top = inning.get("isTop", True)
        half = "top" if top else "bottom"
        return f"We move to the {half} of inning {num}."

    return ""


async def main():
    logger.info("Starting AI Orchestrator...")
    logger.info("NATS: %s", NATS_URL)
    logger.info("CV confidence threshold: %.0f%%", CV_CONFIDENCE_THRESHOLD * 100)

    nc = await nats.connect(NATS_URL)
    logger.info("Connected to NATS.")

    # Subscribe to game events
    await nc.subscribe("dugout.game.*.events", cb=lambda msg: asyncio.create_task(handle_game_event(nc, msg)))
    logger.info("Subscribed to dugout.game.*.events")

    # Subscribe to CV observations
    await nc.subscribe("dugout.game.*.observations", cb=lambda msg: asyncio.create_task(handle_cv_observation(nc, msg)))
    logger.info("Subscribed to dugout.game.*.observations")

    # Subscribe to production commands (simulated adapter)
    await nc.subscribe("dugout.game.*.commands", cb=lambda msg: asyncio.create_task(handle_production_command(nc, msg)))
    logger.info("Subscribed to dugout.game.*.commands (simulated adapter)")

    logger.info("AI Orchestrator is running. Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down AI Orchestrator...")
    finally:
        await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
