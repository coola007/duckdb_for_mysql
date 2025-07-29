package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"

	"duckdb-server/internal/config"
	"duckdb-server/internal/database"
	"duckdb-server/internal/http"
	"duckdb-server/internal/mysql"
	"duckdb-server/internal/query"
)

// Server 主服务器
type Server struct {
	config      *config.ServerConfig
	db          *database.DB
	httpServer  *http.Server
	mysqlServer *mysql.Server
	executor    *query.Executor
	ctx         context.Context
	cancel      context.CancelFunc
	wg          sync.WaitGroup
}

// NewServer 创建服务器实例
func NewServer(cfg *config.ServerConfig) (*Server, error) {
	// 创建数据库连接
	db, err := database.NewDuckDB(cfg.DBPath, cfg.MaxConns)
	if err != nil {
		return nil, err
	}

	// 创建查询执行器
	executor := query.NewExecutor(db)

	// 创建HTTP服务器
	httpServer := http.NewServer(cfg.HTTPPort, db)

	// 创建MySQL服务器
	mysqlServer := mysql.NewServer(cfg.MySQLPort, executor)

	ctx, cancel := context.WithCancel(context.Background())

	return &Server{
		config:      cfg,
		db:          db,
		httpServer:  httpServer,
		mysqlServer: mysqlServer,
		executor:    executor,
		ctx:         ctx,
		cancel:      cancel,
	}, nil
}

// Start 启动服务器
func (s *Server) Start() error {
	log.Println("🚀 启动DuckDB多协议服务器...")

	// 启动HTTP服务器
	if err := s.httpServer.Start(); err != nil {
		return err
	}

	// 启动MySQL服务器
	if err := s.mysqlServer.Start(); err != nil {
		return err
	}

	log.Printf("✅ 服务器启动成功!")
	log.Printf("   HTTP API: http://localhost:%d", s.config.HTTPPort)
	log.Printf("   MySQL协议: localhost:%d", s.config.MySQLPort)

	return nil
}

// Stop 停止服务器
func (s *Server) Stop() error {
	log.Println("🛑 停止服务器...")

	s.cancel()

	// 停止HTTP服务器
	if err := s.httpServer.Stop(); err != nil {
		log.Printf("停止HTTP服务器错误: %v", err)
	}

	// 停止MySQL服务器
	if err := s.mysqlServer.Stop(); err != nil {
		log.Printf("停止MySQL服务器错误: %v", err)
	}

	// 关闭数据库连接
	if err := s.db.Close(); err != nil {
		log.Printf("关闭数据库连接错误: %v", err)
	}

	s.wg.Wait()
	log.Println("✅ 服务器已停止")

	return nil
}

// WaitForShutdown 等待停止信号
func (s *Server) WaitForShutdown() {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-sigChan:
		log.Printf("📨 收到信号: %v", sig)
	case <-s.ctx.Done():
		log.Println("📨 收到上下文取消信号")
	}

	s.Stop()
}

func main() {
	// 解析命令行参数
	var configPath = flag.String("config", "config.json", "配置文件路径")
	var showVersion = flag.Bool("version", false, "显示版本信息")
	flag.Parse()

	// 显示版本信息
	if *showVersion {
		log.Println("DuckDB Multi-Protocol Server v1.0.0")
		return
	}

	// 加载配置
	cfg, err := config.LoadConfig(*configPath)
	if err != nil {
		log.Fatalf("❌ 加载配置失败: %v", err)
	}

	// 创建服务器
	server, err := NewServer(cfg)
	if err != nil {
		log.Fatalf("❌ 创建服务器失败: %v", err)
	}

	// 启动服务器
	if err := server.Start(); err != nil {
		log.Fatalf("❌ 启动服务器失败: %v", err)
	}

	// 等待停止信号
	server.WaitForShutdown()
}
