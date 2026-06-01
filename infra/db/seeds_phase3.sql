-- Phase 3 Seed Data for Dugout.ai
-- Full 9-player rosters for both teams, stats, lineups, media assets, and graphics templates.
-- Run AFTER seeds.sql and migration 000002.

-- ============================================================================
-- 1. Update existing players with new columns
-- ============================================================================
UPDATE players SET headshot_path = 'media/images/headshots/player_ashland_17.png', bat_hand = 'R', throw_hand = 'R', height_inches = 72, weight_lbs = 185 WHERE id = 'player_ashland_17';
UPDATE players SET headshot_path = 'media/images/headshots/player_opponent_22.png', bat_hand = 'R', throw_hand = 'R', height_inches = 75, weight_lbs = 210 WHERE id = 'player_opponent_22';
UPDATE players SET headshot_path = 'media/images/headshots/player_ashland_12.png', bat_hand = 'L', throw_hand = 'R', height_inches = 70, weight_lbs = 175 WHERE id = 'player_ashland_12';
UPDATE players SET headshot_path = 'media/images/headshots/player_opponent_8.png', bat_hand = 'R', throw_hand = 'R', height_inches = 71, weight_lbs = 195 WHERE id = 'player_opponent_8';

-- Update names to be more realistic
UPDATE players SET name = 'Marcus Rivera', position = 'CF', commentary_notes = 'Speed demon, leadoff hitter. Known for stealing bases.' WHERE id = 'player_ashland_17';
UPDATE players SET name = 'Jake Thompson', position = 'P', commentary_notes = 'Right-handed starter. Relies on a nasty curveball.' WHERE id = 'player_opponent_22';
UPDATE players SET name = 'Tyler Chen', position = '2B', commentary_notes = 'Contact hitter, rarely strikes out.' WHERE id = 'player_ashland_12';
UPDATE players SET name = 'Diego Santos', position = 'C', commentary_notes = 'Veteran catcher, strong arm behind the plate.' WHERE id = 'player_opponent_8';

-- ============================================================================
-- 2. Insert remaining Ashland A's players (5 more to make 9 total)
-- ============================================================================
INSERT INTO players (id, team_id, name, jersey_number, position, headshot_path, bat_hand, throw_hand, height_inches, weight_lbs, pronunciation, commentary_notes)
VALUES
  ('player_ashland_1', 'team_ashland', 'Alex Johnson', '1', 'SS', 'media/images/headshots/player_ashland_1.png', 'R', 'R', 71, 180, NULL, 'Leadoff candidate. Quick hands and great range at short.'),
  ('player_ashland_5', 'team_ashland', 'Brandon Lee', '5', 'LF', 'media/images/headshots/player_ashland_5.png', 'L', 'L', 73, 195, NULL, 'Power bat from the left side. Dangerous in the clutch.'),
  ('player_ashland_8', 'team_ashland', 'Chris Nakamura', '8', 'C', 'media/images/headshots/player_ashland_8.png', 'R', 'R', 70, 200, 'nah-kah-MOO-rah', 'Calls a great game. Blocks everything in the dirt.'),
  ('player_ashland_21', 'team_ashland', 'Derek Flores', '21', 'P', 'media/images/headshots/player_ashland_21.png', 'L', 'L', 74, 190, NULL, 'Left-handed ace. Fastball touches 92.'),
  ('player_ashland_25', 'team_ashland', 'Ethan Williams', '25', '1B', 'media/images/headshots/player_ashland_25.png', 'L', 'R', 76, 220, NULL, 'Big first baseman. Home run threat every at-bat.'),
  ('player_ashland_30', 'team_ashland', 'Felix Martinez', '30', '3B', 'media/images/headshots/player_ashland_30.png', 'R', 'R', 72, 195, 'mar-TEE-nez', 'Hot corner specialist. Slick with the glove.'),
  ('player_ashland_44', 'team_ashland', 'Greg Park', '44', 'RF', 'media/images/headshots/player_ashland_44.png', 'R', 'R', 74, 205, NULL, 'Strong arm in right field. Can hit for average and power.')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  jersey_number = EXCLUDED.jersey_number,
  position = EXCLUDED.position,
  headshot_path = EXCLUDED.headshot_path,
  bat_hand = EXCLUDED.bat_hand,
  throw_hand = EXCLUDED.throw_hand,
  height_inches = EXCLUDED.height_inches,
  weight_lbs = EXCLUDED.weight_lbs,
  pronunciation = EXCLUDED.pronunciation,
  commentary_notes = EXCLUDED.commentary_notes;

