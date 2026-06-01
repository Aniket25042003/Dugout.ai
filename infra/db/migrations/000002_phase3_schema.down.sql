-- Migration: Down (000002_phase3_schema)
-- Rollback Phase 3 schema extensions

-- Drop indexes first
DROP INDEX IF EXISTS idx_graphics_templates_type;
DROP INDEX IF EXISTS idx_media_assets_type;
DROP INDEX IF EXISTS idx_media_assets_player_id;
DROP INDEX IF EXISTS idx_command_queue_conflict;
DROP INDEX IF EXISTS idx_command_queue_status;
DROP INDEX IF EXISTS idx_command_queue_game_id;
DROP INDEX IF EXISTS idx_commentary_history_game_id;
DROP INDEX IF EXISTS idx_player_stats_game_id;
DROP INDEX IF EXISTS idx_player_stats_player_id;

-- Drop new tables
DROP TABLE IF EXISTS roster_uploads;
DROP TABLE IF EXISTS command_queue;
DROP TABLE IF EXISTS commentary_history;
DROP TABLE IF EXISTS graphics_templates;
DROP TABLE IF EXISTS player_stats;

-- Remove added columns from media_assets
ALTER TABLE media_assets
  DROP COLUMN IF EXISTS player_id,
  DROP COLUMN IF EXISTS team_id,
  DROP COLUMN IF EXISTS duration_ms,
  DROP COLUMN IF EXISTS thumbnail_path,
  DROP COLUMN IF EXISTS tags;

-- Remove added columns from players
ALTER TABLE players
  DROP COLUMN IF EXISTS headshot_path,
  DROP COLUMN IF EXISTS bat_hand,
  DROP COLUMN IF EXISTS throw_hand,
  DROP COLUMN IF EXISTS height_inches,
  DROP COLUMN IF EXISTS weight_lbs;

-- Remove added columns from teams
ALTER TABLE teams
  DROP COLUMN IF EXISTS logo_path,
  DROP COLUMN IF EXISTS banner_path,
  DROP COLUMN IF EXISTS mascot_name;
