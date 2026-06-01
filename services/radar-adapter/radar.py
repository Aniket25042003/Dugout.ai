import asyncio
import json
import logging
import os
import random
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("radar-adapter")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

async def handle_game_event(nc, msg):
    """Listens to game events and triggers radar readings for pitch results."""
    try:
        data = json.loads(msg.data.decode())
    except json.JSONDecodeError:
        return

    event_id = data.get("eventId")
    game_id = data.get("gameId")
    event_type = data.get("eventType")
    pitch_result = data.get("pitchResult")

    # If it is a pitch event and doesn't already have speed
    if event_type == "pitch_result" and pitch_result and not pitch_result.get("speedMph"):
        logger.info(f"Detected pitch event {event_id} (game: {game_id}). Measuring speed...")
        
        # Simulate time-of-flight of the pitch (approx 400ms for 90mph)
        await asyncio.sleep(0.4)
        
        # Generate pitch speed (fastballs/sliders range)
        speed = round(random.uniform(85.0, 99.5), 1)
        
        # Publish radar reading
        radar_msg = {
            "eventId": event_id,
            "gameId": game_id,
            "speedMph": speed
        }
        
        subject = f"dugout.game.{game_id}.radar"
        await nc.publish(subject, json.dumps(radar_msg).encode())
        logger.info(f"Published radar speed: {speed} MPH on subject {subject} for event {event_id}")

async def main():
    logger.info("Starting Radar Adapter Daemon...")
    logger.info(f"NATS target: {NATS_URL}")

    try:
        nc = await nats.connect(NATS_URL)
        logger.info("Connected to NATS.")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        return

    # Subscribe to game events
    await nc.subscribe("dugout.game.*.events", cb=lambda msg: asyncio.create_task(handle_game_event(nc, msg)))
    logger.info("Subscribed to dugout.game.*.events")

    logger.info("Radar Adapter is running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping Radar Adapter...")
    finally:
        await nc.close()

if __name__ == "__main__":
    import nats
    asyncio.run(main())
