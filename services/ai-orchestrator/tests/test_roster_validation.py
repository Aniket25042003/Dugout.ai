import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from orchestrator import handle_cv_observation, CV_CONFIDENCE_THRESHOLD

class MockMsg:
    def __init__(self, data: bytes):
        self.data = data

@pytest.mark.asyncio
@patch("orchestrator.db")
async def test_handle_cv_observation_not_on_roster(mock_db):
    """Test that a jersey number not present on any roster triggers a player_not_on_roster alert."""
    # Setup mock DB responses
    mock_db.get_broader_roster = AsyncMock(return_value=[])
    mock_db.get_active_lineup = AsyncMock(return_value=[])

    # Setup mock NATS connection
    mock_nc = MagicMock()
    mock_nc.publish = AsyncMock()

    # Create message with observed jersey number '99' (not in active roster)
    obs_payload = {
        "observationId": "obs_test_123",
        "gameId": "game_test_001",
        "confidence": 0.95,
        "jerseyNumber": {
            "jerseyNumber": "99",
            "teamSide": "TEAM_SIDE_HOME"
        }
    }
    msg = MockMsg(json.dumps(obs_payload).encode())

    # Invoke handler
    await handle_cv_observation(mock_nc, msg)

    # Verify dynamic queries were called with correct game ID
    mock_db.get_broader_roster.assert_called_once_with("game_test_001")
    mock_db.get_active_lineup.assert_called_once_with("game_test_001")

    # Verify that a NATS message was published to the alerts subject
    mock_nc.publish.assert_called_once()
    subject, data = mock_nc.publish.call_args[0]
    
    assert subject == "dugout.game.game_test_001.alerts"
    
    alert_cmd = json.loads(data.decode())
    assert alert_cmd["commandType"] == "trigger_alert"
    assert alert_cmd["payload"]["alertType"] == "player_not_on_roster"
    assert "not registered" in alert_cmd["payload"]["message"]


@pytest.mark.asyncio
@patch("orchestrator.db")
async def test_handle_cv_observation_inactive_lineup(mock_db):
    """Test that a player on the roster but not in the active lineup triggers an inactive_lineup_detection alert."""
    # Setup mock DB responses: player '12' is on roster but not in the active lineup
    mock_db.get_broader_roster = AsyncMock(return_value=[
        {"id": "player_12", "jersey_number": "12", "name": "Sam Active", "team_id": "team_home"}
    ])
    mock_db.get_active_lineup = AsyncMock(return_value=[])  # Empty lineup

    mock_nc = MagicMock()
    mock_nc.publish = AsyncMock()

    obs_payload = {
        "observationId": "obs_test_456",
        "gameId": "game_test_001",
        "confidence": 0.95,
        "jerseyNumber": {
            "jerseyNumber": "12",
            "teamSide": "TEAM_SIDE_HOME"
        }
    }
    msg = MockMsg(json.dumps(obs_payload).encode())

    await handle_cv_observation(mock_nc, msg)

    mock_nc.publish.assert_called_once()
    subject, data = mock_nc.publish.call_args[0]
    
    assert subject == "dugout.game.game_test_001.alerts"
    
    alert_cmd = json.loads(data.decode())
    assert alert_cmd["commandType"] == "trigger_alert"
    assert alert_cmd["payload"]["alertType"] == "inactive_lineup_detection"
    assert "not in active lineup" in alert_cmd["payload"]["message"]


@pytest.mark.asyncio
@patch("orchestrator.db")
async def test_handle_cv_observation_valid_lineup(mock_db):
    """Test that a high-confidence active lineup player triggers a walk-up music command."""
    # Setup mock DB responses: player '17' is on both the roster and in the active lineup
    mock_db.get_broader_roster = AsyncMock(return_value=[
        {"id": "player_17", "jersey_number": "17", "name": "Alex Johnson", "team_id": "team_home", "walkup_track_id": "track_custom_17"}
    ])
    mock_db.get_active_lineup = AsyncMock(return_value=[
        {"id": "player_17", "jersey_number": "17", "name": "Alex Johnson", "position": "Outfield", "team_id": "team_home"}
    ])

    mock_nc = MagicMock()
    mock_nc.publish = AsyncMock()

    obs_payload = {
        "observationId": "obs_test_789",
        "gameId": "game_test_001",
        "confidence": 0.95,
        "jerseyNumber": {
            "jerseyNumber": "17",
            "teamSide": "TEAM_SIDE_HOME"
        }
    }
    msg = MockMsg(json.dumps(obs_payload).encode())

    await handle_cv_observation(mock_nc, msg)

    # Verify that a command was published to the commands subject (instead of alerts)
    mock_nc.publish.assert_called_once()
    subject, data = mock_nc.publish.call_args[0]
    
    assert subject == "dugout.game.game_test_001.commands"
    
    cmd = json.loads(data.decode())
    assert cmd["commandType"] == "play_walkup_music"
    assert cmd["payload"]["playerId"] == "player_17"
    assert cmd["payload"]["assetId"] == "track_custom_17"
