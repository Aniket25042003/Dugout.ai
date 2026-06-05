"""
Graphics Adapter for Dugout.ai.

Resolves graphics templates and details from the database and publishes overlay state
to NATS to display scoreboard, player intros, and alerts on the dashboard camera overlay.
"""

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger("ai-orchestrator-graphics")

class GraphicsAdapter:
    """
    Graphics Adapter that manages the overlay display state and auto-dismiss lifecycles.
    """

    def __init__(self, db_client, nats_conn=None):
        self.db = db_client
        self.nc = nats_conn
        self._dismiss_task: Optional[asyncio.Task] = None
        self._current_overlay_state = {
            "activeOverlay": None,  # 'batter_intro', 'pitcher_intro', 'lower_third', 'speed_display', 'sponsor'
            "overlayData": {},
            "scoreboardData": {
                "homeScore": 0,
                "awayScore": 0,
                "inning": 1,
                "isTop": True,
                "balls": 0,
                "strikes": 0,
                "outs": 0,
                "bases": [False, False, False],  # 1st, 2nd, 3rd base runner presence
            }
        }

    async def handle_command(self, cmd_id: str, cmd_type: str, payload: dict):
        """
        Handler registered with the CommandQueue.
        """
        logger.info("GraphicsAdapter handling command %s: type=%s", cmd_id, cmd_type)

        if cmd_type == "show_batter_intro":
            await self._show_batter_intro(payload)
        elif cmd_type == "show_pitcher_intro":
            await self._show_pitcher_intro(payload)
        elif cmd_type == "show_lower_third":
            await self._show_lower_third(payload)
        elif cmd_type == "update_scoreboard":
            await self._update_scoreboard(payload)
        elif cmd_type == "show_speed_display":
            await self._show_speed_display(payload)
        elif cmd_type == "hide_overlay":
            await self._hide_overlay()
        else:
            logger.warning("GraphicsAdapter received unhandled command type: %s", cmd_type)

    async def _show_batter_intro(self, payload: dict):
        player_id = payload.get("playerId")
        player = await self.db.get_player_by_id(player_id)
        if not player:
            logger.error("Player %s not found for batter intro", player_id)
            return

        # Fetch stats
        stats = await self.db.get_player_stats(player_id)
        
        # Fetch template
        template = await self.db.get_graphics_template("batter_intro")
        duration = template.get("display_duration_ms", 8000) if template else 8000

        overlay_data = {
            "playerId": player["id"],
            "playerName": player["name"],
            "jerseyNumber": player["jersey_number"],
            "position": player["position"],
            "headshotUrl": f"/media/images/headshots/{player['id']}.png" if player.get("headshot_path") else "/media/images/headshots/default.png",
            "batHand": player.get("bat_hand", "R"),
            "throwHand": player.get("throw_hand", "R"),
            "battingAvg": str(stats.get("batting_avg", ".000")) if stats else ".000",
            "homeRuns": stats.get("home_runs", 0) if stats else 0,
            "rbis": stats.get("rbis", 0) if stats else 0,
            "ops": str(stats.get("ops", ".000")) if stats else ".000",
            "notes": player.get("commentary_notes", ""),
            "cssClass": template.get("css_class", "overlay-batter-intro") if template else "overlay-batter-intro",
        }

        self._current_overlay_state["activeOverlay"] = "batter_intro"
        self._current_overlay_state["overlayData"] = overlay_data
        await self._publish_state()

        if template and template.get("auto_dismiss", True):
            self._schedule_auto_dismiss(duration)

    async def _show_pitcher_intro(self, payload: dict):
        player_id = payload.get("playerId")
        player = await self.db.get_player_by_id(player_id)
        if not player:
            logger.error("Player %s not found for pitcher intro", player_id)
            return

        # Fetch stats
        stats = await self.db.get_player_stats(player_id)
        
        # Fetch template
        template = await self.db.get_graphics_template("pitcher_intro")
        duration = template.get("display_duration_ms", 6000) if template else 6000

        overlay_data = {
            "playerId": player["id"],
            "playerName": player["name"],
            "jerseyNumber": player["jersey_number"],
            "position": player["position"],
            "headshotUrl": f"/media/images/headshots/{player['id']}.png" if player.get("headshot_path") else "/media/images/headshots/default.png",
            "throwHand": player.get("throw_hand", "R"),
            "era": str(stats.get("era", "0.00")) if stats else "0.00",
            "whip": str(stats.get("whip", "0.00")) if stats else "0.00",
            "wins": stats.get("wins", 0) if stats else 0,
            "losses": stats.get("losses", 0) if stats else 0,
            "strikeouts": stats.get("pitch_strikeouts", 0) if stats else 0,
            "notes": player.get("commentary_notes", ""),
            "cssClass": template.get("css_class", "overlay-pitcher-intro") if template else "overlay-pitcher-intro",
        }

        self._current_overlay_state["activeOverlay"] = "pitcher_intro"
        self._current_overlay_state["overlayData"] = overlay_data
        await self._publish_state()

        if template and template.get("auto_dismiss", True):
            self._schedule_auto_dismiss(duration)

    async def _show_lower_third(self, payload: dict):
        template = await self.db.get_graphics_template("lower_third")
        duration = template.get("display_duration_ms", 5000) if template else 5000

        overlay_data = {
            "title": payload.get("title", ""),
            "subtitle": payload.get("subtitle", ""),
            "cssClass": template.get("css_class", "overlay-lower-third") if template else "overlay-lower-third",
        }

        self._current_overlay_state["activeOverlay"] = "lower_third"
        self._current_overlay_state["overlayData"] = overlay_data
        await self._publish_state()

        if template and template.get("auto_dismiss", True):
            self._schedule_auto_dismiss(duration)

    async def _show_speed_display(self, payload: dict):
        template = await self.db.get_graphics_template("speed_display")
        duration = template.get("display_duration_ms", 3000) if template else 3000

        overlay_data = {
            "speedMph": payload.get("speedMph", 0),
            "pitchType": payload.get("pitchType", "Fastball"),
            "cssClass": template.get("css_class", "overlay-speed") if template else "overlay-speed",
        }

        self._current_overlay_state["activeOverlay"] = "speed_display"
        self._current_overlay_state["overlayData"] = overlay_data
        await self._publish_state()

        if template and template.get("auto_dismiss", True):
            self._schedule_auto_dismiss(duration)

    async def _update_scoreboard(self, payload: dict):
        # Update the embedded scoreboard state
        for key in self._current_overlay_state["scoreboardData"].keys():
            if key in payload:
                self._current_overlay_state["scoreboardData"][key] = payload[key]
        
        await self._publish_state()

    async def _hide_overlay(self):
        self._current_overlay_state["activeOverlay"] = None
        self._current_overlay_state["overlayData"] = {}
        await self._publish_state()
        logger.info("Graphics overlay hidden.")

    def _schedule_auto_dismiss(self, duration_ms: int):
        if self._dismiss_task and not self._dismiss_task.done():
            self._dismiss_task.cancel()

        self._dismiss_task = asyncio.create_task(self._auto_dismiss_loop(duration_ms))

    async def _auto_dismiss_loop(self, duration_ms: int):
        try:
            await asyncio.sleep(duration_ms / 1000.0)
            await self._hide_overlay()
        except asyncio.CancelledError:
            pass

    async def _publish_state(self):
        """Publish graphics state to NATS."""
        if not self.nc:
            return

        try:
            subject = "dugout.production.graphics.state"
            await self.nc.publish(
                subject,
                json.dumps(self._current_overlay_state).encode()
            )
        except Exception as e:
            logger.error("Failed to publish graphics state: %s", e)
