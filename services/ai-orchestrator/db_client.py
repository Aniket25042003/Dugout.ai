"""
Database client for Dugout.ai AI Orchestrator.

Provides async query methods for game data, rosters, player stats,
media assets, lineups, commentary history, and command queue.
"""

import logging
import os
from typing import Optional
import asyncpg

logger = logging.getLogger("ai-orchestrator-db")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://dugout_admin:dugout_secret@localhost:5432/dugout?sslmode=disable"
)

class DBClient:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Initialize the async database connection pool."""
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(DATABASE_URL)
                logger.info("Successfully established PostgreSQL connection pool.")
            except Exception as e:
                logger.error(f"Failed to create database connection pool: {e}")
                raise e

    async def close(self):
        """Close the database pool connection."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed database connection pool.")

    async def _ensure_pool(self):
        """Ensure connection pool is initialized."""
        if not self.pool:
            await self.connect()

    # =========================================================================
    # Roster & Lineup Queries
    # =========================================================================

    async def get_active_lineup(self, game_id: str) -> list:
        """
        Retrieves the active lineup (players currently on the field/batting lineup)
        for a specific game.
        """
        await self._ensure_pool()

        query = """
            SELECT p.id, p.jersey_number, p.name, l.position, l.batting_order,
                   t.id as team_id, t.short_name as team_short,
                   p.headshot_path, p.walkup_track_id, p.bat_hand, p.throw_hand,
                   p.pronunciation, p.commentary_notes
            FROM lineup_entries l
            JOIN players p ON l.player_id = p.id
            JOIN teams t ON l.team_id = t.id
            WHERE l.game_id = $1 AND l.is_active = TRUE
            ORDER BY t.id, l.batting_order;
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, game_id)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching active lineup for game {game_id}: {e}")
            return []

    async def get_broader_roster(self, game_id: str) -> list:
        """
        Retrieves all registered roster players for both competing teams
        in a specific game.
        """
        await self._ensure_pool()

        query = """
            SELECT p.id, p.jersey_number, p.name, p.team_id, p.walkup_track_id,
                   p.position, p.headshot_path, p.bat_hand, p.throw_hand,
                   p.pronunciation, p.commentary_notes
            FROM players p
            JOIN games g ON g.home_team_id = p.team_id OR g.away_team_id = p.team_id
            WHERE g.id = $1;
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, game_id)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching broader roster for game {game_id}: {e}")
            return []

    async def get_game_lineup_ordered(self, game_id: str, team_id: str) -> list:
        """
        Returns the batting order for a team in a game, ordered by batting_order.
        """
        await self._ensure_pool()

        query = """
            SELECT p.id, p.name, p.jersey_number, l.batting_order, l.position,
                   p.headshot_path, p.walkup_track_id, p.bat_hand, p.throw_hand,
                   p.pronunciation, p.commentary_notes
            FROM lineup_entries l
            JOIN players p ON l.player_id = p.id
            WHERE l.game_id = $1 AND l.team_id = $2 AND l.is_active = TRUE
            ORDER BY l.batting_order ASC;
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, game_id, team_id)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching lineup for game {game_id}, team {team_id}: {e}")
            return []

    async def get_next_batters(self, game_id: str, team_id: str, current_batting_index: int, count: int = 3) -> list:
        """
        Returns the next N batters in the lineup after the current batting index.
        Wraps around to the top of the order if needed.
        """
        await self._ensure_pool()

        lineup = await self.get_game_lineup_ordered(game_id, team_id)
        if not lineup:
            return []

        total = len(lineup)
        result = []
        for i in range(1, count + 1):
            idx = (current_batting_index + i - 1) % total
            result.append(lineup[idx])
        return result

    # =========================================================================
    # Player Queries
    # =========================================================================

    async def get_player_by_jersey(self, game_id: str, jersey_number: str, team_side: Optional[str] = None) -> Optional[dict]:
        """
        Find a player by jersey number within a game's rosters.
        team_side: 'home' or 'away' to narrow the search.
        """
        await self._ensure_pool()

        if team_side == 'home':
            query = """
                SELECT p.id, p.name, p.jersey_number, p.team_id, p.position,
                       p.headshot_path, p.walkup_track_id, p.bat_hand, p.throw_hand,
                       p.pronunciation, p.commentary_notes,
                       t.name as team_name, t.short_name as team_short, t.primary_color as team_color
                FROM players p
                JOIN teams t ON p.team_id = t.id
                JOIN games g ON g.home_team_id = p.team_id
                WHERE g.id = $1 AND p.jersey_number = $2
                LIMIT 1;
            """
        elif team_side == 'away':
            query = """
                SELECT p.id, p.name, p.jersey_number, p.team_id, p.position,
                       p.headshot_path, p.walkup_track_id, p.bat_hand, p.throw_hand,
                       p.pronunciation, p.commentary_notes,
                       t.name as team_name, t.short_name as team_short, t.primary_color as team_color
                FROM players p
                JOIN teams t ON p.team_id = t.id
                JOIN games g ON g.away_team_id = p.team_id
                WHERE g.id = $1 AND p.jersey_number = $2
                LIMIT 1;
            """
        else:
            query = """
                SELECT p.id, p.name, p.jersey_number, p.team_id, p.position,
                       p.headshot_path, p.walkup_track_id, p.bat_hand, p.throw_hand,
                       p.pronunciation, p.commentary_notes,
                       t.name as team_name, t.short_name as team_short, t.primary_color as team_color
                FROM players p
                JOIN teams t ON p.team_id = t.id
                JOIN games g ON (g.home_team_id = p.team_id OR g.away_team_id = p.team_id)
                WHERE g.id = $1 AND p.jersey_number = $2
                LIMIT 1;
            """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, game_id, jersey_number)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error finding player jersey #{jersey_number}: {e}")
            return None

    async def get_player_by_id(self, player_id: str) -> Optional[dict]:
        """Fetch a player by their ID with full details."""
        await self._ensure_pool()

        query = """
            SELECT p.id, p.name, p.jersey_number, p.team_id, p.position,
                   p.headshot_path, p.walkup_track_id, p.bat_hand, p.throw_hand,
                   p.pronunciation, p.commentary_notes,
                   t.name as team_name, t.short_name as team_short, t.primary_color as team_color
            FROM players p
            JOIN teams t ON p.team_id = t.id
            WHERE p.id = $1;
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, player_id)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching player {player_id}: {e}")
            return None

    # =========================================================================
    # Player Stats Queries
    # =========================================================================

    async def get_player_stats(self, player_id: str, stat_type: str = 'season') -> Optional[dict]:
        """Fetch season or career stats for a player."""
        await self._ensure_pool()

        query = """
            SELECT player_id, season, stat_type,
                   at_bats, hits, doubles, triples, home_runs, rbis,
                   walks, strikeouts, batting_avg, on_base_pct, slugging_pct, ops,
                   innings_pitched, earned_runs, era, pitch_strikeouts, pitch_walks, whip,
                   wins, losses, saves,
                   stolen_bases, errors, last_5_avg, hit_streak
            FROM player_stats
            WHERE player_id = $1 AND stat_type = $2
            ORDER BY season DESC
            LIMIT 1;
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, player_id, stat_type)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching stats for player {player_id}: {e}")
            return None

    # =========================================================================
    # Media Asset Queries
    # =========================================================================

    async def get_media_asset(self, asset_id: str) -> Optional[dict]:
        """Fetch a media asset by ID."""
        await self._ensure_pool()

        query = """
            SELECT id, name, type, file_path, player_id, team_id,
                   duration_ms, thumbnail_path, tags, metadata
            FROM media_assets
            WHERE id = $1;
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, asset_id)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching media asset {asset_id}: {e}")
            return None

    async def list_media_assets(self, asset_type: Optional[str] = None, player_id: Optional[str] = None) -> list:
        """List media assets, optionally filtered by type and/or player."""
        await self._ensure_pool()

        conditions = []
        params = []
        param_idx = 1

        if asset_type:
            conditions.append(f"type = ${param_idx}")
            params.append(asset_type)
            param_idx += 1

        if player_id:
            conditions.append(f"player_id = ${param_idx}")
            params.append(player_id)
            param_idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT id, name, type, file_path, player_id, team_id,
                   duration_ms, thumbnail_path, tags, metadata
            FROM media_assets
            {where}
            ORDER BY name;
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error listing media assets: {e}")
            return []

    async def create_media_asset(self, asset_id: str, name: str, asset_type: str, file_path: str,
                                  player_id: Optional[str] = None, team_id: Optional[str] = None,
                                  duration_ms: Optional[int] = None, metadata: dict = None) -> Optional[dict]:
        """Insert a new media asset record."""
        await self._ensure_pool()
        import json

        query = """
            INSERT INTO media_assets (id, name, type, file_path, player_id, team_id, duration_ms, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id, name, type, file_path;
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    query, asset_id, name, asset_type, file_path,
                    player_id, team_id, duration_ms, json.dumps(metadata or {})
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error creating media asset {asset_id}: {e}")
            return None

    async def delete_media_asset(self, asset_id: str) -> bool:
        """Delete a media asset by ID."""
        await self._ensure_pool()

        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("DELETE FROM media_assets WHERE id = $1", asset_id)
                return result == "DELETE 1"
        except Exception as e:
            logger.error(f"Error deleting media asset {asset_id}: {e}")
            return False

    # =========================================================================
    # Graphics Template Queries
    # =========================================================================

    async def get_graphics_template(self, template_type: str) -> Optional[dict]:
        """Fetch a graphics template by type."""
        await self._ensure_pool()

        query = """
            SELECT id, name, template_type, file_path, css_class,
                   display_duration_ms, auto_dismiss, layout_config
            FROM graphics_templates
            WHERE template_type = $1
            LIMIT 1;
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, template_type)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching template {template_type}: {e}")
            return None

    async def list_graphics_templates(self) -> list:
        """List all available graphics templates."""
        await self._ensure_pool()

        query = """
            SELECT id, name, template_type, css_class, display_duration_ms, auto_dismiss, layout_config
            FROM graphics_templates
            ORDER BY template_type;
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error listing graphics templates: {e}")
            return []

    # =========================================================================
    # Commentary History
    # =========================================================================

    async def save_commentary(self, game_id: str, text: str, source: str = 'template',
                               source_event_ids: list = None, audio_path: Optional[str] = None,
                               context_snapshot: dict = None, llm_model: Optional[str] = None,
                               generation_ms: Optional[int] = None, tts_model: Optional[str] = None,
                               tts_duration_ms: Optional[int] = None) -> Optional[int]:
        """Persist a commentary entry for audit trail."""
        await self._ensure_pool()
        import json

        query = """
            INSERT INTO commentary_history
                (game_id, text, source, source_event_ids, audio_path,
                 context_snapshot, llm_model, generation_ms, tts_model, tts_duration_ms)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id;
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    query, game_id, text, source, source_event_ids or [],
                    audio_path, json.dumps(context_snapshot or {}),
                    llm_model, generation_ms, tts_model, tts_duration_ms
                )
                return row['id'] if row else None
        except Exception as e:
            logger.error(f"Error saving commentary: {e}")
            return None

    # =========================================================================
    # Command Queue
    # =========================================================================

    async def enqueue_command(self, command_id: str, game_id: str, command_type: str,
                               target: str, payload: dict, source_event_ids: list = None,
                               priority: int = 5, conflict_group: Optional[str] = None,
                               requires_confirmation: bool = False) -> Optional[dict]:
        """Insert a command into the queue."""
        await self._ensure_pool()
        import json

        query = """
            INSERT INTO command_queue
                (command_id, game_id, command_type, target, payload,
                 source_event_ids, priority, conflict_group,
                 requires_manager_confirmation, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                    CASE WHEN $9 THEN 'pending_approval' ELSE 'queued' END)
            RETURNING command_id, status, created_at;
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    query, command_id, game_id, command_type, target,
                    json.dumps(payload), source_event_ids or [],
                    priority, conflict_group, requires_confirmation
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error enqueuing command {command_id}: {e}")
            return None

    async def update_command_status(self, command_id: str, status: str,
                                     error_message: Optional[str] = None) -> bool:
        """Update a command's status in the queue."""
        await self._ensure_pool()

        time_field = ""
        if status == 'started':
            time_field = ", started_at = NOW()"
        elif status in ('completed', 'failed'):
            time_field = ", completed_at = NOW()"
        elif status == 'cancelled':
            time_field = ", cancelled_at = NOW()"

        query = f"""
            UPDATE command_queue
            SET status = $1, error_message = $2, updated_at = NOW(){time_field}
            WHERE command_id = $3;
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, status, error_message, command_id)
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Error updating command {command_id} status: {e}")
            return False

    async def get_queued_commands(self, game_id: str, target: Optional[str] = None) -> list:
        """Fetch pending/queued commands for a game, optionally filtered by target."""
        await self._ensure_pool()

        if target:
            query = """
                SELECT command_id, game_id, command_type, target, priority,
                       conflict_group, cooldown_until, payload, status,
                       requires_manager_confirmation, created_at
                FROM command_queue
                WHERE game_id = $1 AND target = $2 AND status IN ('queued', 'pending_approval', 'approved')
                ORDER BY priority ASC, created_at ASC;
            """
            params = [game_id, target]
        else:
            query = """
                SELECT command_id, game_id, command_type, target, priority,
                       conflict_group, cooldown_until, payload, status,
                       requires_manager_confirmation, created_at
                FROM command_queue
                WHERE game_id = $1 AND status IN ('queued', 'pending_approval', 'approved')
                ORDER BY priority ASC, created_at ASC;
            """
            params = [game_id]

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching queued commands: {e}")
            return []

    async def supersede_conflicting_commands(self, game_id: str, conflict_group: str,
                                              exclude_command_id: str) -> int:
        """Mark all active commands in a conflict group as superseded, except the given one."""
        await self._ensure_pool()

        query = """
            UPDATE command_queue
            SET status = 'superseded', cancelled_at = NOW(), cancel_reason = 'superseded_by_newer',
                updated_at = NOW()
            WHERE game_id = $1 AND conflict_group = $2 AND command_id != $3
              AND status IN ('queued', 'pending_approval', 'approved', 'started');
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, game_id, conflict_group, exclude_command_id)
                count = int(result.split()[-1]) if result else 0
                return count
        except Exception as e:
            logger.error(f"Error superseding commands in group {conflict_group}: {e}")
            return 0

    async def approve_command(self, command_id: str, confirmed_by: str = 'manager') -> bool:
        """Approve a pending command."""
        await self._ensure_pool()

        query = """
            UPDATE command_queue
            SET status = 'approved', manager_confirmed_at = NOW(),
                manager_confirmed_by = $1, updated_at = NOW()
            WHERE command_id = $2 AND status = 'pending_approval';
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, confirmed_by, command_id)
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Error approving command {command_id}: {e}")
            return False

    async def cancel_command(self, command_id: str, cancelled_by: str = 'manager',
                              reason: str = 'manual_cancel') -> bool:
        """Cancel a queued or in-progress command."""
        await self._ensure_pool()

        query = """
            UPDATE command_queue
            SET status = 'cancelled', cancelled_at = NOW(), cancelled_by = $1,
                cancel_reason = $2, updated_at = NOW()
            WHERE command_id = $3 AND status IN ('queued', 'pending_approval', 'approved', 'started');
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, cancelled_by, reason, command_id)
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Error cancelling command {command_id}: {e}")
            return False

    # =========================================================================
    # Game Queries
    # =========================================================================

    async def get_game(self, game_id: str) -> Optional[dict]:
        """Fetch game details including team info."""
        await self._ensure_pool()

        query = """
            SELECT g.id, g.venue_id, g.status, g.started_at,
                   g.home_team_id, g.away_team_id,
                   ht.name as home_team_name, ht.short_name as home_short,
                   ht.primary_color as home_color, ht.logo_path as home_logo,
                   at.name as away_team_name, at.short_name as away_short,
                   at.primary_color as away_color, at.logo_path as away_logo
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.id
            JOIN teams at ON g.away_team_id = at.id
            WHERE g.id = $1;
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, game_id)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching game {game_id}: {e}")
            return None

    # =========================================================================
    # Roster Upload Support
    # =========================================================================

    async def bulk_upsert_players(self, team_id: str, players: list) -> int:
        """
        Upsert multiple players for a team from a roster upload.
        Each player dict should have: name, jersey_number, position, bat_hand, throw_hand.
        Returns count of upserted players.
        """
        await self._ensure_pool()

        query = """
            INSERT INTO players (id, team_id, name, jersey_number, position, bat_hand, throw_hand)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                jersey_number = EXCLUDED.jersey_number,
                position = EXCLUDED.position,
                bat_hand = EXCLUDED.bat_hand,
                throw_hand = EXCLUDED.throw_hand,
                updated_at = NOW();
        """
        count = 0
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for p in players:
                        pid = f"player_{team_id.replace('team_', '')}_{p['jersey_number']}"
                        await conn.execute(
                            query, pid, team_id, p['name'], str(p['jersey_number']),
                            p.get('position', ''), p.get('bat_hand', 'R'), p.get('throw_hand', 'R')
                        )
                        count += 1
            return count
        except Exception as e:
            logger.error(f"Error bulk upserting players for team {team_id}: {e}")
            return 0

    async def save_roster_upload(self, team_id: str, file_name: str, player_count: int,
                                  status: str = 'processed', error_message: Optional[str] = None) -> Optional[int]:
        """Record a roster upload event."""
        await self._ensure_pool()

        query = """
            INSERT INTO roster_uploads (team_id, file_name, player_count, status, error_message)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id;
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, team_id, file_name, player_count, status, error_message)
                return row['id'] if row else None
        except Exception as e:
            logger.error(f"Error saving roster upload record: {e}")
            return None

    async def get_active_players_from_events(self, game_id: str) -> dict:
        """Find the active batter and pitcher by scanning historical events."""
        await self._ensure_pool()
        query_batter = """
            SELECT payload->>'batterId' as batter_id
            FROM game_events
            WHERE game_id = $1 AND event_type = 'pitch_result' AND payload->>'batterId' IS NOT NULL
            ORDER BY occurred_at DESC, sequence DESC
            LIMIT 1;
        """
        query_pitcher = """
            SELECT payload->>'pitcherId' as pitcher_id
            FROM game_events
            WHERE game_id = $1 AND event_type = 'pitch_result' AND payload->>'pitcherId' IS NOT NULL
            ORDER BY occurred_at DESC, sequence DESC
            LIMIT 1;
        """
        res = {"batter_id": "", "pitcher_id": ""}
        try:
            async with self.pool.acquire() as conn:
                row_b = await conn.fetchrow(query_batter, game_id)
                if row_b:
                    res["batter_id"] = row_b["batter_id"]
                row_p = await conn.fetchrow(query_pitcher, game_id)
                if row_p:
                    res["pitcher_id"] = row_p["pitcher_id"]
        except Exception as e:
            logger.error(f"Error fetching active players from events: {e}")
        return res

