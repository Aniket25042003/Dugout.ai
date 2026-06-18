// File: services/event-gateway/internal/db/db.go
// Layer: Data Access — Event Gateway Persistence
// Purpose: Persists protobuf game events to Postgres and rehydrates event history
// for SSE replay and state reconstruction.
// Dependencies: database/sql, protojson, timestamppb, generated Go contracts.
package db

import (
	"context"
	"database/sql"
	"time"

	"github.com/Aniket25042003/Dugout/packages/contracts/go/dugout/v1"
	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Database wraps the shared SQL connection used by gateway handlers.
type Database struct {
	db *sql.DB
}

// New creates a Database around an existing sql.DB connection.
func New(db *sql.DB) *Database {
	return &Database{db: db}
}

// SaveGameEvent stores an official game event and its typed payload as JSON.
func (d *Database) SaveGameEvent(ctx context.Context, event *dugoutv1.GameEvent) error {
	occurredAt := event.OccurredAt.AsTime()
	receivedAt := event.ReceivedAt.AsTime()

	var eventType string
	var payloadBytes []byte
	var err error

	if event.Payload != nil {
		// Store the protobuf oneof discriminator as a queryable event_type column.
		switch p := event.Payload.(type) {
		case *dugoutv1.GameEvent_PitchResult:
			eventType = "pitch_result"
			payloadBytes, err = protojson.Marshal(p.PitchResult)
		case *dugoutv1.GameEvent_PlayOutcome:
			eventType = "play_outcome"
			payloadBytes, err = protojson.Marshal(p.PlayOutcome)
		case *dugoutv1.GameEvent_InningTransition:
			eventType = "inning_transition"
			payloadBytes, err = protojson.Marshal(p.InningTransition)
		case *dugoutv1.GameEvent_Substitution:
			eventType = "substitution"
			payloadBytes, err = protojson.Marshal(p.Substitution)
		case *dugoutv1.GameEvent_ClockControl:
			eventType = "clock_control"
			payloadBytes, err = protojson.Marshal(p.ClockControl)
		case *dugoutv1.GameEvent_Correction:
			eventType = "correction"
			payloadBytes, err = protojson.Marshal(p.Correction)
		case *dugoutv1.GameEvent_ManualOverride:
			eventType = "manual_override"
			payloadBytes, err = protojson.Marshal(p.ManualOverride)
		default:
			eventType = "unknown"
		}
	} else {
		eventType = "unknown"
	}

	if err != nil {
		return err
	}
	if len(payloadBytes) == 0 {
		payloadBytes = []byte("{}")
	}

	// Inserts the immutable event log row used for replay and audit.
	query := `
		INSERT INTO game_events (
			event_id, game_id, source, source_device_id, event_type, 
			occurred_at, received_at, sequence, payload, confidence, 
			authority, correlation_id
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`
	_, err = d.db.ExecContext(
		ctx, query,
		event.EventId, event.GameId, event.Source, event.SourceDeviceId,
		eventType, occurredAt, receivedAt, event.Sequence,
		payloadBytes, event.Confidence, event.Authority, event.CorrelationId,
	)
	return err
}

// GetGameEvents loads a game's events in replay order and rebuilds protobuf payloads.
func (d *Database) GetGameEvents(ctx context.Context, gameID string) ([]*dugoutv1.GameEvent, error) {
	// Sequence is primary ordering; occurred_at provides a stable fallback for equal sequence.
	query := `
		SELECT event_id, game_id, source, source_device_id, event_type, 
		       occurred_at, received_at, sequence, payload, confidence, 
		       authority, correlation_id
		FROM game_events
		WHERE game_id = $1
		ORDER BY sequence ASC, occurred_at ASC
	`
	rows, err := d.db.QueryContext(ctx, query, gameID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var events []*dugoutv1.GameEvent
	for rows.Next() {
		var (
			eventID, gameIdVal, source, sourceDeviceID, eventType, authority, correlationID string
			occurredAt, receivedAt                                                          time.Time
			sequence                                                                        int64
			confidence                                                                      float64
			payloadJSON                                                                     []byte
		)
		err := rows.Scan(
			&eventID, &gameIdVal, &source, &sourceDeviceID, &eventType,
			&occurredAt, &receivedAt, &sequence, &payloadJSON, &confidence,
			&authority, &correlationID,
		)
		if err != nil {
			return nil, err
		}

		evt := &dugoutv1.GameEvent{
			EventId:        eventID,
			GameId:         gameIdVal,
			Source:         source,
			SourceDeviceId: sourceDeviceID,
			Sequence:       sequence,
			Confidence:     confidence,
			Authority:      authority,
			CorrelationId:  correlationID,
			OccurredAt:     timestamppb.New(occurredAt),
			ReceivedAt:     timestamppb.New(receivedAt),
		}

		if len(payloadJSON) > 0 {
			// Rehydrate the stored JSON payload into the protobuf oneof matching event_type.
			switch eventType {
			case "pitch_result":
				var p dugoutv1.PitchResultPayload
				if err := protojson.Unmarshal(payloadJSON, &p); err == nil {
					evt.Payload = &dugoutv1.GameEvent_PitchResult{PitchResult: &p}
				}
			case "play_outcome":
				var p dugoutv1.PlayOutcomePayload
				if err := protojson.Unmarshal(payloadJSON, &p); err == nil {
					evt.Payload = &dugoutv1.GameEvent_PlayOutcome{PlayOutcome: &p}
				}
			case "inning_transition":
				var p dugoutv1.InningTransitionPayload
				if err := protojson.Unmarshal(payloadJSON, &p); err == nil {
					evt.Payload = &dugoutv1.GameEvent_InningTransition{InningTransition: &p}
				}
			case "substitution":
				var p dugoutv1.SubstitutionPayload
				if err := protojson.Unmarshal(payloadJSON, &p); err == nil {
					evt.Payload = &dugoutv1.GameEvent_Substitution{Substitution: &p}
				}
			case "clock_control":
				var p dugoutv1.ClockControlPayload
				if err := protojson.Unmarshal(payloadJSON, &p); err == nil {
					evt.Payload = &dugoutv1.GameEvent_ClockControl{ClockControl: &p}
				}
			case "correction":
				var p dugoutv1.GameCorrectionPayload
				if err := protojson.Unmarshal(payloadJSON, &p); err == nil {
					evt.Payload = &dugoutv1.GameEvent_Correction{Correction: &p}
				}
			case "manual_override":
				var p dugoutv1.ManualOverridePayload
				if err := protojson.Unmarshal(payloadJSON, &p); err == nil {
					evt.Payload = &dugoutv1.GameEvent_ManualOverride{ManualOverride: &p}
				}
			}
		}

		events = append(events, evt)
	}

	return events, nil
}
