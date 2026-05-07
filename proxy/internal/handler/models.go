package handler

import (
	"encoding/json"
	"net/http"

	"github.com/novellaxai/novellaxai/proxy/internal/keypool"
)

type ModelsHandler struct {
	modelMap map[string]string
}

func NewModelsHandler(modelMap map[string]string) *ModelsHandler {
	return &ModelsHandler{modelMap: modelMap}
}

type modelEntry struct {
	ID      string `json:"id"`
	Object  string `json:"object"`
	Created int64  `json:"created"`
	OwnedBy string `json:"owned_by"`
}

type modelsResponse struct {
	Object string       `json:"object"`
	Data   []modelEntry `json:"data"`
}

func (h *ModelsHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	models := make([]modelEntry, 0, len(h.modelMap))
	seen := map[string]bool{}

	for alias, target := range h.modelMap {
		if !seen[alias] {
			models = append(models, modelEntry{ID: alias, Object: "model", Created: 1700000000, OwnedBy: "codebuddy"})
			seen[alias] = true
		}
		if !seen[target] {
			models = append(models, modelEntry{ID: target, Object: "model", Created: 1700000000, OwnedBy: "codebuddy"})
			seen[target] = true
		}
	}

	resp := modelsResponse{Object: "list", Data: models}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

type HealthHandler struct {
	pool *keypool.Pool
}

func NewHealthHandler(pool *keypool.Pool) *HealthHandler {
	return &HealthHandler{pool: pool}
}

func (h *HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	active, err := h.pool.Stats()
	status := "ok"
	if err != nil || active == 0 {
		status = "degraded"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{
		"status":          status,
		"active_sessions": active,
	})
}
