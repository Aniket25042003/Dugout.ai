/**
 * @file apps/referee-mobile/src/api/eventQueue.ts
 * @layer Mobile — Offline Event Queue
 * @description Stores referee-created events in memory when submission fails and
 *              flushes them in FIFO order once the gateway is reachable again.
 * @dependencies GameEventPayload, sendEvent
 */

import { GameEventPayload, sendEvent } from "./client";

let queue: GameEventPayload[] = [];
let isFlushing = false;

/**
 * Adds a failed event submission to the in-memory queue.
 *
 * @param event - Game event payload to retry later
 */
export function enqueueEvent(event: GameEventPayload): void {
  queue.push(event);
}

/**
 * Returns the number of events waiting to be flushed.
 *
 * @returns Current in-memory queue length
 */
export function getQueueLength(): number {
  return queue.length;
}

/**
 * Flushes queued events in FIFO order until the first failed send.
 *
 * @returns Promise resolving to the number of events successfully sent
 */
export async function flushQueue(): Promise<number> {
  if (isFlushing || queue.length === 0) return 0;
  isFlushing = true;

  let sent = 0;
  // Stop on first failure so official event ordering is preserved.
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

/**
 * Clears all queued events without sending them.
 *
 * Side effect: drops unsent in-memory game events.
 */
export function clearQueue(): void {
  queue = [];
}
