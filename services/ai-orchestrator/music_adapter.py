"""
File: services/ai-orchestrator/music_adapter.py
Layer: Worker — Music Production Adapter
Purpose: Converts queued music commands into dashboard playback state updates.
         It resolves player walk-up assets and simulates timing for browser audio.
Dependencies: MediaManager asset resolution, asyncio playback tasks, NATS state bus.
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

    Attributes:
        db: Database client retained for future playback persistence hooks.
        media: Media manager used to resolve player walk-up tracks.
        nc: Optional NATS connection used to publish playback state.
        _current_task (Optional[asyncio.Task]): Active playback/fade task.
        _current_cmd_id (Optional[str]): Command currently controlling playback.
        _current_state (dict): Last published music state snapshot.
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

        Args:
            cmd_id (str): Production command ID being executed.
            cmd_type (str): Music command type to dispatch.
            payload (dict): Adapter-specific payload, usually player and duration data.

        Side Effects:
            Starts, stops, or fades playback and publishes NATS state updates.
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
        """
        Starts a player's walk-up track, replacing any active playback task.

        Args:
            cmd_id (str): Command ID controlling this playback request.
            payload (dict): Contains ``playerId`` and optional ``maxDurationMs``.

        Raises:
            ValueError: If no player-specific or fallback walk-up track can be resolved.

        Side Effects:
            Cancels existing playback, resolves media, and publishes timed state updates.
        """
        # Only one walk-up track should play at a time, so supersede the previous task.
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        player_id = payload.get("playerId")
        # MediaManager handles player-specific lookup plus fallback track selection.
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
        """
        Stops active music playback immediately.

        Args:
            cmd_id (str): Command ID requesting the stop.

        Side Effects:
            Cancels the active playback task and publishes a stopped state.
        """
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
        """
        Transitions active music into a temporary fading state before stopping.

        Args:
            cmd_id (str): Command ID requesting the fade.
            payload (dict): Contains optional ``fadeMs`` duration.

        Side Effects:
            Cancels active playback, publishes fading state, waits, then publishes stopped.
        """
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

            # Preserve the track metadata so the dashboard can fade the correct audio element.
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
        """
        Publishes simulated playback progress until the track completes or is cancelled.

        Args:
            cmd_id (str): Command ID controlling this playback loop.
            track (dict): Resolved media asset with file path, duration, and player fields.
            max_duration_ms (int): Upper bound on how long the dashboard should play.

        Side Effects:
            Emits music state snapshots every 500ms on NATS.
        """
        total_ms = min(track.get("duration_ms", 10000), max_duration_ms)
        elapsed_ms = 0
        step_ms = 500  # Half-second progress updates are smooth enough for UI sync.

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
        """
        Publishes the current music state snapshot to NATS.

        Side Effects:
            Sends JSON on ``dugout.production.music.state``.
        """
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
