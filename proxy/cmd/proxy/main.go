package main

import (
	"context"
	"flag"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/novellaxai/novellaxai/proxy/internal/config"
	"github.com/novellaxai/novellaxai/proxy/internal/handler"
	"github.com/novellaxai/novellaxai/proxy/internal/healthcheck"
	"github.com/novellaxai/novellaxai/proxy/internal/keypool"
	"github.com/novellaxai/novellaxai/proxy/internal/middleware"
	"github.com/novellaxai/novellaxai/proxy/internal/refresher"
	"github.com/novellaxai/novellaxai/proxy/internal/store"
	"github.com/novellaxai/novellaxai/proxy/internal/upstream"
)

func main() {
	configPath := flag.String("config", "config.yaml", "path to config file")
	flag.Parse()

	// Track server start time
	startTime := time.Now()

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
	if cfg.KeyPool.CircuitBreakerCooldown > 0 {
		pool.SetCooldown(cfg.KeyPool.CircuitBreakerCooldown)
	}

	// Init upstream client
	client := upstream.NewClient(cfg.Upstream.BaseURL, cfg.Upstream.ChatPath, cfg.Upstream.Timeout)

	// Build handler chain
	mux := http.NewServeMux()
	mux.Handle("/v1/chat/completions", handler.NewChatHandler(pool, client, db, cfg.ModelMap, cfg.Upstream.MaxRetries))
	mux.Handle("/v1/models", handler.NewModelsHandler(cfg.ModelMap))
	mux.Handle("/health", handler.NewHealthHandler(pool))
	mux.Handle("/api/dashboard", handler.NewDashboardHandler(pool, db, startTime))
	mux.Handle("/api/sessions", handler.NewSessionsHandler(db))
	mux.Handle("/api/sessions/", handler.NewSessionsHandler(db))
	mux.Handle("/api/sessions/login", handler.NewLoginHandler(db))
	mux.Handle("/api/sessions/login-status", handler.NewLoginStatusHandler(db))
	mux.Handle("/api/sessions/login-logs", handler.NewLoginLogsHandler())

	// Serve dashboard static files from ../dashboard/dist/
	// Resolve relative to the executable location
	exePath, _ := os.Executable()
	exeDir := filepath.Dir(exePath)
	dashboardDir := filepath.Join(exeDir, "..", "dashboard", "dist")
	// Fallback: try relative to working directory
	if _, err := os.Stat(dashboardDir); os.IsNotExist(err) {
		dashboardDir = filepath.Join(".", "..", "dashboard", "dist")
	}
	fs := http.FileServer(http.Dir(dashboardDir))
	mux.Handle("/", fs)

	// Apply middleware — skip auth for /api/, /health, and static files
	var h http.Handler = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip auth for dashboard API, health, and static files
		if strings.HasPrefix(r.URL.Path, "/api/") ||
			r.URL.Path == "/health" ||
			!strings.HasPrefix(r.URL.Path, "/v1/") {
			middleware.Logger(mux).ServeHTTP(w, r)
			return
		}
		// Apply auth only for /v1/ routes
		middleware.Logger(middleware.Auth(cfg.Server.AuthToken)(mux)).ServeHTTP(w, r)
	})

	// Context for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start token refresher
	if cfg.Refresher.Enabled {
		ref := refresher.New(db, cfg.Refresher, cfg.Upstream.BaseURL)
		go ref.Start(ctx)
	}

	// Start health checker (validate keys every 5 minutes)
	hc := healthcheck.New(db, 5*time.Minute)
	go hc.Start(ctx)

	// Start server
	active, _ := pool.Stats()
	slog.Info("NovellaxAI started",
		"addr", cfg.Server.Addr,
		"upstream", cfg.Upstream.BaseURL,
		"active_keys", active,
		"dashboard", dashboardDir,
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
		cancel()
		server.Close()
	}()

	if err := server.ListenAndServe(); err != http.ErrServerClosed {
		slog.Error("server error", "error", err)
		os.Exit(1)
	}
}
