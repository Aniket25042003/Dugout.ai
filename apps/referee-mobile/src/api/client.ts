/**
 * API client for communicating with the Dugout Event Gateway.
 * Sends official referee game events.
 */

const isWeb = typeof window !== "undefined" && !!window.location;
const getInitialGatewayUrl = () => {
  if (isWeb && window.location.hostname) {
    return `http://${window.location.hostname}:8080`;
  }
  return "http://localhost:8080";
};

let gatewayUrl = getInitialGatewayUrl();

export function setGatewayUrl(url: string) {
  gatewayUrl = url;
}

export function getGatewayUrl(): string {
  return gatewayUrl;
}

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

export function nextSequence(): number {
  sequenceCounter++;
  return sequenceCounter;
}

export function generateEventId(): string {
  return `evt_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
}
