package server

import (
	"log"
	"net/http"
	"sync"
)

type SSEBroker struct {
	clients    map[chan []byte]bool
	clientsMu  sync.RWMutex
	register   chan chan []byte
	unregister chan chan []byte
}

func NewSSEBroker() *SSEBroker {
	broker := &SSEBroker{
		clients:    make(map[chan []byte]bool),
		register:   make(chan chan []byte),
		unregister: make(chan chan []byte),
	}
	go broker.listen()
	return broker
}

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

func (b *SSEBroker) Broadcast(msg []byte) {
	b.clientsMu.RLock()
	defer b.clientsMu.RUnlock()
	for client := range b.clients {
		select {
		case client <- msg:
		default:
			// Prevent blocking if a client is slow
		}
	}
}

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

	// 1. Flush historical replayed events/state to the client first
	for _, msg := range initialMessages {
		_, err := w.Write([]byte("data: "))
		if err != nil {
			return
		}
		w.Write(msg)
		w.Write([]byte("\n\n"))
	}
	flusher.Flush()

	// 2. Register for real-time updates
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
