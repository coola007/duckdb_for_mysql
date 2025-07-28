# DuckDB Multi-Protocol Server 部署指南

本指南详细说明如何在Ubuntu环境中编译、部署和运行DuckDB多协议服务器。

## 系统要求

### 支持的操作系统
- Ubuntu 18.04 LTS+
- Ubuntu 20.04 LTS
- Ubuntu 22.04 LTS (推荐)
- Debian 10+

### 硬件要求
- **CPU**: x86_64架构，2核心以上
- **内存**: 最小2GB，推荐4GB+
- **存储**: 最小1GB可用空间
- **网络**: 端口8080(HTTP)和3366(MySQL)可用

## 快速开始

### 方法一：一键编译脚本

```bash
# 1. 克隆项目
git clone <repository-url>
cd duckdb

# 2. 运行编译脚本
chmod +x build.sh
./build.sh

# 3. 启动服务
./build/duckdb-server
```

### 方法二：Docker部署

```bash
# 1. 构建镜像
docker build -t duckdb-server .

# 2. 运行容器
docker run -d \
  --name duckdb-server \
  -p 8080:8080 \
  -p 3366:3366 \
  duckdb-server

# 3. 检查状态
curl http://localhost:8080/health
```

### 方法三：Docker Compose

```bash
# 1. 启动服务
docker-compose up -d

# 2. 查看日志
docker-compose logs -f duckdb-server

# 3. 停止服务
docker-compose down
```

## 详细部署步骤

### 1. 环境准备

#### 更新系统包
```bash
sudo apt-get update
sudo apt-get upgrade -y
```

#### 安装基础依赖
```bash
sudo apt-get install -y \
    curl wget git \
    build-essential \
    pkg-config \
    ca-certificates
```

### 2. 依赖安装

#### 自动安装
```bash
# 使用编译脚本自动安装所有依赖
./build.sh
```

#### 手动安装

**安装Go 1.21:**
```bash
wget https://golang.org/dl/go1.21.6.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.6.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc
```

**安装DuckDB:**
```bash
# 添加DuckDB仓库
wget -qO- https://packages.duckdb.org/debian/duckdb.gpg | sudo tee /etc/apt/trusted.gpg.d/duckdb.asc
echo "deb https://packages.duckdb.org/debian/ stable main" | sudo tee /etc/apt/sources.list.d/duckdb.list

# 安装DuckDB
sudo apt-get update
sudo apt-get install -y duckdb libduckdb-dev
```

**安装开发库:**
```bash
sudo apt-get install -y \
    libssl-dev \
    libcurl4-openssl-dev \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev
```

### 3. 编译项目

#### 下载依赖
```bash
go mod tidy
go mod download
```

#### 编译二进制
```bash
# 基础编译
go build -o duckdb-server .

# 优化编译 (推荐生产环境)
CGO_ENABLED=1 GOOS=linux go build \
  -ldflags "-s -w -X main.Version=1.0.0" \
  -o duckdb-server .
```

#### 验证编译
```bash
./duckdb-server --version
file duckdb-server
ldd duckdb-server
```

### 4. 配置服务

#### 配置文件
编辑 `config.json`:
```json
{
  "http_port": 8080,
  "mysql_port": 3366,
  "db_path": "/var/lib/duckdb/data.db",
  "max_connections": 100,
  "log_level": "info"
}
```

#### 创建数据目录
```bash
sudo mkdir -p /var/lib/duckdb
sudo chown duckdb:duckdb /var/lib/duckdb
```

### 5. 系统服务部署

#### 创建系统用户
```bash
sudo useradd -r -s /bin/false duckdb
```

#### 安装服务文件
```bash
# 复制二进制文件
sudo cp duckdb-server /opt/duckdb-server/
sudo cp config.json /opt/duckdb-server/
sudo chown -R duckdb:duckdb /opt/duckdb-server

# 安装systemd服务
sudo cp duckdb-server.service /etc/systemd/system/
sudo systemctl daemon-reload
```

#### systemd服务文件示例
`/etc/systemd/system/duckdb-server.service`:
```ini
[Unit]
Description=DuckDB Multi-Protocol Server
After=network.target
StartLimitBurst=5
StartLimitIntervalSec=10

[Service]
Type=simple
User=duckdb
Group=duckdb
WorkingDirectory=/opt/duckdb-server
ExecStart=/opt/duckdb-server/duckdb-server
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30
Restart=always
RestartSec=5

# 安全设置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/duckdb

# 资源限制
LimitNOFILE=65536
LimitNPROC=32768

[Install]
WantedBy=multi-user.target
```

#### 启动服务
```bash
# 启动并启用服务
sudo systemctl start duckdb-server
sudo systemctl enable duckdb-server

# 检查状态
sudo systemctl status duckdb-server

# 查看日志
sudo journalctl -u duckdb-server -f
```