-- ============================================================================
-- 3. Insert remaining Opponent Giants players (5 more to make 9 total)
-- ============================================================================
INSERT INTO players (id, team_id, name, jersey_number, position, headshot_path, bat_hand, throw_hand, height_inches, weight_lbs, pronunciation, commentary_notes)
VALUES
  ('player_opponent_2', 'team_opponent', 'Ryan Mitchell', '2', 'SS', 'media/images/headshots/player_opponent_2.png', 'R', 'R', 72, 185, NULL, 'Athletic shortstop. Makes the highlight reel regularly.'),
  ('player_opponent_7', 'team_opponent', 'Carlos Ramirez', '7', 'LF', 'media/images/headshots/player_opponent_7.png', 'L', 'L', 71, 190, 'rah-MEER-ez', 'Gap-to-gap hitter. Can beat you with the bat or the legs.'),
  ('player_opponent_11', 'team_opponent', 'Noah Patel', '11', 'CF', 'media/images/headshots/player_opponent_11.png', 'R', 'R', 73, 180, 'puh-TEL', 'Covers a ton of ground in center. Excellent eye at the plate.'),
  ('player_opponent_15', 'team_opponent', 'Sam O''Brien', '15', '1B', 'media/images/headshots/player_opponent_15.png', 'L', 'R', 76, 225, NULL, 'Power-hitting first baseman. Team RBI leader.'),
  ('player_opponent_19', 'team_opponent', 'Trey Washington', '19', '3B', 'media/images/headshots/player_opponent_19.png', 'R', 'R', 73, 200, NULL, 'Reliable third baseman. Consistent at the plate.'),
  ('player_opponent_27', 'team_opponent', 'Vincent Kim', '27', '2B', 'media/images/headshots/player_opponent_27.png', 'L', 'R', 69, 170, NULL, 'Scrappy second baseman. Gets on base any way he can.'),
  ('player_opponent_33', 'team_opponent', 'Will Jackson', '33', 'RF', 'media/images/headshots/player_opponent_33.png', 'R', 'R', 75, 210, NULL, 'Power and speed combo. Five-tool outfielder.')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  jersey_number = EXCLUDED.jersey_number,
  position = EXCLUDED.position,
  headshot_path = EXCLUDED.headshot_path,
  bat_hand = EXCLUDED.bat_hand,
  throw_hand = EXCLUDED.throw_hand,
  height_inches = EXCLUDED.height_inches,
  weight_lbs = EXCLUDED.weight_lbs,
  pronunciation = EXCLUDED.pronunciation,
  commentary_notes = EXCLUDED.commentary_notes;

-- ============================================================================
-- 4. Update team branding
-- ============================================================================
UPDATE teams SET logo_path = 'media/images/team-logos/team_ashland.png', banner_path = NULL, mascot_name = 'Ace' WHERE id = 'team_ashland';
UPDATE teams SET logo_path = 'media/images/team-logos/team_opponent.png', banner_path = NULL, mascot_name = 'Giant' WHERE id = 'team_opponent';

