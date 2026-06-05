import React from 'react';
import type { TimelineEntry } from '../api/sseClient';

type Props = {
  timeline: TimelineEntry[];
};

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