## 运维管理

### 服务控制

```bash
# 启动服务
sudo systemctl start duckdb-server

# 停止服务
sudo systemctl stop duckdb-server

# 重启服务
sudo systemctl restart duckdb-server

# 重载配置
sudo systemctl reload duckdb-server

# 查看状态
sudo systemctl status duckdb-server
```

### 日志管理

```bash
# 查看实时日志
sudo journalctl -u duckdb-server -f

# 查看最近100行日志
sudo journalctl -u duckdb-server -n 100

# 查看特定时间段日志
sudo journalctl -u duckdb-server --since "2024-01-01" --until "2024-01-02"

# 按日期查看日志
sudo journalctl -u duckdb-server --since yesterday
```

### 健康检查

```bash
# HTTP API健康检查
curl http://localhost:8080/health

# 性能指标
curl http://localhost:8080/metrics

# 表列表
curl http://localhost:8080/admin/tables

# MySQL协议连接测试
python3 test_mysql_protocol.py
```

### 备份策略

```bash
# 停止服务
sudo systemctl stop duckdb-server

# 备份数据库文件
sudo cp /var/lib/duckdb/data.db /backup/duckdb-$(date +%Y%m%d_%H%M%S).db

# 备份配置文件
sudo cp /opt/duckdb-server/config.json /backup/config-$(date +%Y%m%d_%H%M%S).json

# 重启服务
sudo systemctl start duckdb-server
```

## 性能调优

### 系统优化

#### 内核参数调优
编辑 `/etc/sysctl.conf`:
```bash
# 网络优化
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 30

# 文件描述符
fs.file-max = 100000

# 应用生效
sudo sysctl -p
```

#### 用户限制
编辑 `/etc/security/limits.conf`:
```bash
duckdb soft nofile 65535
duckdb hard nofile 65535
duckdb soft nproc 32768
duckdb hard nproc 32768
```

### 应用优化

#### 配置调优
```json
{
  "http_port": 8080,
  "mysql_port": 3366,
  "db_path": "/var/lib/duckdb/data.db",
  "max_connections": 200,
  "log_level": "warn",
  "performance": {
    "worker_threads": 4,
    "memory_limit": "2GB",
    "temp_directory": "/tmp/duckdb"
  }
}
```

#### 监控指标
```bash
# CPU使用率
top -p $(pgrep duckdb-server)

# 内存使用
ps aux | grep duckdb-server

# 网络连接
ss -tulpn | grep -E ':(8080|3366)'

# 磁盘I/O
iotop -p $(pgrep duckdb-server)
```

## 故障排除

### 常见问题

#### 1. 编译失败
```bash
# 检查Go版本
go version

# 检查DuckDB库
ldconfig -p | grep duckdb

# 重新安装依赖
./build.sh --skip-tests
```

#### 2. 端口被占用
```bash
# 检查端口占用
sudo lsof -i :8080
sudo lsof -i :3366

# 终止占用进程
sudo kill -9 <PID>
```

#### 3. 权限问题
```bash
# 检查文件权限
ls -la /opt/duckdb-server/
ls -la /var/lib/duckdb/

# 修复权限
sudo chown -R duckdb:duckdb /opt/duckdb-server/
sudo chown -R duckdb:duckdb /var/lib/duckdb/
```

#### 4. 服务启动失败
```bash
# 查看详细错误
sudo journalctl -u duckdb-server -n 50

# 手动运行测试
sudo -u duckdb /opt/duckdb-server/duckdb-server

# 检查配置文件
sudo -u duckdb cat /opt/duckdb-server/config.json
```

### 调试模式

```bash
# 启用调试日志
export LOG_LEVEL=debug
./duckdb-server

# 使用strace追踪系统调用
strace -f -o /tmp/duckdb.trace ./duckdb-server

# 使用gdb调试
gdb ./duckdb-server
```

## 安全建议

### 网络安全
- 使用防火墙限制访问端口
- 启用HTTPS/TLS加密
- 配置认证和授权

### 系统安全
- 定期更新系统和依赖
- 使用专用用户运行服务
- 限制文件系统权限

### 监控告警
- 配置服务监控
- 设置资源使用告警
- 记录安全事件日志

## 扩展部署

### 负载均衡
使用Nginx或HAProxy进行负载均衡：

```nginx
upstream duckdb_backend {
    server 127.0.0.1:8080;
    server 127.0.0.1:8081;
}

server {
    listen 80;
    location / {
        proxy_pass http://duckdb_backend;
    }
}
```

### 集群部署
- 配置多个实例
- 使用共享存储
- 实现数据同步机制

### 监控集成
- 集成Prometheus/Grafana
- 配置告警规则
- 设置监控面板

---

更多详细信息请参考项目文档和测试用例。 