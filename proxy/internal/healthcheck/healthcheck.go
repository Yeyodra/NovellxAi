package healthcheck

import (
	"bytes"
	"context"
	"crypto/rand"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/novellaxai/novellaxai/proxy/internal/store"
)

const (
	StatusActive    = "active"
	StatusBanned    = "banned"
	StatusExhausted = "exhausted"
	StatusExpired   = "expired"

	codebuddyURL = "https://www.codebuddy.ai/v2/chat/completions"

	// Minimal request body to validate a key with minimal credit usage.
	healthCheckBody = `{"model":"default-model-lite","messages":[{"role":"system","content":"hi"},{"role":"user","content":"hi"}],"stream":false,"temperature":1,"max_tokens":1}`
)

// HealthChecker periodically validates all active sessions.
type HealthChecker struct {
	store    *store.Store
	interval time.Duration
	client   *http.Client
}

// New creates a HealthChecker that checks sessions every interval.
func New(s *store.Store, interval time.Duration) *HealthChecker {
	return &HealthChecker{
		store:    s,
		interval: interval,
		client: &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        10,
				MaxIdleConnsPerHost: 5,
				IdleConnTimeout:     60 * time.Second,
			},
		},
	}
}

// Start runs the health check loop. Blocks until ctx is cancelled.
func (h *HealthChecker) Start(ctx context.Context) {
	slog.Info("health checker started", "interval", h.interval)

	ticker := time.NewTicker(h.interval)
	defer ticker.Stop()

	// Run once immediately on start.
	h.checkAll(ctx)

	for {
		select {
		case <-ctx.Done():
			slog.Info("health checker stopped")
			return
		case <-ticker.C:
			h.checkAll(ctx)
		}
	}
}

func (h *HealthChecker) checkAll(ctx context.Context) {
	sessions := h.store.GetAllSessions()
	checked := 0

	for _, sess := range sessions {
		if ctx.Err() != nil {
			return
		}

		// Only check sessions that might still be usable.
		if sess.Status != StatusActive && sess.Status != StatusBanned {
			continue
		}

		// Must have some credential to check.
		if sess.ApiKey == "" && sess.JWTToken == "" {
			continue
		}

		newStatus := h.CheckSession(&sess)
		if newStatus != "" && newStatus != sess.Status {
			slog.Info("health check", "email", sess.Email, "old_status", sess.Status, "new_status", newStatus)
			h.updateStatus(sess.ID, newStatus)
		}

		checked++

		// 3-second delay between sessions to avoid spamming CodeBuddy.
		select {
		case <-ctx.Done():
			return
		case <-time.After(3 * time.Second):
		}
	}

	if checked > 0 {
		slog.Info("health check cycle complete", "checked", checked)
	}
}

// CheckSession validates a session's API key/JWT against CodeBuddy.
// Returns the detected status or empty string if status should not change.
func (h *HealthChecker) CheckSession(sess *store.Session) string {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, codebuddyURL, bytes.NewReader([]byte(healthCheckBody)))
	if err != nil {
		slog.Error("health check: create request", "error", err, "email", sess.Email)
		return ""
	}

	// Set auth header — prefer API key over JWT.
	if sess.ApiKey != "" {
		req.Header.Set("Authorization", "Bearer "+sess.ApiKey)
	} else {
		req.Header.Set("Authorization", sess.JWTToken)
		if sess.UserID != "" {
			req.Header.Set("X-User-Id", sess.UserID)
		}
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-IDE-Name", "CLI")
	req.Header.Set("X-IDE-Type", "CLI")
	req.Header.Set("X-IDE-Version", "2.95.0")
	req.Header.Set("X-Product", "SaaS")
	req.Header.Set("x-codebuddy-request", "1")
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("X-Domain", "www.codebuddy.ai")
	req.Header.Set("X-Conversation-ID", genUUID())
	req.Header.Set("X-Conversation-Message-ID", genHex(16))
	req.Header.Set("X-Request-ID", genHex(16))
	req.Header.Set("X-Agent-Intent", "craft")
	req.Header.Set("X-Agent-Purpose", "conversation")
	req.Header.Set("User-Agent", "CLI/2.95.0 CodeBuddy/2.95.0")

	resp, err := h.client.Do(req)
	if err != nil {
		slog.Warn("health check: request failed", "error", err, "email", sess.Email)
		return "" // Transient error, don't change status.
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))

	return classifyResponse(resp.StatusCode, body)
}

// classifyResponse determines session status from the CodeBuddy response.
func classifyResponse(statusCode int, body []byte) string {
	switch {
	case statusCode == 200:
		// Could still be a soft block returned as 200.
		if bytes.Contains(body, []byte("11140")) || bytes.Contains(body, []byte("not illegal")) {
			return StatusBanned
		}
		return StatusActive

	case statusCode == 403:
		if bytes.Contains(body, []byte("11140")) || bytes.Contains(body, []byte("not illegal")) {
			return StatusBanned
		}
		return StatusBanned // 403 is a block regardless.

	case statusCode == 429:
		if bytes.Contains(body, []byte("14018")) || bytes.Contains(body, []byte("Credits exhausted")) {
			return StatusExhausted
		}
		return "" // Other 429 might be rate limit, transient.

	case statusCode == 401:
		return StatusExpired

	default:
		// Check body for known patterns regardless of status code.
		if bytes.Contains(body, []byte("inactive")) {
			return StatusExpired
		}
		return "" // Unknown/transient, don't change.
	}
}

func (h *HealthChecker) updateStatus(sessionID int, status string) {
	var err error
	switch status {
	case StatusExhausted:
		err = h.store.MarkSessionExhausted(sessionID)
	case StatusExpired:
		err = h.store.MarkSessionExpired(sessionID)
	case StatusBanned:
		err = h.store.MarkSessionBanned(sessionID)
	case StatusActive:
		// Session is already active or recovering — no store method needed
		// since MarkSession* only handles degradation.
		return
	}
	if err != nil {
		slog.Error("health check: update status", "error", err, "session_id", sessionID, "status", status)
	}
}

func genUUID() string {
	b := make([]byte, 16)
	rand.Read(b)
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

func genHex(n int) string {
	b := make([]byte, n)
	rand.Read(b)
	return fmt.Sprintf("%x", b)
}
