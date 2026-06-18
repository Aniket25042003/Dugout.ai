/**
 * @file apps/dashboard/src/api/dashboardApi.ts
 * @layer Frontend — Dashboard REST Client
 * @description Wraps dashboard calls to the AI orchestrator for overrides, controls,
 *              command approvals, lineup/player reads, media uploads, and roster CSVs.
 * @dependencies Browser fetch, FormData, VITE_GATEWAY_URL
 */

const API_BASE_URL =
  (import.meta as any).env?.VITE_GATEWAY_URL || "http://localhost:8080";

/**
 * Sends a manual player override request to the orchestrator.
 *
 * @param gameId - Game identifier being corrected
 * @param jerseyNumber - Jersey number selected by the operator
 * @param teamSide - Optional home/away disambiguator
 * @param reason - Audit reason for the override
 * @returns Promise resolving to the override result with player context
 */
export async function overridePlayer(
  gameId: string,
  jerseyNumber: string,
  teamSide?: string,
  reason: string = "manual_override"
) {
  const response = await fetch(`${API_BASE_URL}/api/v1/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_id: gameId,
      jersey_number: jerseyNumber,
      team_side: teamSide || null,
      reason,
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to override player: ${await response.text()}`);
  }
  return response.json();
}

/**
 * Publishes a music-control action through the orchestrator API.
 *
 * @param gameId - Game identifier
 * @param action - Music action to perform
 * @param playerId - Optional player to play walk-up music for
 * @param assetId - Optional media asset override
 * @param fadeMs - Fade duration for fade-out actions
 * @returns Promise resolving to accepted command metadata
 */
export async function controlMusic(
  gameId: string,
  action: 'play' | 'stop' | 'fade_out' | 'emergency_stop',
  playerId?: string | null,
  assetId?: string | null,
  fadeMs: number = 2000
) {
  const response = await fetch(`${API_BASE_URL}/api/v1/music/control`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_id: gameId,
      action,
      player_id: playerId || null,
      asset_id: assetId || null,
      fade_ms: fadeMs,
    }),
  });
  if (!response.ok) {
    throw new Error(`Music control failed: ${await response.text()}`);
  }
  return response.json();
}

/**
 * Publishes a commentary-control action through the orchestrator API.
 *
 * @param gameId - Game identifier
 * @param action - Commentary control action
 * @param text - Manual text to speak when action is manual
 * @returns Promise resolving to accepted command metadata
 */
export async function controlCommentary(
  gameId: string,
  action: 'mute' | 'unmute' | 'regenerate' | 'manual',
  text?: string
) {
  const response = await fetch(`${API_BASE_URL}/api/v1/commentary/control`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_id: gameId,
      action,
      text: text || null,
    }),
  });
  if (!response.ok) {
    throw new Error(`Commentary control failed: ${await response.text()}`);
  }
  return response.json();
}

/**
 * Approves a pending production command.
 *
 * @param commandId - Command queue identifier
 * @param reason - Optional manager reason
 * @returns Promise resolving to updated command status
 */
export async function approveCommand(commandId: string, reason?: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/commands/${commandId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: "approve",
      reason: reason || null,
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to approve command: ${await response.text()}`);
  }
  return response.json();
}

/**
 * Cancels a queued or in-progress production command.
 *
 * @param commandId - Command queue identifier
 * @param reason - Optional cancellation reason
 * @returns Promise resolving to updated command status
 */
export async function cancelCommand(commandId: string, reason?: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/commands/${commandId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: "cancel",
      reason: reason || "manual_cancel",
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to cancel command: ${await response.text()}`);
  }
  return response.json();
}

/**
 * Fetches the active batting lineup for a team.
 *
 * @param gameId - Game identifier
 * @param teamId - Team identifier
 * @returns Promise resolving to lineup rows
 */
export async function getLineup(gameId: string, teamId: string) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/lineup?game_id=${encodeURIComponent(gameId)}&team_id=${encodeURIComponent(teamId)}`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch lineup");
  }
  return response.json();
}

/**
 * Fetches season stats for one player.
 *
 * @param playerId - Player identifier
 * @returns Promise resolving to a player stats row
 */
export async function getPlayerStats(playerId: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/players/${playerId}/stats`);
  if (!response.ok) {
    throw new Error("Failed to fetch player stats");
  }
  return response.json();
}

/**
 * Fetches player profile data.
 *
 * @param playerId - Player identifier
 * @returns Promise resolving to player metadata
 */
export async function getPlayer(playerId: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/players/${playerId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch player info");
  }
  return response.json();
}

/**
 * Fetches media assets with optional filters.
 *
 * @param type - Optional asset type filter
 * @param playerId - Optional player owner filter
 * @returns Promise resolving to asset list and count
 */
export async function getMediaAssets(type?: string, playerId?: string) {
  let url = `${API_BASE_URL}/api/v1/media`;
  const params = [];
  if (type) params.push(`asset_type=${encodeURIComponent(type)}`);
  if (playerId) params.push(`player_id=${encodeURIComponent(playerId)}`);
  if (params.length) url += `?${params.join("&")}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Failed to fetch media assets");
  }
  return response.json();
}

/**
 * Uploads a media asset using multipart form data.
 *
 * @param name - Display name for the asset
 * @param assetType - Asset category used by the backend
 * @param file - Browser file object to upload
 * @param playerId - Optional linked player
 * @param teamId - Optional linked team
 * @param durationMs - Optional duration metadata
 * @returns Promise resolving to created asset metadata
 */
export async function uploadMediaAsset(
  name: string,
  assetType: string,
  file: File,
  playerId?: string,
  teamId?: string,
  durationMs?: number
) {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("asset_type", assetType);
  formData.append("file", file);
  if (playerId) formData.append("player_id", playerId);
  if (teamId) formData.append("team_id", teamId);
  if (durationMs) formData.append("duration_ms", durationMs.toString());

  const response = await fetch(`${API_BASE_URL}/api/v1/media/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error("Failed to upload media asset");
  }
  return response.json();
}

/**
 * Uploads a roster CSV for bulk player upsert.
 *
 * @param teamId - Team identifier
 * @param file - CSV file containing roster rows
 * @returns Promise resolving to import status and upsert count
 */
export async function uploadRosterCsv(teamId: string, file: File) {
  const formData = new FormData();
  formData.append("team_id", teamId);
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/v1/roster/upload-csv`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error("Failed to upload roster CSV");
  }
  return response.json();
}
