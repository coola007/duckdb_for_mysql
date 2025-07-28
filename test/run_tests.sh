#!/bin/bash

# DuckDB多协议服务综合测试脚本

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  DuckDB Multi-Protocol Server 测试套件${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# 检查依赖
echo "检查测试依赖..."

# 检查jq
if ! command -v jq &> /dev/null; then
    echo -e "${RED}错误: jq 未安装，请先安装 jq${NC}"
    echo "macOS: brew install jq"
    echo "Ubuntu: sudo apt-get install jq"
    exit 1
fi

# 检查curl
if ! command -v curl &> /dev/null; then
    echo -e "${RED}错误: curl 未安装${NC}"
    exit 1
fi

# 检查Go
if ! command -v go &> /dev/null; then
    echo -e "${RED}错误: Go 未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 依赖检查通过${NC}"
echo

# 启动服务
echo "启动DuckDB服务..."
echo -e "${YELLOW}正在后台启动服务器...${NC}"

# 检查端口是否被占用
if lsof -i :8080 >/dev/null 2>&1; then
    echo -e "${YELLOW}警告: 端口8080已被占用，尝试终止现有进程...${NC}"
    pkill -f "go run main.go" 2>/dev/null || true
    sleep 2
fi

if lsof -i :3366 >/dev/null 2>&1; then
    echo -e "${YELLOW}警告: 端口3366已被占用，尝试终止现有进程...${NC}"
    pkill -f "go run main.go" 2>/dev/null || true
    sleep 2
fi

# 启动服务
nohup go run main.go > server.log 2>&1 &
SERVER_PID=$!

echo "服务PID: $SERVER_PID"
echo "日志文件: server.log"

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 检查服务是否启动成功
if ! ps -p $SERVER_PID > /dev/null; then
    echo -e "${RED}错误: 服务启动失败${NC}"
    echo "查看日志:"
    cat server.log
    exit 1
fi

# 检查HTTP端口
if ! curl -s http://localhost:8080/health >/dev/null; then
    echo -e "${RED}错误: HTTP服务未响应${NC}"
    echo "查看日志:"
    tail -20 server.log
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✓ 服务启动成功${NC}"
echo

# 运行测试
TEST_RESULTS=()

# 1. HTTP API测试
echo -e "${BLUE}==================== HTTP API 测试 ====================${NC}"
if ./quick_test.sh; then
    echo -e "${GREEN}✓ HTTP API测试通过${NC}"
    TEST_RESULTS+=("HTTP API测试:通过")
else
    echo -e "${RED}✗ HTTP API测试失败${NC}"
    TEST_RESULTS+=("HTTP API测试:失败")
fi
echo

# 2. MySQL协议测试
echo -e "${BLUE}=================== MySQL 协议测试 ===================${NC}"
if python3 test_mysql_protocol.py; then
    echo -e "${GREEN}✓ MySQL协议测试通过${NC}"
    TEST_RESULTS+=("MySQL协议测试:通过")
else
    echo -e "${RED}✗ MySQL协议测试失败${NC}"
    TEST_RESULTS+=("MySQL协议测试:失败")
fi
echo

# 3. Go单元测试
echo -e "${BLUE}==================== Go 单元测试 ====================${NC}"
if go test -v ./... -run="Test.*" -timeout=30s; then
    echo -e "${GREEN}✓ Go单元测试通过${NC}"
    TEST_RESULTS+=("Go单元测试:通过")
else
    echo -e "${RED}✗ Go单元测试失败${NC}"
    TEST_RESULTS+=("Go单元测试:失败")
fi
echo

# 4. 性能基准测试
echo -e "${BLUE}=================== 性能基准测试 ===================${NC}"
if go test -bench=. -run="Benchmark.*" -timeout=60s; then
    echo -e "${GREEN}✓ 性能基准测试完成${NC}"
    TEST_RESULTS+=("性能基准测试:完成")
else
    echo -e "${RED}✗ 性能基准测试失败${NC}"
    TEST_RESULTS+=("性能基准测试:失败")
fi
echo

# 清理
echo "清理测试环境..."
kill $SERVER_PID 2>/dev/null || true
sleep 2

# 确保进程完全终止
pkill -f "go run main.go" 2>/dev/null || true

echo -e "${GREEN}✓ 服务已停止${NC}"
echo

# 测试结果汇总
echo -e "${BLUE}==================== 测试结果汇总 ====================${NC}"
PASSED=0
TOTAL=${#TEST_RESULTS[@]}

for result in "${TEST_RESULTS[@]}"; do
    IFS=':' read -r test_name status <<< "$result"
    if [[ "$status" == "通过" || "$status" == "完成" ]]; then
        echo -e "${GREEN}✓${NC} $test_name"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} $test_name"
    fi
done

echo
echo "总计: $PASSED/$TOTAL 测试通过"

if [ $PASSED -eq $TOTAL ]; then
    echo -e "${GREEN}🎉 所有测试通过！${NC}"
    echo
    echo "服务功能验证:"
    echo "  ✓ HTTP API (端口8080) - 正常"
    echo "  ✓ MySQL协议 (端口3366) - 正常" 
    echo "  ✓ DuckDB连接 - 正常"
    echo "  ✓ 查询执行 - 正常"
    echo "  ✓ 错误处理 - 正常"
    echo "  ✓ 并发处理 - 正常"
    echo
    echo -e "${BLUE}服务已准备好用于生产环境！${NC}"
    exit 0
else
    echo -e "${RED}⚠️  部分测试失败${NC}"
    echo
    echo "故障排查建议:"
    echo "1. 检查Go版本和依赖: go version && go mod tidy"
    echo "2. 检查端口占用: lsof -i :8080 && lsof -i :3366"
    echo "3. 查看服务日志: cat server.log"
    echo "4. 检查DuckDB驱动: go list -m github.com/marcboeker/go-duckdb"
    echo
    exit 1
fi 