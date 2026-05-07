package usage

import (
	"encoding/json"
	"io"
	"strings"
)

// Capture wraps an io.Writer and captures the tail of the stream
// to extract usage data from SSE responses without blocking relay.
type Capture struct {
	w    io.Writer
	tail []byte
	max  int
}

// NewCapture creates a usage capture writer that keeps the last maxBytes of data.
func NewCapture(w io.Writer, maxBytes int) *Capture {
	return &Capture{
		w:   w,
		tail: make([]byte, 0, maxBytes),
		max:  maxBytes,
	}
}

func (c *Capture) Write(p []byte) (int, error) {
	// Append to tail, trim to max size
	c.tail = append(c.tail, p...)
	if len(c.tail) > c.max {
		c.tail = c.tail[len(c.tail)-c.max:]
	}
	return c.w.Write(p)
}

// Usage holds extracted token usage from SSE stream.
type Usage struct {
	PromptTokens     int     `json:"prompt_tokens"`
	CompletionTokens int     `json:"completion_tokens"`
	TotalTokens      int     `json:"total_tokens"`
	Credit           float64 `json:"credit"`
}

// sseChunk is the minimal structure to extract usage from an SSE data line.
type sseChunk struct {
	Usage *Usage `json:"usage,omitempty"`
}

// ExtractUsage parses the captured tail for the last SSE data line containing usage info.
// Returns the usage data and the computed credits cost.
func (c *Capture) ExtractUsage() (usage Usage, credits float64) {
	text := string(c.tail)
	lines := strings.Split(text, "\n")

	// Scan backwards for the last "data: {...}" line with "usage"
	for i := len(lines) - 1; i >= 0; i-- {
		line := strings.TrimSpace(lines[i])
		if !strings.HasPrefix(line, "data: ") {
			continue
		}
		payload := strings.TrimPrefix(line, "data: ")
		if payload == "[DONE]" {
			continue
		}
		if !strings.Contains(payload, "usage") {
			continue
		}

		var chunk sseChunk
		if err := json.Unmarshal([]byte(payload), &chunk); err != nil {
			continue
		}
		if chunk.Usage == nil {
			continue
		}

		usage = *chunk.Usage

		// Calculate credits
		if usage.Credit > 0 {
			credits = usage.Credit
		} else if usage.TotalTokens > 0 {
			credits = float64(usage.TotalTokens) / 1000.0
		}
		return
	}
	return
}
