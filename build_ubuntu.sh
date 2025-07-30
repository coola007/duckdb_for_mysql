#!/bin/bash
# DuckDB MySQL协议服务器 - Ubuntu编译脚本

set -e

echo "🚀 开始编译DuckDB MySQL协议服务器 (Ubuntu x86_64)"
echo "================================================"

# 检查Go环境
if ! command -v go &> /dev/null; then
    echo "❌ Go未安装，请先安装Go 1.19+"
    exit 1
fi

echo "✅ Go版本: $(go version)"

# 创建构建目录
BUILD_DIR="build"
mkdir -p $BUILD_DIR

# 设置版本信息
VERSION=$(date +"%Y.%m.%d")
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "📦 构建信息:"
echo "  版本: $VERSION"
echo "  构建时间: $BUILD_TIME"
echo "  Git提交: $GIT_COMMIT"

# 交叉编译到Ubuntu Linux x86_64
echo "🔨 编译 Linux x86_64 版本..."
export GOOS=linux
export GOARCH=amd64
export CGO_ENABLED=1

# 设置构建标志
LDFLAGS="-X main.Version=$VERSION -X main.BuildTime=$BUILD_TIME -X main.GitCommit=$GIT_COMMIT -w -s"

go build -ldflags "$LDFLAGS" -o $BUILD_DIR/duckdb-mysql-server-linux-amd64 .

if [ $? -eq 0 ]; then
    echo "✅ Linux x86_64 编译成功"
    
    # 显示文件信息
    ls -lh $BUILD_DIR/duckdb-mysql-server-linux-amd64
    file $BUILD_DIR/duckdb-mysql-server-linux-amd64
else
    echo "❌ Linux x86_64 编译失败"
    exit 1
fi

# 编译ARM64版本（适用于ARM服务器）
echo "🔨 编译 Linux ARM64 版本..."
export GOARCH=arm64
export CGO_ENABLED=0

go build -ldflags "$LDFLAGS" -o $BUILD_DIR/duckdb-mysql-server-linux-arm64 .

if [ $? -eq 0 ]; then
    echo "✅ Linux ARM64 编译成功"
    ls -lh $BUILD_DIR/duckdb-mysql-server-linux-arm64
    file $BUILD_DIR/duckdb-mysql-server-linux-arm64
else
    echo "❌ Linux ARM64 编译失败"
fi

echo ""
echo "📦 构建产物:"
ls -la $BUILD_DIR/

echo ""
echo "🎉 Ubuntu编译完成！"
echo "📍 可执行文件位置:"
echo "  - Linux x86_64: $BUILD_DIR/duckdb-mysql-server-linux-amd64"
echo "  - Linux ARM64:  $BUILD_DIR/duckdb-mysql-server-linux-arm64" 