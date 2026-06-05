"""
Command Queue Manager for Dugout.ai.

Manages production command lifecycle with:
- Priority-based queue ordering
- Cooldown enforcement between commands of the same type
- Conflict group resolution (new command supersedes older ones)
- Manager approval gate for low-confidence or risky commands
- Cancellation support with reason tracking
- Status reporting via NATS
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Optional, Callable

logger = logging.getLogger("ai-orchestrator-cmdqueue")

# Cooldown durations by command type (seconds)
DEFAULT_COOLDOWNS = {
    "play_walkup_music": 5.0,
    "update_scoreboard": 1.0,
    "show_batter_intro": 8.0,
    "show_pitcher_intro": 6.0,
    "generate_commentary": 3.0,
}

# Conflict groups — commands in the same group supersede each other
CONFLICT_GROUPS = {
    "play_walkup_music": "music_playback",
    "stop_music": "music_playback",
    "fade_out_music": "music_playback",
    "show_batter_intro": "player_overlay",
    "show_pitcher_intro": "player_overlay",
    "show_lower_third": "lower_third_overlay",
}


def generate_command_id() -> str:
    return f"cmd_{uuid.uuid4().hex[:12]}"


class CommandQueue:
    """
    Production command queue with priority, cooldowns, and conflict resolution.
    """

    def __init__(self, db_client, nats_conn=None):
        self.db = db_client
        self.nc = nats_conn
        self._cooldown_tracker: dict[str, float] = {}  # key -> timestamp when cooldown expires
        self._active_commands: dict[str, dict] = {}     # command_id -> command data
        self._handlers: dict[str, Callable] = {}        # target -> handler function
        self._running = False
        self._process_task: Optional[asyncio.Task] = None

    def register_handler(self, target: str, handler: Callable):
        """Register a handler function for a command target (e.g., 'music_adapter')."""
        self._handlers[target] = handler
        logger.info("Registered command handler for target: %s", target)

    async def start(self):
        """Start the command queue processing loop."""
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("Command queue processor started.")

    async def stop(self):
        """Stop the command queue processing loop."""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("Command queue processor stopped.")

    async def enqueue(
        self,
        game_id: str,
        command_type: str,
        target: str,
        payload: dict,
        source_event_ids: list = None,
        priority: int = 5,
        requires_confirmation: bool = False,
    ) -> dict:
        """
        Add a new command to the queue.
        Handles conflict resolution automatically.
        """
        command_id = generate_command_id()
        conflict_group = CONFLICT_GROUPS.get(command_type)

        # Resolve conflicts — supersede older commands in the same group
        if conflict_group:
            superseded = await self.db.supersede_conflicting_commands(
                game_id, conflict_group, command_id
            )
            if superseded > 0:
                logger.info(
                    "Superseded %d commands in conflict group '%s' for new command %s",
                    superseded, conflict_group, command_id,
                )

        # Persist to database
        result = await self.db.enqueue_command(
            command_id=command_id,
            game_id=game_id,
            command_type=command_type,
            target=target,
            payload=payload,
            source_event_ids=source_event_ids or [],
            priority=priority,
            conflict_group=conflict_group,
            requires_confirmation=requires_confirmation,
        )

        cmd = {
            "command_id": command_id,
            "game_id": game_id,
            "command_type": command_type,
            "target": target,
            "payload": payload,
            "source_event_ids": source_event_ids or [],
            "priority": priority,
            "conflict_group": conflict_group,
            "requires_confirmation": requires_confirmation,
            "status": "pending_approval" if requires_confirmation else "queued",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }

        # Publish status update
        await self._publish_status(cmd)

        logger.info(
            "Enqueued command %s: type=%s target=%s priority=%d status=%s",
            command_id, command_type, target, priority, cmd["status"],
        )

        return cmd

    async def approve(self, command_id: str, confirmed_by: str = "manager") -> bool:
        """Approve a pending command for execution."""
        success = await self.db.approve_command(command_id, confirmed_by)
        if success:
            await self._publish_status({
                "command_id": command_id,
                "status": "approved",
                "confirmed_by": confirmed_by,
            })
            logger.info("Command %s approved by %s", command_id, confirmed_by)
        return success

    async def cancel(self, command_id: str, cancelled_by: str = "manager",
                      reason: str = "manual_cancel") -> bool:
        """Cancel a queued or in-progress command."""
        success = await self.db.cancel_command(command_id, cancelled_by, reason)
        if success:
            # If command is active, notify the handler
            if command_id in self._active_commands:
                del self._active_commands[command_id]

            await self._publish_status({
                "command_id": command_id,
                "status": "cancelled",
                "cancelled_by": cancelled_by,
                "reason": reason,
            })
            logger.info("Command %s cancelled by %s: %s", command_id, cancelled_by, reason)
        return success

    async def emergency_stop(self, game_id: str) -> int:
        """Cancel all active and queued commands for a game."""
        commands = await self.db.get_queued_commands(game_id)
        cancelled = 0
        for cmd in commands:
            success = await self.cancel(
                cmd["command_id"],
                cancelled_by="emergency_stop",
                reason="emergency_stop_all",
            )
            if success:
                cancelled += 1

        # Also stop any active commands
        active_ids = list(self._active_commands.keys())
        for cmd_id in active_ids:
            await self.cancel(cmd_id, cancelled_by="emergency_stop", reason="emergency_stop_all")

        logger.warning("EMERGENCY STOP: Cancelled %d commands for game %s", cancelled, game_id)
        return cancelled

    # =========================================================================
    # Internal Processing
    # =========================================================================

    async def _process_loop(self):
        """Background loop that processes queued commands."""
        while self._running:
            try:
                # Process all games — in a real system we'd scope to active games
                await self._process_pending_commands()
            except Exception as e:
                logger.error("Error in command queue processing loop: %s", e)
            await asyncio.sleep(0.25)  # Check queue 4 times per second

    async def _process_pending_commands(self):
        """Find and execute the next eligible commands."""
        # Get all queued/approved commands
        # In production, this would be scoped to the active game
        game_id = "game_2026_ashland_vs_opponent"  # TODO: Make dynamic
        commands = await self.db.get_queued_commands(game_id)

        for cmd in commands:
            cmd_id = cmd["command_id"]
            cmd_type = cmd["command_type"]
            target = cmd["target"]
            status = cmd["status"]

            # Skip commands waiting for approval
            if status == "pending_approval":
                continue

            # Check cooldown
            cooldown_key = f"{target}:{cmd_type}"
            if cooldown_key in self._cooldown_tracker:
                if time.time() < self._cooldown_tracker[cooldown_key]:
                    continue  # Still in cooldown

            # Check if handler exists
            if target not in self._handlers:
                logger.warning("No handler for target '%s', command %s", target, cmd_id)
                continue

            # Execute command
            await self._execute_command(cmd)

    async def _execute_command(self, cmd: dict):
        """Execute a single command via its registered handler."""
        cmd_id = cmd["command_id"]
        cmd_type = cmd["command_type"]
        target = cmd["target"]
        payload = cmd.get("payload", {})

        # Parse payload if it's a string
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                pass

        # Mark as started
        await self.db.update_command_status(cmd_id, "started")
        self._active_commands[cmd_id] = cmd
        await self._publish_status({"command_id": cmd_id, "status": "started", "command_type": cmd_type})

        try:
            handler = self._handlers[target]
            await handler(cmd_id, cmd_type, payload)

            # Mark as completed
            await self.db.update_command_status(cmd_id, "completed")
            await self._publish_status({"command_id": cmd_id, "status": "completed", "command_type": cmd_type})
            logger.info("Command %s completed: type=%s target=%s", cmd_id, cmd_type, target)

        except Exception as e:
            # Mark as failed
            error_msg = str(e)
            await self.db.update_command_status(cmd_id, "failed", error_msg)
            await self._publish_status({
                "command_id": cmd_id,
                "status": "failed",
                "error": error_msg,
                "command_type": cmd_type,
            })
            logger.error("Command %s failed: %s", cmd_id, e)

        finally:
            self._active_commands.pop(cmd_id, None)

            # Set cooldown
            cooldown_secs = DEFAULT_COOLDOWNS.get(cmd_type, 1.0)
            cooldown_key = f"{target}:{cmd_type}"
            self._cooldown_tracker[cooldown_key] = time.time() + cooldown_secs

    async def _publish_status(self, status: dict):
        """Publish command status update to NATS."""
        if not self.nc:
            return

        try:
            status["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
            await self.nc.publish(
                "dugout.commands.status",
                json.dumps(status).encode(),
            )
        except Exception as e:
            logger.error("Failed to publish command status: %s", e)
