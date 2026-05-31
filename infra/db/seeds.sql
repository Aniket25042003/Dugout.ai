-- Seed data for Dugout.ai Phase 1 Simulation.
-- Matches game_id, team_ids, venue_id, and player_ids in test-fixtures and frontend config.

-- 1. Insert Venue
INSERT INTO venues (id, name, location) 
VALUES ('venue_stadium_1', 'Ashland Stadium', 'Ashland, OR')
ON CONFLICT (id) DO NOTHING;

-- 2. Insert Teams
INSERT INTO teams (id, name, short_name, primary_color, secondary_color) 
VALUES 
('team_ashland', 'Ashland A''s', 'ASH', '#10b981', '#ffffff'),
('team_opponent', 'Opponent Giants', 'OPP', '#ef4444', '#000000')
ON CONFLICT (id) DO NOTHING;

-- 3. Insert Players
INSERT INTO players (id, team_id, name, jersey_number, position) 
VALUES 
('player_ashland_17', 'team_ashland', 'Ashland Batter', '17', 'Outfield'),
('player_opponent_22', 'team_opponent', 'Opponent Pitcher', '22', 'Pitcher'),
('player_ashland_12', 'team_ashland', 'Ashland Second Baseman', '12', 'Infield'),
('player_opponent_8', 'team_opponent', 'Opponent Catcher', '8', 'Catcher')
ON CONFLICT (id) DO NOTHING;

-- 4. Insert Game
INSERT INTO games (id, venue_id, home_team_id, away_team_id, status, started_at) 
VALUES ('game_2026_ashland_vs_opponent', 'venue_stadium_1', 'team_ashland', 'team_opponent', 'active', NOW())
ON CONFLICT (id) DO NOTHING;
