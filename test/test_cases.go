package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"testing"
	"time"
)

// 测试配置
const (
	TestServerURL = "http://localhost:8080"
	TestTimeout   = 5 * time.Second
)

// 测试辅助函数
func sendHTTPQuery(sql string, params map[string]interface{}) (*QueryResponse, error) {
	reqBody := QueryRequest{
		SQL:    sql,
		Params: params,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return nil, err
	}

	resp, err := http.Post(TestServerURL+"/query", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var response QueryResponse
	err = json.NewDecoder(resp.Body).Decode(&response)
	return &response, err
}

func sendHTTPGet(endpoint string) (map[string]interface{}, error) {
	resp, err := http.Get(TestServerURL + endpoint)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var response map[string]interface{}
	err = json.NewDecoder(resp.Body).Decode(&response)
	return response, err
}

// 1. 基础功能测试
func TestBasicQueries(t *testing.T) {
	tests := []struct {
		name     string
		sql      string
		expected bool
		hasError bool
	}{
		{
			name:     "简单SELECT",
			sql:      "SELECT 1 as num, 'hello' as msg",
			expected: true,
			hasError: false,
		},
		{
			name:     "数学运算",
			sql:      "SELECT 2 + 3 as result, sqrt(16) as sqrt_val",
			expected: true,
			hasError: false,
		},
		{
			name:     "字符串函数",
			sql:      "SELECT upper('duckdb') as upper_str, length('test') as str_len",
			expected: true,
			hasError: false,
		},
		{
			name:     "日期时间",
			sql:      "SELECT current_date as today, current_timestamp as now",
			expected: true,
			hasError: false,
		},
		{
			name:     "错误SQL",
			sql:      "SELECT FROM WHERE",
			expected: false,
			hasError: true,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			resp, err := sendHTTPQuery(test.sql, nil)
			if err != nil {
				t.Fatalf("HTTP请求失败: %v", err)
			}

			if test.hasError {
				if resp.Error == "" {
					t.Error("期望有错误，但没有返回错误")
				}
			} else {
				if resp.Error != "" {
					t.Errorf("不期望错误，但返回: %s", resp.Error)
				}
				if resp.Data == nil {
					t.Error("期望有数据，但data为nil")
				}
			}
		})
	}
}

// 2. DuckDB特有功能测试
func TestDuckDBSpecificFeatures(t *testing.T) {
	tests := []struct {
		name string
		sql  string
	}{
		{
			name: "数组操作",
			sql:  "SELECT [1, 2, 3, 4] as arr, array_length([1, 2, 3], 1) as arr_len",
		},
		{
			name: "JSON操作",
			sql:  "SELECT json('{\"name\": \"test\", \"value\": 42}') as json_data",
		},
		{
			name: "窗口函数",
			sql:  "SELECT row_number() OVER () as rn FROM (VALUES (1), (2), (3)) t(v)",
		},
		{
			name: "列式存储优化查询",
			sql:  "SELECT sum(v) as total FROM (VALUES (1), (2), (3), (4), (5)) t(v)",
		},
		{
			name: "复杂聚合",
			sql:  "SELECT avg(v) as avg_val, stddev(v) as std_val FROM (VALUES (1), (2), (3), (4), (5)) t(v)",
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			resp, err := sendHTTPQuery(test.sql, nil)
			if err != nil {
				t.Fatalf("HTTP请求失败: %v", err)
			}

			if resp.Error != "" {
				t.Errorf("DuckDB特有功能失败: %s", resp.Error)
			}

			if resp.Data == nil {
				t.Error("期望有数据返回")
			}
		})
	}
}

