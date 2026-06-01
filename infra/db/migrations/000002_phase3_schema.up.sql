-- Migration: Up (000002_phase3_schema)
-- Phase 3: Production Automation schema extensions

-- ============================================================================
-- Extend teams table with branding assets
-- ============================================================================
ALTER TABLE teams
  ADD COLUMN IF NOT EXISTS logo_path VARCHAR(500),
  ADD COLUMN IF NOT EXISTS banner_path VARCHAR(500),
  ADD COLUMN IF NOT EXISTS mascot_name VARCHAR(100);

-- ============================================================================
-- Extend players table with headshot and extended info
-- ============================================================================
ALTER TABLE players
  ADD COLUMN IF NOT EXISTS headshot_path VARCHAR(500),
  ADD COLUMN IF NOT EXISTS bat_hand VARCHAR(10) DEFAULT 'R',
  ADD COLUMN IF NOT EXISTS throw_hand VARCHAR(10) DEFAULT 'R',
  ADD COLUMN IF NOT EXISTS height_inches INT,
  ADD COLUMN IF NOT EXISTS weight_lbs INT;

-- ============================================================================
-- Extend media_assets with richer metadata
-- ============================================================================
ALTER TABLE media_assets
  ADD COLUMN IF NOT EXISTS player_id VARCHAR(50) REFERENCES players(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS team_id VARCHAR(50) REFERENCES teams(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS duration_ms INT,
  ADD COLUMN IF NOT EXISTS thumbnail_path VARCHAR(500),
  ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';

-- ============================================================================
-- Player statistics for commentary context
-- ============================================================================
CREATE TABLE IF NOT EXISTS player_stats (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(50) NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    game_id VARCHAR(100) REFERENCES games(id) ON DELETE SET NULL,
    season VARCHAR(10) NOT NULL DEFAULT '2026',

    -- Batting stats
    at_bats INT DEFAULT 0,
    hits INT DEFAULT 0,
    doubles INT DEFAULT 0,
    triples INT DEFAULT 0,
    home_runs INT DEFAULT 0,
    rbis INT DEFAULT 0,
    walks INT DEFAULT 0,
    strikeouts INT DEFAULT 0,
    batting_avg NUMERIC(4,3) DEFAULT 0.000,
    on_base_pct NUMERIC(4,3) DEFAULT 0.000,
    slugging_pct NUMERIC(4,3) DEFAULT 0.000,
    ops NUMERIC(4,3) DEFAULT 0.000,

    -- Pitching stats (nullable for non-pitchers)
    innings_pitched NUMERIC(5,1),
    earned_runs INT,
    era NUMERIC(5,2),
    pitch_strikeouts INT,
    pitch_walks INT,
    whip NUMERIC(4,2),
    wins INT,
    losses INT,
    saves INT,

    -- Game-specific stats
    stolen_bases INT DEFAULT 0,
    errors INT DEFAULT 0,
    
    -- Streak / recent form
    last_5_avg NUMERIC(4,3),
    hit_streak INT DEFAULT 0,

    stat_type VARCHAR(20) NOT NULL DEFAULT 'season', -- 'season', 'career', 'game'
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(player_id, game_id, stat_type, season)
);

-- ============================================================================
-- Graphics templates for scoreboard, overlays, and player cards
-- ============================================================================
CREATE TABLE IF NOT EXISTS graphics_templates (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    template_type VARCHAR(50) NOT NULL, -- 'batter_intro', 'pitcher_intro', 'count_display', 'score_bug', 'lower_third', 'speed_display', 'sponsor'
    file_path VARCHAR(500),
    css_class VARCHAR(100),
    display_duration_ms INT DEFAULT 5000,
    auto_dismiss BOOLEAN DEFAULT TRUE,
    layout_config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Commentary history for audit trail and replay
-- ============================================================================
CREATE TABLE IF NOT EXISTS commentary_history (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(100) NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'template', -- 'llm', 'template', 'manual'
    source_event_ids VARCHAR(50)[] DEFAULT '{}',
    audio_path VARCHAR(500),
    context_snapshot JSONB DEFAULT '{}'::jsonb, -- snapshot of stats/state used for generation
    llm_model VARCHAR(100),
    llm_prompt_tokens INT,
    llm_completion_tokens INT,
    generation_ms INT,
    tts_model VARCHAR(100),
    tts_duration_ms INT,
    played_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Command queue with priority, cooldowns, and conflict resolution
-- ============================================================================
CREATE TABLE IF NOT EXISTS command_queue (
    id SERIAL PRIMARY KEY,
    command_id VARCHAR(50) NOT NULL UNIQUE,
    game_id VARCHAR(100) NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    command_type VARCHAR(50) NOT NULL,
    target VARCHAR(50) NOT NULL,
    priority INT NOT NULL DEFAULT 5, -- 1=highest, 10=lowest
    conflict_group VARCHAR(100), -- commands in same group conflict with each other
    cooldown_until TIMESTAMPTZ, -- don't execute before this time
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_event_ids VARCHAR(50)[] DEFAULT '{}',
    requires_manager_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    manager_confirmed_at TIMESTAMPTZ,
    manager_confirmed_by VARCHAR(100),
    cancelled_at TIMESTAMPTZ,
    cancelled_by VARCHAR(100),
    cancel_reason TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'queued', -- 'queued', 'pending_approval', 'approved', 'started', 'completed', 'failed', 'cancelled', 'superseded'
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Roster upload tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS roster_uploads (
    id SERIAL PRIMARY KEY,
    team_id VARCHAR(50) NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    uploaded_by VARCHAR(100) NOT NULL DEFAULT 'manager',
    player_count INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'processed', -- 'processing', 'processed', 'failed'
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_player_stats_player_id ON player_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_game_id ON player_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_commentary_history_game_id ON commentary_history(game_id);
CREATE INDEX IF NOT EXISTS idx_command_queue_game_id ON command_queue(game_id);
CREATE INDEX IF NOT EXISTS idx_command_queue_status ON command_queue(status);
CREATE INDEX IF NOT EXISTS idx_command_queue_conflict ON command_queue(conflict_group, status);
CREATE INDEX IF NOT EXISTS idx_media_assets_player_id ON media_assets(player_id);
CREATE INDEX IF NOT EXISTS idx_media_assets_type ON media_assets(type);
CREATE INDEX IF NOT EXISTS idx_graphics_templates_type ON graphics_templates(template_type);
