"""
Dugout.ai AI Orchestrator — FastAPI Application.

Phase 3: Extended with media asset management, lineup/roster APIs,
player stats, command queue management, and commentary control endpoints.
"""

import asyncio
import csv
import io
import json
import logging
import os
import sys
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Setup path for local packages/contracts/python imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTRACTS_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "../../packages/contracts/python"))
sys.path.append(CONTRACTS_PATH)

# Verify imports work
try:
    from dugout.v1.game_state_pb2 import GameState
    from dugout.v1.game_event_pb2 import GameEvent
    from dugout.v1.cv_observation_pb2 import CvObservation
    from dugout.v1.production_command_pb2 import ProductionCommand
    contracts_available = True
except ImportError as e:
    logging.warning(f"Could not import generated contract types: {e}")
    contracts_available = False

from db_client import DBClient
from media_manager import MediaManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-orchestrator")

app = FastAPI(title="Dugout.ai AI Orchestrator", version="0.3.0")

# CORS for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://dugout_admin:dugout_secret@localhost:5432/dugout?sslmode=disable")
MEDIA_BASE_PATH = os.getenv("MEDIA_BASE_PATH", os.path.abspath(
    os.path.join(CURRENT_DIR, "../../media")
))

# Shared instances
db = DBClient()
media = MediaManager(db)

# Mount media directory for static file serving
if os.path.isdir(MEDIA_BASE_PATH):
    app.mount("/media", StaticFiles(directory=MEDIA_BASE_PATH), name="media")


# =========================================================================
# Lifecycle
# =========================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("Starting AI Orchestrator (Phase 3)...")
    logger.info(f"NATS target: {NATS_URL}")
    logger.info(f"Database target: {DATABASE_URL}")
    logger.info(f"Media path: {MEDIA_BASE_PATH}")
    logger.info(f"Contracts path configured: {contracts_available} at {CONTRACTS_PATH}")
    await db.connect()
    logger.info("Database connection pool established.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Stopping AI Orchestrator...")
    await db.close()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-orchestrator",
        "version": "0.3.0",
        "contracts_loaded": contracts_available,
    }


# =========================================================================
# Request/Response Models
# =========================================================================

class PlayerOverrideRequest(BaseModel):
    game_id: str
    jersey_number: str
    team_side: Optional[str] = None  # 'home' or 'away'
    reason: Optional[str] = "manual_override"

class MusicControlRequest(BaseModel):
    game_id: str
    action: str  # 'play', 'stop', 'fade_out', 'emergency_stop'
    player_id: Optional[str] = None
    asset_id: Optional[str] = None
    fade_ms: Optional[int] = 2000

class CommentaryControlRequest(BaseModel):
    game_id: str
    action: str  # 'mute', 'unmute', 'regenerate', 'manual'
    text: Optional[str] = None

class CommandActionRequest(BaseModel):
    action: str  # 'approve' or 'cancel'
    reason: Optional[str] = None

class RosterEntry(BaseModel):
    name: str
    jersey_number: str
    position: Optional[str] = ""
    bat_hand: Optional[str] = "R"
    throw_hand: Optional[str] = "R"

class RosterUploadRequest(BaseModel):
    team_id: str
    players: list[RosterEntry]


# =========================================================================
# Game & Lineup Endpoints
# =========================================================================

@app.get("/api/v1/games/{game_id}")
async def get_game(game_id: str):
    """Get game details including team info."""
    game = await db.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game

@app.get("/api/v1/lineup")
async def get_lineup(game_id: str = Query(...), team_id: str = Query(...)):
    """Get ordered batting lineup for a team in a game."""
    lineup = await db.get_game_lineup_ordered(game_id, team_id)
    return {"game_id": game_id, "team_id": team_id, "lineup": lineup}

