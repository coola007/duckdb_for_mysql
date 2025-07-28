package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"sync"
	"time"

	_ "github.com/marcboeker/go-duckdb"
)

// 统一服务配置
type ServerConfig struct {
	HTTPPort  int    `json:"http_port"`
	MySQLPort int    `json:"mysql_port"`
	DBPath    string `json:"db_path"`
	MaxConns  int    `json:"max_connections"`
}

// 查询请求/响应结构
type QueryRequest struct {
	SQL    string                 `json:"sql"`
	Params map[string]interface{} `json:"params,omitempty"`
}

type QueryResponse struct {
	Data          interface{} `json:"data"`
	Error         string      `json:"error,omitempty"`
	RowsAffected  int64       `json:"rows_affected,omitempty"`
	ExecutionTime int64       `json:"execution_time_ms,omitempty"`
}

// 统一服务结构
type DuckDBMultiProtocolServer struct {
	config      *ServerConfig
	duckdb      *sql.DB
	httpServer  *http.Server
	mysqlServer *MySQLServer
	auth        *AuthManager
	metrics     *MetricsCollector
	ctx         context.Context
	cancel      context.CancelFunc
	wg          sync.WaitGroup
}

// 认证管理器
type AuthManager struct {
	users map[string]string
	mu    sync.RWMutex
}

func NewAuthManager() *AuthManager {
	return &AuthManager{
		users: make(map[string]string),
	}
}

func (am *AuthManager) Authenticate(username, password string) bool {
	am.mu.RLock()
	defer am.mu.RUnlock()

	storedPassword, exists := am.users[username]
	return exists && storedPassword == password
}

// 指标收集器
type MetricsCollector struct {
	queryCount  int64
	errorCount  int64
	activeConns int64
	mu          sync.RWMutex
}

func NewMetricsCollector() *MetricsCollector {
	return &MetricsCollector{}
}

func (mc *MetricsCollector) IncrementQueryCount() {
	mc.mu.Lock()
	defer mc.mu.Unlock()
	mc.queryCount++
}

func (mc *MetricsCollector) IncrementErrorCount() {
	mc.mu.Lock()
	defer mc.mu.Unlock()
	mc.errorCount++
}

// MySQL协议服务器（简化版）
type MySQLServer struct {
	server *DuckDBMultiProtocolServer
	port   int
}

func NewMySQLServer(server *DuckDBMultiProtocolServer, port int) *MySQLServer {
	return &MySQLServer{
		server: server,
		port:   port,
	}
}

func (ms *MySQLServer) Start() error {
	listener, err := net.Listen("tcp", fmt.Sprintf(":%d", ms.port))
	if err != nil {
		return fmt.Errorf("failed to start MySQL server: %v", err)
	}

	ms.server.wg.Add(1)
	go func() {
		defer ms.server.wg.Done()
		for {
			select {
			case <-ms.server.ctx.Done():
				return
			default:
				conn, err := listener.Accept()
				if err != nil {
					log.Printf("MySQL accept error: %v", err)
					continue
				}
				go ms.handleConnection(conn)
			}
		}
	}()

	log.Printf("MySQL server started on port %d", ms.port)
	return nil
}

func (ms *MySQLServer) handleConnection(conn net.Conn) {
	defer conn.Close()

	// 简化的MySQL协议处理
	// 实际实现需要完整的MySQL协议栈
	log.Printf("MySQL connection from %s", conn.RemoteAddr())

	// 发送MySQL握手包
	ms.sendHandshake(conn)

	// 处理认证和查询
	ms.handleQueries(conn)
}

func (ms *MySQLServer) sendHandshake(conn net.Conn) {
	// 简化的MySQL握手包
	handshake := []byte{
		0x0a,                                           // protocol version
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // server version
		0x00,                                           // connection id
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // auth-plugin-data-part-1
		0x00,       // filler
		0x00, 0x00, // capability flags
		0x21,       // character set
		0x00, 0x00, // status flags
		0x00, 0x00, // capability flags part 2
		0x00,                                                       // auth plugin data len
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // reserved
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // auth-plugin-data-part-2
	}
	conn.Write(handshake)
}

func (ms *MySQLServer) handleQueries(conn net.Conn) {
	// 简化的查询处理
	buffer := make([]byte, 1024)
	for {
		n, err := conn.Read(buffer)
		if err != nil {
			log.Printf("MySQL read error: %v", err)
			return
		}

		// 这里需要解析MySQL协议包
		// 简化处理：假设收到的就是SQL查询
		query := string(buffer[:n])
		log.Printf("MySQL query: %s", query)

		// 执行查询
		response := ms.server.executeQuery(query)

		// 发送结果
		ms.sendResult(conn, response)
	}
}

func (ms *MySQLServer) sendResult(conn net.Conn, response *QueryResponse) {
	// 简化的结果发送
	if response.Error != "" {
		// 发送错误包
		errorPacket := []byte{0xff, 0x00, 0x00, 0x00, 0x00}
		conn.Write(errorPacket)
	} else {
		// 发送成功包
		okPacket := []byte{0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}
		conn.Write(okPacket)
	}
}

