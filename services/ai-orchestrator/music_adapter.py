"""
Music Adapter for Dugout.ai.

Translates music commands from the queue into NATS playback state events,
resolving media assets and simulating state transitions for the frontend player.
"""

import asyncio
import json
import logging
import time
from typing import Optional

logger = logging.getLogger("ai-orchestrator-music")

class MusicAdapter:
    """
    Music Adapter that handles playback commands and publishes state updates.
    """

    def __init__(self, db_client, media_manager, nats_conn=None):
        self.db = db_client
        self.media = media_manager
        self.nc = nats_conn
        self._current_task: Optional[asyncio.Task] = None
        self._current_cmd_id: Optional[str] = None
        self._current_state = {
            "status": "stopped",
            "trackName": None,
            "playerName": None,
            "playerId": None,
            "assetId": None,
            "elapsedMs": 0,
            "totalMs": 0,
        }

    async def handle_command(self, cmd_id: str, cmd_type: str, payload: dict):
        """
        Handler registered with the CommandQueue.
        """
        logger.info("MusicAdapter handling command %s: type=%s", cmd_id, cmd_type)

        if cmd_type == "play_walkup_music":
            await self._play_walkup_music(cmd_id, payload)
        elif cmd_type == "stop_music":
            await self._stop_music(cmd_id)
        elif cmd_type == "fade_out_music":
            await self._fade_out_music(cmd_id, payload)
        else:
            logger.warning("MusicAdapter received unhandled command type: %s", cmd_type)

    async def _play_walkup_music(self, cmd_id: str, payload: dict):
        # Cancel current playing task if any
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        player_id = payload.get("playerId")
        # Resolve walkup track
        track = await self.media.get_walkup_track(player_id)
        if not track:
            logger.error("Failed to resolve walkup track for player %s", player_id)
            raise ValueError(f"Could not resolve walkup track for player {player_id}")

        self._current_cmd_id = cmd_id
        # Start background playback loop
        self._current_task = asyncio.create_task(
            self._playback_loop(cmd_id, track, payload.get("maxDurationMs", 15000))
        )
        # Wait for it to complete or be cancelled
        try:
            await self._current_task
        except asyncio.CancelledError:
            logger.info("Playback task for command %s was cancelled", cmd_id)

    async def _stop_music(self, cmd_id: str):
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        self._current_state = {
            "status": "stopped",
            "trackName": None,
            "playerName": None,
            "playerId": None,
            "assetId": None,
            "elapsedMs": 0,
            "totalMs": 0,
        }
        await self._publish_state()
        logger.info("Music playback stopped.")

    async def _fade_out_music(self, cmd_id: str, payload: dict):
        fade_ms = payload.get("fadeMs", 2000)
        if self._current_task and not self._current_task.done():
            # If playing, transition to fading
            track_name = self._current_state["trackName"]
            player_name = self._current_state["playerName"]
            player_id = self._current_state["playerId"]
            asset_id = self._current_state["assetId"]
            total_ms = self._current_state["totalMs"]
            elapsed_ms = self._current_state["elapsedMs"]

            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

            # Run a brief fade loop
            self._current_state = {
                "status": "fading",
                "trackName": track_name,
                "playerName": player_name,
                "playerId": player_id,
                "assetId": asset_id,
                "elapsedMs": elapsed_ms,
                "totalMs": total_ms,
            }
            await self._publish_state()
            logger.info("Fading out music over %d ms", fade_ms)
            await asyncio.sleep(fade_ms / 1000.0)

        self._current_state = {
            "status": "stopped",
            "trackName": None,
            "playerName": None,
            "playerId": None,
            "assetId": None,
            "elapsedMs": 0,
            "totalMs": 0,
        }
        await self._publish_state()
        logger.info("Music stopped after fade.")

    async def _playback_loop(self, cmd_id: str, track: dict, max_duration_ms: int):
        total_ms = min(track.get("duration_ms", 10000), max_duration_ms)
        elapsed_ms = 0
        step_ms = 500

        self._current_state = {
            "status": "playing",
            "trackName": track["name"],
            "playerName": track["player_name"],
            "playerId": track["player_id"],
            "assetId": track["asset_id"],
            "elapsedMs": elapsed_ms,
            "totalMs": total_ms,
            "filePath": track["file_path"],
        }

        await self._publish_state()

        try:
            while elapsed_ms < total_ms:
                await asyncio.sleep(step_ms / 1000.0)
                elapsed_ms += step_ms
                self._current_state["elapsedMs"] = min(elapsed_ms, total_ms)
                await self._publish_state()
        except asyncio.CancelledError:
            # Re-raise so the calling block knows we were cancelled
            raise
        else:
            # Normal completion
            self._current_state = {
                "status": "stopped",
                "trackName": None,
                "playerName": None,
                "playerId": None,
                "assetId": None,
                "elapsedMs": 0,
                "totalMs": 0,
            }
            await self._publish_state()
            logger.info("Playback completed normally for command %s", cmd_id)

    async def _publish_state(self):
        """Publish music playback state to NATS."""
        if not self.nc:
            return

        try:
            subject = "dugout.production.music.state"
            await self.nc.publish(
                subject,
                json.dumps(self._current_state).encode()
            )
        except Exception as e:
            logger.error("Failed to publish music state: %s", e)
