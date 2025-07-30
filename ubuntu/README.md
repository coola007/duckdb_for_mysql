# DuckDB MySQL协议服务器 - Ubuntu部署指南

## 🎯 概述

本指南介绍如何在Ubuntu系统上部署和运行DuckDB MySQL协议服务器。

## 📋 系统要求

- Ubuntu 18.04 LTS 或更高版本
- 支持的架构：x86_64 或 ARM64
- 最小内存：512MB
- 推荐内存：2GB 或更多
- 磁盘空间：至少100MB可用空间

## 🚀 快速部署

### 1. 编译程序

在开发机器上（需要Go环境）：

```bash
# 克隆代码
git clone <repository-url>
cd duckdb

# 编译Ubuntu版本
chmod +x build_ubuntu.sh
./build_ubuntu.sh
```

### 2. 传输文件到Ubuntu服务器

```bash
# 将编译产物和部署文件传输到Ubuntu服务器
scp -r build/ ubuntu/ user@your-ubuntu-server:~/duckdb/
```

### 3. 部署安装

在Ubuntu服务器上：

```bash
cd ~/duckdb/ubuntu
chmod +x deploy.sh
sudo ./deploy.sh
```

## 🔧 手动安装步骤

如果需要手动安装，请按以下步骤操作：

### 1. 创建系统用户

```bash
sudo groupadd --system duckdb
sudo useradd --system --gid duckdb --shell /bin/false \
             --home-dir /var/lib/duckdb --create-home \
             --comment "DuckDB MySQL Server" duckdb
```

### 2. 创建目录结构

```bash
sudo mkdir -p /var/lib/duckdb
sudo mkdir -p /var/log/duckdb
sudo mkdir -p /etc/duckdb

sudo chown -R duckdb:duckdb /var/lib/duckdb
sudo chown -R duckdb:duckdb /var/log/duckdb
sudo chmod 755 /var/lib/duckdb /var/log/duckdb /etc/duckdb
```

### 3. 安装二进制文件

```bash
# 根据架构选择对应文件
sudo cp build/duckdb-mysql-server-linux-amd64 /usr/local/bin/duckdb-mysql-server
# 或者 ARM64
# sudo cp build/duckdb-mysql-server-linux-arm64 /usr/local/bin/duckdb-mysql-server

sudo chmod 755 /usr/local/bin/duckdb-mysql-server
sudo chown root:root /usr/local/bin/duckdb-mysql-server
```

### 4. 配置文件

```bash
sudo cp config.json /etc/duckdb/config.json
sudo chmod 644 /etc/duckdb/config.json
sudo chown root:root /etc/duckdb/config.json
```

### 5. 安装systemd服务

```bash
sudo cp duckdb-mysql.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/duckdb-mysql.service
sudo systemctl daemon-reload
```

## 🎛️ 服务管理

### 启动服务

```bash
sudo systemctl start duckdb-mysql
sudo systemctl enable duckdb-mysql  # 开机自启
```

### 查看状态

```bash
sudo systemctl status duckdb-mysql
```

### 查看日志

```bash
# 实时日志
sudo journalctl -u duckdb-mysql -f

# 历史日志
sudo journalctl -u duckdb-mysql --since "1 hour ago"
```

### 重启服务

```bash
sudo systemctl restart duckdb-mysql
```

### 停止服务

```bash
sudo systemctl stop duckdb-mysql
```

## ⚙️ 配置说明

配置文件位置：`/etc/duckdb/config.json`

```json
{
  "http_port": 8080,           // HTTP API端口
  "mysql_port": 33660,          // MySQL协议端口
  "database_path": "/var/lib/duckdb/data.db",  // 数据库文件路径
  "log_level": "info",         // 日志级别
  "max_connections": 100,      // 最大连接数
  "read_timeout": 30,          // 读超时(秒)
  "write_timeout": 30,         // 写超时(秒)
  "idle_timeout": 300          // 空闲超时(秒)
}
```

