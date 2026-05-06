package keypool

import (
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/hanni/aiproxy/proxy/internal/store"
)

type Pool struct {
	store *store.Store
	mu    sync.Mutex
}

func New(s *store.Store) *Pool {
	return &Pool{store: s}
}

func (p *Pool) Acquire() (*store.Session, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	sess, err := p.store.GetCurrentSession()
	if err == nil && sess != nil {
		return sess, nil
	}
	return p.rotate()
}

func (p *Pool) Release(sess *store.Session, statusCode int, errMsg string) {
	p.mu.Lock()
	defer p.mu.Unlock()

	if statusCode == 200 || errMsg == "" {
		_ = p.store.TouchSession(sess.ID)
		return
	}

	if statusCode == 429 {
		slog.Warn("session exhausted, rotating", "email", sess.Email, "session_id", sess.ID)
		_ = p.store.MarkSessionExhausted(sess.ID)
		return
	}

	if statusCode == 401 || statusCode == 403 {
		slog.Warn("session expired/banned, rotating", "email", sess.Email, "status", statusCode)
		if statusCode == 401 {
			_ = p.store.MarkSessionExpired(sess.ID)
		} else {
			_ = p.store.MarkSessionBanned(sess.ID)
		}
		return
	}

	slog.Warn("upstream error (not rotating)", "email", sess.Email, "status", statusCode, "error", errMsg)
}

func (p *Pool) ForceRotate() (*store.Session, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.rotate()
}

func (p *Pool) rotate() (*store.Session, error) {
	next, err := p.store.GetNextActiveSession()
	if err != nil {
		return nil, fmt.Errorf("no active sessions available: %w", err)
	}
	if err := p.store.SetCurrentSession(next.ID); err != nil {
		return nil, fmt.Errorf("set current session: %w", err)
	}
	count, _ := p.store.CountActiveSessions()
	slog.Info("sticky account rotated", "email", next.Email, "session_id", next.ID, "pool_active", count)
	return next, nil
}

func (p *Pool) Stats() (active int, err error) {
	return p.store.CountActiveSessions()
}

var CooldownDuration = 60 * time.Second
