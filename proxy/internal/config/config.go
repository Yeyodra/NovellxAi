package config

import (
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Server   ServerConfig            `yaml:"server"`
	Upstream UpstreamConfig          `yaml:"upstream"`
	KeyPool  KeyPoolConfig           `yaml:"keypool"`
	Database DatabaseConfig          `yaml:"database"`
	ModelMap map[string]string       `yaml:"model_map"`
	Logging  LoggingConfig           `yaml:"logging"`
}

type ServerConfig struct {
	Addr      string `yaml:"addr"`
	AuthToken string `yaml:"auth_token"`
}

type UpstreamConfig struct {
	BaseURL    string        `yaml:"base_url"`
	ChatPath   string        `yaml:"chat_path"`
	Timeout    time.Duration `yaml:"timeout"`
	MaxRetries int           `yaml:"max_retries"`
}

type KeyPoolConfig struct {
	CooldownDuration time.Duration `yaml:"cooldown_duration"`
	MinActiveKeys    int           `yaml:"min_active_keys"`
}

type DatabaseConfig struct {
	Path string `yaml:"path"`
}

type LoggingConfig struct {
	Level string `yaml:"level"`
}

func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	cfg := &Config{
		Server: ServerConfig{
			Addr: ":8080",
		},
		Upstream: UpstreamConfig{
			BaseURL:    "https://www.codebuddy.ai",
			ChatPath:   "/v1/chat/completions",
			Timeout:    120 * time.Second,
			MaxRetries: 3,
		},
		KeyPool: KeyPoolConfig{
			CooldownDuration: 60 * time.Second,
			MinActiveKeys:    5,
		},
		Database: DatabaseConfig{
			Path: "./data/proxy.db",
		},
		Logging: LoggingConfig{
			Level: "info",
		},
	}

	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, err
	}

	return cfg, nil
}
