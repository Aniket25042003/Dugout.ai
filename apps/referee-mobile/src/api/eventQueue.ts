/**
 * Offline event queue for the referee app.
 * Stores events in memory when the network is unavailable,
 * and flushes them in order when connectivity is restored.
 */

import { GameEventPayload, sendEvent } from "./client";

let queue: GameEventPayload[] = [];
let isFlushing = false;

export function enqueueEvent(event: GameEventPayload): void {
  queue.push(event);
}

export function getQueueLength(): number {
  return queue.length;
}

export async function flushQueue(): Promise<number> {
  if (isFlushing || queue.length === 0) return 0;
  isFlushing = true;

  let sent = 0;
  // Process in FIFO order; stop on first failure to preserve ordering
  while (queue.length > 0) {
    const event = queue[0];
    const success = await sendEvent(event);
    if (!success) {
      break;
    }
    queue.shift();
    sent++;
  }

  isFlushing = false;
  return sent;
}

export function clearQueue(): void {
  queue = [];
}
