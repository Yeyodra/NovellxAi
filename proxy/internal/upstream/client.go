package upstream

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/rand"
	"fmt"
	"io"
	"net/http"
	"time"
)

type Client struct {
	httpClient *http.Client
	baseURL    string
	chatPath   string
}

func NewClient(baseURL, chatPath string, timeout time.Duration) *Client {
	return &Client{
		httpClient: &http.Client{
			Timeout: timeout,
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 10,
				IdleConnTimeout:     90 * time.Second,
			},
		},
		baseURL:  baseURL,
		chatPath: chatPath,
	}
}

// ChatCompletion sends gzip-compressed request to CodeBuddy with all required headers
func (c *Client) ChatCompletion(ctx context.Context, jwtToken, userID string, body []byte) (*http.Response, error) {
	url := c.baseURL + c.chatPath

	// Gzip compress the body — CodeBuddy requires Content-Encoding: gzip
	var compressed bytes.Buffer
	gz := gzip.NewWriter(&compressed)
	if _, err := gz.Write(body); err != nil {
		return nil, fmt.Errorf("gzip write: %w", err)
	}
	if err := gz.Close(); err != nil {
		return nil, fmt.Errorf("gzip close: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, &compressed)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	// Generate unique IDs for this request
	convID := genUUID()
	msgID := genHex(16)
	reqID := genHex(16)

	// Required headers (from HAR capture — all needed for 200)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Content-Encoding", "gzip")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Authorization", jwtToken)
	req.Header.Set("X-User-Id", userID)
	req.Header.Set("X-Domain", "www.codebuddy.ai")
	req.Header.Set("X-Product", "SaaS")
	req.Header.Set("X-IDE-Type", "CLI")
	req.Header.Set("X-IDE-Name", "CLI")
	req.Header.Set("X-IDE-Version", "2.95.0")
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("X-Conversation-ID", convID)
	req.Header.Set("X-Conversation-Message-ID", msgID)
	req.Header.Set("X-Conversation-Request-ID", "")
	req.Header.Set("X-Request-ID", reqID)
	req.Header.Set("X-Agent-Intent", "craft")
	req.Header.Set("X-Agent-Purpose", "conversation")
	req.Header.Set("User-Agent", "CLI/2.95.0 CodeBuddy/2.95.0")
	req.Header.Set("Origin", c.baseURL)
	req.Header.Set("Referer", c.baseURL+"/")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	return resp, nil
}

func RelaySSE(w http.ResponseWriter, upstream io.Reader) error {
	flusher, ok := w.(http.Flusher)
	if !ok {
		return fmt.Errorf("response writer does not support flushing")
	}

	scanner := bufio.NewScanner(upstream)
	scanner.Buffer(make([]byte, 0, 256*1024), 256*1024)

	for scanner.Scan() {
		line := scanner.Text()
		if _, err := fmt.Fprintf(w, "%s\n", line); err != nil {
			return fmt.Errorf("write sse line: %w", err)
		}
		if line == "" || (len(line) > 5 && line[:5] == "data:") {
			flusher.Flush()
		}
	}
	return scanner.Err()
}

func IsCreditsExhausted(statusCode int, body []byte) bool {
	if statusCode != 429 {
		return false
	}
	return bytes.Contains(body, []byte("14018")) ||
		bytes.Contains(body, []byte("Credits exhausted")) ||
		bytes.Contains(body, []byte("credit_exhausted"))
}

func IsSessionExpired(statusCode int, body []byte) bool {
	if statusCode == 401 {
		return true
	}
	return bytes.Contains(body, []byte("session expired")) ||
		bytes.Contains(body, []byte("redirected to login"))
}

func IsWAFBlocked(statusCode int, body []byte) bool {
	if statusCode == 403 {
		return bytes.Contains(body, []byte("WAF")) ||
			bytes.Contains(body, []byte("blocked")) ||
			bytes.Contains(body, []byte("Forbidden"))
	}
	return false
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
