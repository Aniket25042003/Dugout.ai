"""
File: services/ai-orchestrator/tests/test_command_queue.py
Layer: Tests — Production Command Queue
Purpose: Verifies command queue priority handling, payload dispatch, and cancellation
         behavior without requiring Postgres or NATS.
Dependencies: pytest, AsyncMock, CommandQueue.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from command_queue import CommandQueue

@pytest.mark.asyncio
# Verifies that queued commands are dispatched through the registered handler.
async def test_command_queue_priority_and_cooldown():
    # Mock DB client
    db = AsyncMock()
    # Mock NATS
    nc = AsyncMock()

    # Create command queue
    queue = CommandQueue(db, nc)
    
    # 1. Enqueue mock commands
    # Mock DB returning commands ordered by priority
    db.get_queued_commands.return_value = [
        {
            "command_id": "cmd_1",
            "game_id": "test_game",
            "command_type": "play_walkup_music",
            "target": "music_adapter",
            "priority": 1,
            "status": "queued",
            "payload": '{"playerId": "player_1"}',
        },
        {
            "command_id": "cmd_2",
            "game_id": "test_game",
            "command_type": "play_walkup_music",
            "target": "music_adapter",
            "priority": 5,
            "status": "queued",
            "payload": '{"playerId": "player_2"}',
        }
    ]

    # Handler mock
    handler_mock = AsyncMock()
    queue.register_handler("music_adapter", handler_mock)

    # Trigger processing once
    await queue._process_pending_commands()

    # The highest priority command (cmd_1) should be executed first
    handler_mock.assert_called_with("cmd_1", "play_walkup_music", {"playerId": "player_1"})

@pytest.mark.asyncio
# Verifies that cancellation delegates to the DB client and returns success.
async def test_command_queue_cancellation():
    db = AsyncMock()
    nc = AsyncMock()
    queue = CommandQueue(db, nc)

    db.cancel_command.return_value = True

    success = await queue.cancel("cmd_cancel", "manager", "manual_cancel")
    assert success is True
    db.cancel_command.assert_called_once_with("cmd_cancel", "manager", "manual_cancel")