// 3. 表操作测试
func TestTableOperations(t *testing.T) {
	// 创建测试表
	t.Run("创建表", func(t *testing.T) {
		sql := `CREATE TABLE test_users (
			id INTEGER PRIMARY KEY,
			name VARCHAR,
			age INTEGER,
			email VARCHAR,
			created_at TIMESTAMP DEFAULT current_timestamp
		)`

		resp, err := sendHTTPQuery(sql, nil)
		if err != nil {
			t.Fatalf("创建表失败: %v", err)
		}
		if resp.Error != "" {
			t.Errorf("创建表错误: %s", resp.Error)
		}
	})

	// 插入数据
	t.Run("插入数据", func(t *testing.T) {
		sql := `INSERT INTO test_users (id, name, age, email) VALUES 
			(1, 'Alice', 25, 'alice@example.com'),
			(2, 'Bob', 30, 'bob@example.com'),
			(3, 'Charlie', 35, 'charlie@example.com')`

		resp, err := sendHTTPQuery(sql, nil)
		if err != nil {
			t.Fatalf("插入数据失败: %v", err)
		}
		if resp.Error != "" {
			t.Errorf("插入数据错误: %s", resp.Error)
		}
	})

	// 查询数据
	t.Run("查询数据", func(t *testing.T) {
		sql := "SELECT * FROM test_users WHERE age > 25 ORDER BY age"

		resp, err := sendHTTPQuery(sql, nil)
		if err != nil {
			t.Fatalf("查询数据失败: %v", err)
		}
		if resp.Error != "" {
			t.Errorf("查询数据错误: %s", resp.Error)
		}

		// 验证结果
		data, ok := resp.Data.(map[string]interface{})
		if !ok {
			t.Error("返回数据格式错误")
			return
		}

		rows, ok := data["rows"].([]interface{})
		if !ok {
			t.Error("rows数据格式错误")
			return
		}

		if len(rows) != 2 {
			t.Errorf("期望2行数据，实际%d行", len(rows))
		}
	})

	// 更新数据
	t.Run("更新数据", func(t *testing.T) {
		sql := "UPDATE test_users SET age = 31 WHERE name = 'Bob'"

		resp, err := sendHTTPQuery(sql, nil)
		if err != nil {
			t.Fatalf("更新数据失败: %v", err)
		}
		if resp.Error != "" {
			t.Errorf("更新数据错误: %s", resp.Error)
		}
	})

	// 删除数据
	t.Run("删除数据", func(t *testing.T) {
		sql := "DELETE FROM test_users WHERE id = 3"

		resp, err := sendHTTPQuery(sql, nil)
		if err != nil {
			t.Fatalf("删除数据失败: %v", err)
		}
		if resp.Error != "" {
			t.Errorf("删除数据错误: %s", resp.Error)
		}
	})

	// 清理
	t.Run("删除表", func(t *testing.T) {
		sql := "DROP TABLE test_users"

		resp, err := sendHTTPQuery(sql, nil)
		if err != nil {
			t.Fatalf("删除表失败: %v", err)
		}
		if resp.Error != "" {
			t.Errorf("删除表错误: %s", resp.Error)
		}
	})
}

// 4. 参数化查询测试
func TestParameterizedQueries(t *testing.T) {
	// 先创建测试表
	createSQL := `CREATE TABLE param_test (
		id INTEGER,
		name VARCHAR,
		value DOUBLE
	)`
	sendHTTPQuery(createSQL, nil)

	// 插入测试数据
	insertSQL := "INSERT INTO param_test VALUES (1, 'test1', 10.5), (2, 'test2', 20.5), (3, 'test3', 30.5)"
	sendHTTPQuery(insertSQL, nil)

	tests := []struct {
		name   string
		sql    string
		params map[string]interface{}
	}{
		{
			name:   "单参数查询",
			sql:    "SELECT * FROM param_test WHERE id = ?",
			params: map[string]interface{}{"id": 1},
		},
		{
			name:   "多参数查询",
			sql:    "SELECT * FROM param_test WHERE id > ? AND value < ?",
			params: map[string]interface{}{"min_id": 1, "max_value": 25.0},
		},
		{
			name:   "字符串参数",
			sql:    "SELECT * FROM param_test WHERE name LIKE ?",
			params: map[string]interface{}{"pattern": "test%"},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			resp, err := sendHTTPQuery(test.sql, test.params)
			if err != nil {
				t.Fatalf("参数化查询失败: %v", err)
			}
			if resp.Error != "" {
				t.Errorf("参数化查询错误: %s", resp.Error)
			}
		})
	}

	// 清理
	sendHTTPQuery("DROP TABLE param_test", nil)
}

