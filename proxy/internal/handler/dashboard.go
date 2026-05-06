package handler

import (
	"encoding/json"
	"math"
	"net/http"
	"time"

	"github.com/hanni/aiproxy/proxy/internal/keypool"
	"github.com/hanni/aiproxy/proxy/internal/store"
)

type DashboardHandler struct {
	pool      *keypool.Pool
	store     *store.Store
	startTime time.Time
}

func NewDashboardHandler(pool *keypool.Pool, s *store.Store, startTime time.Time) *DashboardHandler {
	return &DashboardHandler{pool: pool, store: s, startTime: startTime}
}

type dashboardResponse struct {
	Accounts    accountStats            `json:"accounts"`
	Requests    requestStats            `json:"requests"`
	SuccessRate float64                 `json:"success_rate"`
	Uptime      int64                   `json:"uptime_seconds"`
	Providers   map[string]providerStat `json:"providers"`
	TokenUsage  tokenUsage              `json:"token_usage"`
}

type accountStats struct {
	Active int `json:"active"`
	Total  int `json:"total"`
}

type requestStats struct {
	Total   int `json:"total"`
	Success int `json:"success"`
	Failed  int `json:"failed"`
}

type providerStat struct {
	Active       int `json:"active"`
	Total        int `json:"total"`
	Exhausted    int `json:"exhausted,omitempty"`
	CreditsUsed  int `json:"credits_used,omitempty"`
	CreditsTotal int `json:"credits_total,omitempty"`
}

type tokenUsage struct {
	Total      int `json:"total"`
	Prompt     int `json:"prompt"`
	Completion int `json:"completion"`
}

func (h *DashboardHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	sessions := h.store.GetAllSessions()
	logs := h.store.GetRecentLogs(10000) // get all logs

	// Account stats
	activeCount := 0
	exhaustedCount := 0
	for _, s := range sessions {
		if s.Status == "active" {
			activeCount++
		}
		if s.Status == "exhausted" {
			exhaustedCount++
		}
	}

	// Request stats
	totalReqs := len(logs)
	successReqs := 0
	for _, l := range logs {
		if l.StatusCode == 200 {
			successReqs++
		}
	}
	failedReqs := totalReqs - successReqs

	// Success rate
	var successRate float64
	if totalReqs > 0 {
		successRate = math.Round((float64(successReqs)/float64(totalReqs)*100)*10) / 10
	}

	// Uptime
	uptimeSeconds := int64(time.Since(h.startTime).Seconds())

	// Provider stats (all sessions are codebuddy for now)
	cbActive := activeCount
	cbTotal := len(sessions)
	cbExhausted := exhaustedCount
	// Estimate credits: each session has ~250 credits
	creditsPerAccount := 250
	creditsUsed := totalReqs * 5 // rough estimate: 5 credits per request
	creditsTotal := cbTotal * creditsPerAccount
	if creditsUsed > creditsTotal {
		creditsUsed = creditsTotal
	}

	resp := dashboardResponse{
		Accounts: accountStats{
			Active: activeCount,
			Total:  len(sessions),
		},
		Requests: requestStats{
			Total:   totalReqs,
			Success: successReqs,
			Failed:  failedReqs,
		},
		SuccessRate: successRate,
		Uptime:      uptimeSeconds,
		Providers: map[string]providerStat{
			"codebuddy": {
				Active:       cbActive,
				Total:        cbTotal,
				Exhausted:    cbExhausted,
				CreditsUsed:  creditsUsed,
				CreditsTotal: creditsTotal,
			},
			"kiro": {
				Active: 0,
				Total:  0,
			},
		},
		TokenUsage: tokenUsage{
			Total:      0,
			Prompt:     0,
			Completion: 0,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	json.NewEncoder(w).Encode(resp)
}
