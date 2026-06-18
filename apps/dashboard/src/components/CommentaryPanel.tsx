/**
 * @file apps/dashboard/src/components/CommentaryPanel.tsx
 * @layer Frontend — Commentary Control UI
 * @description Displays generated commentary, maintains a recent commentary log,
 *              and sends mute/regenerate/manual controls to the orchestrator.
 * @dependencies CommentaryState, controlCommentary API
 */

import React, { useState, useEffect, useRef } from 'react';
import type { CommentaryState } from '../api/sseClient';
import { controlCommentary } from '../api/dashboardApi';

/** Props for the commentary status and control panel. */
type Props = {
  commentaryState: CommentaryState;
  gameId: string;
};

/** Local commentary history entry rendered in the dashboard log. */
type LogEntry = {
  id: string;
  text: string;
  source: 'llm' | 'template' | 'manual';
  timestamp: Date;
};

/**
 * Renders commentary state, manual speech controls, and recent commentary history.
 *
 * @param props - Current commentary state and game ID for control actions
 * @returns React commentary control panel
 */
export const CommentaryPanel: React.FC<Props> = ({
  commentaryState,
  gameId,
}) => {
  const [muted, setMuted] = useState(false);
  const [manualText, setManualText] = useState('');
  const [commentaryLog, setCommentaryLog] = useState<LogEntry[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Sync state and log commentary
  useEffect(() => {
    if (!commentaryState.currentText) return;

    // Check if duplicate
    const isDuplicate = commentaryLog.some(
      (entry) => entry.text === commentaryState.currentText
    );
    if (isDuplicate) return;

    const newEntry: LogEntry = {
      id: `${commentaryState.historyId || Date.now()}`,
      text: commentaryState.currentText,
      source: commentaryState.source,
      timestamp: new Date(),
    };

    setCommentaryLog((prev) => [...prev, newEntry].slice(-50)); // Keep the log bounded for long games.
  }, [commentaryState]);

  // Autoscroll
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [commentaryLog]);

  const handleMuteToggle = async () => {
    try {
      const nextMuted = !muted;
      setMuted(nextMuted);
      await controlCommentary(gameId, nextMuted ? 'mute' : 'unmute');
    } catch (e) {
      console.error(e);
    }
  };

  const handleRegenerate = async () => {
    try {
      await controlCommentary(gameId, 'regenerate');
    } catch (e) {
      console.error(e);
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualText.trim()) return;

    try {
      await controlCommentary(gameId, 'manual', manualText);
      setManualText('');
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="card commentary-card">
      <div className="commentary-header">
        <h3>AI Commentary announcer</h3>
        <button 
          className={`btn-mute-toggle ${muted ? 'muted' : 'unmuted'}`}
          onClick={handleMuteToggle}
        >
          {muted ? '🔇 Muted' : '🔊 Announcer ON'}
        </button>
      </div>

      {/* Commentary Log Feed */}
      <div className="commentary-feed-container">
        {commentaryLog.length === 0 ? (
          <div className="empty-state">Announcer is listening for plays...</div>
        ) : (
          commentaryLog.map((entry) => (
            <div key={entry.id} className={`log-entry source-${entry.source}`}>
              <div className="log-entry-header">
                <span className="source-tag">{entry.source.toUpperCase()}</span>
                <span className="timestamp">
                  {entry.timestamp.toLocaleTimeString()}
                </span>
              </div>
              <div className="log-entry-text">{entry.text}</div>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>

      {/* Status Bar */}
      <div className={`commentary-status-row status-${commentaryState.status}`}>
        <span className="status-dot animate-pulse" />
        <span className="status-label">
          {commentaryState.status === 'generating' && 'Thinking... (Ollama LLM)'}
          {commentaryState.status === 'speaking' && 'Speaking... (Piper TTS)'}
          {commentaryState.status === 'idle' && 'Idle (Awaiting event)'}
        </span>
      </div>

      {/* Controls Form */}
      <div className="commentary-controls">
        <form onSubmit={handleManualSubmit} className="manual-commentary-form">
          <input 
            type="text" 
            placeholder="Type custom announcement..."
            value={manualText}
            onChange={(e) => setManualText(e.target.value)}
          />
          <button type="submit" className="btn-manual-speak">Speak</button>
        </form>
        
        <button className="btn-regenerate" onClick={handleRegenerate}>
          🔄 Re-generate Play Call
        </button>
      </div>
    </div>
  );
};
