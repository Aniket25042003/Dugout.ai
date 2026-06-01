import React, { useState, useEffect, useRef } from 'react';
import { getLineup, uploadRosterCsv } from '../api/dashboardApi';

type Props = {
  gameId: string;
  activeBatterId: string | null;
  homeTeamId?: string;
  awayTeamId?: string;
};

export const LineupCard: React.FC<Props> = ({
  gameId,
  activeBatterId,
  homeTeamId = 'team_ashland',
  awayTeamId = 'team_opponent',
}) => {
  const [homeLineup, setHomeLineup] = useState<any[]>([]);
  const [awayLineup, setAwayLineup] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'home' | 'away'>('home');
  const [uploadStatus, setUploadStatus] = useState('');
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchLineups = async () => {
    try {
      const home = await getLineup(gameId, homeTeamId);
      setHomeLineup(home.lineup || []);
      const away = await getLineup(gameId, awayTeamId);
      setAwayLineup(away.lineup || []);
    } catch (err) {
      console.error("Failed to load lineups:", err);
    }
  };

  useEffect(() => {
    fetchLineups();
  }, [gameId, activeBatterId]);

  const handleUploadRoster = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus('Uploading...');
    try {
      const targetTeam = activeTab === 'home' ? homeTeamId : awayTeamId;
      await uploadRosterCsv(targetTeam, file);
      setUploadStatus('Roster uploaded successfully!');
      fetchLineups();
    } catch (err: any) {
      console.error(err);
      setUploadStatus(`Upload failed: ${err.message || 'Error parsing CSV'}`);
    }
  };

  const currentLineup = activeTab === 'home' ? homeLineup : awayLineup;

  return (
    <div className="card lineup-card">
      <div className="lineup-header">
        <h3>Team Lineups</h3>
        <div className="tab-buttons">
          <button 
            className={`tab-btn ${activeTab === 'home' ? 'active' : ''}`}
            onClick={() => setActiveTab('home')}
          >
            Ashland A's
          </button>
          <button 
            className={`tab-btn ${activeTab === 'away' ? 'active' : ''}`}
            onClick={() => setActiveTab('away')}
          >
            Giants
          </button>
        </div>
      </div>

      <div className="lineup-list">
        <div className="list-grid-header">
          <span>#</span>
          <span>Player Name</span>
          <span>Pos</span>
          <span>Jersey</span>
        </div>
        {currentLineup.length === 0 ? (
          <div className="empty-state">No lineup registered</div>
        ) : (
          currentLineup.map((player) => (
            <div 
              key={player.id} 
              className={`lineup-row ${activeBatterId === player.id ? 'current-batter' : ''}`}
            >
              <span className="order">{player.batting_order}.</span>
              <span className="name">
                {player.name} {activeBatterId === player.id && <span className="bat-icon">🏏</span>}
              </span>
              <span className="pos">{player.position}</span>
              <span className="jersey">#{player.jersey_number}</span>
            </div>
          ))
        )}
      </div>

      <div className="roster-upload-section">
        <button 
          className="btn-roster-upload"
          onClick={() => fileInputRef.current?.click()}
        >
          📂 Upload {activeTab === 'home' ? "Ashland" : "Giants"} Roster CSV
        </button>
        <input 
          type="file" 
          ref={fileInputRef} 
          style={{ display: 'none' }}
          accept=".csv"
          onChange={handleUploadRoster}
        />
        {uploadStatus && (
          <div className={`upload-status ${uploadStatus.includes('failed') ? 'err' : 'ok'}`}>
            {uploadStatus}
          </div>
        )}
      </div>
    </div>
  );
};
