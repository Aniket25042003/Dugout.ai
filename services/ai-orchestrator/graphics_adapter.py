"""
File: services/ai-orchestrator/graphics_adapter.py
Layer: Worker — Graphics Production Adapter
Purpose: Resolves player/template data and publishes overlay state for the dashboard.
         Commands arrive from CommandQueue after game events or manual controls.
Dependencies: DBClient player/stat/template lookups, asyncio dismiss tasks, NATS state bus.
"""

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger("ai-orchestrator-graphics")

class GraphicsAdapter:
    """
    Graphics Adapter that manages the overlay display state and auto-dismiss lifecycles.

    Attributes:
        db: Database client used to resolve players, stats, and graphics templates.
        nc: Optional NATS connection used to publish overlay state snapshots.
        _dismiss_task (Optional[asyncio.Task]): Pending auto-hide task for overlays.
        _current_overlay_state (dict): Last published overlay and scoreboard state.
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

        Args:
            cmd_id (str): Production command ID being executed.
            cmd_type (str): Graphics command type to dispatch.
            payload (dict): Adapter-specific payload, usually player or scoreboard data.

        Side Effects:
            Updates in-memory overlay state and publishes the new state to NATS.
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
        """
        Builds and publishes a batter introduction overlay.

        Args:
            payload (dict): Command payload containing ``playerId``.

        Side Effects:
            Reads player/stat/template rows, updates overlay state, publishes NATS,
            and may schedule an auto-dismiss task.
        """
        player_id = payload.get("playerId")
        player = await self.db.get_player_by_id(player_id)
        if not player:
            logger.error("Player %s not found for batter intro", player_id)
            return

        # Batting stats fill the intro card; missing stats fall back to scoreboard-safe zeros.
        stats = await self.db.get_player_stats(player_id)
        
        # Template controls CSS class and auto-dismiss duration without code changes.
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
        """
        Builds and publishes a pitcher introduction overlay.

        Args:
            payload (dict): Command payload containing ``playerId``.

        Side Effects:
            Reads player/stat/template rows, updates overlay state, publishes NATS,
            and may schedule an auto-dismiss task.
        """
        player_id = payload.get("playerId")
        player = await self.db.get_player_by_id(player_id)
        if not player:
            logger.error("Player %s not found for pitcher intro", player_id)
            return

        # Pitching stats fill the intro card; missing stats fall back to neutral values.
        stats = await self.db.get_player_stats(player_id)
        
        # Template controls CSS class and auto-dismiss duration without code changes.
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
        """
        Publishes a text lower-third overlay.

        Args:
            payload (dict): Contains optional ``title`` and ``subtitle`` strings.

        Side Effects:
            Updates overlay state, publishes NATS, and may schedule auto-dismiss.
        """
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
        """
        Publishes a short-lived pitch speed overlay.

        Args:
            payload (dict): Contains optional ``speedMph`` and ``pitchType`` fields.

        Side Effects:
            Updates overlay state, publishes NATS, and may schedule auto-dismiss.
        """
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
        """
        Merges a scoreboard payload into the current graphics state.

        Args:
            payload (dict): Scoreboard fields such as runs, inning, count, and bases.

        Side Effects:
            Publishes the updated graphics state to NATS.
        """
        # Only accept known scoreboard keys so unrelated payload fields cannot leak to the UI.
        for key in self._current_overlay_state["scoreboardData"].keys():
            if key in payload:
                self._current_overlay_state["scoreboardData"][key] = payload[key]
        
        await self._publish_state()

    async def _hide_overlay(self):
        """
        Clears the active overlay while preserving scoreboard state.

        Side Effects:
            Publishes the hidden-overlay state to NATS.
        """
        self._current_overlay_state["activeOverlay"] = None
        self._current_overlay_state["overlayData"] = {}
        await self._publish_state()
        logger.info("Graphics overlay hidden.")

    def _schedule_auto_dismiss(self, duration_ms: int):
        """
        Schedules the active overlay to hide after a template-controlled duration.

        Args:
            duration_ms (int): Delay in milliseconds before hiding the overlay.

        Side Effects:
            Cancels any previous dismiss task and creates a new asyncio task.
        """
        if self._dismiss_task and not self._dismiss_task.done():
            self._dismiss_task.cancel()

        self._dismiss_task = asyncio.create_task(self._auto_dismiss_loop(duration_ms))

    async def _auto_dismiss_loop(self, duration_ms: int):
        """
        Waits for the overlay duration and hides it unless superseded.

        Args:
            duration_ms (int): Delay in milliseconds before hiding the overlay.

        Side Effects:
            Clears and publishes overlay state when the timer completes.
        """
        try:
            await asyncio.sleep(duration_ms / 1000.0)
            await self._hide_overlay()
        except asyncio.CancelledError:
            pass

    async def _publish_state(self):
        """
        Publishes the current graphics state snapshot to NATS.

        Side Effects:
            Sends JSON on ``dugout.production.graphics.state``.
        """
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
