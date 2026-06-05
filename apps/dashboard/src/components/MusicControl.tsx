import React, { useState, useEffect } from 'react';
import type { MusicState } from '../api/sseClient';
import { controlMusic } from '../api/dashboardApi';

type Props = {
  musicState: MusicState;
  gameId: string;
  nextBatters: any[];
  onPlayTrigger?: (playerId: string, assetId: string) => void;
};

export const MusicControl: React.FC<Props> = ({
  musicState,
  gameId,
  nextBatters,
  onPlayTrigger,
}) => {
  const [elapsed, setElapsed] = useState(0);

  // Local ticker for smooth progress updates
  useEffect(() => {
    setElapsed(musicState.elapsedMs);
    if (musicState.status !== 'playing') return;

    const interval = setInterval(() => {
      setElapsed((prev) => {
        if (prev >= musicState.totalMs) {
          clearInterval(interval);
          return musicState.totalMs;
        }
        return prev + 100;
      });
    }, 100);

    return () => clearInterval(interval);
  }, [musicState]);

  const progressPercent = musicState.totalMs > 0 ? (elapsed / musicState.totalMs) * 100 : 0;

  const handleStop = async () => {
    try {
      await controlMusic(gameId, 'stop');
    } catch (e) {
      console.error(e);
    }
  };

  const handleFade = async () => {
    try {
      await controlMusic(gameId, 'fade_out', null, null, 2000);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="card music-control-card">
      <h3>Audio & Walk-up Music</h3>

      {/* Now Playing Widget */}
      <div className={`now-playing-panel status-${musicState.status}`}>
        <div className="panel-header">
          <span className="live-pill">{musicState.status.toUpperCase()}</span>
          <span className="track-name">{musicState.trackName || "No active track"}</span>
        </div>
        
        {musicState.playerName && (
          <div className="player-assignment">
            Batter: <span className="highlight">{musicState.playerName}</span>
          </div>
        )}

        <div className="progress-container">
          <div className="progress-bar" style={{ width: `${progressPercent}%` }} />
          <div className="progress-time">
            {Math.floor(elapsed / 1000)}s / {Math.floor(musicState.totalMs / 1000)}s
          </div>
        </div>

        <div className="now-playing-actions">
          <button 
            className="music-btn btn-stop" 
            onClick={handleStop}
            disabled={musicState.status === 'stopped'}
          >
            ⏹ Stop
          </button>
          <button 
            className="music-btn btn-fade" 
            onClick={handleFade}
            disabled={musicState.status === 'stopped' || musicState.status === 'fading'}
          >
            🔊 Fade Out
          </button>
        </div>
      </div>

      {/* Next Up Batting Music Queue */}
      <div className="next-up-panel">
        <h4>Next Up (Walk-Up Tracks)</h4>
        <div className="next-batters-list">
          {nextBatters.length === 0 ? (
            <div className="empty-state">No upcoming batters</div>
          ) : (
            nextBatters.map((player, idx) => (
              <div key={player.id} className="next-batter-item">
                <div className="item-order">#{idx + 1}</div>
                <div className="item-details">
                  <span className="name">{player.name}</span>
                  <span className="jersey">#{player.jersey_number} · {player.position}</span>
                </div>
                <button 
                  className="btn-play-trigger"
                  onClick={() => onPlayTrigger?.(player.id, player.walkup_track_id)}
                >
                  ▶ Play
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
