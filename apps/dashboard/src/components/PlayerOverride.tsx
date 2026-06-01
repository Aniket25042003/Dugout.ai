import React, { useState } from 'react';
import { overridePlayer } from '../api/dashboardApi';

type Props = {
  gameId: string;
  onOverrideSuccess?: (player: any) => void;
};

export const PlayerOverride: React.FC<Props> = ({
  gameId,
  onOverrideSuccess,
}) => {
  const [jersey, setJersey] = useState('');
  const [teamSide, setTeamSide] = useState<'home' | 'away'>('home');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jersey.trim()) return;

    setLoading(true);
    setMessage('');
    try {
      const res = await overridePlayer(gameId, jersey, teamSide);
      if (res.status === 'override_applied') {
        setMessage(`Success: Player #${jersey} substituted!`);
        setJersey('');
        onOverrideSuccess?.(res.player);
      }
    } catch (err: any) {
      console.error(err);
      setMessage(`Error: ${err.message || 'Player not found in roster'}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card player-override-card">
      <h3>Player Override</h3>
      <form onSubmit={handleSubmit} className="override-form">
        <div className="input-group-row">
          <div className="input-field">
            <label>Jersey Number</label>
            <input 
              type="text" 
              placeholder="e.g. 17"
              value={jersey}
              onChange={(e) => setJersey(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="input-field">
            <label>Team Side</label>
            <select 
              value={teamSide} 
              onChange={(e) => setTeamSide(e.target.value as 'home' | 'away')}
              disabled={loading}
            >
              <option value="home">Home (Ashland)</option>
              <option value="away">Away (Giants)</option>
            </select>
          </div>
        </div>

        <button type="submit" className="btn-override-submit" disabled={loading}>
          {loading ? 'Processing...' : 'Override Active Batter'}
        </button>

        {message && (
          <div className={`override-feedback ${message.startsWith('Error') ? 'err' : 'ok'}`}>
            {message}
          </div>
        )}
      </form>
    </div>
  );
};
