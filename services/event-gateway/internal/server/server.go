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

type Server struct {
	db        *db.Database
	nc        *nats.Conn
	sse       *SSEBroker
	games     map[string]*dugoutv1.GameState
	gamesMu   sync.RWMutex
	natsSub   *nats.Subscription
}

func New(database *db.Database, natsConn *nats.Conn) *Server {
	return &Server{
		db:    database,
		nc:    natsConn,
		sse:   NewSSEBroker(),
		games: make(map[string]*dugoutv1.GameState),
	}
}

func (s *Server) Start(ctx context.Context) error {
	// Subscribe to all game events from NATS
	sub, err := s.nc.Subscribe("dugout.game.*.events", func(msg *nats.Msg) {
		s.handleNatsEvent(msg)
	})
	if err != nil {
		return err
	}
	s.natsSub = sub
	log.Println("Subscribed to NATS subject: dugout.game.*.events")
	return nil
}

func (s *Server) Stop() {
	if s.natsSub != nil {
		s.natsSub.Unsubscribe()
	}
}

// IngestEvent handles HTTP POST /api/v1/events from referee app
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

	// Server enrichment
	event.ReceivedAt = timestamppb.Now()

	// 1. Write to Postgres
	if err := s.db.SaveGameEvent(r.Context(), &event); err != nil {
		log.Printf("Failed to save event in DB: %v", err)
		http.Error(w, "Database error saving event", http.StatusInternalServerError)
		return
	}

	// 2. Publish to NATS
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

// SSEStream upgrades connection and streams events + state for a game
func (s *Server) SSEStream(w http.ResponseWriter, r *http.Request) {
	gameID := r.URL.Query().Get("game_id")
	if gameID == "" {
		http.Error(w, "Missing game_id query param", http.StatusBadRequest)
		return
	}

	// Fetch historical events to build replay payload
	events, err := s.db.GetGameEvents(r.Context(), gameID)
	if err != nil {
		log.Printf("Failed to retrieve game events for replay: %v", err)
		http.Error(w, "Database error replaying state", http.StatusInternalServerError)
		return
	}

	// Replay events to compute current starting state for this connection
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
			"event": nil,
			"state": json.RawMessage(stateJSON),
		}
		frameBytes, _ := json.Marshal(frame)
		initialMsgs = append(initialMsgs, frameBytes)
	}

	s.sse.ServeHTTPWithInitial(w, r, initialMsgs)
}

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

	// Marshal both event and new state into a single frame and broadcast
	eventJSON, _ := protojson.Marshal(&event)
	stateJSON, _ := protojson.Marshal(newState)

	frame := map[string]interface{}{
		"event": json.RawMessage(eventJSON),
		"state": json.RawMessage(stateJSON),
	}
	frameBytes, _ := json.Marshal(frame)
	s.sse.Broadcast(frameBytes)
}

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
