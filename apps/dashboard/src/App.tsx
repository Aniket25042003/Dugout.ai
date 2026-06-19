/**
 * @file apps/dashboard/src/App.tsx
 * @layer Frontend — Dashboard State Coordinator
 * @description Owns live dashboard state from SSE, synchronizes browser audio,
 *              and wires operator controls to panels/components.
 * @dependencies connectSSE, dashboardApi controls, dashboard production components
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import { connectSSE } from './api/sseClient';
import type {
  GameState,
  SSEFrame,
  AlertItem,
  TimelineEntry,
  MusicState,
  GraphicsState,
  CommentaryState,
  CommandStatus,
} from './api/sseClient';
import {
  controlMusic,
  approveCommand,
  cancelCommand,
  getLineup,
} from './api/dashboardApi';


import { ScoreboardCompact } from './components/ScoreboardCompact';
import { MusicControl } from './components/MusicControl';
import { CameraFeed } from './components/CameraFeed';
import { CommentaryPanel } from './components/CommentaryPanel';
import { PlayerStats } from './components/PlayerStats';
import { PlayerOverride } from './components/PlayerOverride';
import { LineupCard } from './components/LineupCard';
import { AlertsPanel } from './components/AlertsPanel';
import { TimelinePanel } from './components/TimelinePanel';
import { ProductionStatus } from './components/ProductionStatus';

const GAME_ID = 'game_2026_ashland_vs_opponent';
const ORCHESTRATOR_URL = 'http://localhost:8000';

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
    const speed = pitch.speedMph ? ` (${Number(pitch.speedMph).toFixed(1)} MPH)` : '';
    return `Pitch: ${result}${speed}`;
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

/**
 * Coordinates the live game-day dashboard experience.
 *
 * @returns React application shell for scoreboard, camera, controls, and audit panels
 */
