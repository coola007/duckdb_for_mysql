#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB ATTACH功能并发测试

测试多客户端同时进行ATTACH/DETACH操作时的并发安全性
包括各种竞态条件和异常场景的测试
"""

import requests
import json
import os
import tempfile
import pymysql
import time
import sys
import threading
import queue
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import traceback

class ConcurrentTestResult:
    def __init__(self):
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.errors = []
        self.warnings = []
        self.race_conditions = []
        self.lock = threading.Lock()
    
    def add_success(self, operation_type, client_id, details=""):
        with self.lock:
            self.total_operations += 1
            self.successful_operations += 1
            print(f"✅ [{client_id}] {operation_type} 成功 {details}")
    
    def add_failure(self, operation_type, client_id, error, details=""):
        with self.lock:
            self.total_operations += 1
            self.failed_operations += 1
            error_msg = f"[{client_id}] {operation_type} 失败: {error} {details}"
            self.errors.append(error_msg)
            print(f"❌ {error_msg}")
    
    def add_warning(self, operation_type, client_id, warning, details=""):
        with self.lock:
            warning_msg = f"[{client_id}] {operation_type} 警告: {warning} {details}"
            self.warnings.append(warning_msg)
            print(f"⚠️ {warning_msg}")
    
    def add_race_condition(self, operation_type, client_id, description):
        with self.lock:
            race_msg = f"[{client_id}] {operation_type} 检测到竞态条件: {description}"
            self.race_conditions.append(race_msg)
            print(f"🏁 {race_msg}")
    
    def summary(self):
        print(f"\n📊 并发测试总结:")
        print(f"总操作数: {self.total_operations}")
        print(f"成功: {self.successful_operations}")
        print(f"失败: {self.failed_operations}")
        if self.total_operations > 0:
            success_rate = (self.successful_operations / self.total_operations) * 100
            print(f"成功率: {success_rate:.2f}%")
        
        if self.errors:
            print(f"\n❌ 错误详情 ({len(self.errors)}个):")
            for error in self.errors[-10:]:  # 显示最后10个错误
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... 还有 {len(self.errors) - 10} 个错误")
        
        if self.warnings:
            print(f"\n⚠️ 警告详情 ({len(self.warnings)}个):")
            for warning in self.warnings[-5:]:  # 显示最后5个警告
                print(f"  - {warning}")
        
        if self.race_conditions:
            print(f"\n🏁 检测到的竞态条件 ({len(self.race_conditions)}个):")
            for race in self.race_conditions:
                print(f"  - {race}")

class ConcurrentAttachTester:
    def __init__(self, http_port=8080, mysql_port=33660):
        self.http_url = f"http://localhost:{http_port}"
        self.mysql_host = "localhost"
        self.mysql_port = mysql_port
        self.mysql_user = "root"
        self.mysql_password = ""
        self.result = ConcurrentTestResult()
        
        # 创建临时目录和数据库文件
        self.temp_dir = tempfile.mkdtemp()
        self.shared_db_files = []
        for i in range(5):
            db_file = os.path.join(self.temp_dir, f"shared_{i}.db")
            self.shared_db_files.append(db_file)
        
        print(f"📁 临时数据库目录: {self.temp_dir}")
        print(f"📊 创建了 {len(self.shared_db_files)} 个共享数据库文件")
    
    def cleanup(self):
        """清理临时文件"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
            print(f"🧹 已清理临时目录: {self.temp_dir}")
        except Exception as e:
            print(f"⚠️ 清理临时目录失败: {e}")
    
    def execute_http(self, sql, client_id="http", timeout=10):
        """通过HTTP API执行SQL"""
        try:
            response = requests.post(
                f"{self.http_url}/query",
                json={"sql": sql},
                timeout=timeout
            )
            result = response.json()
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def execute_mysql(self, sql, client_id="mysql", timeout=10):
        """通过MySQL协议执行SQL"""
        try:
            connection = pymysql.connect(
                host=self.mysql_host,
                port=self.mysql_port,
                user=self.mysql_user,
                password=self.mysql_password,
                charset='utf8mb4',
                connect_timeout=timeout
            )
            
            try:
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
            finally:
                connection.close()
            
        except Exception as e:
            return {"error": str(e)}
    
    def concurrent_attach_detach_worker(self, client_id, operations_count, protocol="http"):
        """并发ATTACH/DETACH工作线程"""
        execute_func = self.execute_http if protocol == "http" else self.execute_mysql
        
        for i in range(operations_count):
            try:
                # 随机选择一个数据库文件或内存数据库
                if random.choice([True, False]):
                    # 使用文件数据库
                    db_file = random.choice(self.shared_db_files)
                    attach_sql = f"ATTACH '{db_file}' AS client_{client_id}_db_{i}"
                    db_name = f"client_{client_id}_db_{i}"
                else:
                    # 使用内存数据库
                    attach_sql = f"ATTACH ':memory:' AS client_{client_id}_mem_{i}"
                    db_name = f"client_{client_id}_mem_{i}"
                
                # ATTACH操作
                result = execute_func(attach_sql, client_id)
                if result.get("error"):
                    if "already exists" in result["error"]:
                        self.result.add_race_condition("ATTACH", client_id, 
                                                     f"数据库名称冲突: {db_name}")
                    else:
                        self.result.add_failure("ATTACH", client_id, result["error"])
                    continue
                else:
                    self.result.add_success("ATTACH", client_id, f"-> {db_name}")
                
                # 在attached数据库中进行操作
                table_name = f"test_table_{i}"
                create_sql = f"CREATE TABLE {db_name}.{table_name} (id INTEGER, data VARCHAR, client_id VARCHAR)"
                result = execute_func(create_sql, client_id)
                if result.get("error"):
                    if "already exists" in result["error"]:
                        self.result.add_race_condition("CREATE_TABLE", client_id, 
                                                     f"表已存在: {table_name}")
                    else:
                        self.result.add_failure("CREATE_TABLE", client_id, result["error"])
                else:
                    self.result.add_success("CREATE_TABLE", client_id)
                
                # 插入数据
                insert_sql = f"INSERT INTO {db_name}.{table_name} VALUES ({i}, 'data_{i}', '{client_id}')"
                result = execute_func(insert_sql, client_id)
                if result.get("error"):
                    self.result.add_failure("INSERT", client_id, result["error"])
                else:
                    self.result.add_success("INSERT", client_id)
                
                # 短暂等待，增加并发冲突概率
                time.sleep(random.uniform(0.001, 0.01))
                
                # 查询数据
                select_sql = f"SELECT COUNT(*) as count FROM {db_name}.{table_name}"
                result = execute_func(select_sql, client_id)
                if result.get("error"):
                    self.result.add_failure("SELECT", client_id, result["error"])
                else:
                    self.result.add_success("SELECT", client_id)
                
                # DETACH操作
                # 先切换到主数据库
                execute_func("USE main", client_id)
                
                detach_sql = f"DETACH {db_name}"
                result = execute_func(detach_sql, client_id)
                if result.get("error"):
                    if "does not exist" in result["error"]:
                        self.result.add_race_condition("DETACH", client_id, 
                                                     f"数据库已被其他客户端detach: {db_name}")
                    else:
                        self.result.add_failure("DETACH", client_id, result["error"])
                else:
                    self.result.add_success("DETACH", client_id)
                
                # 随机休息
                time.sleep(random.uniform(0.001, 0.005))
                
            except Exception as e:
                self.result.add_failure("WORKER_ERROR", client_id, str(e))
                traceback.print_exc()
    
    def concurrent_same_database_worker(self, client_id, db_file, operations_count, protocol="http"):
        """多个客户端操作同一个数据库文件的工作线程"""
        execute_func = self.execute_http if protocol == "http" else self.execute_mysql
        
        db_alias = f"shared_db_{client_id}"
        
        for i in range(operations_count):
            try:
                # 尝试ATTACH同一个数据库文件
                attach_sql = f"ATTACH '{db_file}' AS {db_alias}"
                result = execute_func(attach_sql, client_id)
                
                if result.get("error"):
                    if "already attached" in result["error"] or "already exists" in result["error"]:
                        self.result.add_race_condition("ATTACH_SHARED", client_id, 
                                                     "多客户端尝试attach同一数据库")
                        # 尝试使用已存在的附加数据库
                    else:
                        self.result.add_failure("ATTACH_SHARED", client_id, result["error"])
                        continue
                else:
                    self.result.add_success("ATTACH_SHARED", client_id)
                
                # 尝试在共享数据库中创建表
                table_name = f"client_{client_id}_table_{i}"
                create_sql = f"CREATE TABLE IF NOT EXISTS {db_alias}.{table_name} (id INTEGER, client_id VARCHAR, timestamp TIMESTAMP)"
                result = execute_func(create_sql, client_id)
                if result.get("error"):
                    self.result.add_failure("CREATE_SHARED_TABLE", client_id, result["error"])
                else:
                    self.result.add_success("CREATE_SHARED_TABLE", client_id)
                
                # 插入数据
                timestamp = datetime.now().isoformat()
                insert_sql = f"INSERT INTO {db_alias}.{table_name} VALUES ({i}, '{client_id}', '{timestamp}')"
                result = execute_func(insert_sql, client_id)
                if result.get("error"):
                    self.result.add_failure("INSERT_SHARED", client_id, result["error"])
                else:
                    self.result.add_success("INSERT_SHARED", client_id)
                
                time.sleep(random.uniform(0.001, 0.01))
                
            except Exception as e:
                self.result.add_failure("SHARED_WORKER_ERROR", client_id, str(e))
    
    def database_switching_worker(self, client_id, operations_count, protocol="http"):
        """频繁切换数据库的工作线程"""
        execute_func = self.execute_http if protocol == "http" else self.execute_mysql
        
        # 预先创建几个数据库
        databases = []
        for i in range(3):
            db_name = f"switch_test_{client_id}_{i}"
            attach_sql = f"ATTACH ':memory:' AS {db_name}"
            result = execute_func(attach_sql, client_id)
            if not result.get("error"):
                databases.append(db_name)
        
        for i in range(operations_count):
            try:
                if databases:
                    # 随机切换数据库
                    target_db = random.choice(databases)
                    use_sql = f"USE {target_db}"
                    result = execute_func(use_sql, client_id)
                    
                    if result.get("error"):
                        self.result.add_failure("USE_SWITCH", client_id, result["error"])
                    else:
                        self.result.add_success("USE_SWITCH", client_id, f"-> {target_db}")
                    
                    # 在当前数据库中执行操作
                    table_name = f"switch_table_{i}"
                    create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER, switch_count INTEGER)"
                    result = execute_func(create_sql, client_id)
                    if not result.get("error"):
                        self.result.add_success("CREATE_IN_SWITCHED_DB", client_id)
                    
                    time.sleep(random.uniform(0.001, 0.005))
                
            except Exception as e:
                self.result.add_failure("SWITCH_WORKER_ERROR", client_id, str(e))
        
        # 清理创建的数据库
        execute_func("USE main", client_id)
        for db_name in databases:
            execute_func(f"DETACH {db_name}", client_id)
    
    def test_concurrent_attach_detach(self, num_clients=10, operations_per_client=5):
        """测试并发ATTACH/DETACH操作"""
        print(f"\n🔄 测试并发ATTACH/DETACH操作:")
        print(f"   客户端数量: {num_clients}")
        print(f"   每客户端操作数: {operations_per_client}")
        
        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            futures = []
            
            # 混合使用HTTP和MySQL协议
            for i in range(num_clients):
                protocol = "http" if i % 2 == 0 else "mysql"
                future = executor.submit(
                    self.concurrent_attach_detach_worker,
                    f"{protocol}_{i}",
                    operations_per_client,
                    protocol
                )
                futures.append(future)
            
            # 等待所有线程完成
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ 线程执行异常: {e}")
    
    def test_shared_database_access(self, num_clients=8, operations_per_client=3):
        """测试多客户端访问同一数据库文件"""
        print(f"\n🤝 测试共享数据库访问:")
        print(f"   客户端数量: {num_clients}")
        print(f"   每客户端操作数: {operations_per_client}")
        
        shared_db = self.shared_db_files[0]  # 使用第一个共享数据库
        
        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            futures = []
            
            for i in range(num_clients):
                protocol = "http" if i % 2 == 0 else "mysql"
                future = executor.submit(
                    self.concurrent_same_database_worker,
                    f"{protocol}_{i}",
                    shared_db,
                    operations_per_client,
                    protocol
                )
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ 共享访问线程异常: {e}")
    
    def test_rapid_database_switching(self, num_clients=6, operations_per_client=10):
        """测试快速数据库切换"""
        print(f"\n⚡ 测试快速数据库切换:")
        print(f"   客户端数量: {num_clients}")
        print(f"   每客户端切换次数: {operations_per_client}")
        
        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            futures = []
            
            for i in range(num_clients):
                protocol = "http" if i % 2 == 0 else "mysql"
                future = executor.submit(
                    self.database_switching_worker,
                    f"switch_{protocol}_{i}",
                    operations_per_client,
                    protocol
                )
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ 切换线程异常: {e}")
    
    def test_stress_scenario(self, duration_seconds=30):
        """压力测试场景"""
        print(f"\n💪 压力测试场景 (持续 {duration_seconds} 秒):")
        
        stop_event = threading.Event()
        
        def stress_worker(worker_id, protocol):
            operation_count = 0
            while not stop_event.is_set():
                try:
                    self.concurrent_attach_detach_worker(f"stress_{protocol}_{worker_id}", 1, protocol)
                    operation_count += 1
                    time.sleep(random.uniform(0.001, 0.01))
                except Exception as e:
                    self.result.add_failure("STRESS_TEST", f"stress_{protocol}_{worker_id}", str(e))
            
            print(f"💪 压力工作者 stress_{protocol}_{worker_id} 完成 {operation_count} 次操作")
        
        # 启动多个压力测试工作者
        threads = []
        for i in range(8):  # 8个并发工作者
            protocol = "http" if i % 2 == 0 else "mysql"
            thread = threading.Thread(target=stress_worker, args=(i, protocol))
            thread.start()
            threads.append(thread)
        
        # 运行指定时间
        time.sleep(duration_seconds)
        stop_event.set()
        
        # 等待所有线程结束
        for thread in threads:
            thread.join()
    
    def check_server_health(self):
        """检查服务器健康状态"""
        try:
            response = requests.get(f"{self.http_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ 服务器健康状态正常")
                return True
            else:
                print(f"❌ 服务器健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 无法连接到服务器: {e}")
            return False
    
    def run_all_concurrent_tests(self):
        """运行所有并发测试"""
        print("🔥 开始DuckDB ATTACH并发安全测试...")
        print("=" * 60)
        
        if not self.check_server_health():
            print("❌ 服务器不可用，测试终止")
            return False
        
        start_time = time.time()
        
        try:
            # 1. 基本并发ATTACH/DETACH测试
            self.test_concurrent_attach_detach(num_clients=12, operations_per_client=5)
            
            # 2. 共享数据库访问测试
            self.test_shared_database_access(num_clients=8, operations_per_client=3)
            
            # 3. 快速数据库切换测试
            self.test_rapid_database_switching(num_clients=6, operations_per_client=8)
            
            # 4. 短时间压力测试
            self.test_stress_scenario(duration_seconds=15)
            
        except KeyboardInterrupt:
            print("\n⏹️ 用户中断测试")
        except Exception as e:
            print(f"\n❌ 测试过程中发生异常: {e}")
            traceback.print_exc()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n⏱️ 测试总耗时: {duration:.2f} 秒")
        self.result.summary()
        
        # 分析并发安全性
        self.analyze_concurrency_safety()
        
        return self.result.failed_operations == 0
    
    def analyze_concurrency_safety(self):
        """分析并发安全性"""
        print(f"\n🔍 并发安全性分析:")
        
        total_ops = self.result.total_operations
        failed_ops = self.result.failed_operations
        race_conditions = len(self.result.race_conditions)
        
        if total_ops == 0:
            print("⚠️ 没有执行任何操作")
            return
        
        failure_rate = (failed_ops / total_ops) * 100
        
        print(f"📈 故障率: {failure_rate:.2f}%")
        
        if failure_rate < 5:
            print("✅ 并发安全性良好 (故障率 < 5%)")
        elif failure_rate < 15:
            print("⚠️ 并发安全性一般 (故障率 5-15%)")
        else:
            print("❌ 并发安全性较差 (故障率 > 15%)")
        
        if race_conditions > 0:
            race_rate = (race_conditions / total_ops) * 100
            print(f"🏁 竞态条件率: {race_rate:.2f}%")
            
            if race_rate > 10:
                print("⚠️ 检测到较多竞态条件，建议检查服务器并发控制机制")
        
        # 检查常见并发问题
        error_patterns = {}
        for error in self.result.errors:
            if "already exists" in error:
                error_patterns["名称冲突"] = error_patterns.get("名称冲突", 0) + 1
            elif "timeout" in error.lower():
                error_patterns["超时"] = error_patterns.get("超时", 0) + 1
            elif "connection" in error.lower():
                error_patterns["连接问题"] = error_patterns.get("连接问题", 0) + 1
            elif "lock" in error.lower():
                error_patterns["锁定问题"] = error_patterns.get("锁定问题", 0) + 1
        
        if error_patterns:
            print(f"\n📊 错误类型分布:")
            for pattern, count in error_patterns.items():
                percentage = (count / len(self.result.errors)) * 100
                print(f"  - {pattern}: {count} 次 ({percentage:.1f}%)")

def main():
    print("🔥 DuckDB ATTACH并发安全测试工具")
    print("=" * 50)
    
    # 运行测试
    tester = ConcurrentAttachTester()
    try:
        success = tester.run_all_concurrent_tests()
        
        print(f"\n🎯 测试结论:")
        if success:
            print("✅ 服务器在并发场景下的ATTACH功能表现良好")
        else:
            print("❌ 服务器在并发场景下存在一些问题，需要进一步优化")
        
        return success
    finally:
        tester.cleanup()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
