package store

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type Store struct {
	path string
	mu   sync.RWMutex
	data *Data
}

type Data struct {
	Sessions   []Session  `json:"sessions"`
	Accounts   []Account  `json:"accounts"`
	RequestLog []LogEntry `json:"request_log"`
}

type Session struct {
	ID             int    `json:"id"`
	Email          string `json:"email"`
	AccountID      string `json:"account_id"`
	JWTToken       string `json:"jwt_token"`       // Bearer token (JWT from Keycloak)
	ApiKey         string `json:"api_key"`          // CodeBuddy API key (ck_...) — preferred auth
	UserID         string `json:"user_id"`          // X-User-Id header
	RefreshToken   string `json:"refresh_token"`    // For token refresh
	Status         string `json:"status"`           // active|exhausted|expired|banned
	IsCurrent      bool   `json:"is_current"`
	RemainingQuota int    `json:"remaining_quota"`
	LastUsedAt     string `json:"last_used_at"`
	ExpiresAt      string `json:"expires_at"`
	CreatedAt      string `json:"created_at"`
}

type Account struct {
	ID           string `json:"id"`
	Email        string `json:"email"`
	EnterpriseID string `json:"enterprise_id"`
	Status       string `json:"status"`
	LastLoginAt  string `json:"last_login_at"`
	CreatedAt    string `json:"created_at"`
}

type LogEntry struct {
	SessionID  int    `json:"session_id"`
	Model      string `json:"model"`
	StatusCode int    `json:"status_code"`
	LatencyMs  int64  `json:"latency_ms"`
	Error      string `json:"error"`
	CreatedAt  string `json:"created_at"`
}

func New(dbPath string) (*Store, error) {
	dir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("create data dir: %w", err)
	}

	jsonPath := dbPath + ".json"
	s := &Store{
		path: jsonPath,
		data: &Data{Sessions: []Session{}, Accounts: []Account{}, RequestLog: []LogEntry{}},
	}

	if _, err := os.Stat(jsonPath); err == nil {
		raw, err := os.ReadFile(jsonPath)
		if err != nil {
			return nil, fmt.Errorf("read store: %w", err)
		}
		if len(raw) >= 3 && raw[0] == 0xEF && raw[1] == 0xBB && raw[2] == 0xBF {
			raw = raw[3:]
		}
		if len(raw) > 0 {
			if err := json.Unmarshal(raw, s.data); err != nil {
				return nil, fmt.Errorf("parse store: %w", err)
			}
		}
	}
	return s, nil
}

func (s *Store) Close() error { return s.save() }

func (s *Store) save() error {
	raw, err := json.MarshalIndent(s.data, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.path, raw, 0644)
}

func now() string { return time.Now().Format(time.RFC3339) }

func (s *Store) nextSessionID() int {
	max := 0
	for _, sess := range s.data.Sessions {
		if sess.ID > max {
			max = sess.ID
		}
	}
	return max + 1
}

func (s *Store) GetCurrentSession() (*Session, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	for i := range s.data.Sessions {
		if s.data.Sessions[i].IsCurrent && s.data.Sessions[i].Status == "active" {
			return &s.data.Sessions[i], nil
		}
	}
	return nil, fmt.Errorf("no current session")
}

func (s *Store) GetNextActiveSession() (*Session, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	for i := range s.data.Sessions {
		sess := &s.data.Sessions[i]
		if sess.Status == "active" && !sess.IsCurrent {
			return sess, nil
		}
	}
	return nil, fmt.Errorf("no active sessions available")
}

func (s *Store) SetCurrentSession(sessionID int) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.data.Sessions {
		s.data.Sessions[i].IsCurrent = false
	}
	for i := range s.data.Sessions {
		if s.data.Sessions[i].ID == sessionID {
			s.data.Sessions[i].IsCurrent = true
			break
		}
	}
	return s.save()
}

