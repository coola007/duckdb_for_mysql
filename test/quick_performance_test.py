#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB MySQL协议快速性能测试脚本
适用于快速检查性能基准
"""

import time
import threading
import sys

try:
    import pymysql
except ImportError:
    print("❌ PyMySQL未安装，请执行: pip install PyMySQL")
    sys.exit(1)

def get_connection(host="localhost", port=33660, user="root", password=""):
    """获取数据库连接"""
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        charset='utf8mb4',
        autocommit=True
    )

def test_connection_speed(iterations=20):
    """测试连接速度"""
    print(f"🔗 测试连接速度 ({iterations}次)...")
    
    times = []
    for i in range(iterations):
        start = time.time()
        try:
            conn = get_connection()
            conn.close()
            times.append(time.time() - start)
        except Exception as e:
            print(f"  连接失败: {e}")
            return None
    
    avg_time = sum(times) * 1000 / len(times)  # 转换为毫秒
    print(f"  ✅ 平均连接时间: {avg_time:.2f}ms")
    print(f"  ✅ 连接速率: {1000/avg_time:.2f} 连接/秒")
    return avg_time

def test_query_speed(iterations=100):
    """测试查询速度"""
    print(f"📝 测试查询速度 ({iterations}次)...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 简单查询测试
    start = time.time()
    for i in range(iterations):
        cursor.execute("SELECT 1")
        cursor.fetchall()
    
    total_time = time.time() - start
    avg_time = total_time * 1000 / iterations  # 转换为毫秒
    qps = iterations / total_time
    
    print(f"  ✅ 平均查询时间: {avg_time:.2f}ms")
    print(f"  ✅ QPS: {qps:.2f}")
    
    # 复杂查询测试
    complex_query = "SELECT COUNT(*), AVG(value), SUM(value) FROM (SELECT ROW_NUMBER() OVER() as id, RANDOM() as value FROM range(0, 1000)) t"
    start = time.time()
    for i in range(10):
        cursor.execute(complex_query)
        cursor.fetchall()
    
    complex_time = (time.time() - start) * 1000 / 10
    print(f"  ✅ 复杂查询平均时间: {complex_time:.2f}ms")
    
    cursor.close()
    conn.close()
    
    return qps

def test_concurrent_performance(num_threads=5, queries_per_thread=20):
    """测试并发性能"""
    print(f"🔄 测试并发性能 ({num_threads}线程 x {queries_per_thread}查询)...")
    
    results = []
    threads = []
    
    def worker():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            start = time.time()
            for i in range(queries_per_thread):
                cursor.execute(f"SELECT {threading.current_thread().ident} as thread_id, {i} as query_num")
                cursor.fetchall()
            
            duration = time.time() - start
            results.append(duration)
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"  线程失败: {e}")
    
    # 启动所有线程
    start_time = time.time()
    for i in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    total_time = time.time() - start_time
    total_queries = len(results) * queries_per_thread
    concurrent_qps = total_queries / total_time if total_time > 0 else 0
    
    print(f"  ✅ 总查询数: {total_queries}")
    print(f"  ✅ 总耗时: {total_time:.2f}秒")
    print(f"  ✅ 并发QPS: {concurrent_qps:.2f}")
    print(f"  ✅ 成功线程: {len(results)}/{num_threads}")
    
    return concurrent_qps

def test_data_insertion(num_records=1000):
    """测试数据插入性能"""
    print(f"💾 测试数据插入性能 ({num_records}条记录)...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 创建测试表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quick_test (
                id INTEGER,
                name VARCHAR(50),
                value DOUBLE
            )
        """)
        
        # 批量插入
        start = time.time()
        batch_size = 100
        
        for i in range(0, num_records, batch_size):
            batch_end = min(i + batch_size, num_records)
            values = []
            for j in range(i, batch_end):
                values.append(f"({j}, 'name_{j}', {j * 1.5})")
            
            sql = f"INSERT INTO quick_test (id, name, value) VALUES {','.join(values)}"
            cursor.execute(sql)
        
        insert_time = time.time() - start
        insert_rate = num_records / insert_time
        
        print(f"  ✅ 插入时间: {insert_time:.2f}秒")
        print(f"  ✅ 插入速率: {insert_rate:.2f} 记录/秒")
        
        # 查询测试
        start = time.time()
        cursor.execute("SELECT COUNT(*), AVG(value), MAX(value) FROM quick_test")
        result = cursor.fetchall()
        query_time = (time.time() - start) * 1000
        
        print(f"  ✅ 聚合查询时间: {query_time:.2f}ms")
        print(f"  ✅ 查询结果: {result[0]}")
        
        # 清理
        cursor.execute("DROP TABLE quick_test")
        
    except Exception as e:
        print(f"  ❌ 插入测试失败: {e}")
        try:
            cursor.execute("DROP TABLE IF EXISTS quick_test")
        except:
            pass
    
    finally:
        cursor.close()
        conn.close()

def main():
    """主函数"""
    print("🚀 DuckDB MySQL协议快速性能测试")
    print("=" * 50)
    
    # 验证连接
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        print(f"✅ 连接成功，DuckDB版本: {version[0]}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return
    
    start_time = time.time()
    
    # 运行各项测试
    print("\n" + "=" * 50)
    test_connection_speed(20)
    
    print("\n" + "=" * 50)
    qps = test_query_speed(100)
    
    print("\n" + "=" * 50)
    concurrent_qps = test_concurrent_performance(5, 20)
    
    print("\n" + "=" * 50)
    test_data_insertion(1000)
    
    # 总结
    total_time = time.time() - start_time
    print("\n" + "=" * 50)
    print("📊 快速性能测试总结")
    print("=" * 50)
    print(f"总测试时间: {total_time:.2f}秒")
    if qps:
        print(f"单线程QPS: {qps:.2f}")
    if concurrent_qps:
        print(f"并发QPS: {concurrent_qps:.2f}")
    
    print("\n🎉 快速性能测试完成！")

if __name__ == "__main__":
    main() 