// 创建统一服务
func NewDuckDBMultiProtocolServer(config *ServerConfig) (*DuckDBMultiProtocolServer, error) {
	// 连接DuckDB - 使用正确的DuckDB连接方式
	// DuckDB支持内存数据库和文件数据库
	// 空字符串表示内存数据库，文件路径表示持久化数据库
	dbPath := config.DBPath
	if dbPath == ":memory:" {
		dbPath = "" // DuckDB中空字符串表示内存数据库
	}

	db, err := sql.Open("duckdb", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to DuckDB: %v", err)
	}

	log.Printf("Connected to DuckDB: %s", dbPath)

	// 设置连接池
	db.SetMaxOpenConns(config.MaxConns)
	db.SetMaxIdleConns(config.MaxConns / 2)
	db.SetConnMaxLifetime(time.Hour)

	ctx, cancel := context.WithCancel(context.Background())

	server := &DuckDBMultiProtocolServer{
		config:  config,
		duckdb:  db,
		auth:    NewAuthManager(),
		metrics: NewMetricsCollector(),
		ctx:     ctx,
		cancel:  cancel,
	}

	// 创建MySQL服务器
	server.mysqlServer = NewMySQLServer(server, config.MySQLPort)

	// 设置HTTP服务器
	server.setupHTTPServer()

	return server, nil
}

func (s *DuckDBMultiProtocolServer) setupHTTPServer() {
	mux := http.NewServeMux()

	// 查询接口
	mux.HandleFunc("/query", s.handleHTTPQuery)

	// 健康检查
	mux.HandleFunc("/health", s.handleHealth)

	// 指标接口
	mux.HandleFunc("/metrics", s.handleMetrics)

	// 管理接口
	mux.HandleFunc("/admin/tables", s.handleListTables)
	mux.HandleFunc("/admin/execute", s.handleAdminExecute)

	s.httpServer = &http.Server{
		Addr:    fmt.Sprintf(":%d", s.config.HTTPPort),
		Handler: mux,
	}
}

func (s *DuckDBMultiProtocolServer) Start() error {
	// 启动MySQL服务器
	if err := s.mysqlServer.Start(); err != nil {
		return err
	}

	// 启动HTTP服务器
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		log.Printf("HTTP server starting on port %d", s.config.HTTPPort)
		if err := s.httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("HTTP server error: %v", err)
		}
	}()

	log.Printf("DuckDB Multi-Protocol Server started")
	log.Printf("  HTTP API: http://localhost:%d", s.config.HTTPPort)
	log.Printf("  MySQL: localhost:%d", s.config.MySQLPort)

	return nil
}

func (s *DuckDBMultiProtocolServer) Stop() error {
	s.cancel()

	// 关闭HTTP服务器
	if s.httpServer != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		s.httpServer.Shutdown(ctx)
	}

	// 关闭数据库连接
	if s.duckdb != nil {
		s.duckdb.Close()
	}

	// 等待所有goroutine完成
	s.wg.Wait()

	log.Println("Server stopped gracefully")
	return nil
}

// HTTP处理器
func (s *DuckDBMultiProtocolServer) handleHTTPQuery(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req QueryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	response := s.executeQuery(req.SQL)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *DuckDBMultiProtocolServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"status":           "healthy",
		"timestamp":        time.Now().Unix(),
		"duckdb_connected": s.duckdb != nil,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *DuckDBMultiProtocolServer) handleMetrics(w http.ResponseWriter, r *http.Request) {
	s.metrics.mu.RLock()
	defer s.metrics.mu.RUnlock()

	response := map[string]interface{}{
		"query_count":        s.metrics.queryCount,
		"error_count":        s.metrics.errorCount,
		"active_connections": s.metrics.activeConns,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *DuckDBMultiProtocolServer) handleListTables(w http.ResponseWriter, r *http.Request) {
	query := "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
	response := s.executeQuery(query)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *DuckDBMultiProtocolServer) handleAdminExecute(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req QueryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	response := s.executeQuery(req.SQL)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// 统一的查询执行器
func (s *DuckDBMultiProtocolServer) executeQuery(sqlQuery string) *QueryResponse {
	start := time.Now()
	s.metrics.IncrementQueryCount()

	// 执行查询
	rows, err := s.duckdb.Query(sqlQuery)
	if err != nil {
		s.metrics.IncrementErrorCount()
		return &QueryResponse{
			Error: err.Error(),
		}
	}
	defer rows.Close()

	// 获取列信息
	columns, err := rows.Columns()
	if err != nil {
		s.metrics.IncrementErrorCount()
		return &QueryResponse{
			Error: err.Error(),
		}
	}

	// 扫描结果
	var results []map[string]interface{}
	for rows.Next() {
		values := make([]interface{}, len(columns))
		valuePtrs := make([]interface{}, len(columns))
		for i := range values {
			valuePtrs[i] = &values[i]
		}

		if err := rows.Scan(valuePtrs...); err != nil {
			s.metrics.IncrementErrorCount()
			return &QueryResponse{
				Error: err.Error(),
			}
		}

		row := make(map[string]interface{})
		for i, col := range columns {
			val := values[i]
			row[col] = val
		}
		results = append(results, row)
	}

	executionTime := time.Since(start).Milliseconds()

	return &QueryResponse{
		Data: map[string]interface{}{
			"columns": columns,
			"rows":    results,
			"count":   len(results),
		},
		ExecutionTime: executionTime,
	}
}

func main() {
	config := &ServerConfig{
		HTTPPort:  8080,
		MySQLPort: 3366,
		DBPath:    ":memory:",
		MaxConns:  10,
	}

	server, err := NewDuckDBMultiProtocolServer(config)
	if err != nil {
		log.Fatalf("Failed to create server: %v", err)
	}

	// 优雅关闭
	go func() {
		// 这里可以添加信号处理
		// sigChan := make(chan os.Signal, 1)
		// signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
		// <-sigChan
		// server.Stop()
	}()

	if err := server.Start(); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}

	// 保持服务运行
	select {}
}
