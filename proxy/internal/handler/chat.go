package handler

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/hanni/aiproxy/proxy/internal/keypool"
	"github.com/hanni/aiproxy/proxy/internal/store"
	"github.com/hanni/aiproxy/proxy/internal/upstream"
)

type ChatHandler struct {
	pool     *keypool.Pool
	client   *upstream.Client
	store    *store.Store
	modelMap map[string]string
	maxRetry int
}

func NewChatHandler(pool *keypool.Pool, client *upstream.Client, s *store.Store, modelMap map[string]string, maxRetry int) *ChatHandler {
	return &ChatHandler{pool: pool, client: client, store: s, modelMap: modelMap, maxRetry: maxRetry}
}

type chatRequest struct {
	Model    string          `json:"model"`
	Messages json.RawMessage `json:"messages"`
	Stream   bool            `json:"stream"`
}

func (h *ChatHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, `{"error":{"message":"method not allowed"}}`, http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, `{"error":{"message":"failed to read body"}}`, http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var req chatRequest
	if err := json.Unmarshal(body, &req); err != nil {
		http.Error(w, `{"error":{"message":"invalid JSON"}}`, http.StatusBadRequest)
		return
	}

	if mapped, ok := h.modelMap[req.Model]; ok && mapped != req.Model {
		body = replaceModelInBody(body, req.Model, mapped)
		slog.Debug("model mapped", "from", req.Model, "to", mapped)
	}

	// Track which sessions we've already tried to avoid retrying the same one
	tried := make(map[int]bool)

	var lastErr error
	for attempt := 1; attempt <= h.maxRetry; attempt++ {
		// Use AcquireExcluding to skip sessions we already tried
		sess, err := h.pool.AcquireExcluding(tried)
		if err != nil {
			if errors.Is(err, keypool.ErrCircuitOpen) {
				slog.Error("circuit breaker open, fast-failing", "error", err)
				w.Header().Set("Content-Type", "application/json")
				w.Header().Set("Retry-After", "10")
				w.WriteHeader(http.StatusServiceUnavailable)
				w.Write([]byte(`{"error":{"message":"all sessions exhausted, retry after 10s","type":"circuit_breaker"}}`))
				return
			}
			slog.Error("no sessions available", "error", err)
			http.Error(w, `{"error":{"message":"no active sessions available","type":"server_error"}}`, http.StatusServiceUnavailable)
			return
		}

		// Mark this session as tried
		tried[sess.ID] = true

		slog.Info("proxy request", "model", req.Model, "account", sess.Email, "session_id", sess.ID)

		start := time.Now()
		resp, err := h.client.ChatCompletion(r.Context(), sess.JWTToken, sess.UserID, body)
		latency := time.Since(start)

		if err != nil {
			slog.Warn("upstream request failed", "attempt", attempt, "email", sess.Email, "error", err)
			lastErr = err
			_ = h.store.LogRequest(sess.ID, req.Model, 0, latency.Milliseconds(), err.Error())
			continue
		}

		if resp.StatusCode != 200 {
			respBody, _ := io.ReadAll(resp.Body)
			resp.Body.Close()

			if upstream.IsCreditsExhausted(resp.StatusCode, respBody) {
				slog.Warn("credits exhausted, rotating", "email", sess.Email, "attempt", attempt)
				h.pool.Release(sess, 429, "credits exhausted")
				_ = h.store.LogRequest(sess.ID, req.Model, 429, latency.Milliseconds(), "credits exhausted")
				lastErr = fmt.Errorf("credits exhausted for %s", sess.Email)
				continue
			}

			if upstream.IsSessionExpired(resp.StatusCode, respBody) {
				slog.Warn("session expired, rotating", "email", sess.Email, "attempt", attempt)
				h.pool.Release(sess, 401, "session expired")
				_ = h.store.LogRequest(sess.ID, req.Model, 401, latency.Milliseconds(), "session expired")
				lastErr = fmt.Errorf("session expired for %s", sess.Email)
				continue
			}

			if upstream.IsWAFBlocked(resp.StatusCode, respBody) {
				slog.Warn("WAF blocked, rotating", "email", sess.Email, "attempt", attempt)
				h.pool.Release(sess, 403, "WAF blocked")
				_ = h.store.LogRequest(sess.ID, req.Model, 403, latency.Milliseconds(), "WAF blocked")
				lastErr = fmt.Errorf("WAF blocked %s", sess.Email)
				continue
			}

			_ = h.store.LogRequest(sess.ID, req.Model, resp.StatusCode, latency.Milliseconds(), string(respBody[:min(len(respBody), 200)]))
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(resp.StatusCode)
			w.Write(respBody)
			return
		}

		_ = h.store.LogRequest(sess.ID, req.Model, resp.StatusCode, latency.Milliseconds(), "")
		h.pool.Release(sess, resp.StatusCode, "")

		if req.Stream {
			h.relayStream(w, resp)
		} else {
			h.relayJSON(w, resp)
		}
		return
	}

	slog.Error("all retries exhausted", "last_error", lastErr)
	http.Error(w, fmt.Sprintf(`{"error":{"message":"all retries exhausted: %v","type":"server_error"}}`, lastErr), http.StatusServiceUnavailable)
}

func (h *ChatHandler) relayStream(w http.ResponseWriter, resp *http.Response) {
	defer resp.Body.Close()
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(resp.StatusCode)
	if err := upstream.RelaySSE(w, resp.Body); err != nil {
		slog.Error("sse relay error", "error", err)
	}
}

func (h *ChatHandler) relayJSON(w http.ResponseWriter, resp *http.Response) {
	defer resp.Body.Close()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func replaceModelInBody(body []byte, from, to string) []byte {
	return []byte(strings.Replace(string(body), `"`+from+`"`, `"`+to+`"`, 1))
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
