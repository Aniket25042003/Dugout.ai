"""
Media Asset Manager for Dugout.ai.

Handles resolution, validation, and management of media assets
including walk-up music, headshots, team branding, and graphics templates.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("ai-orchestrator-media")

# Base path for media files — relative to project root
MEDIA_BASE_PATH = os.getenv("MEDIA_BASE_PATH", os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../media")
))

# Fallback track asset ID
FALLBACK_WALKUP_ASSET_ID = "asset_walkup_fallback"


class MediaManager:
    """Manages media asset resolution, validation, and file operations."""

    def __init__(self, db_client):
        self.db = db_client
        logger.info("MediaManager initialized. Base path: %s", MEDIA_BASE_PATH)

    def resolve_path(self, relative_path: str) -> str:
        """Resolve a relative media path to an absolute filesystem path."""
        if os.path.isabs(relative_path):
            return relative_path
        return os.path.join(MEDIA_BASE_PATH, relative_path.replace("media/", "", 1))

    def file_exists(self, relative_path: str) -> bool:
        """Check if a media file exists on disk."""
        abs_path = self.resolve_path(relative_path)
        return os.path.isfile(abs_path)

    # =========================================================================
    # Walk-Up Music
    # =========================================================================

    async def get_walkup_track(self, player_id: str) -> Optional[dict]:
        """
        Get a player's walk-up music track.
        Returns the track info with resolved absolute path.
        Falls back to default track if player's track is missing.
        """
        # Get player to find their walkup_track_id
        player = await self.db.get_player_by_id(player_id)
        if not player or not player.get("walkup_track_id"):
            logger.warning("No walk-up track assigned for player %s, using fallback", player_id)
            return await self.get_fallback_track()

        # Get the media asset
        asset = await self.db.get_media_asset(player["walkup_track_id"])
        if not asset:
            logger.warning("Walk-up asset %s not found in DB, using fallback", player["walkup_track_id"])
            return await self.get_fallback_track()

        # Verify file exists
        if not self.file_exists(asset["file_path"]):
            logger.warning("Walk-up file missing: %s, using fallback", asset["file_path"])
            return await self.get_fallback_track()

        return {
            "asset_id": asset["id"],
            "name": asset["name"],
            "file_path": asset["file_path"],
            "absolute_path": self.resolve_path(asset["file_path"]),
            "duration_ms": asset.get("duration_ms", 8000),
            "player_id": player_id,
            "player_name": player.get("name", "Unknown"),
            "is_fallback": False,
        }

    async def get_fallback_track(self) -> Optional[dict]:
        """Get the default fallback walk-up track."""
        asset = await self.db.get_media_asset(FALLBACK_WALKUP_ASSET_ID)
        if asset and self.file_exists(asset["file_path"]):
            return {
                "asset_id": asset["id"],
                "name": asset["name"],
                "file_path": asset["file_path"],
                "absolute_path": self.resolve_path(asset["file_path"]),
                "duration_ms": asset.get("duration_ms", 10000),
                "player_id": None,
                "player_name": "Default",
                "is_fallback": True,
            }

        # Last resort: check if fallback file exists on disk
        fallback_path = os.path.join(MEDIA_BASE_PATH, "audio", "fallback", "default_walkup.wav")
        if os.path.isfile(fallback_path):
            return {
                "asset_id": FALLBACK_WALKUP_ASSET_ID,
                "name": "Default Walk-Up Track",
                "file_path": "media/audio/fallback/default_walkup.wav",
                "absolute_path": fallback_path,
                "duration_ms": 10000,
                "player_id": None,
                "player_name": "Default",
                "is_fallback": True,
            }

        logger.error("No fallback walk-up track found!")
        return None

    # =========================================================================
    # Headshots & Player Images
    # =========================================================================

    async def get_headshot_path(self, player_id: str) -> Optional[str]:
        """Get the absolute path to a player's headshot image."""
        player = await self.db.get_player_by_id(player_id)
        if not player or not player.get("headshot_path"):
            return None

        if self.file_exists(player["headshot_path"]):
            return self.resolve_path(player["headshot_path"])
        return None

    async def get_headshot_url(self, player_id: str) -> str:
        """
        Get a URL-safe path for the player's headshot.
        Returns the relative path for serving via the API.
        """
        player = await self.db.get_player_by_id(player_id)
        if player and player.get("headshot_path") and self.file_exists(player["headshot_path"]):
            return f"/media/{player['headshot_path'].replace('media/', '', 1)}"
        return "/media/images/headshots/default.png"

    # =========================================================================
    # Team Branding
    # =========================================================================

    async def get_team_logo_path(self, team_id: str) -> Optional[str]:
        """Get absolute path to a team's logo."""
        # Direct file check based on convention
        logo_path = f"media/images/team-logos/{team_id}.png"
        if self.file_exists(logo_path):
            return self.resolve_path(logo_path)
        return None

    # =========================================================================
    # Asset Listing & Management
    # =========================================================================

    async def list_assets(self, asset_type: Optional[str] = None,
                           player_id: Optional[str] = None) -> list:
        """List media assets with file existence validation."""
        assets = await self.db.list_media_assets(asset_type, player_id)
        for asset in assets:
            asset["file_exists"] = self.file_exists(asset["file_path"])
            asset["absolute_path"] = self.resolve_path(asset["file_path"])
        return assets

    async def upload_asset(self, asset_id: str, name: str, asset_type: str,
                            file_data: bytes, filename: str,
                            player_id: Optional[str] = None,
                            team_id: Optional[str] = None,
                            duration_ms: Optional[int] = None) -> Optional[dict]:
        """
        Save an uploaded media file and create a database record.
        """
        # Determine subdirectory based on asset type
        type_dirs = {
            "audio_walkup": "audio/walkup",
            "audio_effect": "audio/effects",
            "image_headshot": "images/headshots",
            "image_logo": "images/team-logos",
            "image_template": "images/templates",
        }
        subdir = type_dirs.get(asset_type, "misc")
        save_dir = os.path.join(MEDIA_BASE_PATH, subdir)
        os.makedirs(save_dir, exist_ok=True)

        # Save file to disk
        save_path = os.path.join(save_dir, filename)
        try:
            with open(save_path, "wb") as f:
                f.write(file_data)
            logger.info("Saved media file: %s (%d bytes)", save_path, len(file_data))
        except Exception as e:
            logger.error("Failed to save media file %s: %s", save_path, e)
            return None

        # Create database record
        relative_path = f"media/{subdir}/{filename}"
        result = await self.db.create_media_asset(
            asset_id=asset_id,
            name=name,
            asset_type=asset_type,
            file_path=relative_path,
            player_id=player_id,
            team_id=team_id,
            duration_ms=duration_ms,
        )
        return result

    async def delete_asset(self, asset_id: str, delete_file: bool = True) -> bool:
        """Delete a media asset from DB and optionally from disk."""
        if delete_file:
            asset = await self.db.get_media_asset(asset_id)
            if asset:
                abs_path = self.resolve_path(asset["file_path"])
                if os.path.isfile(abs_path):
                    try:
                        os.remove(abs_path)
                        logger.info("Deleted media file: %s", abs_path)
                    except OSError as e:
                        logger.error("Failed to delete file %s: %s", abs_path, e)

        return await self.db.delete_media_asset(asset_id)

    # =========================================================================
    # Graphics Templates
    # =========================================================================

    async def get_template(self, template_type: str) -> Optional[dict]:
        """Get a graphics template by type."""
        return await self.db.get_graphics_template(template_type)

    async def list_templates(self) -> list:
        """List all available graphics templates."""
        return await self.db.list_graphics_templates()

    # =========================================================================
    # Validation
    # =========================================================================

    async def validate_game_assets(self, game_id: str) -> dict:
        """
        Validate that all required media assets exist for a game.
        Returns a report of missing/available assets.
        """
        report = {
            "game_id": game_id,
            "missing_walkup_tracks": [],
            "missing_headshots": [],
            "missing_team_logos": [],
            "total_players": 0,
            "assets_ok": True,
        }

        roster = await self.db.get_broader_roster(game_id)
        report["total_players"] = len(roster)

        for player in roster:
            pid = player["id"]

            # Check walk-up track
            if player.get("walkup_track_id"):
                asset = await self.db.get_media_asset(player["walkup_track_id"])
                if not asset or not self.file_exists(asset.get("file_path", "")):
                    report["missing_walkup_tracks"].append({
                        "player_id": pid,
                        "player_name": player["name"],
                        "asset_id": player["walkup_track_id"],
                    })
                    report["assets_ok"] = False
            else:
                report["missing_walkup_tracks"].append({
                    "player_id": pid,
                    "player_name": player["name"],
                    "asset_id": None,
                })
                report["assets_ok"] = False

            # Check headshot
            if not player.get("headshot_path") or not self.file_exists(player.get("headshot_path", "")):
                report["missing_headshots"].append({
                    "player_id": pid,
                    "player_name": player["name"],
                })

        # Check team logos
        game = await self.db.get_game(game_id)
        if game:
            for team_key in ["home_team_id", "away_team_id"]:
                team_id = game[team_key]
                if not await self.get_team_logo_path(team_id):
                    report["missing_team_logos"].append(team_id)

        return report
