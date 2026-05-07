package handler

import (
	"bufio"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/novellaxai/novellaxai/proxy/internal/store"
)

// --- Sessions Handler (GET + POST /api/sessions, DELETE /api/sessions/{id}) ---

type SessionsHandler struct {
	store *store.Store
}

func NewSessionsHandler(s *store.Store) *SessionsHandler {
	return &SessionsHandler{store: s}
}

type sessionListItem struct {
	ID        int    `json:"id"`
	Email     string `json:"email"`
	Status    string `json:"status"`
	HasApiKey bool   `json:"has_api_key"`
	Credits   int    `json:"credits"`
	CreatedAt string `json:"created_at"`
}

type addAccountsRequest struct {
	Accounts []struct {
		Email    string `json:"email"`
		Password string `json:"password"`
	} `json:"accounts"`
}

func (h *SessionsHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}

	// Check if this is a DELETE with an ID in the path
	path := strings.TrimPrefix(r.URL.Path, "/api/sessions")
	path = strings.TrimPrefix(path, "/")

	if r.Method == http.MethodDelete && path != "" {
		h.handleDelete(w, r, path)
		return
	}

	switch r.Method {
	case http.MethodGet:
		h.handleList(w, r)
	case http.MethodPost:
		h.handleAdd(w, r)
	default:
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
	}
}

func (h *SessionsHandler) handleList(w http.ResponseWriter, _ *http.Request) {
	sessions := h.store.GetAllSessions()
	items := make([]sessionListItem, 0, len(sessions))
	for _, s := range sessions {
		items = append(items, sessionListItem{
			ID:        s.ID,
			Email:     s.Email,
			Status:    s.Status,
			HasApiKey: s.ApiKey != "",
			Credits:   s.RemainingQuota,
			CreatedAt: s.CreatedAt,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"sessions": items})
}

func (h *SessionsHandler) handleAdd(w http.ResponseWriter, r *http.Request) {
	var req addAccountsRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid json"}`, http.StatusBadRequest)
		return
	}

	accounts := make([]store.Account, 0, len(req.Accounts))
	for _, a := range req.Accounts {
		if a.Email == "" {
			continue
		}
		accounts = append(accounts, store.Account{
			Email:    a.Email,
			Password: a.Password,
		})
	}

	added, skipped := h.store.AddAccounts(accounts)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]int{"added": added, "skipped": skipped})
}

