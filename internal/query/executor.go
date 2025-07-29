package query

import (
	"sync"
	"time"

	"duckdb-server/internal/database"
)

// Request 查询请求
type Request struct {
	SQL    string                 `json:"sql"`
	Params map[string]interface{} `json:"params,omitempty"`
}

// Response 查询响应
type Response struct {
	Data          interface{} `json:"data"`
	Error         string      `json:"error,omitempty"`
	RowsAffected  int64       `json:"rows_affected,omitempty"`
	ExecutionTime int64       `json:"execution_time_ms,omitempty"`
}

// Stats 查询统计
type Stats struct {
	QueryCount int64 `json:"query_count"`
	ErrorCount int64 `json:"error_count"`
	AvgTime    int64 `json:"avg_execution_time_ms"`
	TotalTime  int64 `json:"total_execution_time_ms"`
}

// Executor 查询执行器
type Executor struct {
	db    *database.DB
	stats Stats
	mutex sync.RWMutex
}

// NewExecutor 创建查询执行器
func NewExecutor(db *database.DB) *Executor {
	return &Executor{
		db: db,
	}
}

// Execute 执行SQL查询
func (e *Executor) Execute(sqlQuery string) *Response {
	start := time.Now()

	e.mutex.Lock()
	e.stats.QueryCount++
	e.mutex.Unlock()

	// 执行查询
	rows, err := e.db.Query(sqlQuery)
	if err != nil {
		e.mutex.Lock()
		e.stats.ErrorCount++
		e.mutex.Unlock()

		return &Response{
			Error: err.Error(),
		}
	}
	defer rows.Close()

	// 获取列信息
	columns, err := rows.Columns()
	if err != nil {
		e.mutex.Lock()
		e.stats.ErrorCount++
		e.mutex.Unlock()

		return &Response{
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
			e.mutex.Lock()
			e.stats.ErrorCount++
			e.mutex.Unlock()

			return &Response{
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

	// 更新统计信息
	e.mutex.Lock()
	e.stats.TotalTime += executionTime
	if e.stats.QueryCount > 0 {
		e.stats.AvgTime = e.stats.TotalTime / e.stats.QueryCount
	}
	e.mutex.Unlock()

	return &Response{
		Data: map[string]interface{}{
			"columns": columns,
			"rows":    results,
			"count":   len(results),
		},
		ExecutionTime: executionTime,
	}
}

// GetStats 获取统计信息
func (e *Executor) GetStats() Stats {
	e.mutex.RLock()
	defer e.mutex.RUnlock()
	return e.stats
}
