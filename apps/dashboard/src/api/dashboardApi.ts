/**
 * REST API client for dashboard actions.
 */

const API_BASE_URL =
  (import.meta as any).env?.VITE_GATEWAY_URL || "http://localhost:8080";

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

export async function getLineup(gameId: string, teamId: string) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/lineup?game_id=${encodeURIComponent(gameId)}&team_id=${encodeURIComponent(teamId)}`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch lineup");
  }
  return response.json();
}

export async function getPlayerStats(playerId: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/players/${playerId}/stats`);
  if (!response.ok) {
    throw new Error("Failed to fetch player stats");
  }
  return response.json();
}

export async function getPlayer(playerId: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/players/${playerId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch player info");
  }
  return response.json();
}


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
