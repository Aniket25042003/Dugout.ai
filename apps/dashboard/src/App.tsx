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

const DEFAULT_MUSIC_STATE: MusicState = {
  status: 'stopped',
  trackName: null,
  playerName: null,
  playerId: null,
  assetId: null,
  elapsedMs: 0,
  totalMs: 0,
};

const DEFAULT_GRAPHICS_STATE: GraphicsState = {
  activeOverlay: null,
  overlayData: {},
  scoreboardData: {
    homeScore: 0,
    awayScore: 0,
    inning: 1,
    isTop: true,
    balls: 0,
    strikes: 0,
    outs: 0,
    bases: [false, false, false],
  },
};

const DEFAULT_COMMENTARY_STATE: CommentaryState = {
  status: 'idle',
  currentText: '',
  contextUsed: {},
  audioPath: '',
  source: 'template',
};

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

  // Audio References for Browser Playback
  const musicAudioRef = useRef<HTMLAudioElement | null>(null);
  const commentaryAudioRef = useRef<HTMLAudioElement | null>(null);
  const lastMusicUrlRef = useRef<string | null>(null);
  const lastCommentaryUrlRef = useRef<string | null>(null);

  // Fetch Next Batters
  const fetchNextBatters = useCallback(async (gState: GameState) => {
    try {
      const activeTeamId = gState.isTop ? 'team_opponent' : 'team_ashland';
      const currentIndex = gState.isTop ? gState.battingIndexAway : gState.battingIndexHome;
      
      const lineupRes = await getLineup(GAME_ID, activeTeamId);
      const lineup = lineupRes.lineup || [];
      if (lineup.length === 0) return;

      // Extract next 3 batters wrapping around order
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

  // Sync Audio Playback
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
        // Sync drift if exceeds 500ms
        const drift = Math.abs(musicAudioRef.current.currentTime - (musicState.elapsedMs / 1000.0));
        if (drift > 0.5) {
          musicAudioRef.current.currentTime = musicState.elapsedMs / 1000.0;
        }
        if (musicAudioRef.current.paused) {
          musicAudioRef.current.play().catch(console.error);
        }
      }
    } else if (musicState.status === 'fading' && musicAudioRef.current) {
      // Fade out volume slowly
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
    // 2. Commentary Audio
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

  // Handle Incoming SSE Frames
  const handleFrame = useCallback((frame: SSEFrame) => {
    setConnected(true);

    if (frame.type === 'game_state') {
      setGameState(frame.state);
      fetchNextBatters(frame.state);

      if (frame.event) {
        const evt = frame.event;
        const pitch = evt.pitchResult as any;
        const play = evt.playOutcome as any;
        const inning = evt.inningTransition as any;
        const sub = evt.substitution as any;
        const corr = evt.correction as any;
        
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

      // Add low-confidence CV alert if it was enqueued with requires_confirmation
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

  // Command Approval Gate actions
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

  // Resolve CV alerts
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

        {/* Right Column */}
        <section className="grid-col col-right">
          <CommentaryPanel 
            commentaryState={commentaryState}
            gameId={GAME_ID}
          />
          <PlayerStats 
            activeBatterId={gameState.activeBatterId}
            activePitcherId={gameState.activePitcherId}
          />
          <AlertsPanel 
            alerts={alerts}
            pendingCommands={pendingCommands}
            onResolveAlert={handleResolveAlert}
            onApproveCommand={handleApproveCommand}
            onCancelCommand={handleCancelCommand}
          />
          <ProductionStatus 
            liveCameraOk={connected}
            radarOk={true}
            audioOk={true}
            graphicsOk={graphicsState.activeOverlay !== null}
            commentaryOk={commentaryState.status !== 'idle'}
          />
          <TimelinePanel timeline={timeline} />
        </section>
      </main>
    </div>
  );
}

export default App;
