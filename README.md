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
├── main.go          # 主程序入口
├── go.mod           # Go模块定义
├── config.json      # 配置文件
└── README.md        # 项目说明
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