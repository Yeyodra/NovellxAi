package keypool

import (
	"errors"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/hanni/aiproxy/proxy/internal/store"
)

// ErrCircuitOpen is returned when the circuit breaker is open (all sessions dead).
var ErrCircuitOpen = errors.New("circuit breaker open: all sessions exhausted")

type Pool struct {
	store *store.Store
	mu    sync.Mutex

	// Circuit breaker state
	cbOpen     bool
	cbOpenAt   time.Time
	cbCooldown time.Duration
}

func New(s *store.Store) *Pool {
	return &Pool{
		store:      s,
		cbCooldown: 10 * time.Second,
	}
}

// SetCooldown configures the circuit breaker cooldown duration.
func (p *Pool) SetCooldown(d time.Duration) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.cbCooldown = d
}

func (p *Pool) Acquire() (*store.Session, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Circuit breaker check
	if p.cbOpen && time.Since(p.cbOpenAt) < p.cbCooldown {
		return nil, ErrCircuitOpen
	}

	sess, err := p.store.GetCurrentSession()
	if err == nil && sess != nil {
		p.cbOpen = false
		return sess, nil
	}

	next, err := p.rotate()
	if err != nil {
		// No sessions available — open circuit breaker
		p.cbOpen = true
		p.cbOpenAt = time.Now()
		return nil, ErrCircuitOpen
	}
	p.cbOpen = false
	return next, nil
}

// AcquireExcluding acquires a session, skipping any session IDs in the exclude set.
func (p *Pool) AcquireExcluding(exclude map[int]bool) (*store.Session, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Circuit breaker check
	if p.cbOpen && time.Since(p.cbOpenAt) < p.cbCooldown {
		return nil, ErrCircuitOpen
	}

	sess, err := p.store.GetCurrentSession()
	if err == nil && sess != nil {
		if !exclude[sess.ID] {
			p.cbOpen = false
			return sess, nil
		}
		// Current session is excluded, try to rotate
	}

	// Try to find a session not in the exclude set
	next, err := p.rotateExcluding(exclude)
	if err != nil {
		p.cbOpen = true
		p.cbOpenAt = time.Now()
		return nil, ErrCircuitOpen
	}
	p.cbOpen = false
	return next, nil
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

// rotateExcluding finds the next active session not in the exclude set.
func (p *Pool) rotateExcluding(exclude map[int]bool) (*store.Session, error) {
	sessions := p.store.GetAllSessions()
	for i := range sessions {
		sess := &sessions[i]
		if sess.Status == "active" && !exclude[sess.ID] {
			if err := p.store.SetCurrentSession(sess.ID); err != nil {
				return nil, fmt.Errorf("set current session: %w", err)
			}
			count, _ := p.store.CountActiveSessions()
			slog.Info("sticky account rotated (excluding tried)", "email", sess.Email, "session_id", sess.ID, "pool_active", count)
			return sess, nil
		}
	}
	return nil, fmt.Errorf("no active sessions available (all excluded)")
}

func (p *Pool) Stats() (active int, err error) {
	return p.store.CountActiveSessions()
}

var CooldownDuration = 60 * time.Second
