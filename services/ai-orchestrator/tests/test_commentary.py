import pytest
from unittest.mock import AsyncMock, MagicMock
from commentary_engine import CommentaryEngine

@pytest.mark.asyncio
async def test_commentary_state_updates():
    db = AsyncMock()
    llm = AsyncMock()
    tts = AsyncMock()
    media = MagicMock()
    
    engine = CommentaryEngine(db, llm, tts, media)

    # Initial state
    state = await engine.get_or_create_game_state("test_game")
    assert state["balls"] == 0
    assert state["strikes"] == 0
    assert state["outs"] == 0
    assert state["homeScore"] == 0
    assert state["awayScore"] == 0

    # 1. Apply a ball event
    event_ball = {
        "pitchResult": {
            "result": "BALL",
            "pitcherId": "pitcher_1",
            "batterId": "batter_1"
        }
    }
    engine.update_game_state_from_event(state, event_ball)
    assert state["balls"] == 1
    assert state["activeBatterId"] == "batter_1"
    assert state["activePitcherId"] == "pitcher_1"

    # 2. Apply a strike event
    event_strike = {
        "pitchResult": {
            "result": "STRIKE_LOOKING"
        }
    }
    engine.update_game_state_from_event(state, event_strike)
    assert state["strikes"] == 1

@pytest.mark.asyncio
async def test_commentary_fallback_generation():
    db = AsyncMock()
    llm = AsyncMock()
    tts = AsyncMock()
    media = MagicMock()

    engine = CommentaryEngine(db, llm, tts, media)

    # Test single outcome fallback
    event_single = {
        "playOutcome": {
            "type": "SINGLE",
            "batterId": "player_17"
        }
    }
    
    text = engine._generate_fallback_template(event_single, "Marcus Rivera", "Jake Thompson")
    assert "single" in text.lower()
    assert "Marcus Rivera" in text
