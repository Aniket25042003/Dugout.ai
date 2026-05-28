package main

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/Aniket25042003/Dugout/services/event-gateway/internal/db"
	"github.com/Aniket25042003/Dugout/services/event-gateway/internal/server"
	_ "github.com/lib/pq"
	"github.com/nats-io/nats.go"
)

type Config struct {
	Port    string
	NatsURL string
	DbURL   string
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
	var dbConn *sql.DB
	for i := 0; i < 5; i++ {
		dbConn, err = sql.Open("postgres", cfg.DbURL)
		if err == nil {
			err = dbConn.Ping()
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
	defer dbConn.Close()
	log.Println("Connected to database successfully.")

	// 4. Initialize components
	eventDb := db.New(dbConn)
	gatewayServer := server.New(eventDb, nc)

	if err := gatewayServer.Start(context.Background()); err != nil {
		log.Fatalf("Failed to start gateway NATS subscriber: %v", err)
	}
	defer gatewayServer.Stop()

	// 5. Setup routes
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy","service":"event-gateway"}`))
	})

	http.HandleFunc("/api/v1/events", gatewayServer.IngestEvent)
	http.HandleFunc("/api/v1/games/stream", gatewayServer.SSEStream)

	serverHttp := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: nil,
	}

	// Start server in background
	go func() {
		log.Printf("HTTP Server listening on port %s", cfg.Port)
		if err := serverHttp.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("ListenAndServe failed: %v", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down Event Gateway...")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	if err := serverHttp.Shutdown(ctx); err != nil {
		log.Printf("HTTP server Shutdown failed: %v", err)
	}
	log.Println("Event Gateway stopped.")
}

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}
