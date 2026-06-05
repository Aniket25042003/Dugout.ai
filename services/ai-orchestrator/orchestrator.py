"""
AI Orchestrator for Dugout.ai (Phase 3).

Subscribes to NATS game events and CV observations.
Orchestrates:
- CommandQueue for priority, cooldowns, conflicts.
- MusicAdapter for walk-up music state.
- GraphicsAdapter for overlay and scoreboard updates.
- CommentaryEngine for local LLM + TTS radio broadcast commentary.
"""

import asyncio
import json
import logging
import os
import sys
import time

import nats
from db_client import DBClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-orchestrator")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
CV_CONFIDENCE_THRESHOLD = float(os.getenv("CV_CONFIDENCE_THRESHOLD", "0.70"))

# Initialize DBClient
db = DBClient()


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
            command_type="update_scoreboard",
            target="graphics_adapter",
            payload=scoreboard_payload,
            source_event_ids=[event_id],
            priority=3,
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

    # 1. Fetch rosters and lineups from DB
    roster_players = await db.get_broader_roster(game_id)
    lineup_players = await db.get_active_lineup(game_id)

    # 2. Find player matching jersey number on the team rosters
    player = next((p for p in roster_players if p["jersey_number"] == jersey_number), None)

    if not player:
        # Task 2.3: Alert: Player not on active roster
        alert_cmd = build_production_command(
            game_id=game_id,
            command_type="trigger_alert",
            target="alert_adapter",
            source_event_ids=[obs_id],
            payload={
                "alertType": "player_not_on_roster",
                "message": f"Alert: Observed jersey #{jersey_number} is not registered on either team roster.",
                "confidence": confidence,
                "entityId": obs_id,
            },
            requires_confirmation=True,
        )
        subject = f"dugout.game.{game_id}.alerts"
        await nc.publish(subject, json.dumps(alert_cmd).encode())
        logger.warning("Jersey #%s not found in team rosters - triggered manager alert", jersey_number)
        return

    # Check if player is in the active lineup
    is_in_lineup = any(p["id"] == player["id"] for p in lineup_players)

    # 3. Check confidence threshold or active lineup status
    if confidence < CV_CONFIDENCE_THRESHOLD or not is_in_lineup:
        alert_msg = f"Low confidence jersey detection: #{jersey_number} ({confidence:.0%})"
        alert_type = "low_cv_confidence"

        if not is_in_lineup:
            alert_msg = f"Active lineup warning: Observed #{jersey_number} ({player['name']}) is on roster but not in active lineup."
            alert_type = "inactive_lineup_detection"

        # Dispatch alert command for manager review
        alert_cmd = build_production_command(
            game_id=game_id,
            command_type="trigger_alert",
            target="alert_adapter",
            source_event_ids=[obs_id],
            payload={
                "alertType": alert_type,
                "message": alert_msg,
                "confidence": confidence,
                "entityId": obs_id,
            },
            requires_confirmation=True,
        )
        subject = f"dugout.game.{game_id}.alerts"
        await nc.publish(subject, json.dumps(alert_cmd).encode())
        logger.warning(
            "ALERT: jersey #%s - type=%s - requires manager confirmation",
            jersey_number, alert_type
        )
        return

    # High confidence & in active lineup — dispatch walkup music command
    music_cmd = build_production_command(
        game_id=game_id,
        command_type="play_walkup_music",
        target="music_adapter",
        source_event_ids=[obs_id],
        payload={
            "playerId": player["id"],
            "assetId": player.get("walkup_track_id") or f"asset_walkup_{jersey_number}",
            "fadeInMs": 250,
            "maxDurationMs": 20000,
        },
    )
    subject = f"dugout.game.{game_id}.commands"
    await nc.publish(subject, json.dumps(music_cmd).encode())
    logger.info(
        "Walk-up music dispatched for %s (#%s) via %s",
        player["name"], jersey_number, player.get("walkup_track_id") or f"asset_walkup_{jersey_number}",
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

    # Initialize db connection pool
    await db.connect()

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
        await daemon.start()
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        await db.close()
        await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
