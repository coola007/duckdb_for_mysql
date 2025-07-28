# DuckDB Multi-Protocol Server 测试指南

本文档详细介绍了DuckDB多协议服务的测试体系，包含HTTP API、MySQL协议、性能测试和边界案例测试。

## 测试概览

### 测试架构
```
测试套件
├── HTTP API 测试 (quick_test.sh)
├── MySQL 协议测试 (test_mysql_protocol.py)
├── Go 单元测试 (test_cases.go)
├── 性能基准测试 (Benchmark*)
└── 综合测试脚本 (run_tests.sh)
```

### 覆盖范围
- ✅ **基础功能**: SELECT、INSERT、UPDATE、DELETE
- ✅ **DuckDB特性**: 数组、窗口函数、聚合分析
- ✅ **协议兼容**: HTTP REST API + MySQL TCP协议
- ✅ **错误处理**: 语法错误、连接错误、类型错误
- ✅ **并发性能**: 多连接、高并发查询
- ✅ **管理接口**: 健康检查、指标监控、表管理

## 快速开始

### 1. 一键运行所有测试
```bash
./run_tests.sh
```

### 2. 单独运行HTTP API测试
```bash
# 先启动服务
go run main.go &

# 运行HTTP测试
./quick_test.sh
```

### 3. 单独运行MySQL协议测试
```bash
# 先启动服务
go run main.go &

# 运行MySQL协议测试
python3 test_mysql_protocol.py
```

### 4. 单独运行Go单元测试
```bash
go test -v ./... -run="Test.*"
```

### 5. 运行性能基准测试
```bash
go test -bench=. -run="Benchmark.*"
```

## 详细测试用例

### 1. HTTP API 测试 (`quick_test.sh`)

#### 1.1 基础SQL查询测试
- **简单SELECT**: `SELECT 1 as num, "hello" as msg`
- **数学运算**: `SELECT 2 + 3 as result, sqrt(16) as sqrt_val`
- **字符串函数**: `SELECT upper("duckdb") as upper_str, length("test") as str_len`
- **当前时间**: `SELECT current_date as today, current_timestamp as now`

#### 1.2 DuckDB特有功能测试
- **数组操作**: `SELECT [1, 2, 3, 4] as arr`
- **窗口函数**: `SELECT row_number() OVER () as rn FROM (VALUES (1), (2), (3)) t(v)`
- **聚合函数**: `SELECT sum(v) as total, avg(v) as average FROM (VALUES (1), (2), (3), (4), (5)) t(v)`

#### 1.3 表操作测试
```sql
-- 创建表
CREATE TABLE quick_test (id INTEGER, name VARCHAR, value DOUBLE)

-- 插入数据
INSERT INTO quick_test VALUES (1, "test1", 10.5), (2, "test2", 20.5)

-- 查询数据
SELECT * FROM quick_test ORDER BY id

-- 更新数据
UPDATE quick_test SET value = 15.5 WHERE id = 1

-- 删除数据
DELETE FROM quick_test WHERE id = 2

-- 删除表
DROP TABLE quick_test
```

#### 1.4 错误处理测试
- **语法错误**: `SELCT * FRM table`
- **表不存在**: `SELECT * FROM non_existent_table`

#### 1.5 管理接口测试
- **健康检查**: `GET /health`
- **查看指标**: `GET /metrics`
- **列出表**: `GET /admin/tables`

#### 1.6 性能测试
- 100次简单查询的吞吐量测试
- 执行时间统计

#### 1.7 分析型查询测试
```sql
-- 创建销售数据分析表
CREATE TABLE sales (id INTEGER, category VARCHAR, amount DOUBLE, date DATE)

-- 聚合分析
SELECT category, COUNT(*) as count, SUM(amount) as total, AVG(amount) as avg 
FROM sales GROUP BY category ORDER BY total DESC

-- 窗口函数分析
SELECT *, ROW_NUMBER() OVER (PARTITION BY category ORDER BY amount DESC) as rank 
FROM sales
```

### 2. Go 单元测试 (`test_cases.go`)

#### 2.1 基础功能测试 (`TestBasicQueries`)
- 简单SELECT查询
- 数学运算和字符串函数
- 日期时间函数
- 错误SQL语法处理