// 5. 分析型查询测试（DuckDB优势场景）
func TestAnalyticalQueries(t *testing.T) {
	// 创建大数据集测试表
	createSQL := `CREATE TABLE sales_data (
		id INTEGER,
		product_id INTEGER,
		category VARCHAR,
		sales_amount DOUBLE,
		sale_date DATE,
		region VARCHAR
	)`
	sendHTTPQuery(createSQL, nil)

	// 插入测试数据
	insertSQL := `INSERT INTO sales_data VALUES 
		(1, 101, 'Electronics', 1500.00, '2024-01-15', 'North'),
		(2, 102, 'Clothing', 800.00, '2024-01-16', 'South'),
		(3, 103, 'Electronics', 2200.00, '2024-01-17', 'East'),
		(4, 104, 'Books', 300.00, '2024-01-18', 'West'),
		(5, 105, 'Electronics', 1800.00, '2024-01-19', 'North'),
		(6, 106, 'Clothing', 1200.00, '2024-01-20', 'South')`
	sendHTTPQuery(insertSQL, nil)

	tests := []struct {
		name        string
		sql         string
		description string
	}{
		{
			name: "聚合分析",
			sql: `SELECT 
				category,
				COUNT(*) as transaction_count,
				SUM(sales_amount) as total_sales,
				AVG(sales_amount) as avg_sales,
				MAX(sales_amount) as max_sales
			FROM sales_data 
			GROUP BY category 
			ORDER BY total_sales DESC`,
			description: "按类别聚合销售数据",
		},
		{
			name: "窗口函数分析",
			sql: `SELECT 
				*,
				ROW_NUMBER() OVER (PARTITION BY category ORDER BY sales_amount DESC) as rank_in_category,
				SUM(sales_amount) OVER (PARTITION BY region) as region_total
			FROM sales_data`,
			description: "使用窗口函数进行排名和累计分析",
		},
		{
			name: "时间序列分析",
			sql: `SELECT 
				DATE_TRUNC('month', sale_date) as month,
				SUM(sales_amount) as monthly_sales,
				COUNT(*) as monthly_transactions
			FROM sales_data 
			GROUP BY DATE_TRUNC('month', sale_date)
			ORDER BY month`,
			description: "按月份聚合销售数据",
		},
		{
			name: "复杂分析查询",
			sql: `WITH regional_stats AS (
				SELECT 
					region,
					AVG(sales_amount) as avg_regional_sales
				FROM sales_data
				GROUP BY region
			)
			SELECT 
				s.*,
				rs.avg_regional_sales,
				s.sales_amount - rs.avg_regional_sales as diff_from_regional_avg
			FROM sales_data s
			JOIN regional_stats rs ON s.region = rs.region
			WHERE s.sales_amount > rs.avg_regional_sales`,
			description: "使用CTE进行复杂分析",
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			resp, err := sendHTTPQuery(test.sql, nil)
			if err != nil {
				t.Fatalf("分析查询失败: %v", err)
			}
			if resp.Error != "" {
				t.Errorf("分析查询错误: %s", resp.Error)
			}

			// 验证执行时间记录
			if resp.ExecutionTime <= 0 {
				t.Error("应该记录执行时间")
			}

			fmt.Printf("查询 '%s' 执行时间: %dms\n", test.name, resp.ExecutionTime)
		})
	}

	// 清理
	sendHTTPQuery("DROP TABLE sales_data", nil)
}

// 6. 健康检查和管理接口测试
func TestManagementEndpoints(t *testing.T) {
	t.Run("健康检查", func(t *testing.T) {
		resp, err := sendHTTPGet("/health")
		if err != nil {
			t.Fatalf("健康检查失败: %v", err)
		}

		status, ok := resp["status"].(string)
		if !ok || status != "healthy" {
			t.Errorf("健康状态异常: %v", resp["status"])
		}

		connected, ok := resp["duckdb_connected"].(bool)
		if !ok || !connected {
			t.Error("DuckDB连接状态异常")
		}
	})

	t.Run("指标接口", func(t *testing.T) {
		resp, err := sendHTTPGet("/metrics")
		if err != nil {
			t.Fatalf("指标获取失败: %v", err)
		}

		queryCount, ok := resp["query_count"].(float64)
		if !ok {
			t.Error("查询计数格式错误")
		}

		if queryCount < 0 {
			t.Error("查询计数应该大于等于0")
		}

		fmt.Printf("当前查询计数: %.0f\n", queryCount)
	})

	t.Run("列出表", func(t *testing.T) {
		// 先创建一个测试表
		sendHTTPQuery("CREATE TABLE list_test (id INTEGER)", nil)

		resp, err := sendHTTPGet("/admin/tables")
		if err != nil {
			t.Fatalf("列出表失败: %v", err)
		}

		if resp["error"] != nil {
			t.Errorf("列出表错误: %v", resp["error"])
		}

		// 清理
		sendHTTPQuery("DROP TABLE list_test", nil)
	})
}

