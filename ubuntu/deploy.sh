#!/bin/bash
# DuckDB MySQL协议服务器 - Ubuntu部署脚本

set -e

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用root权限运行此脚本"
    echo "使用方法: sudo $0"
    exit 1
fi

echo "🚀 开始部署DuckDB MySQL协议服务器到Ubuntu"
echo "============================================="

# 检测架构
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        BINARY_NAME="duckdb-mysql-server-linux-amd64"
        ;;
    aarch64|arm64)
        BINARY_NAME="duckdb-mysql-server-linux-arm64"
        ;;
    *)
        echo "❌ 不支持的架构: $ARCH"
        exit 1
        ;;
esac

echo "✅ 检测到架构: $ARCH"
echo "📦 使用二进制文件: $BINARY_NAME"

# 检查二进制文件是否存在
if [ ! -f "../build/$BINARY_NAME" ]; then
    echo "❌ 二进制文件不存在: ../build/$BINARY_NAME"
    echo "请先运行 ./build_ubuntu.sh 编译程序"
    exit 1
fi

# 1. 创建用户和组
echo "👤 创建duckdb用户和组..."
if ! getent group duckdb > /dev/null 2>&1; then
    groupadd --system duckdb
    echo "✅ 创建组 duckdb"
fi

if ! getent passwd duckdb > /dev/null 2>&1; then
    useradd --system --gid duckdb --shell /bin/false \
            --home-dir /var/lib/duckdb --create-home \
            --comment "DuckDB MySQL Server" duckdb
    echo "✅ 创建用户 duckdb"
fi

# 2. 创建目录结构
echo "📁 创建目录结构..."
mkdir -p /var/lib/duckdb
mkdir -p /var/log/duckdb
mkdir -p /etc/duckdb

# 设置目录权限
chown -R duckdb:duckdb /var/lib/duckdb
chown -R duckdb:duckdb /var/log/duckdb
chmod 755 /var/lib/duckdb
chmod 755 /var/log/duckdb
chmod 755 /etc/duckdb

echo "✅ 目录创建完成"

# 3. 安装二进制文件
echo "📦 安装二进制文件..."
cp "../build/$BINARY_NAME" /usr/local/bin/duckdb-mysql-server
chmod 755 /usr/local/bin/duckdb-mysql-server
chown root:root /usr/local/bin/duckdb-mysql-server

echo "✅ 二进制文件安装完成"

# 4. 安装配置文件
echo "⚙️  安装配置文件..."
cp config.json /etc/duckdb/config.json
chmod 644 /etc/duckdb/config.json
chown root:root /etc/duckdb/config.json

echo "✅ 配置文件安装完成"

# 5. 安装systemd服务
echo "🔧 安装systemd服务..."
cp duckdb-mysql.service /etc/systemd/system/
chmod 644 /etc/systemd/system/duckdb-mysql.service
chown root:root /etc/systemd/system/duckdb-mysql.service

# 重新加载systemd
systemctl daemon-reload

echo "✅ systemd服务安装完成"

# 6. 创建日志轮转配置
echo "📋 创建日志轮转配置..."
cat > /etc/logrotate.d/duckdb-mysql << 'EOF'
/var/log/duckdb/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 0644 duckdb duckdb
    postrotate
        systemctl reload duckdb-mysql || true
    endscript
}
EOF

echo "✅ 日志轮转配置完成"

# 7. 创建防火墙规则（可选）
echo "🔥 配置防火墙..."
if command -v ufw &> /dev/null; then
    echo "检测到ufw防火墙"
    read -p "是否开放MySQL端口3306? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ufw allow 3306/tcp comment "DuckDB MySQL Protocol"
        echo "✅ 已开放端口3306"
    fi
    
    read -p "是否开放HTTP端口8080? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ufw allow 8080/tcp comment "DuckDB HTTP API"
        echo "✅ 已开放端口8080"
    fi
fi

# 8. 显示安装信息
echo ""
echo "🎉 DuckDB MySQL协议服务器部署完成！"
echo "============================================="
echo "📍 安装位置:"
echo "  二进制文件: /usr/local/bin/duckdb-mysql-server"
echo "  配置文件:   /etc/duckdb/config.json"
echo "  数据目录:   /var/lib/duckdb"
echo "  日志目录:   /var/log/duckdb"
echo "  服务文件:   /etc/systemd/system/duckdb-mysql.service"
echo ""
echo "🔧 管理命令:"
echo "  启动服务:   sudo systemctl start duckdb-mysql"
echo "  停止服务:   sudo systemctl stop duckdb-mysql"
echo "  重启服务:   sudo systemctl restart duckdb-mysql"
echo "  查看状态:   sudo systemctl status duckdb-mysql"
echo "  开机启动:   sudo systemctl enable duckdb-mysql"
echo "  查看日志:   sudo journalctl -u duckdb-mysql -f"
echo ""
echo "🌐 服务端口:"
echo "  MySQL协议:  localhost:3306"
echo "  HTTP API:   localhost:8080"
echo ""

# 询问是否立即启动服务
read -p "是否立即启动DuckDB MySQL服务? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 启动服务..."
    systemctl start duckdb-mysql
    systemctl enable duckdb-mysql
    
    echo "✅ 服务启动完成"
    echo "📊 服务状态:"
    systemctl status duckdb-mysql --no-pager
    
    echo ""
    echo "🔍 测试连接:"
    echo "  mysql -h localhost -P 3306 -u root"
    echo "  curl http://localhost:8080/health"
else
    echo "ℹ️  稍后可手动启动服务:"
    echo "  sudo systemctl start duckdb-mysql"
fi

echo ""
echo "�� 更多信息请查看 README.md" 