#### 2.2 DuckDB特有功能测试 (`TestDuckDBSpecificFeatures`)
- 数组操作和函数
- JSON数据处理
- 窗口函数
- 列式存储优化查询
- 复杂聚合函数

#### 2.3 表操作测试 (`TestTableOperations`)
- 完整的CRUD操作流程
- 数据验证和结果检查
- 自动清理测试数据

#### 2.4 参数化查询测试 (`TestParameterizedQueries`)
- 单参数查询: `SELECT * FROM table WHERE id = ?`
- 多参数查询: `SELECT * FROM table WHERE id > ? AND value < ?`
- 字符串模式匹配: `SELECT * FROM table WHERE name LIKE ?`

#### 2.5 分析型查询测试 (`TestAnalyticalQueries`)
```sql
-- 聚合分析
SELECT category, COUNT(*) as transaction_count, SUM(sales_amount) as total_sales
FROM sales_data GROUP BY category ORDER BY total_sales DESC

-- 窗口函数分析
SELECT *, ROW_NUMBER() OVER (PARTITION BY category ORDER BY sales_amount DESC) as rank_in_category
FROM sales_data

-- 时间序列分析
SELECT DATE_TRUNC('month', sale_date) as month, SUM(sales_amount) as monthly_sales
FROM sales_data GROUP BY DATE_TRUNC('month', sale_date) ORDER BY month

-- 复杂CTE查询
WITH regional_stats AS (
    SELECT region, AVG(sales_amount) as avg_regional_sales
    FROM sales_data GROUP BY region
)
SELECT s.*, rs.avg_regional_sales, s.sales_amount - rs.avg_regional_sales as diff
FROM sales_data s JOIN regional_stats rs ON s.region = rs.region
WHERE s.sales_amount > rs.avg_regional_sales
```

#### 2.6 管理接口测试 (`TestManagementEndpoints`)
- 健康检查状态验证
- 指标数据格式检查
- 表列表功能测试

#### 2.7 错误处理测试 (`TestErrorHandling`)
- 语法错误: `SELCT * FRM table`
- 表不存在: `SELECT * FROM non_existent_table`
- 列不存在: `SELECT non_existent_column FROM table`
- 类型错误: `SELECT 'string' + 123`
- 除零错误: `SELECT 1/0`

#### 2.8 并发测试 (`TestConcurrentQueries`)
- 10个goroutine并发执行
- 每个goroutine执行5个查询
- 验证并发安全性和数据一致性

#### 2.9 性能基准测试
- `BenchmarkSimpleQuery`: 简单查询基准
- `BenchmarkComplexQuery`: 复杂聚合查询基准

### 3. MySQL协议测试 (`test_mysql_protocol.py`)

#### 3.1 连接测试
- TCP连接建立
- 端口可用性检查
- 连接超时处理

#### 3.2 协议握手测试
- MySQL握手包接收
- 认证响应发送
- 协议包格式验证

#### 3.3 查询测试
- 基础查询发送
- 响应包接收
- 多查询顺序执行

#### 3.4 多连接测试
- 同时建立多个连接
- 连接池压力测试
- 资源清理验证

## 测试数据和场景

### 1. 测试数据集
```sql
-- 用户数据
CREATE TABLE test_users (
    id INTEGER PRIMARY KEY,
    name VARCHAR,
    age INTEGER,
    email VARCHAR,
    created_at TIMESTAMP DEFAULT current_timestamp
)

-- 销售数据
CREATE TABLE sales_data (
    id INTEGER,
    product_id INTEGER,
    category VARCHAR,
    sales_amount DOUBLE,
    sale_date DATE,
    region VARCHAR
)

-- 参数测试数据
CREATE TABLE param_test (
    id INTEGER,
    name VARCHAR,
    value DOUBLE
)
```

### 2. 测试场景矩阵

| 测试类型 | 简单查询 | 复杂查询 | 错误处理 | 并发测试 | 性能测试 |
|---------|---------|---------|---------|---------|---------|
| HTTP API | ✅ | ✅ | ✅ | ✅ | ✅ |
| MySQL协议 | ✅ | ❌ | ✅ | ✅ | ❌ |
| Go单元测试 | ✅ | ✅ | ✅ | ✅ | ✅ |

