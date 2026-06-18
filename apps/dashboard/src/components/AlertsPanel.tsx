/**
 * @file apps/dashboard/src/components/AlertsPanel.tsx
 * @layer Frontend — Manager Approval UI
 * @description Displays low-confidence CV alerts and pending command approvals so
 *              an operator can confirm or reject automation before it runs.
 * @dependencies AlertItem types from sseClient, dashboard command callbacks
 */

import type { AlertItem } from '../api/sseClient';

/** Props for the alerts and manager approval panel. */
type Props = {
  alerts: AlertItem[];
  pendingCommands: any[];
  onResolveAlert: (alertId: string, action: 'confirm' | 'override') => void;
  onApproveCommand: (cmdId: string) => void;
  onCancelCommand: (cmdId: string) => void;
};

/**
 * Renders unresolved alerts, resolved alert history, and command approval cards.
 *
 * @param props - Alert lists and callbacks for resolving alerts/commands
 * @returns React panel for operator review workflow
 */
export const AlertsPanel: React.FC<Props> = ({
  alerts,
  pendingCommands,
  onResolveAlert,
  onApproveCommand,
  onCancelCommand,
}) => {
  const activeAlerts = alerts.filter(a => !a.resolved);
  const resolvedAlerts = alerts.filter(a => a.resolved);

  return (
    <div className="card alerts-panel-card">
      <h3>Alerts & Manager Approvals</h3>

      {/* Production Command Approval Gate */}
      {pendingCommands.length > 0 && (
        <div className="command-approvals-section">
          <h4>Awaiting Manager Approval</h4>
          {pendingCommands.map((cmd) => (
            <div key={cmd.command_id} className="approval-card animate-pulse-subtle">
              <div className="card-header">
                <span className="approval-pill">GATE</span>
                <span className="cmd-type">{cmd.command_type.toUpperCase().replace(/_/g, ' ')}</span>
              </div>
              <div className="approval-message">
                Target: {cmd.target} · Priority: {cmd.priority}
                {cmd.payload && (
                  <pre className="payload-json">{JSON.stringify(cmd.payload)}</pre>
                )}
              </div>
              <div className="approval-actions">
                <button 
                  className="btn-approve" 
                  onClick={() => onApproveCommand(cmd.command_id)}
                >
                  ✓ Approve
                </button>
                <button 
                  className="btn-deny" 
                  onClick={() => onCancelCommand(cmd.command_id)}
                >
                  ✗ Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Low-confidence CV alerts */}
      <div className="alerts-section">
        <h4>Active System Alerts</h4>
        {activeAlerts.length === 0 ? (
          <div className="empty-state">No active system alerts</div>
        ) : (
          activeAlerts.map((alert) => (
            <div key={alert.id} className="alert-card animate-shake-subtle">
              <div className="alert-header">
                <span className="alert-pill alert-warn">⚠️ CV CONFIDENCE LOW</span>
                <span className="conf-value">{(alert.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="alert-msg">{alert.message}</div>
              <div className="alert-actions">
                <button 
                  className="btn-confirm" 
                  onClick={() => onResolveAlert(alert.id, 'confirm')}
                >
                  Confirm (Allow)
                </button>
                <button 
                  className="btn-override" 
                  onClick={() => onResolveAlert(alert.id, 'override')}
                >
                  Override (Substitute)
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Resolved Alerts List */}
      {resolvedAlerts.length > 0 && (
        <div className="resolved-alerts-section">
          <h4>Resolved Logs</h4>
          <div className="resolved-list">
            {resolvedAlerts.slice(0, 5).map((alert) => (
              <div key={alert.id} className="resolved-row">
                <span className="check">✓</span>
                <span className="text">{alert.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
