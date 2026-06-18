// File: services/event-gateway/internal/server/server.go
// Layer: API Gateway — HTTP/SSE/NATS Server
// Purpose: Handles event ingestion, replayable SSE streams, in-memory game state,
// and NATS fan-in for production status updates.
// Dependencies: internal db/reducer packages, NATS, protojson, net/http.
package server

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/Aniket25042003/Dugout/packages/contracts/go/dugout/v1"
	"github.com/Aniket25042003/Dugout/services/event-gateway/internal/db"
	"github.com/Aniket25042003/Dugout/services/event-gateway/internal/reducer"
	"github.com/nats-io/nats.go"
	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Server coordinates HTTP handlers, NATS subscriptions, SSE broadcasting, and cached state.
type Server struct {
	db       *db.Database
	nc       *nats.Conn
	sse      *SSEBroker
	games    map[string]*dugoutv1.GameState
	gamesMu  sync.RWMutex
	natsSubs []*nats.Subscription
}

// New constructs a gateway server with an empty game-state cache and SSE broker.
func New(database *db.Database, natsConn *nats.Conn) *Server {
	return &Server{
		db:    database,
		nc:    natsConn,
		sse:   NewSSEBroker(),
		games: make(map[string]*dugoutv1.GameState),
	}
}

// Start subscribes to NATS subjects that should be forwarded to dashboard SSE clients.
func (s *Server) Start(ctx context.Context) error {
	// Game events drive reducer state and timeline updates.
	sub, err := s.nc.Subscribe("dugout.game.*.events", func(msg *nats.Msg) {
		s.handleNatsEvent(msg)
	})
	if err != nil {
		return err
	}
	s.natsSubs = append(s.natsSubs, sub)
	log.Println("Subscribed to NATS subject: dugout.game.*.events")

	// Production state subjects are forwarded as typed SSE frames.
	subMusic, err := s.nc.Subscribe("dugout.production.music.state", func(msg *nats.Msg) {
		s.handleMusicState(msg)
	})
	if err == nil {
		s.natsSubs = append(s.natsSubs, subMusic)
		log.Println("Subscribed to NATS subject: dugout.production.music.state")
	}

	// Subscribe to production graphics state
	subGraphics, err := s.nc.Subscribe("dugout.production.graphics.state", func(msg *nats.Msg) {
		s.handleGraphicsState(msg)
	})
	if err == nil {
		s.natsSubs = append(s.natsSubs, subGraphics)
		log.Println("Subscribed to NATS subject: dugout.production.graphics.state")
	}

	// Subscribe to production commentary state
	subCommentary, err := s.nc.Subscribe("dugout.production.commentary.state", func(msg *nats.Msg) {
		s.handleCommentaryState(msg)
	})
	if err == nil {
		s.natsSubs = append(s.natsSubs, subCommentary)
		log.Println("Subscribed to NATS subject: dugout.production.commentary.state")
	}

	// Subscribe to command queue status updates
	subCommands, err := s.nc.Subscribe("dugout.commands.status", func(msg *nats.Msg) {
		s.handleCommandStatus(msg)
	})
	if err == nil {
		s.natsSubs = append(s.natsSubs, subCommands)
		log.Println("Subscribed to NATS subject: dugout.commands.status")
	}

	return nil
}

// Stop unsubscribes from all NATS subjects owned by the server.
func (s *Server) Stop() {
	for _, sub := range s.natsSubs {
		if sub != nil {
			sub.Unsubscribe()
		}
	}
}

// IngestEvent handles HTTP POST /api/v1/events from the referee app.
func (s *Server) IngestEvent(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")

	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read body", http.StatusBadRequest)
		return
	}

	var event dugoutv1.GameEvent
	if err := protojson.Unmarshal(body, &event); err != nil {
		log.Printf("Failed to unmarshal proto JSON event: %v", err)
		http.Error(w, "Invalid protobuf JSON payload", http.StatusBadRequest)
		return
	}

	// Server enrichment records when the gateway accepted the official event.
	event.ReceivedAt = timestamppb.Now()

	// Persist before publishing so replay can recover events even if NATS is transiently down.
	if err := s.db.SaveGameEvent(r.Context(), &event); err != nil {
		log.Printf("Failed to save event in DB: %v", err)
		http.Error(w, "Database error saving event", http.StatusInternalServerError)
		return
	}

	// Publish the accepted event for orchestrator automation and SSE reducer updates.
	eventJSON, err := protojson.Marshal(&event)
	if err != nil {
		http.Error(w, "Serialization error", http.StatusInternalServerError)
		return
	}

	subject := "dugout.game." + event.GameId + ".events"
	if err := s.nc.Publish(subject, eventJSON); err != nil {
		log.Printf("Failed to publish to NATS: %v", err)
		// Don't fail the request if NATS is temporarily down but database succeeded
	}

	w.WriteHeader(http.StatusCreated)
	w.Write([]byte(`{"status":"created","event_id":"` + event.EventId + `"}`))
}

