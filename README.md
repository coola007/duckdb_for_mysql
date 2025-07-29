# DuckDB Multi-Protocol Server

一个同时支持HTTP API和MySQL TCP协议的统一DuckDB服务。

## 功能特性

- **双协议支持**: 同时提供HTTP REST API和MySQL TCP协议
- **统一查询引擎**: 所有查询都通过DuckDB执行
- **连接池管理**: 支持连接池和并发控制
- **监控指标**: 内置查询统计和性能监控
- **健康检查**: 提供健康状态检查接口
- **管理接口**: 支持表管理和查询执行

## 快速开始

### 1. 安装依赖

```bash
go mod tidy
```

### 2. 运行服务

```bash
go run main.go
```

服务将在以下端口启动：
- HTTP API: http://localhost:8080
- MySQL: localhost:3366

### 3. 使用HTTP API

#### 执行查询
```bash
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT 1 as test"}'
```

#### 健康检查
```bash
curl http://localhost:8080/health
```

#### 查看指标
```bash
curl http://localhost:8080/metrics
```

#### 列出表
```bash
curl http://localhost:8080/admin/tables
```

### 4. 使用MySQL客户端

```bash
mysql -h localhost -P 3366 -u root -p
```

## API接口

### POST /query
执行SQL查询

**请求体:**
```json
{
  "sql": "SELECT * FROM users WHERE age > 18",
  "params": {
    "age": 18
  }
}
```

**响应:**
```json
{
  "data": {
    "columns": ["id", "name", "age"],
    "rows": [
      {"id": 1, "name": "Alice", "age": 25},
      {"id": 2, "name": "Bob", "age": 30}
    ],
    "count": 2
  },
  "execution_time_ms": 15
}
```

### GET /health
健康状态检查

### GET /metrics
性能指标统计

### GET /admin/tables
列出所有表

### POST /admin/execute
管理查询执行

## 配置说明

通过 `config.json` 文件配置服务：

```json
{
  "http_port": 8080,
  "mysql_port": 3366,
  "db_path": ":memory:",
  "max_connections": 10,
  "log_level": "info",
  "auth": {
    "enabled": false,
    "users": {
      "admin": "password123"
    }
  }
}
```

## 架构设计

### 核心组件

1. **DuckDBMultiProtocolServer**: 主服务容器
2. **MySQLServer**: MySQL协议处理器
3. **AuthManager**: 认证管理器
4. **MetricsCollector**: 指标收集器

### 数据流

```
HTTP Client     MySQL Client
     |               |
     v               v
HTTP Handler   MySQL Handler
     |               |
     +-------+-------+
             |
     Unified Query Engine
             |
         DuckDB Database
```

## 开发说明

### 项目结构
```
.
├── main.go                     # 主入口，只负责启动
├── internal/
│   ├── config/config.go       # 配置管理
│   ├── database/duckdb.go     # 数据库连接封装
│   ├── query/executor.go      # 查询执行器
│   ├── http/server.go         # HTTP服务器
│   └── mysql/server.go        # MySQL协议服务器
├── test/                      # 测试文件
└── config.json                # 配置文件
```

### 扩展功能

1. **完整MySQL协议**: 当前MySQL协议实现为简化版，可扩展为完整实现
2. **连接池优化**: 可添加更复杂的连接池管理
3. **查询缓存**: 可添加查询结果缓存机制
4. **负载均衡**: 可支持多实例负载均衡
5. **监控集成**: 可集成Prometheus等监控系统

## 注意事项

- 当前MySQL协议实现为简化版，仅支持基本查询
- 建议在生产环境中启用认证
- 内存数据库模式数据不会持久化，请根据需求配置文件路径
- 并发连接数受配置限制，请根据服务器资源调整

## 许可证

MIT License 

## 总结

我已经成功重构了项目架构并修复了您提到的两个问题：

### ✅ 1. 配置文件读取问题已修复

现在程序正确地从`config.json`读取配置：

- **配置模块**: `internal/config/config.go` - 专门处理配置加载和验证
- **默认配置**: 如果配置文件不存在，使用合理的默认值
- **命令行支持**: 支持 `--config` 参数指定配置文件路径
- **配置验证**: 验证端口范围、连接数等参数

### ✅ 2. 代码架构已重新组织

项目现在使用清晰的模块化架构：

```
duckdb-server/
├── main.go                     # 简洁的主入口，只负责启动
├── internal/
│   ├── config/config.go       # 配置管理
│   ├── database/duckdb.go     # 数据库连接封装
│   ├── query/executor.go      # 查询执行器
│   ├── http/server.go         # HTTP服务器
│   └── mysql/server.go        # MySQL协议服务器
├── test/                      # 测试文件
└── config.json               # 配置文件
```

### ✅ 3. 功能验证成功

**HTTP API** (完全正常):
- ✅ 健康检查: `/health`
- ✅ SQL查询: `/query`  
- ✅ 表操作: CREATE, INSERT, SELECT
- ✅ 管理接口: `/admin/tables`, `/metrics`

**MySQL协议** (基本可用):
- ✅ TCP连接和握手
- ✅ 基本认证 
- ✅ 简单查询支持
- ⚠️ 标准客户端有版本不匹配警告（这是预期的，因为我们使用简化协议）

### 🚀 使用方式

```bash
<code_block_to_apply_from>
# 使用默认配置启动
go run main.go

# 使用自定义配置文件
go run main.go --config myconfig.json

# 显示版本信息
go run main.go --version

# HTTP API测试
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT 1 as test"}'

# MySQL协议测试
mysql -h 127.0.0.1 -P 3366 -u root --skip-password -e "SELECT 1"
```