func (h *SessionsHandler) handleDelete(w http.ResponseWriter, _ *http.Request, idStr string) {
	id, err := strconv.Atoi(idStr)
	if err != nil {
		http.Error(w, `{"error":"invalid id"}`, http.StatusBadRequest)
		return
	}

	if err := h.store.RemoveSession(id); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"%s"}`, err.Error()), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]bool{"ok": true})
}

// --- Login Handler (POST /api/sessions/login) ---

type loginLogEntry struct {
	Time    string `json:"time"`
	Message string `json:"message"`
	Level   string `json:"level"`
}

var (
	loginMu      sync.Mutex
	loginRunning bool
	loginTotal   int
	loginCmd     *exec.Cmd
	loginLogs    []loginLogEntry
)

type LoginHandler struct {
	store *store.Store
}

func NewLoginHandler(s *store.Store) *LoginHandler {
	return &LoginHandler{store: s}
}

func (h *LoginHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	loginMu.Lock()
	if loginRunning {
		loginMu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"error": "already running"})
		return
	}

	pending := h.store.GetPendingAccounts()
	if len(pending) == 0 {
		loginMu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"error": "no pending accounts"})
		return
	}

	// Write temp file with email:password
	tmpFile, err := os.CreateTemp("", "novellaxai-login-*.txt")
	if err != nil {
		loginMu.Unlock()
		http.Error(w, `{"error":"failed to create temp file"}`, http.StatusInternalServerError)
		return
	}

	for _, a := range pending {
		fmt.Fprintf(tmpFile, "%s:%s\n", a.Email, a.Password)
	}
	tmpFile.Close()

	// Find batch_login.py relative to executable
	exePath, _ := os.Executable()
	exeDir := filepath.Dir(exePath)
	scriptPath := filepath.Join(exeDir, "..", "auth-engine", "src", "batch_login.py")
	if _, err := os.Stat(scriptPath); os.IsNotExist(err) {
		// Fallback: relative to working directory
		scriptPath = filepath.Join(".", "..", "auth-engine", "src", "batch_login.py")
	}

	// Use venv Python (has all dependencies: browserforge, camoufox, etc.)
	venvPython := filepath.Join(exeDir, "..", "auth-engine", ".venv", "Scripts", "python.exe")
	if _, err := os.Stat(venvPython); os.IsNotExist(err) {
		venvPython = filepath.Join(".", "..", "auth-engine", ".venv", "Scripts", "python.exe")
	}
	if _, err := os.Stat(venvPython); os.IsNotExist(err) {
		venvPython = "python" // fallback to system python
	}

	loginTotal = len(pending)
	loginRunning = true
	loginLogs = nil // reset logs
	loginCmd = exec.Command(venvPython, "-u", scriptPath, tmpFile.Name(), "--headless")
	loginMu.Unlock()

	// Run in background with line-by-line capture
	go func() {
		defer func() {
			loginMu.Lock()
			loginRunning = false
			loginCmd = nil
			loginMu.Unlock()
			os.Remove(tmpFile.Name())
		}()

		stdout, err := loginCmd.StdoutPipe()
		if err != nil {
			slog.Error("failed to get stdout pipe", "error", err)
			return
		}
		loginCmd.Stderr = loginCmd.Stdout // merge stderr into stdout

		if err := loginCmd.Start(); err != nil {
			slog.Error("batch login start failed", "error", err)
			return
		}

		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			now := time.Now().Format("15:04:05")
			level := "info"
			if strings.Contains(strings.ToLower(line), "error") || strings.Contains(strings.ToLower(line), "fail") {
				level = "error"
			} else if strings.Contains(strings.ToLower(line), "success") || strings.Contains(strings.ToLower(line), "authenticated") || strings.Contains(line, "✓") {
				level = "success"
			}

			loginMu.Lock()
			loginLogs = append(loginLogs, loginLogEntry{
				Time:    now,
				Message: line,
				Level:   level,
			})
			// Keep last 200 lines
			if len(loginLogs) > 200 {
				loginLogs = loginLogs[len(loginLogs)-200:]
			}
			loginMu.Unlock()

			slog.Debug("login output", "line", line)
		}

		if err := loginCmd.Wait(); err != nil {
			slog.Error("batch login failed", "error", err)
		} else {
			slog.Info("batch login completed")
		}
	}()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"started": true, "total": loginTotal})
}

// --- Login Status Handler (GET /api/sessions/login-status) ---

type LoginStatusHandler struct {
	store *store.Store
}

func NewLoginStatusHandler(s *store.Store) *LoginStatusHandler {
	return &LoginStatusHandler{store: s}
}

func (h *LoginStatusHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method != http.MethodGet {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	loginMu.Lock()
	running := loginRunning
	total := loginTotal
	loginMu.Unlock()

	// Count completed: sessions with active status that were pending
	sessions := h.store.GetAllSessions()
	completed := 0
	for _, s := range sessions {
		if s.Status == "active" && s.ApiKey != "" {
			completed++
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{
		"running":   running,
		"completed": completed,
		"total":     total,
	})
}

// --- Login Logs Handler (GET /api/sessions/login-logs) ---

type LoginLogsHandler struct{}

func NewLoginLogsHandler() *LoginLogsHandler {
	return &LoginLogsHandler{}
}

func (h *LoginLogsHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method != http.MethodGet {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	loginMu.Lock()
	logs := make([]loginLogEntry, len(loginLogs))
	copy(logs, loginLogs)
	loginMu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"logs": logs})
}