-- ============================================================================
-- 5. Media assets for walk-up music
-- ============================================================================
INSERT INTO media_assets (id, name, type, file_path, player_id, team_id, duration_ms, metadata)
VALUES
  -- Ashland A's walk-up tracks
  ('asset_walkup_ashland_1',  'Alex Johnson Walk-Up',    'audio_walkup', 'media/audio/walkup/player_ashland_1.wav',  'player_ashland_1',  'team_ashland', 8000, '{"genre": "rock"}'),
  ('asset_walkup_ashland_5',  'Brandon Lee Walk-Up',     'audio_walkup', 'media/audio/walkup/player_ashland_5.wav',  'player_ashland_5',  'team_ashland', 8000, '{"genre": "hip-hop"}'),
  ('asset_walkup_ashland_8',  'Chris Nakamura Walk-Up',  'audio_walkup', 'media/audio/walkup/player_ashland_8.wav',  'player_ashland_8',  'team_ashland', 8000, '{"genre": "j-pop"}'),
  ('asset_walkup_ashland_12', 'Tyler Chen Walk-Up',      'audio_walkup', 'media/audio/walkup/player_ashland_12.wav', 'player_ashland_12', 'team_ashland', 8000, '{"genre": "electronic"}'),
  ('asset_walkup_ashland_17', 'Marcus Rivera Walk-Up',   'audio_walkup', 'media/audio/walkup/player_ashland_17.wav', 'player_ashland_17', 'team_ashland', 8000, '{"genre": "latin"}'),
  ('asset_walkup_ashland_21', 'Derek Flores Walk-Up',    'audio_walkup', 'media/audio/walkup/player_ashland_21.wav', 'player_ashland_21', 'team_ashland', 8000, '{"genre": "country"}'),
  ('asset_walkup_ashland_25', 'Ethan Williams Walk-Up',  'audio_walkup', 'media/audio/walkup/player_ashland_25.wav', 'player_ashland_25', 'team_ashland', 8000, '{"genre": "rock"}'),
  ('asset_walkup_ashland_30', 'Felix Martinez Walk-Up',  'audio_walkup', 'media/audio/walkup/player_ashland_30.wav', 'player_ashland_30', 'team_ashland', 8000, '{"genre": "reggaeton"}'),
  ('asset_walkup_ashland_44', 'Greg Park Walk-Up',       'audio_walkup', 'media/audio/walkup/player_ashland_44.wav', 'player_ashland_44', 'team_ashland', 8000, '{"genre": "pop"}'),
  -- Opponent Giants walk-up tracks
  ('asset_walkup_opponent_2',  'Ryan Mitchell Walk-Up',   'audio_walkup', 'media/audio/walkup/player_opponent_2.wav',  'player_opponent_2',  'team_opponent', 8000, '{"genre": "rock"}'),
  ('asset_walkup_opponent_7',  'Carlos Ramirez Walk-Up',  'audio_walkup', 'media/audio/walkup/player_opponent_7.wav',  'player_opponent_7',  'team_opponent', 8000, '{"genre": "latin"}'),
  ('asset_walkup_opponent_8',  'Diego Santos Walk-Up',    'audio_walkup', 'media/audio/walkup/player_opponent_8.wav',  'player_opponent_8',  'team_opponent', 8000, '{"genre": "samba"}'),
  ('asset_walkup_opponent_11', 'Noah Patel Walk-Up',      'audio_walkup', 'media/audio/walkup/player_opponent_11.wav', 'player_opponent_11', 'team_opponent', 8000, '{"genre": "electronic"}'),
  ('asset_walkup_opponent_15', 'Sam O Brien Walk-Up',     'audio_walkup', 'media/audio/walkup/player_opponent_15.wav', 'player_opponent_15', 'team_opponent', 8000, '{"genre": "country"}'),
  ('asset_walkup_opponent_19', 'Trey Washington Walk-Up', 'audio_walkup', 'media/audio/walkup/player_opponent_19.wav', 'player_opponent_19', 'team_opponent', 8000, '{"genre": "hip-hop"}'),
  ('asset_walkup_opponent_22', 'Jake Thompson Walk-Up',   'audio_walkup', 'media/audio/walkup/player_opponent_22.wav', 'player_opponent_22', 'team_opponent', 8000, '{"genre": "rock"}'),
  ('asset_walkup_opponent_27', 'Vincent Kim Walk-Up',     'audio_walkup', 'media/audio/walkup/player_opponent_27.wav', 'player_opponent_27', 'team_opponent', 8000, '{"genre": "k-pop"}'),
  ('asset_walkup_opponent_33', 'Will Jackson Walk-Up',    'audio_walkup', 'media/audio/walkup/player_opponent_33.wav', 'player_opponent_33', 'team_opponent', 8000, '{"genre": "r&b"}'),
  -- Fallback track
  ('asset_walkup_fallback', 'Default Walk-Up Track', 'audio_walkup', 'media/audio/fallback/default_walkup.wav', NULL, NULL, 10000, '{"genre": "generic"}'),
  -- Sound effects
  ('asset_sfx_crowd',  'Crowd Cheer',  'audio_effect', 'media/audio/effects/crowd_cheer.wav',  NULL, NULL, 3000, '{}'),
  ('asset_sfx_organ',  'Organ Riff',   'audio_effect', 'media/audio/effects/organ_riff.wav',   NULL, NULL, 2000, '{}')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  file_path = EXCLUDED.file_path,
  player_id = EXCLUDED.player_id,
  team_id = EXCLUDED.team_id,
  duration_ms = EXCLUDED.duration_ms,
  metadata = EXCLUDED.metadata;

