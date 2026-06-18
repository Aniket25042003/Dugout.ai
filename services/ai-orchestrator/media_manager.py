"""
File: services/ai-orchestrator/media_manager.py
Layer: Worker/API — Media Asset Management
Purpose: Resolves and validates media assets used by music, graphics, and API routes.
         It bridges database asset metadata with files stored under the media folder.
Dependencies: DBClient media/player lookups, local filesystem, MEDIA_BASE_PATH.
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
    """
    Manages media asset resolution, validation, and file operations.

    Attributes:
        db: Database client used to read and write asset metadata.
    """

    def __init__(self, db_client):
        self.db = db_client
        logger.info("MediaManager initialized. Base path: %s", MEDIA_BASE_PATH)

    def resolve_path(self, relative_path: str) -> str:
        """
        Resolves a media path to an absolute filesystem path.

        Args:
            relative_path (str): Absolute path or path relative to the media root.

        Returns:
            str: Absolute path on disk for the media asset.
        """
        if os.path.isabs(relative_path):
            return relative_path
        return os.path.join(MEDIA_BASE_PATH, relative_path.replace("media/", "", 1))

    def file_exists(self, relative_path: str) -> bool:
        """
        Checks whether a media file exists on disk.

        Args:
            relative_path (str): Absolute or relative media path to validate.

        Returns:
            bool: True when the resolved path points to a file.
        """
        abs_path = self.resolve_path(relative_path)
        return os.path.isfile(abs_path)

    # =========================================================================
    # Walk-Up Music
    # =========================================================================

    async def get_walkup_track(self, player_id: str) -> Optional[dict]:
        """
        Gets a player's walk-up music track with fallback handling.

        Args:
            player_id (str): Player whose walk-up audio should be resolved.

        Returns:
            Optional[dict]: Track metadata with relative and absolute paths, or None
                when neither player-specific nor fallback audio is available.

        Side Effects:
            Reads player and media asset records from Postgres.
        """
        # Player metadata stores the media asset ID rather than a direct file path.
        player = await self.db.get_player_by_id(player_id)
        if not player or not player.get("walkup_track_id"):
            logger.warning("No walk-up track assigned for player %s, using fallback", player_id)
            return await self.get_fallback_track()

        # Get the media asset
        asset = await self.db.get_media_asset(player["walkup_track_id"])
        if not asset:
            logger.warning("Walk-up asset %s not found in DB, using fallback", player["walkup_track_id"])
            return await self.get_fallback_track()

        # Database metadata is not enough; the dashboard can only play files present on disk.
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
        """
        Gets the default walk-up track used when player-specific audio is missing.

        Returns:
            Optional[dict]: Fallback track metadata, or None if no fallback file exists.

        Side Effects:
            Reads the fallback media asset record from Postgres.
        """
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

        # Last-resort file convention keeps local demos working even if seed data is missing.
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
        """
        Gets the absolute path to a player's headshot image.

        Args:
            player_id (str): Player whose image should be resolved.

        Returns:
            Optional[str]: Absolute image path, or None when unavailable.
        """
        player = await self.db.get_player_by_id(player_id)
        if not player or not player.get("headshot_path"):
            return None

        if self.file_exists(player["headshot_path"]):
            return self.resolve_path(player["headshot_path"])
        return None

    async def get_headshot_url(self, player_id: str) -> str:
        """
        Gets a URL-safe path for a player's headshot.

        Args:
            player_id (str): Player whose image URL should be resolved.

        Returns:
            str: API-served media URL, falling back to the default headshot URL.
        """
        player = await self.db.get_player_by_id(player_id)
        if player and player.get("headshot_path") and self.file_exists(player["headshot_path"]):
            return f"/media/{player['headshot_path'].replace('media/', '', 1)}"
        return "/media/images/headshots/default.png"

    # =========================================================================
    # Team Branding
    # =========================================================================

    async def get_team_logo_path(self, team_id: str) -> Optional[str]:
        """
        Gets the absolute path to a team's logo by naming convention.

        Args:
            team_id (str): Team identifier used in ``team_<name>.png`` assets.

        Returns:
            Optional[str]: Absolute logo path, or None when unavailable.
        """
        # Team logos are convention-based assets rather than DB-backed media rows.
        logo_path = f"media/images/team-logos/{team_id}.png"
        if self.file_exists(logo_path):
            return self.resolve_path(logo_path)
        return None

    # =========================================================================
    # Asset Listing & Management
    # =========================================================================

    async def list_assets(self, asset_type: Optional[str] = None,
                           player_id: Optional[str] = None) -> list:
        """
        Lists media assets with filesystem validation fields.

        Args:
            asset_type (Optional[str]): Optional asset type filter.
            player_id (Optional[str]): Optional player ownership filter.

        Returns:
            list: Asset rows augmented with ``file_exists`` and ``absolute_path``.
        """
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
        Saves an uploaded media file and creates a database asset record.

        Args:
            asset_id (str): Unique asset identifier to store in Postgres.
            name (str): Display name for the uploaded asset.
            asset_type (str): Asset category controlling destination subdirectory.
            file_data (bytes): Uploaded file bytes.
            filename (str): File name to write under the media root.
            player_id (Optional[str]): Optional player linked to the asset.
            team_id (Optional[str]): Optional team linked to the asset.
            duration_ms (Optional[int]): Optional audio duration metadata.

        Returns:
            Optional[dict]: Created asset record, or None if writing the file fails.

        Side Effects:
            Writes a file to disk and inserts a media asset row in Postgres.
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

        # File storage is local for the pilot; DB only stores a relative media path.
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
        """
        Deletes a media asset from the database and optionally from disk.

        Args:
            asset_id (str): Asset identifier to delete.
            delete_file (bool): Whether to remove the physical file as well.

        Returns:
            bool: True when the database delete succeeds.

        Side Effects:
            May delete a local media file.
        """
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
        """
        Gets a graphics template by type.

        Args:
            template_type (str): Template key such as ``batter_intro``.

        Returns:
            Optional[dict]: Template row, or None when unavailable.
        """
        return await self.db.get_graphics_template(template_type)

    async def list_templates(self) -> list:
        """
        Lists available graphics templates.

        Returns:
            list: Graphics template rows ordered by the database client.
        """
        return await self.db.list_graphics_templates()

    # =========================================================================
    # Validation
    # =========================================================================

    async def validate_game_assets(self, game_id: str) -> dict:
        """
        Validates that required media assets exist for a game.

        Args:
            game_id (str): Game whose roster and team assets should be checked.

        Returns:
            dict: Validation report containing missing walk-up tracks, headshots,
                logos, total player count, and an overall ``assets_ok`` flag.

        Side Effects:
            Reads roster, asset, and game records from Postgres.
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

            # Walk-up tracks are required for automated batter-intro music.
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

            # Headshots are useful for overlays, but they do not fail the overall asset flag.
            if not player.get("headshot_path") or not self.file_exists(player.get("headshot_path", "")):
                report["missing_headshots"].append({
                    "player_id": pid,
                    "player_name": player["name"],
                })

        # Logo validation is convention-based because team logos are static pilot assets.
        game = await self.db.get_game(game_id)
        if game:
            for team_key in ["home_team_id", "away_team_id"]:
                team_id = game[team_key]
                if not await self.get_team_logo_path(team_id):
                    report["missing_team_logos"].append(team_id)

        return report
