import { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import {
  connectSSE,
  GameState,
  SSEFrame,
  AlertItem,
  TimelineEntry,
} from './api/sseClient';

const GAME_ID = 'game_2026_ashland_vs_opponent';

const DEFAULT_STATE: GameState = {
  gameId: GAME_ID,
  balls: 0,
  strikes: 0,
  outs: 0,
  homeScore: 0,
  awayScore: 0,
  inning: 1,
  isTop: true,
  runnerOnFirst: false,
  runnerOnFirstPlayerId: '',
  runnerOnSecond: false,
  runnerOnSecondPlayerId: '',
  runnerOnThird: false,
  runnerOnThirdPlayerId: '',
  activeBatterId: '',
  activePitcherId: '',
  battingIndexHome: 1,
  battingIndexAway: 1,
  lastEventId: '',
};

function formatEventSummary(event: Record<string, unknown>): string {
  const pitch = event.pitchResult as Record<string, unknown> | undefined;
  const play = event.playOutcome as Record<string, unknown> | undefined;
  const inning = event.inningTransition as Record<string, unknown> | undefined;
  const correction = event.correction as Record<string, unknown> | undefined;
  const override = event.manualOverride as Record<string, unknown> | undefined;

  if (pitch) {
    const result = String(pitch.result || '').replace('PITCH_RESULT_TYPE_', '');
    return `Pitch: ${result}`;
  }
  if (play) {
    const type = String(play.type || '').replace('PLAY_OUTCOME_TYPE_', '');
    return `Play: ${type}`;
  }
  if (inning) {
    const half = inning.isTop ? 'Top' : 'Bottom';
    return `Inning: ${half} ${inning.inningNumber}`;
  }
  if (correction) return `Correction: ${correction.reason || 'Manual fix'}`;
  if (override) return `Override: ${override.overrideType || 'Manual'}`;
  return 'Event received';
}

function App() {
  const [gameState, setGameState] = useState<GameState>(DEFAULT_STATE);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  const handleFrame = useCallback((frame: SSEFrame) => {
    setConnected(true);

    if (frame.state) {
      setGameState(frame.state);
    }

    if (frame.event) {
      const evt = frame.event;
      const entry: TimelineEntry = {
        id: String(evt.eventId || `tl_${Date.now()}`),
        type: String(evt.pitchResult ? 'pitch' : evt.playOutcome ? 'play' : 'event'),
        summary: formatEventSummary(evt),
        timestamp: String(evt.occurredAt || new Date().toISOString()),
        source: String(evt.source || 'system'),
      };

      setTimeline((prev) => [entry, ...prev].slice(0, 100));
    }
  }, []);

  useEffect(() => {
    const source = connectSSE(GAME_ID, handleFrame, () =>
      setConnected(false)
    );
    sourceRef.current = source;
    return () => source.close();
  }, [handleFrame]);

  // Simulate alerts from a NATS alert subscription (in production this would be a separate SSE channel)
  const addMockAlert = useCallback(() => {
    const alert: AlertItem = {
      id: `alert_${Date.now()}`,
      type: 'low_cv_confidence',
      message: `Low confidence jersey detection: #${Math.floor(Math.random() * 30 + 1)} (${(Math.random() * 30 + 40).toFixed(0)}%)`,
      confidence: Math.random() * 0.3 + 0.4,
      entityId: `obs_mock_${Date.now()}`,
      timestamp: new Date().toISOString(),
      resolved: false,
    };
    setAlerts((prev) => [alert, ...prev]);
  }, []);

  const resolveAlert = useCallback((alertId: string, action: 'confirm' | 'override') => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === alertId ? { ...a, resolved: true } : a
      )
    );

    const entry: TimelineEntry = {
      id: `override_${Date.now()}`,
      type: 'override',
      summary: `Manager ${action}: Alert ${alertId.slice(-8)}`,
      timestamp: new Date().toISOString(),
      source: 'manager_dashboard',
    };
    setTimeline((prev) => [entry, ...prev].slice(0, 100));
  }, []);

  const handleEmergencyStop = useCallback(() => {
    const entry: TimelineEntry = {
      id: `estop_${Date.now()}`,
      type: 'emergency',
      summary: '🚨 EMERGENCY STOP activated — all production commands cancelled',
      timestamp: new Date().toISOString(),
      source: 'manager_dashboard',
    };
    setTimeline((prev) => [entry, ...prev]);
  }, []);

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <h1>⚾ DUGOUT.AI — CONTROL CENTER</h1>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button
            onClick={addMockAlert}
            style={{
              padding: '4px 12px',
              borderRadius: 6,
              border: '1px solid var(--border-light)',
              background: 'var(--bg-card)',
              color: 'var(--text-secondary)',
              fontSize: 11,
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            + Mock Alert
          </button>
          <span className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '● LIVE' : '○ DISCONNECTED'}
          </span>
        </div>
      </div>

      {/* Scoreboard */}
      <div className="scoreboard-panel">
        <h2>Live Scoreboard</h2>

        <div className="score-display">
          <div className="team-score">
            <div className="label">AWAY</div>
            <div className="score">{gameState.awayScore}</div>
          </div>
          <div className="score-divider">—</div>
          <div className="team-score">
            <div className="label">HOME</div>
            <div className="score">{gameState.homeScore}</div>
          </div>
        </div>

        <div className="inning-display">
          <div className="inning-text">
            {gameState.isTop ? '▲' : '▼'} Inning {gameState.inning}
          </div>
        </div>

        <div className="count-row">
          <div className="count-item">
            <div className="count-label">Balls</div>
            <div className="count-value balls">{gameState.balls}</div>
          </div>
          <div className="count-item">
            <div className="count-label">Strikes</div>
            <div className="count-value strikes">{gameState.strikes}</div>
          </div>
          <div className="count-item">
            <div className="count-label">Outs</div>
            <div className="count-value outs">{gameState.outs}</div>
          </div>
        </div>

        {/* Bases Diamond */}
        <div className="bases-diamond">
          <div className="bases-row">
            <div className={`base ${gameState.runnerOnSecond ? 'occupied' : ''}`} />
          </div>
          <div className="bases-row">
            <div className={`base ${gameState.runnerOnThird ? 'occupied' : ''}`} />
            <div className="base spacer" />
            <div className={`base ${gameState.runnerOnFirst ? 'occupied' : ''}`} />
          </div>
        </div>

        {/* Active Players */}
        <div className="active-players">
          <div className="player-card">
            <div className="role">AT BAT</div>
            <div className="name">{gameState.activeBatterId || '—'}</div>
          </div>
          <div className="player-card">
            <div className="role">PITCHING</div>
            <div className="name">{gameState.activePitcherId || '—'}</div>
          </div>
        </div>
      </div>

      {/* Alerts & Override Panel */}
      <div className="alerts-panel">
        <h2>Alerts & Overrides</h2>
        {alerts.length === 0 ? (
          <div className="empty-state">No active alerts</div>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className={`alert-card ${alert.resolved ? 'resolved' : ''}`}
            >
              <div className="alert-header">
                <span className="alert-type">
                  {alert.resolved ? '✓ RESOLVED' : '⚠ ' + alert.type.replace(/_/g, ' ')}
                </span>
                <span className="alert-conf">
                  {(alert.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <div className="alert-message">{alert.message}</div>
              {!alert.resolved && (
                <div className="alert-actions">
                  <button
                    className="alert-btn confirm"
                    onClick={() => resolveAlert(alert.id, 'confirm')}
                  >
                    Confirm
                  </button>
                  <button
                    className="alert-btn override"
                    onClick={() => resolveAlert(alert.id, 'override')}
                  >
                    Override
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Event Timeline */}
      <div className="timeline-panel" style={{ gridColumn: '1 / 3' }}>
        <h2>Event Timeline</h2>
        {timeline.length === 0 ? (
          <div className="empty-state">
            Waiting for events... Connect the referee app to begin.
          </div>
        ) : (
          timeline.map((entry) => (
            <div key={entry.id} className="timeline-entry">
              <div className="entry-time">
                {new Date(entry.timestamp).toLocaleTimeString()}
              </div>
              <div className="entry-text">{entry.summary}</div>
              <div className="entry-source">{entry.source}</div>
            </div>
          ))
        )}
      </div>

      {/* Emergency Stop */}
      <button className="emergency-stop-btn" onClick={handleEmergencyStop}>
        🛑 EMERGENCY STOP
      </button>
    </div>
  );
}

export default App;