-- Link players to their walk-up tracks
UPDATE players SET walkup_track_id = 'asset_walkup_ashland_1'  WHERE id = 'player_ashland_1';
UPDATE players SET walkup_track_id = 'asset_walkup_ashland_5'  WHERE id = 'player_ashland_5';
UPDATE players SET walkup_track_id = 'asset_walkup_ashland_8'  WHERE id = 'player_ashland_8';
UPDATE players SET walkup_track_id = 'asset_walkup_ashland_12' WHERE id = 'player_ashland_12';
UPDATE players SET walkup_track_id = 'asset_walkup_ashland_17' WHERE id = 'player_ashland_17';
UPDATE players SET walkup_track_id = 'asset_walkup_ashland_21' WHERE id = 'player_ashland_21';
UPDATE players SET walkup_track_id = 'asset_walkup_ashland_25' WHERE id = 'player_ashland_25';
UPDATE players SET walkup_track_id = 'asset_walkup_ashland_30' WHERE id = 'player_ashland_30';
UPDATE players SET walkup_track_id = 'asset_walkup_ashland_44' WHERE id = 'player_ashland_44';
UPDATE players SET walkup_track_id = 'asset_walkup_opponent_2'  WHERE id = 'player_opponent_2';
UPDATE players SET walkup_track_id = 'asset_walkup_opponent_7'  WHERE id = 'player_opponent_7';
UPDATE players SET walkup_track_id = 'asset_walkup_opponent_8'  WHERE id = 'player_opponent_8';
UPDATE players SET walkup_track_id = 'asset_walkup_opponent_11' WHERE id = 'player_opponent_11';
UPDATE players SET walkup_track_id = 'asset_walkup_opponent_15' WHERE id = 'player_opponent_15';
UPDATE players SET walkup_track_id = 'asset_walkup_opponent_19' WHERE id = 'player_opponent_19';
UPDATE players SET walkup_track_id = 'asset_walkup_opponent_22' WHERE id = 'player_opponent_22';
UPDATE players SET walkup_track_id = 'asset_walkup_opponent_27' WHERE id = 'player_opponent_27';
UPDATE players SET walkup_track_id = 'asset_walkup_opponent_33' WHERE id = 'player_opponent_33';