@app.get("/api/v1/lineup/next-batters")
async def get_next_batters(
    game_id: str = Query(...),
    team_id: str = Query(...),
    current_index: int = Query(1),
    count: int = Query(3),
):
    """Get the next N batters in the lineup from current batting index."""
    batters = await db.get_next_batters(game_id, team_id, current_index, count)
    return {"game_id": game_id, "team_id": team_id, "next_batters": batters}

@app.get("/api/v1/roster")
async def get_roster(game_id: str = Query(...)):
    """Get full roster for all teams in a game."""
    roster = await db.get_broader_roster(game_id)
    return {"game_id": game_id, "players": roster, "count": len(roster)}


# =========================================================================
# Player Endpoints
# =========================================================================

@app.get("/api/v1/players/{player_id}")
async def get_player(player_id: str):
    """Get player details."""
    player = await db.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player

@app.get("/api/v1/players/{player_id}/stats")
async def get_player_stats(player_id: str, stat_type: str = Query("season")):
    """Get player statistics."""
    stats = await db.get_player_stats(player_id, stat_type)
    if not stats:
        raise HTTPException(status_code=404, detail="Stats not found for player")
    return stats

@app.get("/api/v1/players/by-jersey/{jersey_number}")
async def get_player_by_jersey(jersey_number: str, game_id: str = Query(...), team_side: Optional[str] = None):
    """Find a player by jersey number within a game."""
    player = await db.get_player_by_jersey(game_id, jersey_number, team_side)
    if not player:
        raise HTTPException(status_code=404, detail=f"No player found with jersey #{jersey_number}")
    return player


# =========================================================================
# Player Override Endpoint
# =========================================================================

@app.post("/api/v1/override")
async def override_player(req: PlayerOverrideRequest):
    """
    Override the currently detected player.
    Finds the player by jersey number and triggers re-evaluation of
    music, graphics, commentary, and stats for the new player.
    """
    player = await db.get_player_by_jersey(req.game_id, req.jersey_number, req.team_side)
    if not player:
        raise HTTPException(status_code=404, detail=f"No player found with jersey #{req.jersey_number}")

    # Get player stats
    stats = await db.get_player_stats(player["id"])

    # Get walkup track info
    walkup = await media.get_walkup_track(player["id"])

    return {
        "status": "override_applied",
        "player": player,
        "stats": stats,
        "walkup_track": walkup,
        "override_reason": req.reason,
    }


# =========================================================================
# Roster Upload Endpoints
# =========================================================================

@app.post("/api/v1/roster/upload")
async def upload_roster(req: RosterUploadRequest):
    """Upload/update a team roster with player list."""
    players = [p.model_dump() for p in req.players]
    count = await db.bulk_upsert_players(req.team_id, players)
    await db.save_roster_upload(req.team_id, "api_upload", count)
    return {"status": "success", "team_id": req.team_id, "players_upserted": count}

