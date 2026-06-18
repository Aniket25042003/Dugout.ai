/**
 * @file apps/dashboard/src/components/PlayerStats.tsx
 * @layer Frontend — Matchup Stats UI
 * @description Fetches and displays active batter and pitcher profile/stat context.
 * @dependencies getPlayer, getPlayerStats APIs
 */

import React, { useState, useEffect } from 'react';
import { getPlayerStats, getPlayer } from '../api/dashboardApi';

/** Props for the active matchup statistics panel. */
type Props = {
  activeBatterId: string | null;
  activePitcherId: string | null;
};

/**
 * Renders the active batter-versus-pitcher matchup statistics.
 *
 * @param props - Active batter and pitcher IDs from game state
 * @returns React matchup statistics card
 */
export const PlayerStats: React.FC<Props> = ({
  activeBatterId,
  activePitcherId,
}) => {
  const [batterInfo, setBatterInfo] = useState<any>(null);
  const [batterStats, setBatterStats] = useState<any>(null);
  const [pitcherInfo, setPitcherInfo] = useState<any>(null);
  const [pitcherStats, setPitcherStats] = useState<any>(null);

  useEffect(() => {
    if (!activeBatterId) {
      setBatterInfo(null);
      setBatterStats(null);
      return;
    }

    const fetchBatter = async () => {
      try {
        const info = await getPlayer(activeBatterId);
        setBatterInfo(info);
        const stats = await getPlayerStats(activeBatterId);
        setBatterStats(stats);
      } catch (err) {
        console.error("Failed to load batter stats:", err);
      }
    };

    fetchBatter();
  }, [activeBatterId]);

  useEffect(() => {
    if (!activePitcherId) {
      setPitcherInfo(null);
      setPitcherStats(null);
      return;
    }

    const fetchPitcher = async () => {
      try {
        const info = await getPlayer(activePitcherId);
        setPitcherInfo(info);
        const stats = await getPlayerStats(activePitcherId);
        setPitcherStats(stats);
      } catch (err) {
        console.error("Failed to load pitcher stats:", err);
      }
    };

    fetchPitcher();
  }, [activePitcherId]);

  return (
    <div className="card player-stats-card">
      <h3>Matchup Statistics</h3>
      
      <div className="matchup-grid">
        {/* Active Batter Column */}
        <div className="matchup-col batter-col">
          <h4 className="role-title">AT BAT</h4>
          {batterInfo ? (
            <div className="player-stats-detail">
              <div className="name-row">
                <span className="jersey">#{batterInfo.jersey_number}</span>
                <span className="name">{batterInfo.name}</span>
              </div>
              <div className="meta">{batterInfo.position} · Bats {batterInfo.bat_hand || 'R'}</div>
              
              {batterStats ? (
                <div className="stats-box-vertical">
                  <div className="stat-line">
                    <span className="lbl">Batting Avg</span>
                    <span className="val">{batterStats.batting_avg || '.000'}</span>
                  </div>
                  <div className="stat-line">
                    <span className="lbl">Home Runs</span>
                    <span className="val">{batterStats.home_runs || 0}</span>
                  </div>
                  <div className="stat-line">
                    <span className="lbl">RBIs</span>
                    <span className="val">{batterStats.rbis || 0}</span>
                  </div>
                  <div className="stat-line">
                    <span className="lbl">OPS</span>
                    <span className="val">{batterStats.ops || '.000'}</span>
                  </div>
                  {batterStats.hit_streak > 0 && (
                    <div className="stat-streak">
                      🔥 {batterStats.hit_streak} Game Hit Streak!
                    </div>
                  )}
                </div>
              ) : (
                <div className="empty-stats">No stats recorded</div>
              )}
            </div>
          ) : (
            <div className="empty-player">No active batter</div>
          )}
        </div>

        {/* Divider */}
        <div className="matchup-vs">VS</div>

        {/* Active Pitcher Column */}
        <div className="matchup-col pitcher-col">
          <h4 className="role-title">ON THE MOUND</h4>
          {pitcherInfo ? (
            <div className="player-stats-detail">
              <div className="name-row">
                <span className="jersey">#{pitcherInfo.jersey_number}</span>
                <span className="name">{pitcherInfo.name}</span>
              </div>
              <div className="meta">Pitcher · Throws {pitcherInfo.throw_hand || 'R'}</div>
              
              {pitcherStats ? (
                <div className="stats-box-vertical">
                  <div className="stat-line">
                    <span className="lbl">ERA</span>
                    <span className="val">{pitcherStats.era || '0.00'}</span>
                  </div>
                  <div className="stat-line">
                    <span className="lbl">WHIP</span>
                    <span className="val">{pitcherStats.whip || '0.00'}</span>
                  </div>
                  <div className="stat-line">
                    <span className="lbl">Record</span>
                    <span className="val">{pitcherStats.wins || 0}W - {pitcherStats.losses || 0}L</span>
                  </div>
                  <div className="stat-line">
                    <span className="lbl">Strikeouts</span>
                    <span className="val">{pitcherStats.pitch_strikeouts || 0}</span>
                  </div>
                </div>
              ) : (
                <div className="empty-stats">No stats recorded</div>
              )}
            </div>
          ) : (
            <div className="empty-player">No active pitcher</div>
          )}
        </div>
      </div>
    </div>
  );
};
