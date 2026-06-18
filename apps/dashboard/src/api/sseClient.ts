/**
 * @file apps/dashboard/src/api/sseClient.ts
 * @layer Frontend — Event Stream Client
 * @description Connects the dashboard to the Go event-gateway SSE stream and
 *              normalizes game, music, graphics, commentary, and command frames.
 * @dependencies Browser EventSource, VITE_GATEWAY_URL, event-gateway SSE route
 */

/** Reduced baseball game state displayed across the dashboard. */
export type GameState = {
  gameId: string;
  balls: number;
  strikes: number;
  outs: number;
  homeScore: number;
  awayScore: number;
  inning: number;
  isTop: boolean;
  runnerOnFirst: boolean;
  runnerOnFirstPlayerId: string;
  runnerOnSecond: boolean;
  runnerOnSecondPlayerId: string;
  runnerOnThird: boolean;
  runnerOnThirdPlayerId: string;
  activeBatterId: string;
  activePitcherId: string;
  battingIndexHome: number;
  battingIndexAway: number;
  lastEventId: string;
};

/** Music playback state published by the AI orchestrator music adapter. */
export type MusicState = {
  status: 'playing' | 'stopped' | 'fading';
  trackName: string | null;
  playerName: string | null;
  playerId: string | null;
  assetId: string | null;
  elapsedMs: number;
  totalMs: number;
  filePath?: string;
};

/** Graphics overlay state published by the AI orchestrator graphics adapter. */
export type GraphicsState = {
  activeOverlay: 'batter_intro' | 'pitcher_intro' | 'lower_third' | 'speed_display' | 'sponsor' | null;
  overlayData: Record<string, any>;
  scoreboardData: {
    homeScore: number;
    awayScore: number;
    inning: number;
    isTop: boolean;
    balls: number;
    strikes: number;
    outs: number;
    bases: [boolean, boolean, boolean];
  };
};

/** Commentary state published after LLM/template generation and optional TTS. */
export type CommentaryState = {
  status: 'generating' | 'speaking' | 'idle';
  currentText: string;
  contextUsed: Record<string, any>;
  audioPath: string;
  source: 'llm' | 'template' | 'manual';
  historyId?: number;
};

/** Command lifecycle status emitted by the production command queue. */
export type CommandStatus = {
  command_id: string;
  status: 'queued' | 'pending_approval' | 'approved' | 'started' | 'completed' | 'failed' | 'cancelled' | 'superseded';
  command_type?: string;
  confirmed_by?: string;
  cancelled_by?: string;
  reason?: string;
  error?: string;
  updated_at: string;
};

/** Discriminated union for every SSE frame type the dashboard consumes. */
export type SSEFrame =
  | { type: 'game_state'; event: Record<string, any> | null; state: GameState }
  | { type: 'music_state'; data: MusicState }
  | { type: 'graphics_state'; data: GraphicsState }
  | { type: 'commentary_state'; data: CommentaryState }
  | { type: 'command_status'; data: CommandStatus };

/** Operator-facing alert derived from low-confidence or exceptional events. */
export type AlertItem = {
  id: string;
  type: string;
  message: string;
  confidence: number;
  entityId: string;
  timestamp: string;
  resolved: boolean;
};

/** Timeline entry shown in the game-event activity panel. */
export type TimelineEntry = {
  id: string;
  type: string;
  summary: string;
  timestamp: string;
  source: string;
};

const GATEWAY_URL =
  (import.meta as any).env?.VITE_GATEWAY_URL || "http://localhost:8080";

/**
 * Opens an EventSource connection for a single game and dispatches parsed frames.
 *
 * @param gameId - Game identifier to stream from the gateway
 * @param onFrame - Callback invoked for each parsed SSE frame
 * @param onError - Optional callback invoked when EventSource reports an error
 * @returns Browser EventSource instance; caller owns closing it
 */
export function connectSSE(
  gameId: string,
  onFrame: (frame: SSEFrame) => void,
  onError?: (err: Event) => void
): EventSource {
  const url = `${GATEWAY_URL}/api/v1/games/stream?game_id=${encodeURIComponent(gameId)}`;
  const source = new EventSource(url);

  source.onmessage = (evt) => {
    try {
      const raw = JSON.parse(evt.data);
      // Older gateway frames lacked an explicit type, so default to game_state.
      const frameType = raw.type || 'game_state';
      
      let frame: SSEFrame;
      if (frameType === 'game_state') {
        frame = {
          type: 'game_state',
          event: raw.event,
          state: raw.state
        };
      } else {
        frame = {
          type: frameType,
          data: raw.data
        } as SSEFrame;
      }
      
      onFrame(frame);
    } catch (e) {
      console.error("Failed to parse SSE frame:", e);
    }
  };

  source.onerror = (err) => {
    console.error("SSE connection error:", err);
    onError?.(err);
  };

  return source;
}
