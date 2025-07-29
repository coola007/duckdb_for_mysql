package config

import (
	"encoding/json"
	"fmt"
	"os"
)

// ServerConfig 服务器配置结构
type ServerConfig struct {
	HTTPPort  int    `json:"http_port"`
	MySQLPort int    `json:"mysql_port"`
	DBPath    string `json:"db_path"`
	MaxConns  int    `json:"max_connections"`
	LogLevel  string `json:"log_level,omitempty"`
}

// DefaultConfig 返回默认配置
func DefaultConfig() *ServerConfig {
	return &ServerConfig{
		HTTPPort:  8080,
		MySQLPort: 3366,
		DBPath:    ":memory:",
		MaxConns:  100,
		LogLevel:  "info",
	}
}

// LoadConfig 从文件加载配置
func LoadConfig(configPath string) (*ServerConfig, error) {
	// 如果配置文件不存在，使用默认配置
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		fmt.Printf("配置文件 %s 不存在，使用默认配置\n", configPath)
		return DefaultConfig(), nil
	}

	// 读取配置文件
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, fmt.Errorf("读取配置文件失败: %v", err)
	}

	// 解析JSON配置
	var config ServerConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("解析配置文件失败: %v", err)
	}

	// 验证配置
	if err := validateConfig(&config); err != nil {
		return nil, fmt.Errorf("配置验证失败: %v", err)
	}

	fmt.Printf("成功加载配置: HTTP端口=%d, MySQL端口=%d, 数据库路径=%s\n",
		config.HTTPPort, config.MySQLPort, config.DBPath)

	return &config, nil
}

// SaveConfig 保存配置到文件
func SaveConfig(config *ServerConfig, configPath string) error {
	data, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return fmt.Errorf("序列化配置失败: %v", err)
	}

	if err := os.WriteFile(configPath, data, 0644); err != nil {
		return fmt.Errorf("写入配置文件失败: %v", err)
	}

	return nil
}

// validateConfig 验证配置参数
func validateConfig(config *ServerConfig) error {
	if config.HTTPPort <= 0 || config.HTTPPort > 65535 {
		return fmt.Errorf("HTTP端口无效: %d", config.HTTPPort)
	}

	if config.MySQLPort <= 0 || config.MySQLPort > 65535 {
		return fmt.Errorf("MySQL端口无效: %d", config.MySQLPort)
	}

	if config.HTTPPort == config.MySQLPort {
		return fmt.Errorf("HTTP端口和MySQL端口不能相同: %d", config.HTTPPort)
	}

	if config.MaxConns <= 0 {
		return fmt.Errorf("最大连接数必须大于0: %d", config.MaxConns)
	}

	return nil
}