-- ============================================================================
-- 6. Lineup entries (batting order) for the game
-- ============================================================================
-- Ashland A's batting order
INSERT INTO lineup_entries (game_id, team_id, player_id, batting_order, position, is_active)
VALUES
  ('game_2026_ashland_vs_opponent', 'team_ashland', 'player_ashland_1',  1, 'SS', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_ashland', 'player_ashland_17', 2, 'CF', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_ashland', 'player_ashland_5',  3, 'LF', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_ashland', 'player_ashland_25', 4, '1B', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_ashland', 'player_ashland_30', 5, '3B', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_ashland', 'player_ashland_44', 6, 'RF', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_ashland', 'player_ashland_12', 7, '2B', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_ashland', 'player_ashland_8',  8, 'C',  TRUE),
  ('game_2026_ashland_vs_opponent', 'team_ashland', 'player_ashland_21', 9, 'P',  TRUE)
ON CONFLICT (game_id, team_id, player_id) DO UPDATE SET
  batting_order = EXCLUDED.batting_order,
  position = EXCLUDED.position,
  is_active = EXCLUDED.is_active;

-- Opponent Giants batting order
INSERT INTO lineup_entries (game_id, team_id, player_id, batting_order, position, is_active)
VALUES
  ('game_2026_ashland_vs_opponent', 'team_opponent', 'player_opponent_11', 1, 'CF', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_opponent', 'player_opponent_2',  2, 'SS', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_opponent', 'player_opponent_7',  3, 'LF', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_opponent', 'player_opponent_15', 4, '1B', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_opponent', 'player_opponent_33', 5, 'RF', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_opponent', 'player_opponent_19', 6, '3B', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_opponent', 'player_opponent_27', 7, '2B', TRUE),
  ('game_2026_ashland_vs_opponent', 'team_opponent', 'player_opponent_8',  8, 'C',  TRUE),
  ('game_2026_ashland_vs_opponent', 'team_opponent', 'player_opponent_22', 9, 'P',  TRUE)
ON CONFLICT (game_id, team_id, player_id) DO UPDATE SET
  batting_order = EXCLUDED.batting_order,
  position = EXCLUDED.position,
  is_active = EXCLUDED.is_active;

-- ============================================================================
-- 7. Player statistics (season averages for commentary context)
-- ============================================================================
INSERT INTO player_stats (player_id, season, stat_type, at_bats, hits, doubles, triples, home_runs, rbis, walks, strikeouts, batting_avg, on_base_pct, slugging_pct, ops, stolen_bases, hit_streak, last_5_avg)
VALUES
  -- Ashland A's batters
  ('player_ashland_1',  '2026', 'season', 185, 56, 10, 3, 4,  22, 28, 32, 0.303, 0.385, 0.438, 0.823, 15, 4, 0.350),
  ('player_ashland_17', '2026', 'season', 210, 68, 12, 5, 8,  35, 30, 38, 0.324, 0.401, 0.524, 0.925, 22, 7, 0.400),
  ('player_ashland_5',  '2026', 'season', 195, 58, 14, 1, 12, 42, 35, 45, 0.297, 0.388, 0.533, 0.921, 3,  2, 0.280),
  ('player_ashland_25', '2026', 'season', 200, 54, 8,  0, 18, 52, 40, 55, 0.270, 0.370, 0.530, 0.900, 1,  0, 0.220),
  ('player_ashland_30', '2026', 'season', 190, 52, 11, 2, 6,  30, 25, 35, 0.274, 0.345, 0.421, 0.766, 5,  3, 0.310),
  ('player_ashland_44', '2026', 'season', 180, 50, 9,  3, 7,  28, 22, 40, 0.278, 0.348, 0.456, 0.804, 8,  1, 0.260),
  ('player_ashland_12', '2026', 'season', 175, 53, 8,  1, 2,  18, 30, 20, 0.303, 0.393, 0.383, 0.776, 10, 5, 0.340),
  ('player_ashland_8',  '2026', 'season', 165, 42, 7,  0, 5,  25, 18, 30, 0.255, 0.320, 0.394, 0.714, 2,  0, 0.200),
  -- Opponent Giants batters
  ('player_opponent_11', '2026', 'season', 200, 62, 10, 4, 6,  28, 32, 35, 0.310, 0.390, 0.480, 0.870, 18, 6, 0.380),
  ('player_opponent_2',  '2026', 'season', 190, 55, 12, 2, 5,  24, 25, 38, 0.289, 0.360, 0.432, 0.792, 12, 3, 0.300),
  ('player_opponent_7',  '2026', 'season', 185, 58, 14, 1, 10, 38, 30, 42, 0.314, 0.395, 0.530, 0.925, 6,  4, 0.350),
  ('player_opponent_15', '2026', 'season', 205, 55, 10, 0, 20, 55, 38, 60, 0.268, 0.362, 0.541, 0.903, 0,  1, 0.240),
  ('player_opponent_33', '2026', 'season', 195, 56, 11, 3, 9,  32, 28, 45, 0.287, 0.358, 0.482, 0.840, 10, 2, 0.300),
  ('player_opponent_19', '2026', 'season', 180, 48, 9,  1, 4,  22, 20, 32, 0.267, 0.335, 0.389, 0.724, 3,  0, 0.250),
  ('player_opponent_27', '2026', 'season', 170, 50, 7,  2, 1,  15, 28, 22, 0.294, 0.385, 0.371, 0.756, 8,  3, 0.320),
  ('player_opponent_8',  '2026', 'season', 160, 40, 6,  0, 6,  28, 15, 35, 0.250, 0.310, 0.400, 0.710, 1,  0, 0.220)
ON CONFLICT (player_id, game_id, stat_type, season) DO UPDATE SET
  at_bats = EXCLUDED.at_bats,
  hits = EXCLUDED.hits,
  doubles = EXCLUDED.doubles,
  triples = EXCLUDED.triples,
  home_runs = EXCLUDED.home_runs,
  rbis = EXCLUDED.rbis,
  walks = EXCLUDED.walks,
  strikeouts = EXCLUDED.strikeouts,
  batting_avg = EXCLUDED.batting_avg,
  on_base_pct = EXCLUDED.on_base_pct,
  slugging_pct = EXCLUDED.slugging_pct,
  ops = EXCLUDED.ops,
  stolen_bases = EXCLUDED.stolen_bases,
  hit_streak = EXCLUDED.hit_streak,
  last_5_avg = EXCLUDED.last_5_avg;

-- Pitching stats
INSERT INTO player_stats (player_id, season, stat_type, innings_pitched, earned_runs, era, pitch_strikeouts, pitch_walks, whip, wins, losses, saves, at_bats, hits, batting_avg)
VALUES
  ('player_ashland_21', '2026', 'season', 85.1, 28, 2.95, 92, 25, 1.08, 7, 3, 0, 30, 5, 0.167),
  ('player_opponent_22', '2026', 'season', 90.0, 32, 3.20, 88, 30, 1.18, 6, 4, 0, 35, 6, 0.171)
ON CONFLICT (player_id, game_id, stat_type, season) DO UPDATE SET
  innings_pitched = EXCLUDED.innings_pitched,
  earned_runs = EXCLUDED.earned_runs,
  era = EXCLUDED.era,
  pitch_strikeouts = EXCLUDED.pitch_strikeouts,
  pitch_walks = EXCLUDED.pitch_walks,
  whip = EXCLUDED.whip,
  wins = EXCLUDED.wins,
  losses = EXCLUDED.losses,
  saves = EXCLUDED.saves;

-- ============================================================================
-- 8. Graphics templates
-- ============================================================================
INSERT INTO graphics_templates (id, name, template_type, css_class, display_duration_ms, auto_dismiss, layout_config)
VALUES
  ('tpl_batter_intro', 'Batter Introduction', 'batter_intro', 'overlay-batter-intro', 8000, TRUE, '{"position": "center", "animation": "slide-up"}'),
  ('tpl_pitcher_intro', 'Pitcher Introduction', 'pitcher_intro', 'overlay-pitcher-intro', 6000, TRUE, '{"position": "center", "animation": "slide-up"}'),
  ('tpl_count_display', 'Count Display', 'count_display', 'overlay-count', 0, FALSE, '{"position": "top-right", "persistent": true}'),
  ('tpl_score_bug', 'Score Bug', 'score_bug', 'overlay-score-bug', 0, FALSE, '{"position": "top-left", "persistent": true}'),
  ('tpl_lower_third', 'Lower Third', 'lower_third', 'overlay-lower-third', 5000, TRUE, '{"position": "bottom", "animation": "slide-right"}'),
  ('tpl_speed_display', 'Pitch Speed Display', 'speed_display', 'overlay-speed', 3000, TRUE, '{"position": "center-right", "animation": "pop"}'),
  ('tpl_sponsor', 'Sponsor Interstitial', 'sponsor', 'overlay-sponsor', 4000, TRUE, '{"position": "bottom-right", "animation": "fade"}')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  template_type = EXCLUDED.template_type,
  css_class = EXCLUDED.css_class,
  display_duration_ms = EXCLUDED.display_duration_ms,
  auto_dismiss = EXCLUDED.auto_dismiss,
  layout_config = EXCLUDED.layout_config;
