package database

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "github.com/marcboeker/go-duckdb"
)

// DB 数据库连接封装
type DB struct {
	conn *sql.DB
}

// NewDuckDB 创建DuckDB连接
func NewDuckDB(dbPath string, maxConns int) (*DB, error) {
	// 处理内存数据库路径
	if dbPath == ":memory:" {
		dbPath = "" // DuckDB使用空字符串表示内存数据库
	}

	// 连接数据库
	conn, err := sql.Open("duckdb", dbPath)
	if err != nil {
		return nil, fmt.Errorf("连接DuckDB失败: %v", err)
	}

	// 设置连接池参数
	conn.SetMaxOpenConns(maxConns)
	conn.SetMaxIdleConns(maxConns / 2)
	conn.SetConnMaxLifetime(time.Hour)

	// 测试连接
	if err := conn.Ping(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("DuckDB连接测试失败: %v", err)
	}

	log.Printf("DuckDB连接成功: %s (最大连接数: %d)", dbPath, maxConns)

	return &DB{conn: conn}, nil
}

// Close 关闭数据库连接
func (db *DB) Close() error {
	if db.conn != nil {
		return db.conn.Close()
	}
	return nil
}

// Query 执行查询
func (db *DB) Query(query string, args ...interface{}) (*sql.Rows, error) {
	return db.conn.Query(query, args...)
}

// Exec 执行非查询语句
func (db *DB) Exec(query string, args ...interface{}) (sql.Result, error) {
	return db.conn.Exec(query, args...)
}

// QueryRow 执行单行查询
func (db *DB) QueryRow(query string, args ...interface{}) *sql.Row {
	return db.conn.QueryRow(query, args...)
}

// Ping 测试连接
func (db *DB) Ping() error {
	return db.conn.Ping()
}

// Stats 获取连接池统计信息
func (db *DB) Stats() sql.DBStats {
	return db.conn.Stats()
}
