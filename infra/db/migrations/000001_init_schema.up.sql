-- Migration: Up (000001_init_schema)

CREATE TABLE IF NOT EXISTS venues (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS teams (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(20),
    primary_color VARCHAR(10),   -- Hex color codes e.g. #FF0000
    secondary_color VARCHAR(10),
    logo_url VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS media_assets (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,    -- 'audio_walkup', 'graphic_card', 'video_loop', etc.
    file_path VARCHAR(255) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS players (
    id VARCHAR(50) PRIMARY KEY,
    team_id VARCHAR(50) NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    jersey_number VARCHAR(10) NOT NULL,
    position VARCHAR(50),
    walkup_track_id VARCHAR(50) REFERENCES media_assets(id) ON DELETE SET NULL,
    pronunciation VARCHAR(255),
    commentary_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS games (
    id VARCHAR(100) PRIMARY KEY,
    venue_id VARCHAR(50) NOT NULL REFERENCES venues(id),
    home_team_id VARCHAR(50) NOT NULL REFERENCES teams(id),
    away_team_id VARCHAR(50) NOT NULL REFERENCES teams(id),
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled', -- 'scheduled', 'active', 'completed', 'paused'
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lineup_entries (
    game_id VARCHAR(100) NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    team_id VARCHAR(50) NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    player_id VARCHAR(50) NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    batting_order INT,   -- 1 to 9 (null for subs or pitchers not batting)
    position VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, team_id, player_id)
);

CREATE TABLE IF NOT EXISTS game_events (
    event_id VARCHAR(50) PRIMARY KEY,
    game_id VARCHAR(100) NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,          -- 'referee_app', 'manager_dashboard'
    source_device_id VARCHAR(100),
    event_type VARCHAR(50) NOT NULL,      -- 'pitch_result', 'game_state_correction', etc.
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    sequence INT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    authority VARCHAR(50) NOT NULL DEFAULT 'official', -- 'official', 'manager'
    correlation_id VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cv_observations (
    observation_id VARCHAR(50) PRIMARY KEY,
    game_id VARCHAR(100) NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    camera_id VARCHAR(50) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    observation_type VARCHAR(50) NOT NULL, -- 'jersey_number', 'player_localization', etc.
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence DOUBLE PRECISION NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_runtime VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS production_commands (
    command_id VARCHAR(50) PRIMARY KEY,
    game_id VARCHAR(100) NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    command_type VARCHAR(50) NOT NULL,     -- 'play_walkup_music', 'update_scoreboard', etc.
    target VARCHAR(50) NOT NULL,           -- 'music_adapter', 'graphics_adapter', etc.
    created_at TIMESTAMPTZ NOT NULL,
    source_event_ids VARCHAR(50)[] NOT NULL DEFAULT '{}',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    requires_manager_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'queued', -- 'queued', 'started', 'completed', 'failed', 'cancelled'
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(100) REFERENCES games(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    actor_id VARCHAR(100) NOT NULL,         -- 'system', 'manager_user_id', etc.
    entity_type VARCHAR(50),                -- 'game_event', 'cv_observation', 'production_command'
    entity_id VARCHAR(50),
    description TEXT NOT NULL,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_game_events_game_id ON game_events(game_id);
CREATE INDEX idx_game_events_sequence ON game_events(game_id, sequence);
CREATE INDEX idx_cv_observations_game_id ON cv_observations(game_id);
CREATE INDEX idx_production_commands_game_id ON production_commands(game_id);
CREATE INDEX idx_production_commands_status ON production_commands(status);
CREATE INDEX idx_audit_logs_game_id ON audit_logs(game_id);
CREATE INDEX idx_lineup_entries_game_id ON lineup_entries(game_id);
