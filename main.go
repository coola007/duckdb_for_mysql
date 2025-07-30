package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"duckdb-server/internal/config"
	"duckdb-server/internal/database"
	"duckdb-server/internal/http"
	"duckdb-server/internal/mysql"
	"duckdb-server/internal/query"
)

// 版本信息 - 在编译时通过 -ldflags 设置
var (
	Version   = "dev"
	BuildTime = "unknown"
	GitCommit = "unknown"
)

func main() {
	// 命令行参数
	var (
		showVersion = flag.Bool("version", false, "显示版本信息")
		configPath  = flag.String("config", "config.json", "配置文件路径")
	)
	flag.Parse()

	// 显示版本信息
	if *showVersion {
		fmt.Printf("DuckDB MySQL协议服务器\n")
		fmt.Printf("版本:     %s\n", Version)
		fmt.Printf("构建时间: %s\n", BuildTime)
		fmt.Printf("Git提交:  %s\n", GitCommit)
		fmt.Printf("Go版本:   %s\n", "go1.21+")
		os.Exit(0)
	}

	// 从环境变量获取配置路径
	if envConfig := os.Getenv("CONFIG_PATH"); envConfig != "" {
		*configPath = envConfig
	}

	// 加载配置
	cfg, err := config.LoadConfig(*configPath)
	if err != nil {
		log.Fatalf("❌ 加载配置失败: %v", err)
	}

	fmt.Printf("成功加载配置: HTTP端口=%d, MySQL端口=%d, 数据库路径=%s\n",
		cfg.HTTPPort, cfg.MySQLPort, cfg.DBPath)

	// 初始化数据库
	db, err := database.NewDuckDB(cfg.DBPath, cfg.MaxConns)
	if err != nil {
		log.Fatalf("❌ 连接DuckDB失败: %v", err)
	}
	defer db.Close()

	// 创建查询执行器
	executor := query.NewExecutor(db)

	// 创建HTTP服务器
	httpServer := http.NewServer(cfg.HTTPPort, db)

	// 创建MySQL服务器
	mysqlServer := mysql.NewServer(cfg.MySQLPort, executor)

	// 启动服务器
	go func() {
		if err := httpServer.Start(); err != nil {
			log.Fatalf("❌ 启动HTTP服务器失败: %v", err)
		}
	}()

	go func() {
		if err := mysqlServer.Start(); err != nil {
			log.Fatalf("❌ 启动MySQL服务器失败: %v", err)
		}
	}()

	// 显示启动信息
	fmt.Printf("🚀 DuckDB服务器启动成功！\n")
	fmt.Printf("📊 HTTP API: http://localhost:%d\n", cfg.HTTPPort)
	fmt.Printf("🐬 MySQL协议: localhost:%d\n", cfg.MySQLPort)
	fmt.Printf("💾 数据库: %s\n", cfg.DBPath)
	fmt.Printf("📖 版本: %s (%s)\n", Version, GitCommit)

	// 等待中断信号
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	<-c

	fmt.Printf("\n🛑 收到停止信号，正在关闭服务器...\n")

	// 优雅关闭
	if err := httpServer.Stop(); err != nil {
		log.Printf("关闭HTTP服务器失败: %v", err)
	}

	if err := mysqlServer.Stop(); err != nil {
		log.Printf("关闭MySQL服务器失败: %v", err)
	}

	fmt.Printf("✅ 服务器已关闭\n")
}
