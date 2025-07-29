package http

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"duckdb-server/internal/database"
	"duckdb-server/internal/query"
)

// Server HTTP服务器
type Server struct {
	port     int
	db       *database.DB
	executor *query.Executor
	server   *http.Server
}

// NewServer 创建HTTP服务器
func NewServer(port int, db *database.DB) *Server {
	executor := query.NewExecutor(db)

	return &Server{
		port:     port,
		db:       db,
		executor: executor,
	}
}

// Start 启动HTTP服务器
func (s *Server) Start() error {
	mux := http.NewServeMux()

	// 注册路由
	mux.HandleFunc("/query", s.handleQuery)
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/metrics", s.handleMetrics)
	mux.HandleFunc("/admin/tables", s.handleListTables)
	mux.HandleFunc("/admin/execute", s.handleAdminExecute)

	s.server = &http.Server{
		Addr:         fmt.Sprintf(":%d", s.port),
		Handler:      mux,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	log.Printf("HTTP服务器启动在端口 %d", s.port)

	go func() {
		if err := s.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP服务器失败: %v", err)
		}
	}()

	return nil
}

// Stop 停止HTTP服务器
func (s *Server) Stop() error {
	if s.server == nil {
		return nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	return s.server.Shutdown(ctx)
}

// handleQuery 处理查询请求
func (s *Server) handleQuery(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "只支持POST方法", http.StatusMethodNotAllowed)
		return
	}

	var req query.Request
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "请求体格式错误", http.StatusBadRequest)
		return
	}

	// 执行查询
	response := s.executor.Execute(req.SQL)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleHealth 健康检查
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	var dbConnected bool
	if s.db != nil {
		dbConnected = s.db.Ping() == nil
	}

	response := map[string]interface{}{
		"status":           "healthy",
		"timestamp":        time.Now().Unix(),
		"duckdb_connected": dbConnected,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleMetrics 指标接口
func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	stats := s.executor.GetStats()

	var dbStats interface{}
	if s.db != nil {
		dbStats = s.db.Stats()
	}

	response := map[string]interface{}{
		"query_stats": stats,
		"db_stats":    dbStats,
		"timestamp":   time.Now().Unix(),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleListTables 列出表
func (s *Server) handleListTables(w http.ResponseWriter, r *http.Request) {
	sql := "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
	response := s.executor.Execute(sql)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleAdminExecute 管理员执行SQL
func (s *Server) handleAdminExecute(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "只支持POST方法", http.StatusMethodNotAllowed)
		return
	}

	var req query.Request
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "请求体格式错误", http.StatusBadRequest)
		return
	}

	response := s.executor.Execute(req.SQL)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