修改配置后需要重启服务：

```bash
sudo systemctl restart duckdb-mysql
```

## 🔥 防火墙配置

如果使用ufw防火墙：

```bash
# 开放MySQL端口
sudo ufw allow 3306/tcp comment "DuckDB MySQL Protocol"

# 开放HTTP API端口
sudo ufw allow 8080/tcp comment "DuckDB HTTP API"

# 查看防火墙状态
sudo ufw status
```

## 📊 性能调优

### 系统参数优化

编辑 `/etc/security/limits.conf`：

```
duckdb soft nofile 65536
duckdb hard nofile 65536
duckdb soft nproc 4096
duckdb hard nproc 4096
```

### 内核参数优化

编辑 `/etc/sysctl.conf`：

```
# 网络连接优化
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_keepalive_time = 600

# 内存优化
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
```

应用配置：

```bash
sudo sysctl -p
```

## 🔍 监控和诊断

### 健康检查

```bash
# HTTP健康检查
curl http://localhost:8080/health

# MySQL连接测试
mysql -h localhost -P 3306 -u root -e "SELECT version()"
```

### 性能监控

```bash
# 查看进程状态
ps aux | grep duckdb-mysql-server

# 查看内存使用
free -h

# 查看磁盘使用
df -h /var/lib/duckdb

# 查看网络连接
ss -tulpn | grep ":3306\|:8080"
```

### 日志分析

```bash
# 错误日志
sudo journalctl -u duckdb-mysql -p err

# 连接日志
sudo journalctl -u duckdb-mysql | grep "MySQL连接"

# 性能日志
sudo journalctl -u duckdb-mysql | grep "QPS\|查询"
```

## 🛠️ 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   sudo ss -tulpn | grep ":3306"
   sudo lsof -i :3306
   ```

2. **权限问题**
   ```bash
   sudo chown -R duckdb:duckdb /var/lib/duckdb
   sudo chmod 755 /var/lib/duckdb
   ```

3. **内存不足**
   ```bash
   free -h
   sudo systemctl restart duckdb-mysql
   ```

4. **数据库文件损坏**
   ```bash
   sudo -u duckdb cp /var/lib/duckdb/data.db /var/lib/duckdb/data.db.backup
   sudo systemctl restart duckdb-mysql
   ```

### 日志级别调整

编辑 `/etc/duckdb/config.json`，将 `log_level` 改为 `debug`：

```json
{
  "log_level": "debug"
}
```

然后重启服务。

## 🔄 更新升级

1. 编译新版本
2. 停止服务：`sudo systemctl stop duckdb-mysql`
3. 备份数据：`sudo cp /var/lib/duckdb/data.db /var/lib/duckdb/data.db.backup`
4. 替换二进制文件：`sudo cp new-binary /usr/local/bin/duckdb-mysql-server`
5. 启动服务：`sudo systemctl start duckdb-mysql`

## 🗑️ 卸载

```bash
# 停止并禁用服务
sudo systemctl stop duckdb-mysql
sudo systemctl disable duckdb-mysql

# 删除文件
sudo rm -f /usr/local/bin/duckdb-mysql-server
sudo rm -f /etc/systemd/system/duckdb-mysql.service
sudo rm -rf /etc/duckdb
sudo rm -rf /var/lib/duckdb
sudo rm -rf /var/log/duckdb
sudo rm -f /etc/logrotate.d/duckdb-mysql

# 删除用户
sudo userdel duckdb
sudo groupdel duckdb

# 重新加载systemd
sudo systemctl daemon-reload
```

## 📞 支持

如遇问题，请：

1. 查看日志：`sudo journalctl -u duckdb-mysql -f`
2. 检查配置：`sudo cat /etc/duckdb/config.json`
3. 测试连接：`curl http://localhost:8080/health`
4. 查看GitHub Issues或联系维护者

## 📝 许可证

本项目基于MIT许可证开源。 