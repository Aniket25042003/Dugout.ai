// File: services/event-gateway/internal/server/sse.go
// Layer: API Gateway — Server-Sent Events Broker
// Purpose: Tracks connected dashboard SSE clients and broadcasts replay/live frames.
// Dependencies: net/http streaming, sync locks, per-client buffered channels.
package server

import (
	"log"
	"net/http"
	"sync"
)

// SSEBroker manages connected SSE clients and non-blocking broadcasts.
type SSEBroker struct {
	clients    map[chan []byte]bool
	clientsMu  sync.RWMutex
	register   chan chan []byte
	unregister chan chan []byte
}

// NewSSEBroker creates and starts an SSE broker.
func NewSSEBroker() *SSEBroker {
	broker := &SSEBroker{
		clients:    make(map[chan []byte]bool),
		register:   make(chan chan []byte),
		unregister: make(chan chan []byte),
	}
	go broker.listen()
	return broker
}

// listen serializes client registration and unregistration.
func (b *SSEBroker) listen() {
	for {
		select {
		case client := <-b.register:
			b.clientsMu.Lock()
			b.clients[client] = true
			b.clientsMu.Unlock()
			log.Println("New SSE client registered.")

		case client := <-b.unregister:
			b.clientsMu.Lock()
			if _, ok := b.clients[client]; ok {
				delete(b.clients, client)
				close(client)
				log.Println("SSE client unregistered.")
			}
			b.clientsMu.Unlock()
		}
	}
}

// Broadcast sends a message to every connected SSE client without blocking on slow clients.
func (b *SSEBroker) Broadcast(msg []byte) {
	b.clientsMu.RLock()
	defer b.clientsMu.RUnlock()
	for client := range b.clients {
		select {
		case client <- msg:
		default:
			// Drop the frame for a slow client rather than blocking live updates globally.
		}
	}
}

// ServeHTTPWithInitial writes replay frames, registers the client, and streams live frames.
func (b *SSEBroker) ServeHTTPWithInitial(w http.ResponseWriter, r *http.Request, initialMessages [][]byte) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Historical replay gives a newly opened dashboard the same state as long-lived clients.
	for _, msg := range initialMessages {
		_, err := w.Write([]byte("data: "))
		if err != nil {
			return
		}
		w.Write(msg)
		w.Write([]byte("\n\n"))
	}
	flusher.Flush()

	// Buffered channel smooths brief client/network stalls without blocking Broadcast.
	messageChan := make(chan []byte, 10)
	b.register <- messageChan

	defer func() {
		b.unregister <- messageChan
	}()

	notify := r.Context().Done()

	for {
		select {
		case <-notify:
			return
		case msg, ok := <-messageChan:
			if !ok {
				return
			}
			_, err := w.Write([]byte("data: "))
			if err != nil {
				return
			}
			w.Write(msg)
			w.Write([]byte("\n\n"))
			flusher.Flush()
		}
	}
}
