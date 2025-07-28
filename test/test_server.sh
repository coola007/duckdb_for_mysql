#!/bin/bash

# 测试DuckDB Multi-Protocol Server的HTTP API

BASE_URL="http://localhost:8080"

echo "=== DuckDB Multi-Protocol Server 测试 ==="
echo

# 等待服务启动
echo "等待服务启动..."
sleep 3

# 测试健康检查
echo "1. 测试健康检查..."
curl -s "$BASE_URL/health" | jq .
echo

# 测试简单查询
echo "2. 测试简单查询..."
curl -s -X POST "$BASE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT 1 as test, \"Hello DuckDB\" as message"}' | jq .
echo

# 测试创建表
echo "3. 测试创建表..."
curl -s -X POST "$BASE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{"sql": "CREATE TABLE users (id INTEGER, name VARCHAR, age INTEGER)"}' | jq .
echo

# 测试插入数据
echo "4. 测试插入数据..."
curl -s -X POST "$BASE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{"sql": "INSERT INTO users VALUES (1, \"Alice\", 25), (2, \"Bob\", 30), (3, \"Charlie\", 35)"}' | jq .
echo

# 测试查询数据
echo "5. 测试查询数据..."
curl -s -X POST "$BASE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM users WHERE age > 25"}' | jq .
echo

# 测试列出表
echo "6. 测试列出表..."
curl -s "$BASE_URL/admin/tables" | jq .
echo

# 测试指标
echo "7. 测试指标..."
curl -s "$BASE_URL/metrics" | jq .
echo

echo "=== 测试完成 ===" 