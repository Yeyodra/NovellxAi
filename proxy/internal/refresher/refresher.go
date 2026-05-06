package refresher

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/hanni/aiproxy/proxy/internal/config"
	"github.com/hanni/aiproxy/proxy/internal/store"
)

type Refresher struct {
	store   *store.Store
	cfg     config.RefresherConfig
	baseURL string
	client  *http.Client

	// Track consecutive failures per session
	failures map[int]int
}

func New(s *store.Store, cfg config.RefresherConfig, baseURL string) *Refresher {
	transport := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
	}
	return &Refresher{
		store:   s,
		cfg:     cfg,
		baseURL: baseURL,
		client:  &http.Client{Transport: transport, Timeout: 30 * time.Second},
		failures: make(map[int]int),
	}
}

func (r *Refresher) Start(ctx context.Context) {
	slog.Info("refresher started", "interval", r.cfg.Interval, "buffer", r.cfg.RefreshBuffer)
	ticker := time.NewTicker(r.cfg.Interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			slog.Info("refresher stopped")
			return
		case <-ticker.C:
			r.tick()
		}
	}
}

func (r *Refresher) tick() {
	sessions := r.store.GetAllSessions()
	now := time.Now()

	for _, sess := range sessions {
		if sess.Status != "active" {
			continue
		}
		if sess.ExpiresAt == "" {
			continue
		}

		expiresAt, err := time.Parse(time.RFC3339, sess.ExpiresAt)
		if err != nil {
			slog.Warn("refresher: invalid expiry format", "session_id", sess.ID, "expires_at", sess.ExpiresAt)
			continue
		}

		// Proactive health-check: if session is already expired, mark immediately
		if now.After(expiresAt) {
			slog.Warn("refresher: session already expired, marking",
				"session_id", sess.ID,
				"expired_since", now.Sub(expiresAt).Round(time.Second),
			)
			if markErr := r.store.MarkSessionExpired(sess.ID); markErr != nil {
				slog.Error("refresher: failed to mark session expired", "session_id", sess.ID, "error", markErr)
			}
			delete(r.failures, sess.ID)
			continue
		}

		// Refresh if expiry is within the buffer window
		if time.Until(expiresAt) > r.cfg.RefreshBuffer {
			continue
		}

		slog.Debug("refresher: token expiring soon, refreshing",
			"session_id", sess.ID,
			"expires_in", time.Until(expiresAt).Round(time.Second),
		)

		err = r.refreshSession(sess, now)
		if err != nil {
			r.failures[sess.ID]++
			slog.Warn("refresher: refresh failed",
				"session_id", sess.ID,
				"attempt", r.failures[sess.ID],
				"error", err,
			)
			if r.failures[sess.ID] >= r.cfg.MaxRetries {
				slog.Error("refresher: max retries exceeded, marking session expired", "session_id", sess.ID)
				if markErr := r.store.MarkSessionExpired(sess.ID); markErr != nil {
					slog.Error("refresher: failed to mark session expired", "session_id", sess.ID, "error", markErr)
				}
				delete(r.failures, sess.ID)
			}
		} else {
			delete(r.failures, sess.ID)
			slog.Info("refresher: token refreshed", "session_id", sess.ID)
		}
	}
}

type refreshResponse struct {
	Code int `json:"code"`
	Data struct {
		AccessToken  string `json:"accessToken"`
		RefreshToken string `json:"refreshToken"`
	} `json:"data"`
}

func (r *Refresher) refreshSession(sess store.Session, _ time.Time) error {
	// Strip "Bearer " prefix for the Authorization header value
	jwt := sess.JWTToken
	if !strings.HasPrefix(jwt, "Bearer ") {
		jwt = "Bearer " + jwt
	}

	// Gzip compress the body "{}"
	var bodyBuf bytes.Buffer
	gzWriter := gzip.NewWriter(&bodyBuf)
	if _, err := gzWriter.Write([]byte("{}")); err != nil {
		return fmt.Errorf("gzip write: %w", err)
	}
	if err := gzWriter.Close(); err != nil {
		return fmt.Errorf("gzip close: %w", err)
	}

	url := strings.TrimRight(r.baseURL, "/") + "/v2/plugin/auth/token/refresh"
	req, err := http.NewRequest(http.MethodPost, url, &bodyBuf)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Authorization", jwt)
	req.Header.Set("X-Refresh-Token", sess.RefreshToken)
	req.Header.Set("X-Auth-Refresh-Source", "plugin")
	req.Header.Set("X-User-Id", sess.UserID)
	req.Header.Set("X-Domain", "www.codebuddy.ai")
	req.Header.Set("X-Product", "SaaS")
	req.Header.Set("X-IDE-Type", "CLI")
	req.Header.Set("X-IDE-Name", "CLI")
	req.Header.Set("X-IDE-Version", "2.95.0")
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("User-Agent", "CLI/2.95.0 CodeBuddy/2.95.0")
	req.Header.Set("Content-Encoding", "gzip")

	resp, err := r.client.Do(req)
	if err != nil {
		return fmt.Errorf("http request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}

	var result refreshResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return fmt.Errorf("decode response: %w", err)
	}

	if result.Code != 0 {
		return fmt.Errorf("api error code: %d", result.Code)
	}

	if result.Data.AccessToken == "" {
		return fmt.Errorf("empty access token in response")
	}

	// Parse expiry from new JWT
	newExpiry, err := parseJWTExpiry(result.Data.AccessToken)
	if err != nil {
		return fmt.Errorf("parse jwt expiry: %w", err)
	}

	// Store token with "Bearer " prefix
	newJWT := "Bearer " + result.Data.AccessToken
	expiresAtStr := newExpiry.Format(time.RFC3339)

	if err := r.store.UpdateSessionTokens(sess.ID, newJWT, result.Data.RefreshToken, expiresAtStr); err != nil {
		return fmt.Errorf("update store: %w", err)
	}

	return nil
}

// parseJWTExpiry extracts the "exp" claim from a JWT token by base64-decoding the payload segment.
func parseJWTExpiry(token string) (time.Time, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return time.Time{}, fmt.Errorf("invalid jwt: expected 3 parts, got %d", len(parts))
	}

	payload := parts[1]
	// Add padding if needed
	switch len(payload) % 4 {
	case 2:
		payload += "=="
	case 3:
		payload += "="
	}

	decoded, err := base64.URLEncoding.DecodeString(payload)
	if err != nil {
		// Try raw encoding (no padding)
		decoded, err = base64.RawURLEncoding.DecodeString(parts[1])
		if err != nil {
			return time.Time{}, fmt.Errorf("base64 decode: %w", err)
		}
	}

	var claims struct {
		Exp json.Number `json:"exp"`
	}
	if err := json.Unmarshal(decoded, &claims); err != nil {
		return time.Time{}, fmt.Errorf("unmarshal claims: %w", err)
	}

	expInt, err := claims.Exp.Int64()
	if err != nil {
		return time.Time{}, fmt.Errorf("parse exp as int64: %w", err)
	}

	return time.Unix(expInt, 0), nil
}
