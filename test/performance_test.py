#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB MySQL协议性能测试脚本
测试连接性能、查询性能、并发性能等多项指标
"""

import time
import threading
import concurrent.futures
import statistics
import sys
import argparse
from typing import List, Dict, Any
import json

try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False
    print("❌ PyMySQL未安装，请执行: pip install PyMySQL")
    sys.exit(1)

class PerformanceTester:
    """性能测试器"""
    
    def __init__(self, host: str = "localhost", port: int = 33660, user: str = "root", password: str = ""):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.results = {}
        
    def get_connection(self):
        """获取数据库连接"""
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            charset='utf8mb4',
            autocommit=True
        )
    
    def test_connection_performance(self, iterations: int = 100) -> Dict[str, Any]:
        """测试连接性能"""
        print(f"🔗 测试连接性能 ({iterations}次连接)...")
        
        connection_times = []
        for i in range(iterations):
            start_time = time.time()
            try:
                conn = self.get_connection()
                conn.close()
                connection_time = (time.time() - start_time) * 1000  # 转换为毫秒
                connection_times.append(connection_time)
                
                if (i + 1) % 10 == 0:
                    print(f"  完成 {i + 1}/{iterations} 连接测试")
            except Exception as e:
                print(f"  连接失败: {e}")
                return {}
        
        if not connection_times:
            return {}
            
        result = {
            "total_connections": iterations,
            "avg_connection_time_ms": statistics.mean(connection_times),
            "min_connection_time_ms": min(connection_times),
            "max_connection_time_ms": max(connection_times),
            "median_connection_time_ms": statistics.median(connection_times),
            "connections_per_second": 1000 / statistics.mean(connection_times) if connection_times else 0
        }
        
        print(f"  ✅ 平均连接时间: {result['avg_connection_time_ms']:.2f}ms")
        print(f"  ✅ 连接速率: {result['connections_per_second']:.2f} 连接/秒")
        
        return result
    
    def test_query_performance(self, iterations: int = 1000) -> Dict[str, Any]:
        """测试查询性能"""
        print(f"📝 测试查询性能 ({iterations}次查询)...")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 测试不同类型的查询
        test_queries = [
            ("simple_select", "SELECT 1"),
            ("math_calculation", "SELECT 1 + 1 as result, 2 * 3 as product, 10 / 2 as division"),
            ("string_operations", "SELECT 'Hello' || ' ' || 'DuckDB' as greeting, LENGTH('performance') as len"),
            ("current_functions", "SELECT version(), current_timestamp"),
            ("small_aggregation", "SELECT COUNT(*) as cnt, SUM(value) as total FROM (SELECT 1 as value UNION SELECT 2 UNION SELECT 3) t"),
        ]
        
        results = {}
        
        for query_name, query_sql in test_queries:
            print(f"  测试查询类型: {query_name}")
            query_times = []
            
            for i in range(iterations):
                start_time = time.time()
                try:
                    cursor.execute(query_sql)
                    cursor.fetchall()
                    query_time = (time.time() - start_time) * 1000  # 转换为毫秒
                    query_times.append(query_time)
                except Exception as e:
                    print(f"    查询失败: {e}")
                    continue
                
                if (i + 1) % 100 == 0:
                    print(f"    完成 {i + 1}/{iterations} 查询")
            
            if query_times:
                results[query_name] = {
                    "total_queries": len(query_times),
                    "avg_query_time_ms": statistics.mean(query_times),
                    "min_query_time_ms": min(query_times),
                    "max_query_time_ms": max(query_times),
                    "median_query_time_ms": statistics.median(query_times),
                    "queries_per_second": 1000 / statistics.mean(query_times) if query_times else 0
                }
                
                print(f"    ✅ 平均查询时间: {results[query_name]['avg_query_time_ms']:.2f}ms")
                print(f"    ✅ QPS: {results[query_name]['queries_per_second']:.2f}")
        
        cursor.close()
        conn.close()
        
        return results
    
    def test_concurrent_performance(self, num_threads: int = 10, queries_per_thread: int = 100) -> Dict[str, Any]:
        """测试并发性能"""
        print(f"🔄 测试并发性能 ({num_threads}个线程，每线程{queries_per_thread}次查询)...")
        
        def worker_thread(thread_id: int) -> Dict[str, Any]:
            """工作线程函数"""
            thread_results = {
                "thread_id": thread_id,
                "queries": 0,
                "errors": 0,
                "total_time": 0,
                "query_times": []
            }
            
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                start_time = time.time()
                
                for i in range(queries_per_thread):
                    query_start = time.time()
                    try:
                        cursor.execute(f"SELECT {thread_id} as thread_id, {i} as query_num, 'concurrent test' as message")
                        cursor.fetchall()
                        query_time = (time.time() - query_start) * 1000
                        thread_results["query_times"].append(query_time)
                        thread_results["queries"] += 1
                    except Exception as e:
                        thread_results["errors"] += 1
                        print(f"    线程{thread_id}查询{i}失败: {e}")
                
                thread_results["total_time"] = (time.time() - start_time) * 1000
                
                cursor.close()
                conn.close()
                
            except Exception as e:
                print(f"    线程{thread_id}连接失败: {e}")
                thread_results["errors"] += 1
            
            return thread_results
        
        # 启动并发测试
        overall_start = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            future_to_thread = {executor.submit(worker_thread, i): i for i in range(num_threads)}
            thread_results = []
            
            for future in concurrent.futures.as_completed(future_to_thread):
                thread_id = future_to_thread[future]
                try:
                    result = future.result()
                    thread_results.append(result)
                    print(f"  线程{thread_id}完成: {result['queries']}个查询, {result['errors']}个错误")
                except Exception as e:
                    print(f"  线程{thread_id}异常: {e}")
        
        overall_time = (time.time() - overall_start) * 1000
        
        # 汇总结果
        total_queries = sum(r["queries"] for r in thread_results)
        total_errors = sum(r["errors"] for r in thread_results)
        all_query_times = []
        for r in thread_results:
            all_query_times.extend(r["query_times"])
        
        result = {
            "num_threads": num_threads,
            "queries_per_thread": queries_per_thread,
            "total_queries": total_queries,
            "total_errors": total_errors,
            "success_rate": (total_queries / (total_queries + total_errors)) * 100 if (total_queries + total_errors) > 0 else 0,
            "overall_time_ms": overall_time,
            "overall_qps": total_queries / (overall_time / 1000) if overall_time > 0 else 0,
            "avg_query_time_ms": statistics.mean(all_query_times) if all_query_times else 0,
            "thread_results": thread_results
        }
        
        print(f"  ✅ 总查询数: {total_queries}")
        print(f"  ✅ 成功率: {result['success_rate']:.2f}%")
        print(f"  ✅ 整体QPS: {result['overall_qps']:.2f}")
        print(f"  ✅ 平均查询时间: {result['avg_query_time_ms']:.2f}ms")
        
        return result
    
    def test_data_operations_performance(self, num_records: int = 10000) -> Dict[str, Any]:
        """测试数据操作性能"""
        print(f"💾 测试数据操作性能 ({num_records}条记录)...")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        results = {}
        
        try:
            # 1. 创建表
            start_time = time.time()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS perf_test (
                    id INTEGER,
                    name VARCHAR(100),
                    value DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            create_time = (time.time() - start_time) * 1000
            results["table_creation_ms"] = create_time
            print(f"  ✅ 表创建时间: {create_time:.2f}ms")
            
            # 2. 批量插入
            start_time = time.time()
            batch_size = 1000
            for i in range(0, num_records, batch_size):
                batch_end = min(i + batch_size, num_records)
                values = []
                for j in range(i, batch_end):
                    values.append(f"({j}, 'name_{j}', {j * 1.5})")
                
                sql = f"INSERT INTO perf_test (id, name, value) VALUES {','.join(values)}"
                cursor.execute(sql)
                
                if (batch_end) % 5000 == 0:
                    print(f"    插入进度: {batch_end}/{num_records}")
            
            insert_time = (time.time() - start_time) * 1000
            results["bulk_insert_ms"] = insert_time
            results["insert_rate_per_second"] = num_records / (insert_time / 1000) if insert_time > 0 else 0
            print(f"  ✅ 批量插入时间: {insert_time:.2f}ms")
            print(f"  ✅ 插入速率: {results['insert_rate_per_second']:.2f} 记录/秒")
            
            # 3. 查询性能
            query_tests = [
                ("count_all", "SELECT COUNT(*) FROM perf_test"),
                ("simple_where", "SELECT * FROM perf_test WHERE id < 100"),
                ("aggregation", "SELECT AVG(value), MIN(value), MAX(value), SUM(value) FROM perf_test"),
                ("group_by", "SELECT MOD(id, 100) as group_id, COUNT(*), AVG(value) FROM perf_test GROUP BY MOD(id, 100) ORDER BY group_id LIMIT 10"),
                ("range_query", f"SELECT * FROM perf_test WHERE id BETWEEN {num_records//4} AND {num_records//2} ORDER BY id LIMIT 100")
            ]
            
            for test_name, test_sql in query_tests:
                start_time = time.time()
                cursor.execute(test_sql)
                rows = cursor.fetchall()
                query_time = (time.time() - start_time) * 1000
                
                results[f"{test_name}_ms"] = query_time
                results[f"{test_name}_rows"] = len(rows)
                print(f"  ✅ {test_name}: {query_time:.2f}ms ({len(rows)} 行)")
            
            # 4. 更新性能
            start_time = time.time()
            cursor.execute(f"UPDATE perf_test SET value = value * 1.1 WHERE id < {num_records // 10}")
            update_time = (time.time() - start_time) * 1000
            results["update_ms"] = update_time
            print(f"  ✅ 更新操作: {update_time:.2f}ms")
            
            # 5. 删除性能
            start_time = time.time()
            cursor.execute(f"DELETE FROM perf_test WHERE id >= {num_records - 1000}")
            delete_time = (time.time() - start_time) * 1000
            results["delete_ms"] = delete_time
            print(f"  ✅ 删除操作: {delete_time:.2f}ms")
            
            # 清理
            cursor.execute("DROP TABLE perf_test")
            
        except Exception as e:
            print(f"  ❌ 数据操作测试失败: {e}")
            # 尝试清理
            try:
                cursor.execute("DROP TABLE IF EXISTS perf_test")
            except:
                pass
        
        finally:
            cursor.close()
            conn.close()
        
        return results
    
    def test_memory_usage_performance(self, iterations: int = 100) -> Dict[str, Any]:
        """测试内存使用性能"""
        print(f"🧠 测试内存使用性能 ({iterations}次大查询)...")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        results = {}
        query_times = []
        
        try:
            # 创建测试数据
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_test AS 
                SELECT 
                    ROW_NUMBER() OVER() as id,
                    'data_' || CAST(ROW_NUMBER() OVER() as VARCHAR) as name,
                    RANDOM() as value,
                    CURRENT_TIMESTAMP as created_at
                FROM range(0, 10000)
            """)
            
            # 执行内存密集型查询
            complex_query = """
                SELECT 
                    t1.id,
                    t1.name,
                    t1.value,
                    t2.value as value2,
                    t1.value + t2.value as sum_value,
                    ROW_NUMBER() OVER (ORDER BY t1.value) as rn
                FROM memory_test t1
                JOIN memory_test t2 ON t1.id <= t2.id + 1000
                WHERE t1.value > 0.5
                ORDER BY t1.value
                LIMIT 1000
            """
            
            for i in range(iterations):
                start_time = time.time()
                cursor.execute(complex_query)
                rows = cursor.fetchall()
                query_time = (time.time() - start_time) * 1000
                query_times.append(query_time)
                
                if (i + 1) % 10 == 0:
                    print(f"  完成 {i + 1}/{iterations} 复杂查询")
            
            if query_times:
                results = {
                    "complex_queries": iterations,
                    "avg_complex_query_ms": statistics.mean(query_times),
                    "min_complex_query_ms": min(query_times),
                    "max_complex_query_ms": max(query_times),
                    "median_complex_query_ms": statistics.median(query_times)
                }
                
                print(f"  ✅ 平均复杂查询时间: {results['avg_complex_query_ms']:.2f}ms")
            
            # 清理
            cursor.execute("DROP TABLE memory_test")
            
        except Exception as e:
            print(f"  ❌ 内存测试失败: {e}")
            try:
                cursor.execute("DROP TABLE IF EXISTS memory_test")
            except:
                pass
        
        finally:
            cursor.close()
            conn.close()
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有性能测试"""
        print("🚀 开始DuckDB MySQL协议性能测试...")
        print("=" * 60)
        
        start_time = time.time()
        
        # 验证连接
        try:
            conn = self.get_connection()
            conn.close()
            print("✅ 连接验证成功")
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return {}
        
        all_results = {
            "test_info": {
                "host": self.host,
                "port": self.port,
                "user": self.user,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        }
        
        # 1. 连接性能测试
        print("\n" + "=" * 60)
        all_results["connection_performance"] = self.test_connection_performance(50)
        
        # 2. 查询性能测试
        print("\n" + "=" * 60)
        all_results["query_performance"] = self.test_query_performance(500)
        
        # 3. 并发性能测试
        print("\n" + "=" * 60)
        all_results["concurrent_performance"] = self.test_concurrent_performance(5, 50)
        
        # 4. 数据操作性能测试
        print("\n" + "=" * 60)
        all_results["data_operations_performance"] = self.test_data_operations_performance(5000)
        
        # 5. 内存使用性能测试
        print("\n" + "=" * 60)
        all_results["memory_performance"] = self.test_memory_usage_performance(50)
        
        total_time = time.time() - start_time
        all_results["total_test_time_seconds"] = total_time
        
        print("\n" + "=" * 60)
        print("📊 性能测试总结")
        print("=" * 60)
        print(f"总测试时间: {total_time:.2f}秒")
        
        # 打印关键指标摘要
        if "connection_performance" in all_results:
            cp = all_results["connection_performance"]
            if cp:
                print(f"连接性能: {cp.get('connections_per_second', 0):.2f} 连接/秒")
        
        if "query_performance" in all_results:
            qp = all_results["query_performance"]
            if qp and "simple_select" in qp:
                print(f"简单查询QPS: {qp['simple_select'].get('queries_per_second', 0):.2f}")
        
        if "concurrent_performance" in all_results:
            concur = all_results["concurrent_performance"]
            if concur:
                print(f"并发QPS: {concur.get('overall_qps', 0):.2f}")
                print(f"并发成功率: {concur.get('success_rate', 0):.2f}%")
        
        if "data_operations_performance" in all_results:
            data_perf = all_results["data_operations_performance"]
            if data_perf:
                print(f"数据插入速率: {data_perf.get('insert_rate_per_second', 0):.2f} 记录/秒")
        
        return all_results
    
    def save_results(self, results: Dict[str, Any], filename: str = None):
        """保存测试结果到JSON文件"""
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"performance_test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"📁 测试结果已保存到: {filename}")
        except Exception as e:
            print(f"❌ 保存结果失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="DuckDB MySQL协议性能测试")
    parser.add_argument("--host", default="localhost", help="服务器地址")
    parser.add_argument("--port", type=int, default=33660, help="服务器端口")
    parser.add_argument("--user", default="root", help="用户名")
    parser.add_argument("--password", default="", help="密码")
    parser.add_argument("--output", help="结果输出文件名")
    parser.add_argument("--test", choices=["connection", "query", "concurrent", "data", "memory", "all"], 
                       default="all", help="选择要运行的测试类型")
    
    args = parser.parse_args()
    
    tester = PerformanceTester(args.host, args.port, args.user, args.password)
    
    if args.test == "all":
        results = tester.run_all_tests()
    elif args.test == "connection":
        results = {"connection_performance": tester.test_connection_performance()}
    elif args.test == "query":
        results = {"query_performance": tester.test_query_performance()}
    elif args.test == "concurrent":
        results = {"concurrent_performance": tester.test_concurrent_performance()}
    elif args.test == "data":
        results = {"data_operations_performance": tester.test_data_operations_performance()}
    elif args.test == "memory":
        results = {"memory_performance": tester.test_memory_usage_performance()}
    
    if results and args.output:
        tester.save_results(results, args.output)

if __name__ == "__main__":
    main() 