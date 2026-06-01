import logging
import os
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

    async def get_active_lineup(self, game_id: str) -> list:
        """
        Retrieves the active lineup (players currently on the field/batting lineup)
        for a specific game.
        """
        if not self.pool:
            await self.connect()

        query = """
            SELECT p.id, p.jersey_number, p.name, l.position, t.id as team_id
            FROM lineup_entries l
            JOIN players p ON l.player_id = p.id
            JOIN teams t ON l.team_id = t.id
            WHERE l.game_id = $1 AND l.is_active = TRUE;
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
        if not self.pool:
            await self.connect()

        query = """
            SELECT p.id, p.jersey_number, p.name, p.team_id, p.walkup_track_id
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
