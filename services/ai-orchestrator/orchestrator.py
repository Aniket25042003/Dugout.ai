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
from media_manager import MediaManager
from command_queue import CommandQueue
from music_adapter import MusicAdapter
from graphics_adapter import GraphicsAdapter
from llm_client import OllamaClient
from tts_client import TTSClient
from commentary_engine import CommentaryEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ai-orchestrator")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
CV_CONFIDENCE_THRESHOLD = float(os.getenv("CV_CONFIDENCE_THRESHOLD", "0.70"))

class OrchestratorDaemon:
    """Main background daemon for Dugout.ai production automation."""

    def __init__(self):
        self.nc = None
        self.db = DBClient()
        self.media = MediaManager(self.db)
        
        self.llm = OllamaClient()
        self.tts = TTSClient()
        
        self.cmd_queue = None
        self.music_adapter = None
        self.graphics_adapter = None
        self.commentary_engine = None
        self._running = False

    async def start(self):
        logger.info("Initializing Orchestrator Daemon services...")
        await self.db.connect()
        self.nc = await nats.connect(NATS_URL)
        logger.info("Connected to NATS.")

        # Initialize adapters & engines
        self.cmd_queue = CommandQueue(self.db, self.nc)
        self.music_adapter = MusicAdapter(self.db, self.media, self.nc)
        self.graphics_adapter = GraphicsAdapter(self.db, self.nc)
        self.commentary_engine = CommentaryEngine(self.db, self.llm, self.tts, self.media, self.nc)

        # Register handlers with the command queue
        self.cmd_queue.register_handler("music_adapter", self.music_adapter.handle_command)
        self.cmd_queue.register_handler("graphics_adapter", self.graphics_adapter.handle_command)

        # Start Command Queue processor loop
        await self.cmd_queue.start()

        # Initialize TTS (triggers download of voice models)
        asyncio.create_task(self.tts.initialize())

        # Subscriptions
        await self.nc.subscribe("dugout.game.*.events", cb=self.handle_game_event)
        await self.nc.subscribe("dugout.game.*.observations", cb=self.handle_cv_observation)
        await self.nc.subscribe("dugout.production.music.control", cb=self.handle_music_control)
        await self.nc.subscribe("dugout.production.commentary.control", cb=self.handle_commentary_control)

        self._running = True
        logger.info("Orchestrator Daemon successfully started.")

    async def stop(self):
        logger.info("Shutting down Orchestrator Daemon...")
        self._running = False
        if self.cmd_queue:
            await self.cmd_queue.stop()
        if self.llm:
            await self.llm.close()
        if self.nc:
            await self.nc.close()
        await self.db.close()
        logger.info("Orchestrator Daemon shut down.")

    async def handle_game_event(self, msg):
        """Process official game events from NATS."""
        try:
            data = json.loads(msg.data.decode())
        except json.JSONDecodeError:
            logger.warning("Failed to decode game event JSON")
            return

        event_id = data.get("eventId", "unknown")
        game_id = data.get("gameId", "unknown")
        logger.info("Received game event: %s type=%s (game: %s)", event_id, data.get("eventType"), game_id)

        # Get previous state for comparison (e.g. active batter changes)
        state_before = (await self.commentary_engine.get_or_create_game_state(game_id)).copy()

        # 1. Trigger Commentary Generation (LLM + TTS)
        # Note: run in background to keep LAN latency low
        asyncio.create_task(self.commentary_engine.generate_commentary(game_id, data))

        # Get updated state
        state_after = await self.commentary_engine.get_or_create_game_state(game_id)

        # 2. Scoreboard updates
        scoreboard_payload = {
            "homeScore": state_after["homeScore"],
            "awayScore": state_after["awayScore"],
            "inning": state_after["inning"],
            "isTop": state_after["isTop"],
            "balls": state_after["balls"],
            "strikes": state_after["strikes"],
            "outs": state_after["outs"],
            "bases": [state_after["runnerOnFirst"], state_after["runnerOnSecond"], state_after["runnerOnThird"]],
        }
        await self.cmd_queue.enqueue(
            game_id=game_id,
            command_type="update_scoreboard",
            target="graphics_adapter",
            payload=scoreboard_payload,
            source_event_ids=[event_id],
            priority=3,
        )

        # 3. Check for new Batter stepping up
        new_batter_id = state_after["activeBatterId"]
        if new_batter_id and new_batter_id != state_before.get("activeBatterId"):
            logger.info("New batter detected at plate: %s. Enqueuing batter intro overlay.", new_batter_id)
            await self.cmd_queue.enqueue(
                game_id=game_id,
                command_type="show_batter_intro",
                target="graphics_adapter",
                payload={"playerId": new_batter_id},
                source_event_ids=[event_id],
                priority=4,
            )

        # 4. Check for new Pitcher
        new_pitcher_id = state_after["activePitcherId"]
        if new_pitcher_id and new_pitcher_id != state_before.get("activePitcherId"):
            logger.info("New pitcher detected: %s. Enqueuing pitcher intro overlay.", new_pitcher_id)
            await self.cmd_queue.enqueue(
                game_id=game_id,
                command_type="show_pitcher_intro",
                target="graphics_adapter",
                payload={"playerId": new_pitcher_id},
                source_event_ids=[event_id],
                priority=4,
            )

    async def handle_cv_observation(self, msg):
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
        jersey_number = str(jersey_data.get("jerseyNumber", "?"))

        logger.info(
            "CV observation: jersey=%s confidence=%.2f obs_id=%s",
            jersey_number, confidence, obs_id,
        )

        # Try to resolve player from DB by jersey number
        player = await self.db.get_player_by_jersey(game_id, jersey_number)

        # Check confidence threshold
        if confidence < CV_CONFIDENCE_THRESHOLD:
            # Enqueue alert command for manager review
            alert_payload = {
                "alertType": "low_cv_confidence",
                "message": f"Low confidence jersey detection: #{jersey_number} ({confidence:.0%})",
                "confidence": confidence,
                "entityId": obs_id,
                "jerseyNumber": jersey_number,
                "player": player,
            }
            # Enqueue as play_walkup_music command requiring manager confirmation
            if player:
                await self.cmd_queue.enqueue(
                    game_id=game_id,
                    command_type="play_walkup_music",
                    target="music_adapter",
                    payload={"playerId": player["id"], "fadeInMs": 250, "maxDurationMs": 15000},
                    source_event_ids=[obs_id],
                    priority=5,
                    requires_confirmation=True,
                )
                logger.warning("LOW CONFIDENCE: Enqueued walk-up music for %s (#%s) awaiting confirmation", player["name"], jersey_number)
            return

        # High confidence — trigger directly
        if not player:
            logger.warning("Jersey #%s not found in roster for game %s, skipping walk-up", jersey_number, game_id)
            return

        # Enqueue direct play walkup music command
        await self.cmd_queue.enqueue(
            game_id=game_id,
            command_type="play_walkup_music",
            target="music_adapter",
            payload={"playerId": player["id"], "fadeInMs": 250, "maxDurationMs": 15000},
            source_event_ids=[obs_id],
            priority=5,
            requires_confirmation=False,
        )
        logger.info("Walk-up music command enqueued for player %s (#%s)", player["name"], jersey_number)

    async def handle_music_control(self, msg):
        """Handle manual music playback control from dashboard."""
        try:
            req = json.loads(msg.data.decode())
            action = req.get("action")
            game_id = req.get("game_id")
            player_id = req.get("player_id")
            asset_id = req.get("asset_id")
            fade_ms = req.get("fade_ms", 2000)

            logger.info("Manual music control message: action=%s, player=%s, asset=%s", action, player_id, asset_id)

            if action == "play":
                # Find player ID if only asset is provided
                if not player_id and asset_id:
                    asset = await self.db.get_media_asset(asset_id)
                    if asset:
                        player_id = asset.get("player_id")
                
                await self.cmd_queue.enqueue(
                    game_id=game_id,
                    command_type="play_walkup_music",
                    target="music_adapter",
                    payload={"playerId": player_id, "assetId": asset_id, "fadeInMs": 250, "maxDurationMs": 15000},
                    priority=2,  # Manual override is higher priority
                )
            elif action == "stop":
                await self.cmd_queue.enqueue(
                    game_id=game_id,
                    command_type="stop_music",
                    target="music_adapter",
                    payload={},
                    priority=1,  # Stop commands have highest priority
                )
            elif action == "fade_out":
                await self.cmd_queue.enqueue(
                    game_id=game_id,
                    command_type="fade_out_music",
                    target="music_adapter",
                    payload={"fadeMs": fade_ms},
                    priority=1,
                )
            elif action == "emergency_stop":
                await self.cmd_queue.emergency_stop(game_id)
                # Enqueue a stop to graphics too
                await self.cmd_queue.enqueue(
                    game_id=game_id,
                    command_type="hide_overlay",
                    target="graphics_adapter",
                    payload={},
                    priority=1,
                )
        except Exception as e:
            logger.error("Error handling manual music control: %s", e)

    async def handle_commentary_control(self, msg):
        """Handle manual commentary control from dashboard."""
        try:
            req = json.loads(msg.data.decode())
            action = req.get("action")
            game_id = req.get("game_id")
            text = req.get("text")

            logger.info("Manual commentary control message: action=%s", action)

            if action == "mute":
                self.commentary_engine.set_muted(True)
            elif action == "unmute":
                self.commentary_engine.set_muted(False)
            elif action == "manual" and text:
                asyncio.create_task(self.commentary_engine.speak_manual(game_id, text))
            elif action == "regenerate":
                # Regenerate based on the current context
                state = await self.commentary_engine.get_or_create_game_state(game_id)
                # Dispatch a dummy event matching current state to regenerate
                dummy_event = {
                    "gameId": game_id,
                    "eventId": f"regen_{int(time.time())}",
                    "eventType": "regenerate_commentary",
                    "pitchResult": None,
                    "playOutcome": None,
                }
                asyncio.create_task(self.commentary_engine.generate_commentary(game_id, dummy_event))
        except Exception as e:
            logger.error("Error handling manual commentary control: %s", e)


async def main():
    logger.info("Starting AI Orchestrator Daemon (Phase 3)...")
    daemon = OrchestratorDaemon()
    try:
        await daemon.start()
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        await daemon.stop()

if __name__ == "__main__":
    asyncio.run(main())
