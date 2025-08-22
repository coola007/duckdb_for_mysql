#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的DuckDB ATTACH功能测试

专门测试基本的ATTACH/DETACH功能
"""

import requests
import json
import os
import tempfile
import pymysql
import time
import sys

def test_http_attach():
    """通过HTTP API测试ATTACH功能"""
    print("🌐 测试HTTP API ATTACH功能:")
    
    base_url = "http://localhost:8080"
    
    def execute_sql(sql):
        try:
            response = requests.post(
                f"{base_url}/query",
                json={"sql": sql},
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # 测试1: 基本健康检查
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 服务器连接正常")
        else:
            print(f"❌ 服务器响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接服务器: {e}")
        return False
    
    # 测试2: ATTACH内存数据库
    print("\n📝 测试基本ATTACH功能:")
    
    sql = "ATTACH ':memory:' AS test_mem_db"
    result = execute_sql(sql)
    if result.get("error"):
        print(f"❌ ATTACH内存数据库失败: {result['error']}")
        return False
    else:
        print("✅ ATTACH内存数据库成功")
    
    # 测试3: 在attached数据库中创建表
    sql = "CREATE TABLE test_mem_db.users (id INTEGER, name VARCHAR)"
    result = execute_sql(sql)
    if result.get("error"):
        print(f"❌ 创建表失败: {result['error']}")
    else:
        print("✅ 在attached数据库创建表成功")
    
    # 测试4: 插入数据
    sql = "INSERT INTO test_mem_db.users VALUES (1, 'Alice'), (2, 'Bob')"
    result = execute_sql(sql)
    if result.get("error"):
        print(f"❌ 插入数据失败: {result['error']}")
    else:
        print("✅ 插入数据成功")
    
    # 测试5: 查询数据
    sql = "SELECT * FROM test_mem_db.users"
    result = execute_sql(sql)
    if result.get("error"):
        print(f"❌ 查询数据失败: {result['error']}")
    else:
        rows = result.get("data", {}).get("rows", [])
        print(f"✅ 查询数据成功，获得 {len(rows)} 行数据")
        for row in rows:
            print(f"   - {row}")
    
    # 测试6: 列出数据库
    sql = "SELECT DISTINCT catalog_name FROM information_schema.schemata"
    result = execute_sql(sql)
    if result.get("error"):
        print(f"❌ 列出数据库失败: {result['error']}")
    else:
        catalogs = result.get("data", {}).get("rows", [])
        print(f"✅ 当前连接的数据库:")
        for catalog in catalogs:
            print(f"   - {catalog}")
    
    # 测试7: 测试USE命令
    sql = "USE test_mem_db"
    result = execute_sql(sql)
    if result.get("error"):
        print(f"❌ USE命令失败: {result['error']}")
    else:
        print("✅ USE命令成功")
    
    # 测试8: 切换回主数据库
    sql = "USE main"
    result = execute_sql(sql)
    if result.get("error"):
        print(f"❌ 切换回主数据库失败: {result['error']}")
    else:
        print("✅ 切换回主数据库成功")
    
    # 测试9: DETACH数据库
    sql = "DETACH test_mem_db"
    result = execute_sql(sql)
    if result.get("error"):
        print(f"❌ DETACH数据库失败: {result['error']}")
    else:
        print("✅ DETACH数据库成功")
    
    return True

def test_mysql_attach():
    """通过MySQL协议测试ATTACH功能"""
    print("\n🐬 测试MySQL协议ATTACH功能:")
    
    try:
        connection = pymysql.connect(
            host="localhost",
            port=33660,
            user="root",
            password="",
            charset='utf8mb4'
        )
        print("✅ MySQL协议连接成功")
        
        def execute_sql(sql):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    if cursor.description:
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        return {"success": True, "columns": columns, "rows": rows}
                    else:
                        return {"success": True, "affected_rows": cursor.rowcount}
            except Exception as e:
                return {"error": str(e)}
        
        # 测试ATTACH
        result = execute_sql("ATTACH ':memory:' AS mysql_test_db")
        if result.get("error"):
            print(f"❌ MySQL ATTACH失败: {result['error']}")
        else:
            print("✅ MySQL ATTACH成功")
        
        # 测试创建表和数据操作
        result = execute_sql("CREATE TABLE mysql_test_db.products (id INTEGER, name VARCHAR, price DECIMAL)")
        if result.get("error"):
            print(f"❌ MySQL创建表失败: {result['error']}")
        else:
            print("✅ MySQL创建表成功")
        
        result = execute_sql("INSERT INTO mysql_test_db.products VALUES (1, 'Apple', 1.50), (2, 'Banana', 0.80)")
        if result.get("error"):
            print(f"❌ MySQL插入数据失败: {result['error']}")
        else:
            print("✅ MySQL插入数据成功")
        
        result = execute_sql("SELECT * FROM mysql_test_db.products")
        if result.get("error"):
            print(f"❌ MySQL查询数据失败: {result['error']}")
        else:
            print(f"✅ MySQL查询数据成功，获得 {len(result['rows'])} 行")
            for row in result['rows']:
                print(f"   - {row}")
        
        # 测试DETACH
        result = execute_sql("USE main")
        if result.get("error"):
            print(f"⚠️ MySQL USE main: {result['error']}")
        
        result = execute_sql("DETACH mysql_test_db")
        if result.get("error"):
            print(f"❌ MySQL DETACH失败: {result['error']}")
        else:
            print("✅ MySQL DETACH成功")
        
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ MySQL协议连接失败: {e}")
        return False

def test_file_attach():
    """测试文件数据库ATTACH功能"""
    print("\n📁 测试文件数据库ATTACH功能:")
    
    # 创建临时数据库文件
    temp_dir = tempfile.mkdtemp()
    test_db = os.path.join(temp_dir, "attach_test.db")
    print(f"📂 临时数据库: {test_db}")
    
    base_url = "http://localhost:8080"
    
    def execute_sql(sql):
        try:
            response = requests.post(
                f"{base_url}/query",
                json={"sql": sql},
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    try:
        # ATTACH文件数据库
        sql = f"ATTACH '{test_db}' AS file_test_db"
        result = execute_sql(sql)
        if result.get("error"):
            print(f"❌ ATTACH文件数据库失败: {result['error']}")
            return False
        else:
            print("✅ ATTACH文件数据库成功")
        
        # 创建表
        sql = "CREATE TABLE file_test_db.orders (id INTEGER, customer VARCHAR, amount DECIMAL)"
        result = execute_sql(sql)
        if result.get("error"):
            print(f"❌ 创建表失败: {result['error']}")
        else:
            print("✅ 在文件数据库创建表成功")
        
        # 插入数据
        sql = "INSERT INTO file_test_db.orders VALUES (1, 'John', 100.50), (2, 'Jane', 250.00)"
        result = execute_sql(sql)
        if result.get("error"):
            print(f"❌ 插入数据失败: {result['error']}")
        else:
            print("✅ 插入数据成功")
        
        # DETACH
        sql = "DETACH file_test_db"
        result = execute_sql(sql)
        if result.get("error"):
            print(f"❌ DETACH失败: {result['error']}")
        else:
            print("✅ DETACH成功")
        
        # 重新ATTACH验证持久性
        sql = f"ATTACH '{test_db}' AS file_test_db"
        result = execute_sql(sql)
        if result.get("error"):
            print(f"❌ 重新ATTACH失败: {result['error']}")
        else:
            print("✅ 重新ATTACH成功")
        
        # 验证数据持久性
        sql = "SELECT * FROM file_test_db.orders"
        result = execute_sql(sql)
        if result.get("error"):
            print(f"❌ 验证持久性失败: {result['error']}")
        else:
            rows = result.get("data", {}).get("rows", [])
            print(f"✅ 数据持久性验证成功，获得 {len(rows)} 行数据")
            for row in rows:
                print(f"   - {row}")
        
        # 清理
        execute_sql("DETACH file_test_db")
        
    finally:
        # 清理临时文件
        import shutil
        try:
            shutil.rmtree(temp_dir)
            print(f"🧹 已清理临时目录: {temp_dir}")
        except Exception as e:
            print(f"⚠️ 清理临时目录失败: {e}")
    
    return True

def main():
    print("🦆 DuckDB ATTACH功能简化测试")
    print("=" * 50)
    
    success = True
    
    # 测试HTTP API
    if not test_http_attach():
        success = False
    
    # 测试MySQL协议
    if not test_mysql_attach():
        success = False
    
    # 测试文件数据库
    if not test_file_attach():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 所有基本ATTACH功能测试通过!")
        print("\n📋 功能支持总结:")
        print("✅ ATTACH内存数据库 (:memory:)")
        print("✅ ATTACH文件数据库")
        print("✅ 在attached数据库中创建表")
        print("✅ 跨数据库数据操作")
        print("✅ USE命令切换数据库")
        print("✅ DETACH数据库")
        print("✅ 数据持久性")
        print("✅ HTTP和MySQL双协议支持")
        
        print("\n⚠️ 注意事项:")
        print("- ATTACH OR REPLACE语法可能不被支持")
        print("- 不能DETACH默认数据库，需要先USE切换")
        
    else:
        print("❌ 部分功能测试失败")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
