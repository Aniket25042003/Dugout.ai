import type { GraphicsState } from '../api/sseClient';

type Props = {
  graphicsState: GraphicsState;
};

export const GraphicsOverlay: React.FC<Props> = ({ graphicsState }) => {
  const { activeOverlay, overlayData } = graphicsState;

  if (!activeOverlay) return null;

  return (
    <div className={`graphics-overlay-container ${activeOverlay}`}>
      {/* Batter Intro Overlay */}
      {activeOverlay === 'batter_intro' && (
        <div className="overlay-card batter-intro-card animate-slide-up">
          <div className="card-left">
            <img 
              src={overlayData.headshotUrl || "/media/images/headshots/default.png"} 
              alt={overlayData.playerName} 
              className="player-headshot"
              onError={(e) => {
                (e.target as HTMLImageElement).src = "/media/images/headshots/default.png";
              }}
            />
          </div>
          <div className="card-right">
            <div className="player-meta-row">
              <span className="jersey-num">#{overlayData.jerseyNumber}</span>
              <span className="player-name">{overlayData.playerName}</span>
            </div>
            <div className="player-position">{overlayData.position} · Bats {overlayData.batHand}</div>
            
            <div className="stats-grid">
              <div className="stat-box">
                <span className="stat-label">AVG</span>
                <span className="stat-val">{overlayData.battingAvg}</span>
              </div>
              <div className="stat-box">
                <span className="stat-label">HR</span>
                <span className="stat-val">{overlayData.homeRuns}</span>
              </div>
              <div className="stat-box">
                <span className="stat-label">RBI</span>
                <span className="stat-val">{overlayData.rbis}</span>
              </div>
              <div className="stat-box">
                <span className="stat-label">OPS</span>
                <span className="stat-val">{overlayData.ops}</span>
              </div>
            </div>

            {overlayData.notes && (
              <div className="player-notes-bubble">
                "{overlayData.notes}"
              </div>
            )}
          </div>
        </div>
      )}

      {/* Pitcher Intro Overlay */}
      {activeOverlay === 'pitcher_intro' && (
        <div className="overlay-card pitcher-intro-card animate-slide-up">
          <div className="card-left">
            <img 
              src={overlayData.headshotUrl || "/media/images/headshots/default.png"} 
              alt={overlayData.playerName} 
              className="player-headshot"
              onError={(e) => {
                (e.target as HTMLImageElement).src = "/media/images/headshots/default.png";
              }}
            />
          </div>
          <div className="card-right">
            <div className="player-meta-row">
              <span className="jersey-num">#{overlayData.jerseyNumber}</span>
              <span className="player-name">{overlayData.playerName}</span>
            </div>
            <div className="player-position">Starting Pitcher · Throws {overlayData.throwHand}</div>
            
            <div className="stats-grid">
              <div className="stat-box">
                <span className="stat-label">ERA</span>
                <span className="stat-val">{overlayData.era}</span>
              </div>
              <div className="stat-box">
                <span className="stat-label">WHIP</span>
                <span className="stat-val">{overlayData.whip}</span>
              </div>
              <div className="stat-box">
                <span className="stat-label">W - L</span>
                <span className="stat-val">{overlayData.wins} - {overlayData.losses}</span>
              </div>
              <div className="stat-box">
                <span className="stat-label">SO</span>
                <span className="stat-val">{overlayData.strikeouts}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Lower Third Overlay */}
      {activeOverlay === 'lower_third' && (
        <div className="lower-third-overlay-bar animate-slide-right">
          <div className="bar-accent" />
          <div className="bar-content">
            <div className="bar-title">{overlayData.title}</div>
            <div className="bar-subtitle">{overlayData.subtitle}</div>
          </div>
        </div>
      )}

      {/* Pitch Speed Popup */}
      {activeOverlay === 'speed_display' && (
        <div className="pitch-speed-popup animate-pop">
          <div className="speed-value">{overlayData.speedMph}</div>
          <div className="speed-unit">MPH</div>
          <div className="pitch-type">{overlayData.pitchType}</div>
        </div>
      )}
    </div>
  );
};