function App() {
  const [gameState, setGameState] = useState<GameState>(DEFAULT_STATE);
  const [musicState, setMusicState] = useState<MusicState>(DEFAULT_MUSIC_STATE);
  const [graphicsState, setGraphicsState] = useState<GraphicsState>(DEFAULT_GRAPHICS_STATE);
  const [commentaryState, setCommentaryState] = useState<CommentaryState>(DEFAULT_COMMENTARY_STATE);
  
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [pendingCommands, setPendingCommands] = useState<any[]>([]);
  const [nextBatters, setNextBatters] = useState<any[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastPitchSpeed, setLastPitchSpeed] = useState<number | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  // Audio References for Browser Playback
  const musicAudioRef = useRef<HTMLAudioElement | null>(null);
  const commentaryAudioRef = useRef<HTMLAudioElement | null>(null);
  const lastMusicUrlRef = useRef<string | null>(null);
  const lastCommentaryUrlRef = useRef<string | null>(null);

  /**
   * Fetches upcoming batters for the currently batting team.
   *
   * @param gState - Latest reduced game state from SSE
   */
  const fetchNextBatters = useCallback(async (gState: GameState) => {
    try {
      const activeTeamId = gState.isTop ? 'team_opponent' : 'team_ashland';
      const currentIndex = gState.isTop ? gState.battingIndexAway : gState.battingIndexHome;
      
      const lineupRes = await getLineup(GAME_ID, activeTeamId);
      const lineup = lineupRes.lineup || [];
      if (lineup.length === 0) return;

      // Extract next 3 batters, wrapping around the lineup order.
      const total = lineup.length;
      const nextList = [];
      for (let i = 1; i <= 3; i++) {
        const idx = (currentIndex + i - 1) % total;
        if (lineup[idx]) nextList.push(lineup[idx]);
      }
      setNextBatters(nextList);
    } catch (e) {
      console.error('Failed to fetch next batters:', e);
    }
  }, []);

  // Sync browser audio playback with orchestrator-published music state.
  useEffect(() => {
    // 1. Music Audio
    if (musicState.status === 'playing' && musicState.filePath) {
      const audioUrl = `${ORCHESTRATOR_URL}/${musicState.filePath}`;
      
      if (lastMusicUrlRef.current !== audioUrl) {
        if (musicAudioRef.current) {
          musicAudioRef.current.pause();
        }
        musicAudioRef.current = new Audio(audioUrl);
        lastMusicUrlRef.current = audioUrl;
        
        // Sync starting position
        musicAudioRef.current.currentTime = musicState.elapsedMs / 1000.0;
        musicAudioRef.current.volume = 1.0;
        musicAudioRef.current.play().catch(e => console.warn("Audio play blocked by browser", e));
      } else if (musicAudioRef.current) {
        // Correct drift over 500ms so backend state and browser audio stay aligned.
        const drift = Math.abs(musicAudioRef.current.currentTime - (musicState.elapsedMs / 1000.0));
        if (drift > 0.5) {
          musicAudioRef.current.currentTime = musicState.elapsedMs / 1000.0;
        }
        if (musicAudioRef.current.paused) {
          musicAudioRef.current.play().catch(console.error);
        }
      }
    } else if (musicState.status === 'fading' && musicAudioRef.current) {
      // Fade out volume gradually while the backend reports fading state.
      const interval = setInterval(() => {
        if (musicAudioRef.current && musicAudioRef.current.volume > 0.1) {
          musicAudioRef.current.volume = Math.max(0, musicAudioRef.current.volume - 0.2);
        } else {
          clearInterval(interval);
          if (musicAudioRef.current) {
            musicAudioRef.current.pause();
            lastMusicUrlRef.current = null;
          }
        }
      }, 200);
      return () => clearInterval(interval);
    } else if (musicState.status === 'stopped' && musicAudioRef.current) {
      musicAudioRef.current.pause();
      lastMusicUrlRef.current = null;
    }
  }, [musicState]);

  useEffect(() => {
    // Commentary audio is one-shot; play only when the published audio path changes.
    if (commentaryState.status === 'speaking' && commentaryState.audioPath) {
      const audioUrl = `${ORCHESTRATOR_URL}${commentaryState.audioPath}`;
      
      if (lastCommentaryUrlRef.current !== audioUrl) {
        if (commentaryAudioRef.current) {
          commentaryAudioRef.current.pause();
        }
        commentaryAudioRef.current = new Audio(audioUrl);
        lastCommentaryUrlRef.current = audioUrl;
        commentaryAudioRef.current.play().catch(e => console.warn("Commentary audio blocked", e));
      }
    } else if (commentaryState.status === 'idle' && commentaryAudioRef.current) {
      commentaryAudioRef.current.pause();
      lastCommentaryUrlRef.current = null;
    }
  }, [commentaryState]);

  /**
   * Applies one SSE frame to dashboard state.
   *
   * @param frame - Parsed frame from the event gateway SSE stream
   */
  const handleFrame = useCallback((frame: SSEFrame) => {
    setConnected(true);

    if (frame.type === 'game_state') {
      setGameState(frame.state);
      fetchNextBatters(frame.state);

      if (frame.event) {
        // Timeline entries summarize official event payloads for operator audit.
        const evt = frame.event;
        const pitch = evt.pitchResult as any;
        const play = evt.playOutcome as any;
        const inning = evt.inningTransition as any;
        const sub = evt.substitution as any;
        const corr = evt.correction as any;

        if (pitch?.speedMph) {
          setLastPitchSpeed(Number(pitch.speedMph));
        }

        let type = 'event';
        let summary = 'Event received';

        if (pitch) {
          type = 'pitch';
          summary = `Pitch: ${pitch.result.replace('PITCH_RESULT_TYPE_', '')} (${pitch.speedMph || 0} MPH)`;
        } else if (play) {
          type = 'play';
          summary = `Play: ${play.type.replace('PLAY_OUTCOME_TYPE_', '')} (Runs: ${play.runsScored}, Outs: ${play.outsRecorded})`;
        } else if (inning) {
          type = 'inning';
          summary = `Inning: ${inning.isTop ? 'Top' : 'Bottom'} of the ${inning.inningNumber}`;
        } else if (sub) {
          type = 'sub';
          summary = `Substitution: Player ${sub.playerInId} replaces ${sub.playerOutId}`;
        } else if (corr) {
          type = 'correction';
          summary = `Correction: Count set to ${corr.balls}-${corr.strikes}`;
        }

        const entry: TimelineEntry = {
          id: String(evt.eventId || `tl_${Date.now()}`),
          type,
          summary,
          timestamp: String(evt.occurredAt || new Date().toISOString()),
          source: String(evt.source || 'system'),
        };
        setTimeline((prev) => [entry, ...prev].slice(0, 50));
      }
    } else if (frame.type === 'music_state') {
      setMusicState(frame.data);
    } else if (frame.type === 'graphics_state') {
      setGraphicsState(frame.data);
    } else if (frame.type === 'commentary_state') {
      setCommentaryState(frame.data);
    } else if (frame.type === 'command_status') {
      const cmd: CommandStatus = frame.data;
      if (cmd.status === 'pending_approval') {
        setPendingCommands((prev) => {
          if (prev.some(c => c.command_id === cmd.command_id)) return prev;
          return [...prev, cmd];
        });
      } else {
        // Remove from pending if resolved
        setPendingCommands((prev) => prev.filter(c => c.command_id !== cmd.command_id));
      }

      // Low-confidence CV detections arrive as pending walk-up music commands.
      if (cmd.status === 'pending_approval' && cmd.command_type === 'play_walkup_music') {
        const alert: AlertItem = {
          id: `alert_${cmd.command_id}`,
          type: 'low_cv_confidence',
          message: `Confirm walk-up music for player #${cmd.command_id.slice(-4)}?`,
          confidence: 0.65,
          entityId: cmd.command_id,
          timestamp: new Date().toISOString(),
          resolved: false,
        };
        setAlerts((prev) => {
          if (prev.some(a => a.id === alert.id)) return prev;
          return [alert, ...prev];
        });
      }
    }
  }, [fetchNextBatters]);

  // Connect to SSE stream
  useEffect(() => {
    const source = connectSSE(GAME_ID, handleFrame, () => setConnected(false));
    return () => source.close();
  }, [handleFrame]);

  // Command approval handlers mirror Postgres queue status in local UI state.
  const handleApproveCommand = async (cmdId: string) => {
    try {
      await approveCommand(cmdId);
      setPendingCommands((prev) => prev.filter(c => c.command_id !== cmdId));
    } catch (e) {
      console.error(e);
    }
  };

  const handleCancelCommand = async (cmdId: string) => {
    try {
      await cancelCommand(cmdId, "Rejected by manager");
      setPendingCommands((prev) => prev.filter(c => c.command_id !== cmdId));
    } catch (e) {
      console.error(e);
    }
  };

  /**
   * Resolves an alert by approving or cancelling its linked command.
   *
   * @param alertId - Dashboard alert ID derived from command ID
   * @param action - Confirm approves; override cancels
   */
  const handleResolveAlert = useCallback(async (alertId: string, action: 'confirm' | 'override') => {
    setAlerts((prev) => prev.map((a) => a.id === alertId ? { ...a, resolved: true } : a));
    const cmdId = alertId.replace('alert_', '');
    
    if (action === 'confirm') {
      await handleApproveCommand(cmdId);
    } else {
      await handleCancelCommand(cmdId);
    }

    const entry: TimelineEntry = {
      id: `override_${Date.now()}`,
      type: 'override',
      summary: `Manager ${action.toUpperCase()}: Resolved Alert ${cmdId.slice(-6)}`,
      timestamp: new Date().toISOString(),
      source: 'manager_dashboard',
    };
    setTimeline((prev) => [entry, ...prev].slice(0, 50));
  }, []);

  const handleManualPlayMusic = async (playerId: string, assetId: string) => {
    try {
      await controlMusic(GAME_ID, 'play', playerId, assetId);
    } catch (e) {
      console.error(e);
    }
  };

  const handleHideOverlay = async () => {
    // Send command to clear overlay
    try {
      await fetch(`${ORCHESTRATOR_URL}/api/v1/music/control`, { // or graphics control
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: GAME_ID, action: 'stop_music' }) // or hide overlay
      });
      setGraphicsState(prev => ({ ...prev, activeOverlay: null, overlayData: {} }));
    } catch (e) {
      console.error(e);
    }
  };

  const handleEmergencyStopAll = async () => {
    try {
      await controlMusic(GAME_ID, 'emergency_stop');
      const entry: TimelineEntry = {
        id: `estop_${Date.now()}`,
        type: 'emergency',
        summary: '🛑 EMERGENCY STOP activated — all music and overlays cleared',
        timestamp: new Date().toISOString(),
        source: 'manager_dashboard',
      };
      setTimeline((prev) => [entry, ...prev]);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="dashboard-grid-container">
      {/* Header */}
      <header className="main-header">
        <div className="title-section">
          <h1>⚾ DUGOUT.AI — PRODUCTION CONTROL CENTER</h1>
          <span className={`live-badge ${connected ? 'live' : 'offline'}`}>
            {connected ? '● LIVE' : '○ OFFLINE'}
          </span>
        </div>
        <button className="btn-emergency-stop" onClick={handleEmergencyStopAll}>
          🛑 EMERGENCY STOP
        </button>
      </header>

      {/* Grid Layout */}
      <main className="dashboard-grid">
        {/* Left Column */}
        <section className="grid-col col-left">
          <MusicControl 
            musicState={musicState}
            gameId={GAME_ID}
            nextBatters={nextBatters}
            onPlayTrigger={handleManualPlayMusic}
          />
          <PlayerOverride gameId={GAME_ID} />
        </section>

        {/* Center Column */}
        <section className="grid-col col-center">
          <CameraFeed 
            graphicsState={graphicsState}
            onHideOverlay={handleHideOverlay}
          />
          <div className="horizontal-panel-row">
            <ScoreboardCompact gameState={gameState} />
            <LineupCard gameId={GAME_ID} activeBatterId={gameState.activeBatterId} />
          </div>
        </section>

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

        {/* Last Pitch Speed */}
        {lastPitchSpeed !== null && (
          <div className="last-pitch-speed-card" style={{
            marginTop: 12,
            padding: '12px 16px',
            background: 'linear-gradient(135deg, rgba(96, 165, 250, 0.1), rgba(129, 140, 248, 0.15))',
            borderRadius: 10,
            border: '1px solid rgba(96, 165, 250, 0.2)',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: 10, color: 'var(--text-secondary)', fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 2 }}>Last Pitch Speed</div>
            <div style={{ fontSize: 26, fontWeight: 900, color: 'var(--accent-blue)', fontFamily: 'monospace' }}>
              {lastPitchSpeed.toFixed(1)} <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>MPH</span>
            </div>
          </div>
        )}
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