func (s *Store) MarkSessionExhausted(sessionID int) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.data.Sessions {
		if s.data.Sessions[i].ID == sessionID {
			s.data.Sessions[i].Status = "exhausted"
			s.data.Sessions[i].IsCurrent = false
			break
		}
	}
	return s.save()
}

func (s *Store) MarkSessionExpired(sessionID int) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.data.Sessions {
		if s.data.Sessions[i].ID == sessionID {
			s.data.Sessions[i].Status = "expired"
			s.data.Sessions[i].IsCurrent = false
			break
		}
	}
	return s.save()
}

func (s *Store) MarkSessionBanned(sessionID int) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.data.Sessions {
		if s.data.Sessions[i].ID == sessionID {
			s.data.Sessions[i].Status = "banned"
			s.data.Sessions[i].IsCurrent = false
			break
		}
	}
	return s.save()
}

func (s *Store) TouchSession(sessionID int) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.data.Sessions {
		if s.data.Sessions[i].ID == sessionID {
			s.data.Sessions[i].LastUsedAt = now()
			break
		}
	}
	return s.save()
}

func (s *Store) CountActiveSessions() (int, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	count := 0
	for _, sess := range s.data.Sessions {
		if sess.Status == "active" {
			count++
		}
	}
	return count, nil
}

func (s *Store) LogRequest(sessionID int, model string, statusCode int, latencyMs int64, errMsg string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.data.RequestLog = append(s.data.RequestLog, LogEntry{
		SessionID: sessionID, Model: model, StatusCode: statusCode,
		LatencyMs: latencyMs, Error: errMsg, CreatedAt: now(),
	})
	if len(s.data.RequestLog) > 1000 {
		s.data.RequestLog = s.data.RequestLog[len(s.data.RequestLog)-1000:]
	}
	return s.save()
}

func (s *Store) InsertSession(email, accountID, jwtToken, userID, expiresAt string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.data.Sessions {
		if s.data.Sessions[i].Email == email {
			s.data.Sessions[i].JWTToken = jwtToken
			s.data.Sessions[i].UserID = userID
			s.data.Sessions[i].Status = "active"
			s.data.Sessions[i].ExpiresAt = expiresAt
			return s.save()
		}
	}
	s.data.Sessions = append(s.data.Sessions, Session{
		ID: s.nextSessionID(), Email: email, AccountID: accountID,
		JWTToken: jwtToken, UserID: userID, Status: "active",
		ExpiresAt: expiresAt, CreatedAt: now(),
	})
	return s.save()
}

func (s *Store) InsertAccount(id, email, enterpriseID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, a := range s.data.Accounts {
		if a.Email == email {
			return nil
		}
	}
	s.data.Accounts = append(s.data.Accounts, Account{
		ID: id, Email: email, EnterpriseID: enterpriseID,
		Status: "active", CreatedAt: now(),
	})
	return s.save()
}

func (s *Store) UpdateSessionTokens(sessionID int, jwtToken, refreshToken, expiresAt string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.data.Sessions {
		if s.data.Sessions[i].ID == sessionID {
			s.data.Sessions[i].JWTToken = jwtToken
			s.data.Sessions[i].RefreshToken = refreshToken
			s.data.Sessions[i].ExpiresAt = expiresAt
			return s.save()
		}
	}
	return fmt.Errorf("session %d not found", sessionID)
}

func (s *Store) GetAllSessions() []Session {
	s.mu.RLock()
	defer s.mu.RUnlock()
	result := make([]Session, len(s.data.Sessions))
	copy(result, s.data.Sessions)
	return result
}

func (s *Store) GetRecentLogs(n int) []LogEntry {
	s.mu.RLock()
	defer s.mu.RUnlock()
	logs := s.data.RequestLog
	if len(logs) > n {
		logs = logs[len(logs)-n:]
	}
	result := make([]LogEntry, len(logs))
	copy(result, logs)
	return result
}
