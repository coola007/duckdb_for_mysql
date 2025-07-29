# DuckDB Multi-Protocol Server Docker & Kubernetes 部署指南

本文档详细说明如何使用Docker和Kubernetes部署DuckDB多协议服务器，包括开发、测试和生产环境的完整配置。

## 📋 目录

- [Docker 部署](#docker-部署)
- [Kubernetes 部署](#kubernetes-部署)
- [MySQL协议测试](#mysql协议测试)
- [监控和运维](#监控和运维)
- [故障排除](#故障排除)

## 🐳 Docker 部署

### 基础Docker部署

#### 1. 构建镜像

```bash
# 构建Docker镜像
docker build -t duckdb-server:latest .

# 查看镜像
docker images | grep duckdb-server
```

#### 2. 运行容器

```bash
# 基础运行
docker run -d \
  --name duckdb-server \
  -p 8080:8080 \
  -p 3366:3366 \
  duckdb-server:latest

# 带数据持久化
docker run -d \
  --name duckdb-server \
  -p 8080:8080 \
  -p 3366:3366 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.json:/app/config.json:ro \
  duckdb-server:latest
```

#### 3. 验证部署

```bash
# 检查容器状态
docker ps | grep duckdb-server

# 查看日志
docker logs duckdb-server

# 健康检查
curl http://localhost:8080/health
```

### Docker Compose 部署

#### 1. 开发环境

```bash
# 启动开发环境 (基础服务)
docker-compose up -d

# 启动开发环境 (包含测试客户端)
docker-compose --profile development up -d

# 查看服务状态
docker-compose ps
```

#### 2. 生产环境

```bash
# 启动生产环境 (包含负载均衡和缓存)
docker-compose --profile production up -d

# 启动监控服务
docker-compose --profile monitoring up -d

# 启动备份服务
docker-compose --profile backup up -d
```

#### 3. 环境配置

创建 `.env` 文件：

```bash
# 端口配置
HTTP_PORT=8080
MYSQL_PORT=3366
NGINX_PORT=80
NGINX_SSL_PORT=443

# 数据库配置
DB_PATH=/app/data/duckdb.db
DATA_DIR=./data

# 监控配置
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_PASSWORD=admin123

# 其他配置
TZ=Asia/Shanghai
LOG_LEVEL=info
```

#### 4. 完整服务栈

```bash
# 启动完整服务栈
docker-compose \
  --profile production \
  --profile monitoring \
  --profile logging \
  up -d

# 查看所有服务
docker-compose ps --services
```

## ☸️ Kubernetes 部署

### 前置要求

- Kubernetes 1.20+
- kubectl 配置完成
- 足够的资源配额

### 快速部署

#### 1. 使用部署脚本

```bash
# 给脚本执行权限
chmod +x k8s/deploy.sh

# 完整部署
./k8s/deploy.sh all

# 分步部署
./k8s/deploy.sh build    # 构建镜像
./k8s/deploy.sh deploy   # 部署到K8s
./k8s/deploy.sh status   # 查看状态
./k8s/deploy.sh test     # 运行测试
```

#### 2. 手动部署

```bash
# 1. 创建命名空间和资源限制
kubectl apply -f k8s/namespace.yaml

# 2. 创建存储
kubectl apply -f k8s/pv.yaml

# 3. 创建配置
kubectl apply -f k8s/configmap.yaml

# 4. 创建部署
kubectl apply -f k8s/deployment.yaml

# 5. 创建服务
kubectl apply -f k8s/service.yaml

# 6. 创建Ingress (可选)
kubectl apply -f k8s/ingress.yaml
```

### 验证部署

#### 1. 检查Pod状态

```bash
# 查看Pod
kubectl get pods -n duckdb-system

# 查看Pod详情
kubectl describe pod -l app=duckdb-server -n duckdb-system

# 查看日志
kubectl logs -f -l app=duckdb-server -n duckdb-system
```

#### 2. 检查服务

```bash
# 查看服务
kubectl get services -n duckdb-system

# 查看端点
kubectl get endpoints -n duckdb-system
```

### 访问服务

#### 1. 端口转发访问

```bash
# HTTP API端口转发
kubectl port-forward -n duckdb-system service/duckdb-server 8080:8080

# MySQL协议端口转发
kubectl port-forward -n duckdb-system service/duckdb-server 3366:3366

# 测试连接
curl http://localhost:8080/health
```

#### 2. NodePort访问

```bash
# 获取NodePort
kubectl get service duckdb-mysql-nodeport -n duckdb-system

# 使用NodePort连接MySQL
mysql -h <NODE_IP> -P 30366 -u root
```

#### 3. LoadBalancer访问

```bash
# 获取LoadBalancer IP
kubectl get service nginx-proxy -n duckdb-system

# 访问服务
curl http://<LOAD_BALANCER_IP>/health
```

### 扩缩容和更新

#### 1. 水平扩缩容

```bash
# 扩容到3个副本
kubectl scale deployment duckdb-server --replicas=3 -n duckdb-system

# 使用脚本扩缩容
./k8s/deploy.sh scale 3

# 查看扩缩容状态
kubectl get pods -l app=duckdb-server -n duckdb-system
```

#### 2. 滚动更新

```bash
# 更新镜像
kubectl set image deployment/duckdb-server \
  duckdb-server=duckdb-server:v2.0.0 \
  -n duckdb-system

# 查看更新状态
kubectl rollout status deployment/duckdb-server -n duckdb-system

# 回滚更新
kubectl rollout undo deployment/duckdb-server -n duckdb-system
```

## 🧪 MySQL协议测试

### 使用低级协议测试器

```bash
# 运行完整的MySQL协议测试
python3 test/mysql_protocol_test.py --host localhost --port 3366

# Docker环境测试
docker exec -it duckdb-test-client python3 /workspace/test/mysql_protocol_test.py \
  --host duckdb-server --port 3366

# Kubernetes环境测试
kubectl exec -n duckdb-system -it duckdb-test-runner -- \
  python3 /tmp/mysql_test.py --host duckdb-server --port 3366
```

### 使用MySQL客户端测试

```bash
# 安装MySQL客户端依赖
pip install PyMySQL mysql-connector-python

# 运行客户端测试
python3 test/mysql_client_test.py --host localhost --port 3366

# 使用标准MySQL客户端
mysql -h localhost -P 3366 -u root
```

### 测试内容

#### 1. 协议兼容性测试
- TCP连接建立
- MySQL握手协议
- 认证过程
- 命令执行
- 结果集处理

#### 2. 功能测试
- 基本SQL查询
- 表操作 (CREATE, INSERT, UPDATE, DELETE)
- 数据类型支持
- 事务处理
- 并发连接

#### 3. 性能测试
- 连接建立速度
- 查询响应时间
- 并发处理能力
- 资源使用情况

## 📊 监控和运维

### Prometheus + Grafana 监控

#### 1. 启动监控服务

```bash
# Docker Compose
docker-compose --profile monitoring up -d

# 访问监控界面
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin123)
```

#### 2. 监控指标

- **系统指标**: CPU、内存、磁盘、网络
- **应用指标**: 请求数、响应时间、错误率
- **数据库指标**: 连接数、查询数、数据大小
- **协议指标**: HTTP和MySQL协议的具体指标

### 日志管理

#### 1. 查看日志

```bash
# Docker日志
docker logs -f duckdb-server

# Docker Compose日志
docker-compose logs -f duckdb-server

# Kubernetes日志
kubectl logs -f -l app=duckdb-server -n duckdb-system
```

#### 2. 日志聚合

```bash
# 启动日志收集服务
docker-compose --profile logging up -d

# 日志会被收集到Fluentd中进行处理
```

### 健康检查

#### 1. HTTP健康检查

```bash
# 基本健康检查
curl http://localhost:8080/health

# 详细状态信息
curl http://localhost:8080/metrics

# 数据库状态
curl http://localhost:8080/admin/tables
```

#### 2. MySQL协议检查

```bash
# 使用自定义测试工具
python3 test/mysql_protocol_test.py --host localhost --port 3366

# 使用标准客户端
mysql -h localhost -P 3366 -u root -e "SELECT 1"
```

### 备份和恢复

#### 1. 数据备份

```bash
# Docker环境备份
docker exec duckdb-server cp /app/data/duckdb.db /app/backup/backup-$(date +%Y%m%d_%H%M%S).db

# Kubernetes环境备份
kubectl exec -n duckdb-system deployment/duckdb-server -- \
  cp /data/duckdb.db /data/backup-$(date +%Y%m%d_%H%M%S).db
```

#### 2. 自动备份

```bash
# 启动备份服务
docker-compose --profile backup up -d

# 备份计划: 每天2点自动备份，保留7天
```

## 🔧 故障排除

### 常见问题

#### 1. 容器启动失败

```bash
# 检查容器日志
docker logs duckdb-server

# 检查配置文件
docker exec duckdb-server cat /app/config.json

# 检查端口占用
lsof -i :8080
lsof -i :3366
```

#### 2. MySQL协议连接失败

```bash
# 检查网络连通性
telnet localhost 3366

# 查看服务器日志中的连接信息
docker logs duckdb-server | grep MySQL

# 使用协议测试工具诊断
python3 test/mysql_protocol_test.py --host localhost --port 3366
```

#### 3. Kubernetes部署问题

```bash
# 检查Pod状态
kubectl get pods -n duckdb-system
kubectl describe pod <pod-name> -n duckdb-system

# 检查资源配额
kubectl describe quota -n duckdb-system

# 检查存储
kubectl get pv,pvc -n duckdb-system

# 查看事件
kubectl get events -n duckdb-system --sort-by=.metadata.creationTimestamp
```

#### 4. 性能问题

```bash
# 检查资源使用
docker stats duckdb-server

# Kubernetes资源使用
kubectl top pods -n duckdb-system

# 检查连接数
ss -tulpn | grep -E ':(8080|3366)'

# 查看数据库状态
curl http://localhost:8080/metrics
```

### 调试模式

#### 1. 启用调试日志

```bash
# Docker环境
docker run -e LOG_LEVEL=debug duckdb-server

# 更新Kubernetes配置
kubectl patch deployment duckdb-server -n duckdb-system -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"duckdb-server","env":[{"name":"LOG_LEVEL","value":"debug"}]}]}}}}'
```

#### 2. 交互式调试

```bash
# 进入容器
docker exec -it duckdb-server bash

# 进入Kubernetes Pod
kubectl exec -it -n duckdb-system deployment/duckdb-server -- bash

# 手动运行服务
./duckdb-server --debug
```

### 性能调优

#### 1. 资源配置优化

```yaml
# Kubernetes资源限制调优
resources:
  requests:
    cpu: 200m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 4Gi
```

#### 2. 数据库配置优化

```json
{
  "performance": {
    "max_memory": "2GB",
    "max_threads": 4,
    "temp_directory": "/tmp/duckdb"
  }
}
```

## 📚 参考资料

### 官方文档
- [DuckDB 官方文档](https://duckdb.org/docs/)
- [Docker 部署指南](https://docs.docker.com/)
- [Kubernetes 文档](https://kubernetes.io/docs/)

### 相关工具
- **Docker**: 容器化平台
- **Docker Compose**: 多容器应用编排
- **Kubernetes**: 容器编排平台
- **Prometheus**: 监控系统
- **Grafana**: 监控可视化
- **nginx**: 负载均衡器

### 测试工具
- **PyMySQL**: Python MySQL客户端
- **mysql-connector-python**: Oracle官方MySQL连接器
- **MySQL CLI**: 标准MySQL命令行客户端

---

## 📝 总结

本文档提供了DuckDB多协议服务器的完整Docker和Kubernetes部署方案，包括：

- ✅ **多环境支持**: 开发、测试、生产环境配置
- ✅ **完整监控**: Prometheus + Grafana监控栈
- ✅ **协议测试**: HTTP API + MySQL协议完整测试
- ✅ **运维支持**: 日志、备份、健康检查
- ✅ **故障排除**: 常见问题和解决方案

通过这些配置，您可以在任何支持Docker和Kubernetes的环境中快速部署和运行DuckDB多协议服务器。 