// SSEStream streams historical replay frames followed by live updates for one game.
func (s *Server) SSEStream(w http.ResponseWriter, r *http.Request) {
	gameID := r.URL.Query().Get("game_id")
	if gameID == "" {
		http.Error(w, "Missing game_id query param", http.StatusBadRequest)
		return
	}

	// Fetch historical events to build a deterministic replay payload for new clients.
	events, err := s.db.GetGameEvents(r.Context(), gameID)
	if err != nil {
		log.Printf("Failed to retrieve game events for replay: %v", err)
		http.Error(w, "Database error replaying state", http.StatusInternalServerError)
		return
	}

	// Replay events to compute the current starting state for this connection.
	state := &dugoutv1.GameState{
		GameId: gameID,
		Inning: 1,
		IsTop:  true,
	}

	var initialMsgs [][]byte
	for _, evt := range events {
		state = reducer.Reduce(state, evt)

		evtJSON, _ := protojson.Marshal(evt)
		stateJSON, _ := protojson.Marshal(state)

		frame := map[string]interface{}{
			"type":  "game_state",
			"event": json.RawMessage(evtJSON),
			"state": json.RawMessage(stateJSON),
		}
		frameBytes, _ := json.Marshal(frame)
		initialMsgs = append(initialMsgs, frameBytes)
	}

	// If no events have occurred, send an initial clean state frame
	if len(initialMsgs) == 0 {
		stateJSON, _ := protojson.Marshal(state)
		frame := map[string]interface{}{
			"type":  "game_state",
			"event": nil,
			"state": json.RawMessage(stateJSON),
		}
		frameBytes, _ := json.Marshal(frame)
		initialMsgs = append(initialMsgs, frameBytes)
	}

	s.sse.ServeHTTPWithInitial(w, r, initialMsgs)
}

// handleNatsEvent reduces an accepted game event and broadcasts the new state frame.
func (s *Server) handleNatsEvent(msg *nats.Msg) {
	var event dugoutv1.GameEvent
	if err := protojson.Unmarshal(msg.Data, &event); err != nil {
		log.Printf("Error unmarshaling NATS event payload: %v", err)
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// Load state from cache or reconstruct via DB replay
	state, err := s.loadOrCreateGameState(ctx, event.GameId)
	if err != nil {
		log.Printf("Error replaying game state: %v", err)
		return
	}

	// Apply event to state
	s.gamesMu.Lock()
	newState := reducer.Reduce(state, &event)
	s.games[event.GameId] = newState
	s.gamesMu.Unlock()

	// Broadcast event and reduced state together so the dashboard updates atomically.
	eventJSON, _ := protojson.Marshal(&event)
	stateJSON, _ := protojson.Marshal(newState)

	frame := map[string]interface{}{
		"type":  "game_state",
		"event": json.RawMessage(eventJSON),
		"state": json.RawMessage(stateJSON),
	}
	frameBytes, _ := json.Marshal(frame)
	s.sse.Broadcast(frameBytes)
}

// handleMusicState forwards music adapter state as an SSE frame.
func (s *Server) handleMusicState(msg *nats.Msg) {
	frame := map[string]interface{}{
		"type": "music_state",
		"data": json.RawMessage(msg.Data),
	}
	frameBytes, _ := json.Marshal(frame)
	s.sse.Broadcast(frameBytes)
}

// handleGraphicsState forwards graphics adapter state as an SSE frame.
func (s *Server) handleGraphicsState(msg *nats.Msg) {
	frame := map[string]interface{}{
		"type": "graphics_state",
		"data": json.RawMessage(msg.Data),
	}
	frameBytes, _ := json.Marshal(frame)
	s.sse.Broadcast(frameBytes)
}

// handleCommentaryState forwards commentary engine state as an SSE frame.
func (s *Server) handleCommentaryState(msg *nats.Msg) {
	frame := map[string]interface{}{
		"type": "commentary_state",
		"data": json.RawMessage(msg.Data),
	}
	frameBytes, _ := json.Marshal(frame)
	s.sse.Broadcast(frameBytes)
}

// handleCommandStatus forwards command queue lifecycle updates as SSE frames.
func (s *Server) handleCommandStatus(msg *nats.Msg) {
	frame := map[string]interface{}{
		"type": "command_status",
		"data": json.RawMessage(msg.Data),
	}
	frameBytes, _ := json.Marshal(frame)
	s.sse.Broadcast(frameBytes)
}

// loadOrCreateGameState returns cached state or rebuilds it from stored events.
func (s *Server) loadOrCreateGameState(ctx context.Context, gameID string) (*dugoutv1.GameState, error) {
	s.gamesMu.Lock()
	defer s.gamesMu.Unlock()

	if state, ok := s.games[gameID]; ok {
		return state, nil
	}

	state := &dugoutv1.GameState{
		GameId: gameID,
		Inning: 1,
		IsTop:  true,
	}

	events, err := s.db.GetGameEvents(ctx, gameID)
	if err != nil {
		return nil, err
	}

	for _, evt := range events {
		state = reducer.Reduce(state, evt)
	}

	s.games[gameID] = state
	return state, nil
}
