/**
 * @file apps/dashboard/src/components/ScoreboardCompact.tsx
 * @layer Frontend — Live Scoreboard UI
 * @description Displays score, inning, count, outs, and occupied bases from reduced
 *              game state.
 * @dependencies GameState from sseClient
 */

import React from 'react';
import type { GameState } from '../api/sseClient';

/** Props for the compact scoreboard component. */
type Props = {
  gameState: GameState;
  homeTeamName?: string;
  awayTeamName?: string;
};

/**
 * Renders the live scoreboard and base runner diamond.
 *
 * @param props - Game state plus optional team display names
 * @returns React scoreboard card
 */
export const ScoreboardCompact: React.FC<Props> = ({
  gameState,
  homeTeamName = "ASHLAND A's",
  awayTeamName = "GIANTS",
}) => {
  const { homeScore, awayScore, inning, isTop, balls, strikes, outs } = gameState;

  return (
    <div className="card scoreboard-card">
      <h3>Live Scoreboard</h3>
      <div className="score-row">
        <div className="team-score-col away">
          <div className="team-name">{awayTeamName}</div>
          <div className="score-value">{awayScore}</div>
        </div>
        <div className="inning-col">
          <div className="inning-indicator">
            <span className="arrow">{isTop ? '▲' : '▼'}</span>
            <span className="number">{inning}</span>
          </div>
          <div className="inning-label">{isTop ? 'Top' : 'Bot'}</div>
        </div>
        <div className="team-score-col home">
          <div className="team-name">{homeTeamName}</div>
          <div className="score-value">{homeScore}</div>
        </div>
      </div>

      <div className="bso-count-row">
        <div className="count-item balls">
          <span className="label">B</span>
          <div className="indicators">
            {[1, 2, 3].map((i) => (
              <span key={i} className={`dot ${balls >= i ? 'active' : ''}`} />
            ))}
          </div>
        </div>
        <div className="count-item strikes">
          <span className="label">S</span>
          <div className="indicators">
            {[1, 2].map((i) => (
              <span key={i} className={`dot ${strikes >= i ? 'active' : ''}`} />
            ))}
          </div>
        </div>
        <div className="count-item outs">
          <span className="label">O</span>
          <div className="indicators">
            {[1, 2].map((i) => (
              <span key={i} className={`dot ${outs >= i ? 'active' : ''}`} />
            ))}
          </div>
        </div>
      </div>

      <div className="runners-diamond-container">
        <div className="diamond">
          <div className={`base second ${gameState.runnerOnSecond ? 'occupied' : ''}`} title="Second Base" />
          <div className={`base third ${gameState.runnerOnThird ? 'occupied' : ''}`} title="Third Base" />
          <div className={`base first ${gameState.runnerOnFirst ? 'occupied' : ''}`} title="First Base" />
        </div>
      </div>
    </div>
  );
};
