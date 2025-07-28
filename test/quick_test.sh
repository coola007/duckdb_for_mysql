#!/bin/bash

# DuckDB多协议服务快速测试脚本

BASE_URL="http://localhost:8080"

echo "=== DuckDB Multi-Protocol Server 快速测试 ==="
echo

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试函数
test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    
    echo -n "测试 $name... "
    
    if [ "$method" = "POST" ]; then
        result=$(curl -s -X POST "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    else
        result=$(curl -s "$BASE_URL$endpoint")
    fi
    
    if echo "$result" | jq . >/dev/null 2>&1; then
        if echo "$result" | jq -e '.error' >/dev/null 2>&1; then
            error=$(echo "$result" | jq -r '.error')
            if [ "$error" != "null" ]; then
                echo -e "${RED}失败${NC} - 错误: $error"
                return 1
            fi
        fi
        echo -e "${GREEN}成功${NC}"
        return 0
    else
        echo -e "${RED}失败${NC} - 无效响应"
        return 1
    fi
}

# 等待服务启动
echo "等待服务启动..."
sleep 2

# 1. 健康检查
test_endpoint "健康检查" "GET" "/health" ""

# 2. 基础查询
echo
echo "=== 基础SQL查询测试 ==="
test_endpoint "简单SELECT" "POST" "/query" '{"sql": "SELECT 1 as num, '\''hello'\'' as msg"}'
test_endpoint "数学运算" "POST" "/query" '{"sql": "SELECT 2 + 3 as result, sqrt(16) as sqrt_val"}'
test_endpoint "字符串函数" "POST" "/query" '{"sql": "SELECT upper('\''duckdb'\'') as upper_str, length('\''test'\'') as str_len"}'
test_endpoint "当前时间" "POST" "/query" '{"sql": "SELECT current_date as today, current_timestamp as now"}'

# 3. DuckDB特有功能
echo
echo "=== DuckDB特有功能测试 ==="
test_endpoint "数组操作" "POST" "/query" '{"sql": "SELECT [1, 2, 3, 4] as arr"}'
test_endpoint "窗口函数" "POST" "/query" '{"sql": "SELECT row_number() OVER () as rn FROM (VALUES (1), (2), (3)) t(v)"}'
test_endpoint "聚合函数" "POST" "/query" '{"sql": "SELECT sum(v) as total, avg(v) as average FROM (VALUES (1), (2), (3), (4), (5)) t(v)"}'

# 4. 表操作
echo
echo "=== 表操作测试 ==="
test_endpoint "创建表" "POST" "/query" '{"sql": "CREATE TABLE quick_test (id INTEGER, name VARCHAR, value DOUBLE)"}'
test_endpoint "插入数据" "POST" "/query" '{"sql": "INSERT INTO quick_test VALUES (1, '\''test1'\'', 10.5), (2, '\''test2'\'', 20.5)"}'
test_endpoint "查询数据" "POST" "/query" '{"sql": "SELECT * FROM quick_test ORDER BY id"}'
test_endpoint "更新数据" "POST" "/query" '{"sql": "UPDATE quick_test SET value = 15.5 WHERE name = '\''test1'\''"}'
test_endpoint "删除数据" "POST" "/query" '{"sql": "DELETE FROM quick_test WHERE id = 2"}'
test_endpoint "删除表" "POST" "/query" '{"sql": "DROP TABLE quick_test"}'

# 5. 错误处理
echo
echo "=== 错误处理测试 ==="
echo -n "测试语法错误... "
result=$(curl -s -X POST "$BASE_URL/query" \
    -H "Content-Type: application/json" \
    -d '{"sql": "SELCT * FRM table"}')
if echo "$result" | jq -e '.error' >/dev/null 2>&1; then
    echo -e "${GREEN}成功${NC} (正确返回错误)"
else
    echo -e "${RED}失败${NC} (应该返回错误)"
fi

# 6. 管理接口
echo
echo "=== 管理接口测试 ==="
test_endpoint "查看指标" "GET" "/metrics" ""
test_endpoint "列出表" "GET" "/admin/tables" ""

# 7. 性能测试
echo
echo "=== 性能测试 ==="
echo -n "性能测试 (100次简单查询)... "
start_time=$(date +%s%N)
for i in {1..100}; do
    curl -s -X POST "$BASE_URL/query" \
        -H "Content-Type: application/json" \
        -d '{"sql": "SELECT 1"}' >/dev/null
done
end_time=$(date +%s%N)
duration=$(( (end_time - start_time) / 1000000 ))
echo -e "${GREEN}完成${NC} - 总耗时: ${duration}ms (平均: $((duration/100))ms/query)"

# 8. 分析型查询测试
echo
echo "=== 分析型查询测试 ==="

# 创建测试数据
test_endpoint "创建销售数据表" "POST" "/query" '{"sql": "CREATE TABLE sales (id INTEGER, category VARCHAR, amount DOUBLE, date DATE)"}'

test_endpoint "插入销售数据" "POST" "/query" '{"sql": "INSERT INTO sales VALUES (1, '\''Electronics'\'', 1500.00, '\''2024-01-15'\''), (2, '\''Clothing'\'', 800.00, '\''2024-01-16'\''), (3, '\''Electronics'\'', 2200.00, '\''2024-01-17'\''), (4, '\''Books'\'', 300.00, '\''2024-01-18'\'')"}'

test_endpoint "聚合分析" "POST" "/query" '{"sql": "SELECT category, COUNT(*) as count, SUM(amount) as total, AVG(amount) as avg FROM sales GROUP BY category ORDER BY total DESC"}'

test_endpoint "窗口函数分析" "POST" "/query" '{"sql": "SELECT *, ROW_NUMBER() OVER (PARTITION BY category ORDER BY amount DESC) as rank FROM sales"}'

# 清理测试数据
test_endpoint "清理销售数据表" "POST" "/query" '{"sql": "DROP TABLE sales"}'

echo
echo "=== 测试完成 ==="
echo -e "${YELLOW}注意: 确保DuckDB服务正在运行在 http://localhost:8080${NC}" 