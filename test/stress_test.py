#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB MySQL协议压力测试脚本
测试系统在高负载下的稳定性和性能
"""

import time
import threading
import sys
import argparse
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue

try:
    import pymysql
except ImportError:
    print("❌ PyMySQL未安装，请执行: pip install PyMySQL")
    sys.exit(1)

class StressTester:
    """压力测试器"""
    
    def __init__(self, host="localhost", port=33660, user="root", password=""):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.running = True
        self.stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_connections": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "start_time": None,
            "errors": []
        }
        self.lock = threading.Lock()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """处理中断信号"""
        print(f"\n收到信号 {signum}，正在停止测试...")
        self.running = False
    
    def get_connection(self):
        """获取数据库连接"""
        with self.lock:
            self.stats["total_connections"] += 1
            
        try:
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                charset='utf8mb4',
                autocommit=True,
                connect_timeout=5,
                read_timeout=10,
                write_timeout=10
            )
            with self.lock:
                self.stats["successful_connections"] += 1
            return conn
        except Exception as e:
            with self.lock:
                self.stats["failed_connections"] += 1
                self.stats["errors"].append(f"连接错误: {str(e)}")
            raise
    
    def execute_query(self, cursor, query):
        """执行查询"""
        with self.lock:
            self.stats["total_queries"] += 1
            
        try:
            cursor.execute(query)
            cursor.fetchall()
            with self.lock:
                self.stats["successful_queries"] += 1
            return True
        except Exception as e:
            with self.lock:
                self.stats["failed_queries"] += 1
                self.stats["errors"].append(f"查询错误: {str(e)[:100]}")
            return False
    
    def worker_thread(self, thread_id, duration_seconds, queries_per_second):
        """工作线程"""
        query_interval = 1.0 / queries_per_second if queries_per_second > 0 else 0
        end_time = time.time() + duration_seconds
        
        # 测试查询
        queries = [
            "SELECT 1",
            "SELECT CURRENT_TIMESTAMP",
            f"SELECT {thread_id} as thread_id, 'stress test' as message",
            "SELECT COUNT(*) FROM (SELECT ROW_NUMBER() OVER() as id FROM range(0, 100)) t",
            "SELECT AVG(value) FROM (SELECT RANDOM() as value FROM range(0, 50)) t",
        ]
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query_count = 0
            while self.running and time.time() < end_time:
                query = queries[query_count % len(queries)]
                
                if self.execute_query(cursor, query):
                    query_count += 1
                
                if query_interval > 0:
                    time.sleep(query_interval)
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            with self.lock:
                self.stats["errors"].append(f"线程 {thread_id} 失败: {str(e)}")
    
    def monitor_thread(self, duration_seconds):
        """监控线程，定期输出统计信息"""
        last_queries = 0
        last_time = time.time()
        
        while self.running and time.time() < self.stats["start_time"] + duration_seconds:
            time.sleep(5)  # 每5秒输出一次统计
            
            current_time = time.time()
            current_queries = self.stats["successful_queries"]
            
            # 计算QPS
            time_diff = current_time - last_time
            query_diff = current_queries - last_queries
            current_qps = query_diff / time_diff if time_diff > 0 else 0
            
            elapsed = current_time - self.stats["start_time"]
            total_qps = self.stats["successful_queries"] / elapsed if elapsed > 0 else 0
            
            print(f"⏱️  运行时间: {elapsed:.1f}s | "
                  f"总查询: {self.stats['total_queries']} | "
                  f"成功: {self.stats['successful_queries']} | "
                  f"失败: {self.stats['failed_queries']} | "
                  f"当前QPS: {current_qps:.1f} | "
                  f"平均QPS: {total_qps:.1f}")
            
            last_queries = current_queries
            last_time = current_time
    
    def run_stress_test(self, num_threads=10, duration_seconds=60, queries_per_second=10):
        """运行压力测试"""
        print(f"🚀 开始压力测试")
        print(f"参数: {num_threads}个线程, 持续{duration_seconds}秒, 目标{queries_per_second}QPS/线程")
        print("=" * 70)
        
        # 初始化统计
        self.stats["start_time"] = time.time()
        self.running = True
        
        # 验证连接
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
            print(f"✅ 连接验证成功，DuckDB版本: {version[0]}")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ 连接验证失败: {e}")
            return
        
        # 启动监控线程
        monitor = threading.Thread(target=self.monitor_thread, args=(duration_seconds,))
        monitor.daemon = True
        monitor.start()
        
        # 启动工作线程
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            
            for i in range(num_threads):
                future = executor.submit(self.worker_thread, i, duration_seconds, queries_per_second)
                futures.append(future)
            
            # 等待所有线程完成
            try:
                for future in as_completed(futures, timeout=duration_seconds + 10):
                    future.result()
            except Exception as e:
                print(f"执行异常: {e}")
                self.running = False
        
        # 等待监控线程结束
        self.running = False
        monitor.join(timeout=5)
        
        # 输出最终统计
        self.print_final_stats()
    
    def run_connection_stress_test(self, num_connections=50, duration_seconds=30):
        """运行连接压力测试"""
        print(f"🔗 开始连接压力测试")
        print(f"参数: {num_connections}个并发连接, 持续{duration_seconds}秒")
        print("=" * 70)
        
        self.stats["start_time"] = time.time()
        self.running = True
        connections = []
        
        def connection_worker(conn_id):
            """连接工作函数"""
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                end_time = time.time() + duration_seconds
                while self.running and time.time() < end_time:
                    self.execute_query(cursor, f"SELECT {conn_id} as connection_id, CURRENT_TIMESTAMP")
                    time.sleep(0.1)  # 100ms间隔
                
                cursor.close()
                conn.close()
                
            except Exception as e:
                with self.lock:
                    self.stats["errors"].append(f"连接 {conn_id} 失败: {str(e)}")
        
        # 启动监控
        monitor = threading.Thread(target=self.monitor_thread, args=(duration_seconds,))
        monitor.daemon = True
        monitor.start()
        
        # 启动连接线程
        with ThreadPoolExecutor(max_workers=num_connections) as executor:
            futures = [executor.submit(connection_worker, i) for i in range(num_connections)]
            
            try:
                for future in as_completed(futures, timeout=duration_seconds + 10):
                    future.result()
            except Exception as e:
                print(f"连接测试异常: {e}")
        
        self.running = False
        monitor.join(timeout=5)
        self.print_final_stats()
    
    def run_data_stress_test(self, num_threads=5, records_per_thread=1000):
        """运行数据操作压力测试"""
        print(f"💾 开始数据操作压力测试")
        print(f"参数: {num_threads}个线程, 每线程{records_per_thread}条记录")
        print("=" * 70)
        
        self.stats["start_time"] = time.time()
        self.running = True
        
        def data_worker(thread_id):
            """数据操作工作函数"""
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # 创建线程专用表
                table_name = f"stress_test_{thread_id}"
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER,
                        thread_id INTEGER,
                        name VARCHAR(100),
                        value DOUBLE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 批量插入
                batch_size = 100
                for i in range(0, records_per_thread, batch_size):
                    if not self.running:
                        break
                        
                    batch_end = min(i + batch_size, records_per_thread)
                    values = []
                    for j in range(i, batch_end):
                        values.append(f"({j}, {thread_id}, 'name_{j}', {j * 1.5})")
                    
                    sql = f"INSERT INTO {table_name} (id, thread_id, name, value) VALUES {','.join(values)}"
                    self.execute_query(cursor, sql)
                
                # 执行一些查询操作
                queries = [
                    f"SELECT COUNT(*) FROM {table_name}",
                    f"SELECT AVG(value), MIN(value), MAX(value) FROM {table_name}",
                    f"SELECT * FROM {table_name} WHERE id < 10 ORDER BY id",
                    f"SELECT thread_id, COUNT(*) FROM {table_name} GROUP BY thread_id",
                ]
                
                for query in queries:
                    if self.running:
                        self.execute_query(cursor, query)
                
                # 清理表
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                
                cursor.close()
                conn.close()
                
            except Exception as e:
                with self.lock:
                    self.stats["errors"].append(f"数据线程 {thread_id} 失败: {str(e)}")
        
        # 启动数据操作线程
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(data_worker, i) for i in range(num_threads)]
            
            try:
                for future in as_completed(futures):
                    future.result()
            except Exception as e:
                print(f"数据测试异常: {e}")
        
        self.running = False
        self.print_final_stats()
    
    def print_final_stats(self):
        """输出最终统计信息"""
        total_time = time.time() - self.stats["start_time"]
        
        print("\n" + "=" * 70)
        print("📊 压力测试最终统计")
        print("=" * 70)
        print(f"总运行时间: {total_time:.2f}秒")
        print(f"总连接数: {self.stats['total_connections']}")
        print(f"成功连接: {self.stats['successful_connections']}")
        print(f"失败连接: {self.stats['failed_connections']}")
        print(f"连接成功率: {(self.stats['successful_connections'] / max(1, self.stats['total_connections'])) * 100:.2f}%")
        print(f"总查询数: {self.stats['total_queries']}")
        print(f"成功查询: {self.stats['successful_queries']}")
        print(f"失败查询: {self.stats['failed_queries']}")
        print(f"查询成功率: {(self.stats['successful_queries'] / max(1, self.stats['total_queries'])) * 100:.2f}%")
        print(f"平均QPS: {self.stats['successful_queries'] / total_time:.2f}")
        
        if self.stats['errors']:
            print(f"\n❌ 错误数量: {len(self.stats['errors'])}")
            # 显示前5个错误
            for i, error in enumerate(self.stats['errors'][:5]):
                print(f"  {i+1}. {error}")
            if len(self.stats['errors']) > 5:
                print(f"  ... 还有 {len(self.stats['errors']) - 5} 个错误")
        else:
            print("\n✅ 无错误发生")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="DuckDB MySQL协议压力测试")
    parser.add_argument("--host", default="localhost", help="服务器地址")
    parser.add_argument("--port", type=int, default=33660, help="服务器端口")
    parser.add_argument("--user", default="root", help="用户名")
    parser.add_argument("--password", default="", help="密码")
    parser.add_argument("--test", choices=["query", "connection", "data"], default="query", help="测试类型")
    parser.add_argument("--threads", type=int, default=10, help="线程数")
    parser.add_argument("--duration", type=int, default=60, help="测试持续时间(秒)")
    parser.add_argument("--qps", type=int, default=10, help="每线程目标QPS")
    parser.add_argument("--connections", type=int, default=50, help="连接数(连接测试)")
    parser.add_argument("--records", type=int, default=1000, help="每线程记录数(数据测试)")
    
    args = parser.parse_args()
    
    tester = StressTester(args.host, args.port, args.user, args.password)
    
    try:
        if args.test == "query":
            tester.run_stress_test(args.threads, args.duration, args.qps)
        elif args.test == "connection":
            tester.run_connection_stress_test(args.connections, args.duration)
        elif args.test == "data":
            tester.run_data_stress_test(args.threads, args.records)
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"测试异常: {e}")

if __name__ == "__main__":
    main() 