#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB ATTACH/DETACH 功能测试

根据 DuckDB ATTACH 文档测试服务对 ATTACH 和 DETACH 语句的支持
文档参考: https://duckdb.org/docs/stable/sql/statements/attach
"""

import requests
import json
import os
import tempfile
import pymysql
import time
import sys

class AttachTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_success(self, test_name):
        self.passed += 1
        print(f"✅ {test_name}")
    
    def add_failure(self, test_name, error):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"❌ {test_name}: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n📊 测试总结:")
        print(f"总计: {total}, 通过: {self.passed}, 失败: {self.failed}")
        if self.errors:
            print(f"\n错误详情:")
            for error in self.errors:
                print(f"  - {error}")

class DuckDBAttachTester:
    def __init__(self, http_port=8080, mysql_port=33660):
        self.http_url = f"http://localhost:{http_port}"
        self.mysql_host = "localhost"
        self.mysql_port = mysql_port
        self.mysql_user = "root"
        self.mysql_password = ""
        self.result = AttachTestResult()
        
        # 创建临时数据库文件
        self.temp_dir = tempfile.mkdtemp()
        self.test_db1 = os.path.join(self.temp_dir, "test1.db")
        self.test_db2 = os.path.join(self.temp_dir, "test2.db")
        print(f"📁 临时数据库目录: {self.temp_dir}")
    
    def cleanup(self):
        """清理临时文件"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
            print(f"🧹 已清理临时目录: {self.temp_dir}")
        except Exception as e:
            print(f"⚠️ 清理临时目录失败: {e}")
    
    def execute_http(self, sql):
        """通过HTTP API执行SQL"""
        try:
            response = requests.post(
                f"{self.http_url}/query",
                json={"sql": sql},
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def execute_mysql(self, sql):
        """通过MySQL协议执行SQL"""
        try:
            connection = pymysql.connect(
                host=self.mysql_host,
                port=self.mysql_port,
                user=self.mysql_user,
                password=self.mysql_password,
                charset='utf8mb4'
            )
            
            with connection.cursor() as cursor:
                cursor.execute(sql)
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    rows = []
                    for row in cursor.fetchall():
                        row_dict = {}
                        for i, col in enumerate(columns):
                            row_dict[col] = row[i]
                        rows.append(row_dict)
                    return {
                        "data": {
                            "columns": columns,
                            "rows": rows,
                            "count": len(rows)
                        }
                    }
                else:
                    return {"data": {"affected_rows": cursor.rowcount}}
            
        except Exception as e:
            return {"error": str(e)}
        finally:
            try:
                connection.close()
            except:
                pass
    
    def test_basic_attach_detach(self, protocol="http"):
        """测试基本的ATTACH/DETACH功能"""
        execute_func = self.execute_http if protocol == "http" else self.execute_mysql
        
        # 清理之前可能存在的数据库
        execute_func("DETACH mem_db")
        
        # 1. 测试ATTACH内存数据库
        sql = "ATTACH ':memory:' AS mem_db"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - ATTACH内存数据库", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - ATTACH内存数据库")
        
        # 2. 测试在attached数据库中创建表
        sql = "CREATE TABLE IF NOT EXISTS mem_db.test_table (id INTEGER, name VARCHAR)"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 在attached数据库创建表", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - 在attached数据库创建表")
        
        # 3. 测试插入数据
        sql = "INSERT INTO mem_db.test_table VALUES (1, 'Alice'), (2, 'Bob')"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 插入数据到attached数据库", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - 插入数据到attached数据库")
        
        # 4. 测试查询attached数据库
        sql = "SELECT * FROM mem_db.test_table"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 查询attached数据库", result["error"])
        elif result.get("data", {}).get("count", 0) != 2:
            self.result.add_failure(f"{protocol.upper()} - 查询attached数据库", f"期望2行数据，实际{result.get('data', {}).get('count', 0)}行")
        else:
            self.result.add_success(f"{protocol.upper()} - 查询attached数据库")
        
        # 5. 测试SHOW DATABASES (如果支持的话)
        sql = "SHOW DATABASES"
        result = execute_func(sql)
        if result.get("error"):
            # DuckDB可能不支持SHOW DATABASES，尝试替代方案
            sql = "SELECT DISTINCT catalog_name FROM information_schema.schemata"
            result = execute_func(sql)
            if result.get("error"):
                self.result.add_failure(f"{protocol.upper()} - 列出数据库", result["error"])
            else:
                self.result.add_success(f"{protocol.upper()} - 列出数据库 (使用information_schema)")
        else:
            self.result.add_success(f"{protocol.upper()} - SHOW DATABASES")
        
        # 6. 测试USE命令切换数据库
        sql = "USE mem_db"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - USE切换数据库", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - USE切换数据库")
        
        # 7. 测试DETACH
        sql = "DETACH mem_db"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - DETACH数据库", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - DETACH数据库")
    
    def test_file_attach(self, protocol="http"):
        """测试文件数据库ATTACH"""
        execute_func = self.execute_http if protocol == "http" else self.execute_mysql
        
        # 1. ATTACH文件数据库
        sql = f"ATTACH '{self.test_db1}' AS file_db"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - ATTACH文件数据库", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - ATTACH文件数据库")
        
        # 2. 在文件数据库中创建表
        sql = "CREATE TABLE file_db.products (id INTEGER, name VARCHAR, price DECIMAL)"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 在文件数据库创建表", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - 在文件数据库创建表")
        
        # 3. 插入数据
        sql = "INSERT INTO file_db.products VALUES (1, 'Apple', 1.50), (2, 'Banana', 0.80)"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 文件数据库插入数据", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - 文件数据库插入数据")
        
        # 4. DETACH并重新ATTACH验证持久性
        sql = "DETACH file_db"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - DETACH文件数据库", result["error"])
            return
        
        sql = f"ATTACH '{self.test_db1}' AS file_db"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 重新ATTACH文件数据库", result["error"])
            return
        
        # 5. 验证数据持久性
        sql = "SELECT * FROM file_db.products"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 验证文件数据库持久性", result["error"])
        elif result.get("data", {}).get("count", 0) != 2:
            self.result.add_failure(f"{protocol.upper()} - 验证文件数据库持久性", f"期望2行数据，实际{result.get('data', {}).get('count', 0)}行")
        else:
            self.result.add_success(f"{protocol.upper()} - 验证文件数据库持久性")
    
    def test_attach_or_replace(self, protocol="http"):
        """测试ATTACH OR REPLACE功能"""
        execute_func = self.execute_http if protocol == "http" else self.execute_mysql
        
        # 1. 首次ATTACH
        sql = f"ATTACH '{self.test_db2}' AS replace_test"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 首次ATTACH for REPLACE测试", result["error"])
            return
        
        # 2. 创建表
        sql = "CREATE TABLE replace_test.version_info (version INTEGER)"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 创建版本表", result["error"])
            return
        
        sql = "INSERT INTO replace_test.version_info VALUES (1)"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 插入版本1", result["error"])
            return
        
        # 3. 测试ATTACH OR REPLACE (如果支持的话)
        sql = f"ATTACH OR REPLACE '{self.test_db2}' AS replace_test"
        result = execute_func(sql)
        if result.get("error"):
            # 可能不支持OR REPLACE语法，这是可以接受的
            self.result.add_failure(f"{protocol.upper()} - ATTACH OR REPLACE (可能不支持)", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - ATTACH OR REPLACE")
    
    def test_cross_database_operations(self, protocol="http"):
        """测试跨数据库操作"""
        execute_func = self.execute_http if protocol == "http" else self.execute_mysql
        
        # 1. ATTACH两个数据库
        sql = f"ATTACH ':memory:' AS db1"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - ATTACH db1", result["error"])
            return
        
        sql = f"ATTACH ':memory:' AS db2"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - ATTACH db2", result["error"])
            return
        
        # 2. 在两个数据库中创建表
        sql = "CREATE TABLE db1.source_data (id INTEGER, value VARCHAR)"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 创建源表", result["error"])
            return
        
        sql = "CREATE TABLE db2.target_data (id INTEGER, value VARCHAR)"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 创建目标表", result["error"])
            return
        
        # 3. 插入测试数据
        sql = "INSERT INTO db1.source_data VALUES (1, 'test1'), (2, 'test2')"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 插入源数据", result["error"])
            return
        
        # 4. 测试跨数据库数据复制
        sql = "INSERT INTO db2.target_data SELECT * FROM db1.source_data"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 跨数据库数据复制", result["error"])
        else:
            self.result.add_success(f"{protocol.upper()} - 跨数据库数据复制")
        
        # 5. 验证复制结果
        sql = "SELECT COUNT(*) as count FROM db2.target_data"
        result = execute_func(sql)
        if result.get("error"):
            self.result.add_failure(f"{protocol.upper()} - 验证跨数据库复制结果", result["error"])
        elif len(result.get("data", {}).get("rows", [])) > 0:
            count = result["data"]["rows"][0].get("count", 0)
            if count == 2:
                self.result.add_success(f"{protocol.upper()} - 验证跨数据库复制结果")
            else:
                self.result.add_failure(f"{protocol.upper()} - 验证跨数据库复制结果", f"期望2行，实际{count}行")
        else:
            self.result.add_failure(f"{protocol.upper()} - 验证跨数据库复制结果", "无法获取计数结果")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始DuckDB ATTACH功能测试...")
        print("=" * 60)
        
        # 测试HTTP API
        print("\n📡 测试HTTP API:")
        self.test_basic_attach_detach("http")
        self.test_file_attach("http")
        self.test_attach_or_replace("http")
        self.test_cross_database_operations("http")
        
        # 测试MySQL协议
        print("\n🐬 测试MySQL协议:")
        self.test_basic_attach_detach("mysql")
        self.test_file_attach("mysql")
        self.test_attach_or_replace("mysql")
        self.test_cross_database_operations("mysql")
        
        # 显示结果
        print("\n" + "=" * 60)
        self.result.summary()
        
        return self.result.failed == 0

def check_server_status(http_port=8080):
    """检查服务器状态"""
    try:
        response = requests.get(f"http://localhost:{http_port}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 服务器运行正常")
            return True
        else:
            print(f"❌ 服务器健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        return False

def main():
    print("🦆 DuckDB ATTACH功能测试工具")
    print("基于文档: https://duckdb.org/docs/stable/sql/statements/attach")
    print("=" * 60)
    
    # 检查服务器状态
    if not check_server_status():
        print("\n💡 请确保DuckDB服务器正在运行:")
        print("   go run main.go")
        return False
    
    # 运行测试
    tester = DuckDBAttachTester()
    try:
        success = tester.run_all_tests()
        return success
    finally:
        tester.cleanup()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
