package main

import (
	"flag"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/hanni/aiproxy/proxy/internal/config"
	"github.com/hanni/aiproxy/proxy/internal/handler"
	"github.com/hanni/aiproxy/proxy/internal/keypool"
	"github.com/hanni/aiproxy/proxy/internal/middleware"
	"github.com/hanni/aiproxy/proxy/internal/store"
	"github.com/hanni/aiproxy/proxy/internal/upstream"
)

func main() {
	configPath := flag.String("config", "config.yaml", "path to config file")
	flag.Parse()

	// Load config
	cfg, err := config.Load(*configPath)
	if err != nil {
		slog.Error("failed to load config", "error", err)
		os.Exit(1)
	}

	// Set log level
	var level slog.Level
	switch cfg.Logging.Level {
	case "debug":
		level = slog.LevelDebug
	case "warn":
		level = slog.LevelWarn
	case "error":
		level = slog.LevelError
	default:
		level = slog.LevelInfo
	}
	slog.SetDefault(slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: level})))

	// Init store
	db, err := store.New(cfg.Database.Path)
	if err != nil {
		slog.Error("failed to init database", "error", err)
		os.Exit(1)
	}
	defer db.Close()

	// Init key pool
	pool := keypool.New(db)

	// Init upstream client
	client := upstream.NewClient(cfg.Upstream.BaseURL, cfg.Upstream.ChatPath, cfg.Upstream.Timeout)

	// Build handler chain
	mux := http.NewServeMux()
	mux.Handle("/v1/chat/completions", handler.NewChatHandler(pool, client, db, cfg.ModelMap, cfg.Upstream.MaxRetries))
	mux.Handle("/v1/models", handler.NewModelsHandler(cfg.ModelMap))
	mux.Handle("/health", handler.NewHealthHandler(pool))

	// Apply middleware
	var h http.Handler = mux
	h = middleware.Logger(h)
	h = middleware.Auth(cfg.Server.AuthToken)(h)

	// Start server
	active, _ := pool.Stats()
	slog.Info("aiproxy started",
		"addr", cfg.Server.Addr,
		"upstream", cfg.Upstream.BaseURL,
		"active_keys", active,
	)

	server := &http.Server{
		Addr:    cfg.Server.Addr,
		Handler: h,
	}

	// Graceful shutdown
	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		<-sigCh
		slog.Info("shutting down...")
		server.Close()
	}()

	if err := server.ListenAndServe(); err != http.ErrServerClosed {
		slog.Error("server error", "error", err)
		os.Exit(1)
	}
}
