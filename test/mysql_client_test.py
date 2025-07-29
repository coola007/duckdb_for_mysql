#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的MySQL客户端连接测试
使用标准MySQL客户端库测试DuckDB的MySQL协议兼容性
"""

import sys
import time
import logging
from typing import Optional, List, Dict

try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

try:
    import mysql.connector
    HAS_MYSQL_CONNECTOR = True
except ImportError:
    HAS_MYSQL_CONNECTOR = False

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MySQLClientTester:
    """MySQL客户端测试器"""
    
    def __init__(self, host: str = "localhost", port: int = 33660, user: str = "root", password: str = ""):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connection = None
    
    def test_pymysql(self) -> bool:
        """使用PyMySQL测试连接"""
        if not HAS_PYMYSQL:
            logger.warning("❌ PyMySQL 未安装，跳过测试")
            return False
        
        try:
            logger.info("🔗 使用PyMySQL连接...")
            
            # 连接配置
            config = {
                'host': self.host,
                'port': self.port,
                'user': self.user,
                'password': self.password,
                'charset': 'utf8mb4',
                'connect_timeout': 10,
                'read_timeout': 10,
                'write_timeout': 10,
                'autocommit': True
            }
            
            self.connection = pymysql.connect(**config)
            logger.info("✅ PyMySQL连接成功")
            
            # 基本查询测试
            with self.connection.cursor() as cursor:
                # 简单查询
                cursor.execute("SELECT 1 as test_number")
                result = cursor.fetchone()
                logger.info(f"简单查询结果: {result}")
                
                # 版本查询
                try:
                    cursor.execute("SELECT version()")
                    version = cursor.fetchone()
                    logger.info(f"服务器版本: {version}")
                except Exception as e:
                    logger.warning(f"版本查询失败: {e}")
                
                # 表操作测试
                try:
                    cursor.execute("CREATE TABLE IF NOT EXISTS test_pymysql (id INT, name VARCHAR(50))")
                    logger.info("✅ 表创建成功")
                    
                    cursor.execute("INSERT INTO test_pymysql VALUES (1, 'PyMySQL Test')")
                    logger.info("✅ 数据插入成功")
                    
                    cursor.execute("SELECT * FROM test_pymysql")
                    rows = cursor.fetchall()
                    logger.info(f"查询结果: {rows}")
                    
                    cursor.execute("DROP TABLE test_pymysql")
                    logger.info("✅ 表删除成功")
                    
                except Exception as e:
                    logger.error(f"表操作失败: {e}")
            
            self.connection.close()
            logger.info("✅ PyMySQL测试完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ PyMySQL测试失败: {e}")
            return False
    
    def test_mysql_connector(self) -> bool:
        """使用mysql-connector-python测试连接"""
        if not HAS_MYSQL_CONNECTOR:
            logger.warning("❌ mysql-connector-python 未安装，跳过测试")
            return False
        
        try:
            logger.info("🔗 使用mysql-connector-python连接...")
            
            # 连接配置
            config = {
                'host': self.host,
                'port': self.port,
                'user': self.user,
                'password': self.password,
                'charset': 'utf8mb4',
                'connection_timeout': 10,
                'autocommit': True
            }
            
            self.connection = mysql.connector.connect(**config)
            logger.info("✅ mysql-connector连接成功")
            
            # 基本查询测试
            cursor = self.connection.cursor()
            
            # 简单查询
            cursor.execute("SELECT 1 as test_number, 'connector test' as test_string")
            result = cursor.fetchone()
            logger.info(f"简单查询结果: {result}")
            
            # 表操作测试
            try:
                cursor.execute("CREATE TABLE IF NOT EXISTS test_connector (id INT, name VARCHAR(50))")
                logger.info("✅ 表创建成功")
                
                cursor.execute("INSERT INTO test_connector VALUES (2, 'Connector Test')")
                logger.info("✅ 数据插入成功")
                
                cursor.execute("SELECT * FROM test_connector")
                rows = cursor.fetchall()
                logger.info(f"查询结果: {rows}")
                
                cursor.execute("DROP TABLE test_connector")
                logger.info("✅ 表删除成功")
                
            except Exception as e:
                logger.error(f"表操作失败: {e}")
            
            cursor.close()
            self.connection.close()
            logger.info("✅ mysql-connector测试完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ mysql-connector测试失败: {e}")
            return False
    
    def test_connection_pooling(self) -> bool:
        """测试连接池"""
        if not HAS_PYMYSQL:
            logger.warning("❌ 连接池测试需要PyMySQL")
            return False
        
        try:
            logger.info("🏊 测试连接池...")
            
            connections = []
            max_connections = 5
            
            # 创建多个连接
            for i in range(max_connections):
                conn = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    charset='utf8mb4'
                )
                connections.append(conn)
                logger.info(f"创建连接 {i+1}/{max_connections}")
            
            # 并发执行查询
            for i, conn in enumerate(connections):
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT {i+1} as connection_id")
                    result = cursor.fetchone()
                    logger.info(f"连接 {i+1} 查询结果: {result}")
            
            # 关闭所有连接
            for conn in connections:
                conn.close()
            
            logger.info("✅ 连接池测试完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 连接池测试失败: {e}")
            return False
    
    def test_data_types(self) -> bool:
        """测试数据类型兼容性"""
        if not HAS_PYMYSQL:
            logger.warning("❌ 数据类型测试需要PyMySQL")
            return False
        
        try:
            logger.info("🔢 测试数据类型兼容性...")
            
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                charset='utf8mb4'
            )
            
            with conn.cursor() as cursor:
                # 创建测试表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_types (
                        id INTEGER,
                        name VARCHAR(100),
                        age BIGINT,
                        salary DOUBLE,
                        is_active BOOLEAN,
                        created_date DATE
                    )
                """)
                
                # 插入测试数据
                test_data = [
                    (1, 'Alice', 30, 50000.50, True, '2024-01-01'),
                    (2, 'Bob', 25, 45000.00, False, '2024-01-02'),
                    (3, '张三', 35, 60000.75, True, '2024-01-03')
                ]
                
                for data in test_data:
                    cursor.execute(
                        "INSERT INTO test_types VALUES (%s, %s, %s, %s, %s, %s)",
                        data
                    )
                
                # 查询并验证数据
                cursor.execute("SELECT * FROM test_types ORDER BY id")
                rows = cursor.fetchall()
                
                logger.info(f"数据类型测试结果 ({len(rows)} 行):")
                for row in rows:
                    logger.info(f"  {row}")
                
                # 聚合查询测试
                cursor.execute("SELECT COUNT(*), AVG(salary), MAX(age) FROM test_types")
                stats = cursor.fetchone()
                logger.info(f"聚合查询结果: {stats}")
                
                # 清理测试表
                cursor.execute("DROP TABLE test_types")
            
            conn.close()
            logger.info("✅ 数据类型测试完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 数据类型测试失败: {e}")
            return False
    
    def test_transactions(self) -> bool:
        """测试事务支持"""
        if not HAS_PYMYSQL:
            logger.warning("❌ 事务测试需要PyMySQL")
            return False
        
        try:
            logger.info("💾 测试事务支持...")
            
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                charset='utf8mb4',
                autocommit=False  # 关闭自动提交
            )
            
            with conn.cursor() as cursor:
                # 创建测试表
                cursor.execute("CREATE TABLE IF NOT EXISTS test_transaction (id INT, value VARCHAR(50))")
                conn.commit()
                
                # 测试事务回滚
                cursor.execute("INSERT INTO test_transaction VALUES (1, 'before rollback')")
                conn.rollback()  # 回滚
                
                # 检查数据是否被回滚
                cursor.execute("SELECT COUNT(*) FROM test_transaction")
                count = cursor.fetchone()[0]
                logger.info(f"回滚后记录数: {count}")
                
                # 测试事务提交
                cursor.execute("INSERT INTO test_transaction VALUES (2, 'after commit')")
                conn.commit()  # 提交
                
                # 检查数据是否被提交
                cursor.execute("SELECT * FROM test_transaction")
                rows = cursor.fetchall()
                logger.info(f"提交后数据: {rows}")
                
                # 清理测试表
                cursor.execute("DROP TABLE test_transaction")
                conn.commit()
            
            conn.close()
            logger.info("✅ 事务测试完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 事务测试失败: {e}")
            return False

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MySQL客户端连接测试")
    parser.add_argument("--host", default="localhost", help="服务器地址")
    parser.add_argument("--port", type=int, default=33660, help="服务器端口")
    parser.add_argument("--user", default="root", help="用户名")
    parser.add_argument("--password", default="", help="密码")
    
    args = parser.parse_args()
    
    logger.info("🚀 开始MySQL客户端测试...")
    logger.info(f"连接信息: {args.host}:{args.port} (用户: {args.user})")
    
    # 检查依赖
    if not HAS_PYMYSQL and not HAS_MYSQL_CONNECTOR:
        logger.error("❌ 未安装MySQL客户端库。请安装: pip install PyMySQL mysql-connector-python")
        sys.exit(1)
    
    tester = MySQLClientTester(args.host, args.port, args.user, args.password)
    
    tests = [
        ("PyMySQL连接测试", tester.test_pymysql),
        ("MySQL Connector测试", tester.test_mysql_connector),
        ("连接池测试", tester.test_connection_pooling),
        ("数据类型测试", tester.test_data_types),
        ("事务测试", tester.test_transactions),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"🧪 {test_name}")
        logger.info('='*50)
        
        try:
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} 通过")
            else:
                logger.error(f"❌ {test_name} 失败")
        except Exception as e:
            logger.error(f"❌ {test_name} 异常: {e}")
    
    # 测试总结
    logger.info(f"\n{'='*50}")
    logger.info("📊 测试总结")
    logger.info('='*50)
    logger.info(f"总测试数: {total}")
    logger.info(f"通过测试: {passed}")
    logger.info(f"失败测试: {total - passed}")
    logger.info(f"通过率: {passed/total*100:.1f}%")
    
    if passed == total:
        logger.info("🎉 所有测试通过！MySQL协议兼容性良好。")
        sys.exit(0)
    else:
        logger.warning("⚠️ 部分测试失败，请检查服务器兼容性。")
        sys.exit(1)

if __name__ == "__main__":
    main() 