### 3. 边界条件测试
- 空结果集处理
- 大数据量查询
- 长时间运行查询
- 内存限制测试
- 连接数限制测试

## 测试环境要求

### 1. 软件依赖
- **Go**: 1.21+
- **Python**: 3.6+
- **curl**: HTTP请求工具
- **jq**: JSON处理工具
- **lsof**: 端口检查工具

### 2. 端口要求
- **HTTP API**: 8080
- **MySQL协议**: 3366

### 3. 系统资源
- **内存**: 最小512MB
- **CPU**: 双核以上推荐
- **磁盘**: 100MB可用空间

## 测试输出和报告

### 1. 成功输出示例
```
=== DuckDB Multi-Protocol Server 测试套件 ===
✓ 依赖检查通过
✓ 服务启动成功

==================== HTTP API 测试 ====================
测试 健康检查... ✓ 成功
测试 简单SELECT... ✓ 成功
测试 数学运算... ✓ 成功
...
✓ HTTP API测试通过

=================== MySQL 协议测试 ===================
✓ 成功连接到 localhost:3366
✓ 收到握手包，长度: 40 字节
...
✓ MySQL协议测试通过

==================== 测试结果汇总 ====================
✓ HTTP API测试
✓ MySQL协议测试  
✓ Go单元测试
✓ 性能基准测试

总计: 4/4 测试通过
🎉 所有测试通过！
```

### 2. 失败输出示例
```
✗ HTTP API测试失败
错误: 连接被拒绝

故障排查建议:
1. 检查Go版本和依赖: go version && go mod tidy
2. 检查端口占用: lsof -i :8080 && lsof -i :3366
3. 查看服务日志: cat server.log
4. 检查DuckDB驱动: go list -m github.com/marcboeker/go-duckdb
```

## 持续集成配置

### 1. GitHub Actions示例
```yaml
name: DuckDB Server Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-go@v3
        with:
          go-version: '1.21'
      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y jq curl
      - name: Run tests
        run: ./run_tests.sh
```

### 2. Docker测试环境
```dockerfile
FROM golang:1.21-alpine
RUN apk add --no-cache curl jq python3 lsof
WORKDIR /app
COPY . .
RUN go mod tidy
CMD ["./run_tests.sh"]
```

## 故障排查指南

### 1. 常见问题

#### 问题: DuckDB驱动编译失败
```bash
# 解决方案
brew install duckdb  # macOS
sudo apt-get install libduckdb-dev  # Ubuntu
```

#### 问题: 端口被占用
```bash
# 检查端口占用
lsof -i :8080
lsof -i :3366

# 终止占用进程
pkill -f "go run main.go"
```

#### 问题: Go模块依赖错误
```bash
# 清理并重新安装依赖
go clean -modcache
go mod tidy
go mod download
```

### 2. 调试技巧
- 查看服务日志: `cat server.log`
- 检查HTTP响应: `curl -v http://localhost:8080/health`
- 验证JSON格式: `curl -s http://localhost:8080/health | jq .`
- 测试特定端点: `curl -X POST http://localhost:8080/query -d '{"sql":"SELECT 1"}'`

## 扩展测试

### 1. 压力测试
```bash
# 使用Apache Bench进行压力测试
ab -n 1000 -c 10 -p query.json -T application/json http://localhost:8080/query
```

### 2. 内存泄漏测试
```bash
# 使用pprof进行内存分析
go test -memprofile=mem.prof -bench=.
go tool pprof mem.prof
```

### 3. 覆盖率测试
```bash
# 生成测试覆盖率报告
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

## 总结

这套测试体系提供了DuckDB多协议服务的全面验证，包括：

- **9大测试类别**: 基础功能、DuckDB特性、表操作、参数化查询、分析查询、管理接口、错误处理、并发测试、性能基准
- **3种测试方式**: HTTP API、MySQL协议、Go单元测试
- **自动化流程**: 一键启动、测试、清理和报告
- **丰富的边界案例**: 错误处理、并发安全、资源限制
- **完整的故障排查**: 日志分析、调试技巧、CI/CD集成

通过这套测试体系，可以确保DuckDB多协议服务在各种场景下的稳定性和正确性。 