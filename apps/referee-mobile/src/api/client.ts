/**
 * @file apps/referee-mobile/src/api/client.ts
 * @layer Mobile — Referee Event Gateway Client
 * @description Builds and sends official game events from the referee mobile app
 *              to the Go event-gateway ingestion endpoint.
 * @dependencies Browser/React Native fetch, event-gateway HTTP API
 */

const isWeb = typeof window !== "undefined" && !!window.location;
/** Resolves the default gateway URL for web and local mobile development. */
const getInitialGatewayUrl = () => {
  if (isWeb && window.location.hostname) {
    return `http://${window.location.hostname}:8080`;
  }
  return "http://localhost:8080";
};

let gatewayUrl = getInitialGatewayUrl();

/**
 * Updates the gateway base URL used for future event submissions.
 *
 * @param url - Base URL for the event gateway, including protocol and port
 */
export function setGatewayUrl(url: string) {
  gatewayUrl = url;
}

/**
 * Returns the currently configured gateway base URL.
 *
 * @returns Gateway base URL used by sendEvent
 */
export function getGatewayUrl(): string {
  return gatewayUrl;
}

/** Official game event payload shape accepted by the event gateway. */
export interface GameEventPayload {
  eventId: string;
  gameId: string;
  source: string;
  sourceDeviceId: string;
  occurredAt: string;
  sequence: number;
  confidence: number;
  authority: string;
  correlationId?: string;
  pitchResult?: {
    result: string;
    pitcherId: string;
    batterId: string;
    speedMph?: number;
  };
  playOutcome?: {
    type: string;
    runsScored: number;
    outsRecorded: number;
    batterId: string;
    description?: string;
  };
  inningTransition?: {
    inningNumber: number;
    isTop: boolean;
  };
  substitution?: {
    teamId: string;
    playerInId: string;
    playerOutId: string;
    position: string;
  };
  clockControl?: {
    action: string;
    setTimeSeconds?: number;
  };
  correction?: {
    balls: number;
    strikes: number;
    outs: number;
    homeScore: number;
    awayScore: number;
    reason: string;
  };
}

/**
 * Sends an official game event to the event gateway.
 *
 * @param event - Game event payload created by the referee app
 * @returns Promise resolving to true when the gateway accepted the event
 */
export async function sendEvent(event: GameEventPayload): Promise<boolean> {
  try {
    const response = await fetch(`${gatewayUrl}/api/v1/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
    return response.ok;
  } catch (error) {
    console.error("Failed to send event:", error);
    return false;
  }
}

let sequenceCounter = 0;

/**
 * Increments and returns the local event sequence counter.
 *
 * @returns Monotonic sequence number for events created in this app session
 */
export function nextSequence(): number {
  sequenceCounter++;
  return sequenceCounter;
}

/**
 * Builds a unique-enough event ID for referee-created events.
 *
 * @returns Event ID prefixed with evt_
 */
export function generateEventId(): string {
  return `evt_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
}