@app.post("/api/v1/roster/upload-csv")
async def upload_roster_csv(
    team_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload a CSV file with roster data.
    Expected columns: name, jersey_number, position, bat_hand, throw_hand
    """
    content = await file.read()
    try:
        text = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        players = []
        for row in reader:
            players.append({
                "name": row.get("name", ""),
                "jersey_number": row.get("jersey_number", ""),
                "position": row.get("position", ""),
                "bat_hand": row.get("bat_hand", "R"),
                "throw_hand": row.get("throw_hand", "R"),
            })
    except Exception as e:
        await db.save_roster_upload(team_id, file.filename, 0, "failed", str(e))
        raise HTTPException(status_code=400, detail=f"CSV parsing error: {e}")

    count = await db.bulk_upsert_players(team_id, players)
    await db.save_roster_upload(team_id, file.filename, count)
    return {"status": "success", "team_id": team_id, "file": file.filename, "players_upserted": count}


# =========================================================================
# Media Asset Endpoints
# =========================================================================

@app.get("/api/v1/media")
async def list_media_assets(
    asset_type: Optional[str] = Query(None),
    player_id: Optional[str] = Query(None),
):
    """List media assets with optional filtering."""
    assets = await media.list_assets(asset_type, player_id)
    return {"assets": assets, "count": len(assets)}

@app.get("/api/v1/media/{asset_id}")
async def get_media_asset(asset_id: str):
    """Get a specific media asset by ID."""
    asset = await db.get_media_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    asset["file_exists"] = media.file_exists(asset["file_path"])
    return asset

@app.post("/api/v1/media/upload")
async def upload_media_asset(
    name: str = Form(...),
    asset_type: str = Form(...),
    player_id: Optional[str] = Form(None),
    team_id: Optional[str] = Form(None),
    duration_ms: Optional[int] = Form(None),
    file: UploadFile = File(...),
):
    """Upload a new media asset file."""
    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    file_data = await file.read()

    result = await media.upload_asset(
        asset_id=asset_id,
        name=name,
        asset_type=asset_type,
        file_data=file_data,
        filename=file.filename,
        player_id=player_id,
        team_id=team_id,
        duration_ms=duration_ms,
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to upload asset")

    return {"status": "uploaded", "asset": result}

@app.delete("/api/v1/media/{asset_id}")
async def delete_media_asset(asset_id: str):
    """Delete a media asset."""
    success = await media.delete_asset(asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found or delete failed")
    return {"status": "deleted", "asset_id": asset_id}

@app.get("/api/v1/media/validate/{game_id}")
async def validate_game_assets(game_id: str):
    """Validate all media assets required for a game."""
    report = await media.validate_game_assets(game_id)
    return report


# =========================================================================
# Graphics Template Endpoints
# =========================================================================

@app.get("/api/v1/templates")
async def list_templates():
    """List all graphics templates."""
    templates = await media.list_templates()
    return {"templates": templates}

@app.get("/api/v1/templates/{template_type}")
async def get_template(template_type: str):
    """Get a specific graphics template by type."""
    template = await media.get_template(template_type)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_type}' not found")
    return template


# =========================================================================
# Command Queue Endpoints
# =========================================================================

@app.get("/api/v1/commands")
async def list_commands(game_id: str = Query(...), target: Optional[str] = Query(None)):
    """List active commands in the queue."""
    commands = await db.get_queued_commands(game_id, target)
    return {"commands": commands, "count": len(commands)}

@app.post("/api/v1/commands/{command_id}")
async def command_action(command_id: str, req: CommandActionRequest):
    """Approve or cancel a command."""
    if req.action == "approve":
        success = await db.approve_command(command_id)
        if not success:
            raise HTTPException(status_code=404, detail="Command not found or not pending approval")
        return {"status": "approved", "command_id": command_id}
    elif req.action == "cancel":
        success = await db.cancel_command(command_id, reason=req.reason or "manual_cancel")
        if not success:
            raise HTTPException(status_code=404, detail="Command not found or already completed")
        return {"status": "cancelled", "command_id": command_id}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")


# =========================================================================
# Music Control Endpoint (Placeholder — wired in PR 2)
# =========================================================================

@app.post("/api/v1/music/control")
async def music_control(req: MusicControlRequest):
    """Control music playback. Wired to music adapter in PR 2."""
    logger.info("Music control: action=%s game=%s player=%s", req.action, req.game_id, req.player_id)
    return {
        "status": "accepted",
        "action": req.action,
        "message": f"Music control '{req.action}' acknowledged (adapter not yet connected)",
    }


# =========================================================================
# Commentary Control Endpoint (Placeholder — wired in PR 4)
# =========================================================================

@app.post("/api/v1/commentary/control")
async def commentary_control(req: CommentaryControlRequest):
    """Control commentary generation. Wired to commentary engine in PR 4."""
    logger.info("Commentary control: action=%s game=%s", req.action, req.game_id)
    return {
        "status": "accepted",
        "action": req.action,
        "message": f"Commentary control '{req.action}' acknowledged (engine not yet connected)",
    }