// 7. 错误处理测试
func TestErrorHandling(t *testing.T) {
	tests := []struct {
		name     string
		sql      string
		hasError bool
	}{
		{
			name:     "语法错误",
			sql:      "SELCT * FRM table",
			hasError: true,
		},
		{
			name:     "表不存在",
			sql:      "SELECT * FROM non_existent_table",
			hasError: true,
		},
		{
			name:     "列不存在",
			sql:      "SELECT non_existent_column FROM (SELECT 1 as id) t",
			hasError: true,
		},
		{
			name:     "类型错误",
			sql:      "SELECT 'string' + 123",
			hasError: true,
		},
		{
			name:     "除零错误",
			sql:      "SELECT 1/0",
			hasError: true,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			resp, err := sendHTTPQuery(test.sql, nil)
			if err != nil {
				t.Fatalf("HTTP请求失败: %v", err)
			}

			if test.hasError && resp.Error == "" {
				t.Error("期望有错误，但没有返回错误")
			}

			if !test.hasError && resp.Error != "" {
				t.Errorf("不期望错误，但返回: %s", resp.Error)
			}
		})
	}
}

// 8. 并发测试
func TestConcurrentQueries(t *testing.T) {
	const numGoroutines = 10
	const queriesPerGoroutine = 5

	results := make(chan error, numGoroutines*queriesPerGoroutine)

	for i := 0; i < numGoroutines; i++ {
		go func(goroutineID int) {
			for j := 0; j < queriesPerGoroutine; j++ {
				sql := fmt.Sprintf("SELECT %d as goroutine_id, %d as query_id, current_timestamp as ts", goroutineID, j)
				resp, err := sendHTTPQuery(sql, nil)
				if err != nil {
					results <- fmt.Errorf("goroutine %d query %d failed: %v", goroutineID, j, err)
					continue
				}
				if resp.Error != "" {
					results <- fmt.Errorf("goroutine %d query %d error: %s", goroutineID, j, resp.Error)
					continue
				}
				results <- nil
			}
		}(i)
	}

	// 收集结果
	errorCount := 0
	for i := 0; i < numGoroutines*queriesPerGoroutine; i++ {
		if err := <-results; err != nil {
			t.Errorf("并发查询错误: %v", err)
			errorCount++
		}
	}

	if errorCount > 0 {
		t.Errorf("并发测试失败，错误数量: %d", errorCount)
	} else {
		fmt.Printf("并发测试成功：%d个goroutine，每个执行%d个查询\n", numGoroutines, queriesPerGoroutine)
	}
}

// 9. 性能基准测试
func BenchmarkSimpleQuery(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_, err := sendHTTPQuery("SELECT 1", nil)
		if err != nil {
			b.Fatalf("基准测试失败: %v", err)
		}
	}
}

func BenchmarkComplexQuery(b *testing.B) {
	// 准备测试数据
	sendHTTPQuery("CREATE TABLE IF NOT EXISTS bench_test (id INTEGER, value DOUBLE)", nil)
	sendHTTPQuery("INSERT INTO bench_test SELECT i, random() FROM generate_series(1, 1000) s(i)", nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sql := `SELECT 
			COUNT(*) as count,
			AVG(value) as avg_value,
			SUM(value) as sum_value,
			MIN(value) as min_value,
			MAX(value) as max_value
		FROM bench_test`

		_, err := sendHTTPQuery(sql, nil)
		if err != nil {
			b.Fatalf("复杂查询基准测试失败: %v", err)
		}
	}

	// 清理
	sendHTTPQuery("DROP TABLE bench_test", nil)
}

// 主测试函数
func TestMain(m *testing.M) {
	// 这里可以添加测试前的准备工作
	fmt.Println("开始DuckDB多协议服务测试...")

	// 运行所有测试
	m.Run()

	// 这里可以添加测试后的清理工作
	fmt.Println("测试完成")
}
