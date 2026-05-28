package main

import (
	"database/sql"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/lib/pq"
	"github.com/nats-io/nats.go"
)

type Config struct {
	Port     string
	NatsURL  string
	DbURL    string
}

func main() {
	log.Println("Starting Dugout.ai Event Gateway...")

	// 1. Load config
	cfg := Config{
		Port:    getEnv("EVENT_GATEWAY_PORT", "8080"),
		NatsURL: getEnv("NATS_URL", "nats://localhost:4222"),
		DbURL:   getEnv("DATABASE_URL", "postgres://dugout_admin:dugout_secret@localhost:5432/dugout?sslmode=disable"),
	}

	// 2. Connect to NATS
	var nc *nats.Conn
	var err error
	for i := 0; i < 5; i++ {
		nc, err = nats.Connect(cfg.NatsURL)
		if err == nil {
			break
		}
		log.Printf("Failed to connect to NATS (attempt %d/5): %v. Retrying in 2s...", i+1, err)
		time.Sleep(2 * time.Second)
	}
	if err != nil {
		log.Fatalf("Could not connect to NATS: %v", err)
	}
	defer nc.Close()
	log.Printf("Connected to NATS at %s", cfg.NatsURL)

	// 3. Connect to Database
	var db *sql.DB
	for i := 0; i < 5; i++ {
		db, err = sql.Open("postgres", cfg.DbURL)
		if err == nil {
			err = db.Ping()
			if err == nil {
				break
			}
		}
		log.Printf("Failed to connect to DB (attempt %d/5): %v. Retrying in 2s...", i+1, err)
		time.Sleep(2 * time.Second)
	}
	if err != nil {
		log.Fatalf("Could not connect to database: %v", err)
	}
	defer db.Close()
	log.Println("Connected to database successfully.")

	// 4. Setup routes
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy","service":"event-gateway"}`))
	})

	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		// Placeholder for WebSocket handler
		w.WriteHeader(http.StatusNotImplemented)
		w.Write([]byte("WebSocket handler not implemented yet"))
	})

	http.HandleFunc("/events", func(w http.ResponseWriter, r *http.Request) {
		// Placeholder for Server-Sent Events handler
		w.WriteHeader(http.StatusNotImplemented)
		w.Write([]byte("SSE events handler not implemented yet"))
	})

	server := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: nil,
	}

	// Start server in background
	go func() {
		log.Printf("HTTP Server listening on port %s", cfg.Port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("ListenAndServe failed: %v", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down Event Gateway...")
	server.Close()
	log.Println("Event Gateway stopped.")
}

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}
