import httpx
import time
from datetime import datetime, timezone

GATEWAY_URL = "http://localhost:8080"
GAME_ID = "game_2026_ashland_vs_opponent"

def send_event(event_id, payload_key, payload):
    # RFC3339 format string for timestamp
    now_rfc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # Make event_id unique
    unique_id = f"{event_id}_{int(time.time())}"
    
    event = {
        "eventId": unique_id,
        "gameId": GAME_ID,
        "source": "referee_mobile",
        "occurredAt": now_rfc,
        "sequence": int(time.time() * 1000) % 1000000,
        "confidence": 1.0,
        "authority": "official",
        payload_key: payload
    }
    
    print(f"Sending {payload_key} event ({unique_id})...")
    response = httpx.post(f"{GATEWAY_URL}/api/v1/events", json=event)
    print(f"Response: {response.status_code} - {response.text}")
    return response

if __name__ == "__main__":
    # Event 1: First pitch - Strike looking
    send_event(
        event_id="evt_test_pitch_001",
        payload_key="pitchResult",
        payload={
            "result": "PITCH_RESULT_TYPE_STRIKE_LOOKING",
            "batterId": "player_ashland_17",
            "pitcherId": "player_opponent_22",
            "speedMph": 91.5
        }
    )
    
    # Wait for processing
    time.sleep(3)
    
    # Event 2: Pitch 2 - Ball
    send_event(
        event_id="evt_test_pitch_002",
        payload_key="pitchResult",
        payload={
            "result": "PITCH_RESULT_TYPE_BALL",
            "batterId": "player_ashland_17",
            "pitcherId": "player_opponent_22",
            "speedMph": 88.0
        }
    )
