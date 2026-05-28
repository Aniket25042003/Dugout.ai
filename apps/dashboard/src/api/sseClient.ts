/**
 * SSE client hook for consuming the Event Gateway stream.
 */

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

export type SSEFrame = {
  event: Record<string, unknown> | null;
  state: GameState;
};

export type AlertItem = {
  id: string;
  type: string;
  message: string;
  confidence: number;
  entityId: string;
  timestamp: string;
  resolved: boolean;
};

export type TimelineEntry = {
  id: string;
  type: string;
  summary: string;
  timestamp: string;
  source: string;
};

const GATEWAY_URL =
  (import.meta as any).env?.VITE_GATEWAY_URL || "http://localhost:8080";

export function connectSSE(
  gameId: string,
  onFrame: (frame: SSEFrame) => void,
  onError?: (err: Event) => void
): EventSource {
  const url = `${GATEWAY_URL}/api/v1/games/stream?game_id=${encodeURIComponent(gameId)}`;
  const source = new EventSource(url);

  source.onmessage = (evt) => {
    try {
      const frame: SSEFrame = JSON.parse(evt.data);
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
