/**
 * @file apps/dashboard/src/components/TimelinePanel.tsx
 * @layer Frontend — Event Timeline UI
 * @description Displays the chronological game event/audit feed received through SSE.
 * @dependencies TimelineEntry from sseClient
 */

import React from 'react';
import type { TimelineEntry } from '../api/sseClient';

/** Props for the event timeline panel. */
type Props = {
  timeline: TimelineEntry[];
};

/**
 * Renders the game event timeline.
 *
 * @param props - Timeline entries derived from streamed game events
 * @returns React timeline card
 */
export const TimelinePanel: React.FC<Props> = ({ timeline }) => {
  return (
    <div className="card timeline-panel-card">
      <h3>Event Log & Audit Trail</h3>
      <div className="timeline-feed-container">
        {timeline.length === 0 ? (
          <div className="empty-state">Waiting for official referee events...</div>
        ) : (
          timeline.map((entry) => (
            <div key={entry.id} className={`timeline-row type-${entry.type}`}>
              <div className="row-header">
                <span className="timestamp">
                  {new Date(entry.timestamp).toLocaleTimeString()}
                </span>
                <span className="source">{entry.source}</span>
              </div>
              <div className="row-text">{entry.summary}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
