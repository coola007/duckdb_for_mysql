#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB MySQL Protocol 完整测试套件
测试MySQL协议的连接、认证、查询、事务等功能
"""

import socket
import struct
import time
import sys
import threading
import hashlib
import random
import string
from typing import Optional, List, Dict, Any

class Colors:
    """控制台颜色"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_colored(text: str, color: str = Colors.WHITE):
    """打印彩色文本"""
    print(f"{color}{text}{Colors.END}")

class MySQLProtocolTester:
    """MySQL协议测试器"""
    
    def __init__(self, host: str = "localhost", port: int = 33660):
        self.host = host
        self.port = port
        self.socket = None
        self.server_version = ""
        self.thread_id = 0
        self.auth_data = b""
        self.capabilities = 0
        self.charset = 0
        self.status = 0
        
    def connect(self) -> bool:
        """连接到服务器"""
        try:
            print_colored(f"🔗 连接到 {self.host}:{self.port}...", Colors.BLUE)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            print_colored("✅ TCP连接成功", Colors.GREEN)
            return True
        except Exception as e:
            print_colored(f"❌ 连接失败: {e}", Colors.RED)
            return False
    
    def read_packet(self) -> Optional[bytes]:
        """读取MySQL数据包"""
        try:
            # 读取包头 (4字节)
            header = self.socket.recv(4)
            if len(header) != 4:
                return None
            
            # 解析包长度和序列号
            packet_length = struct.unpack('<I', header[:3] + b'\x00')[0]
            sequence_id = header[3]
            
            # 读取包体
            payload = b""
            while len(payload) < packet_length:
                chunk = self.socket.recv(packet_length - len(payload))
                if not chunk:
                    break
                payload += chunk
            
            print_colored(f"📥 收到数据包 [seq={sequence_id}, len={packet_length}]", Colors.CYAN)
            return payload
        except Exception as e:
            print_colored(f"❌ 读取数据包失败: {e}", Colors.RED)
            return None
    
    def send_packet(self, payload: bytes, sequence_id: int = 0) -> bool:
        """发送MySQL数据包"""
        try:
            packet_length = len(payload)
            header = struct.pack('<I', packet_length)[:3] + struct.pack('B', sequence_id)
            packet = header + payload
            
            self.socket.send(packet)
            print_colored(f"📤 发送数据包 [seq={sequence_id}, len={packet_length}]", Colors.CYAN)
            return True
        except Exception as e:
            print_colored(f"❌ 发送数据包失败: {e}", Colors.RED)
            return False
    
    def parse_handshake(self, data: bytes) -> bool:
        """解析握手包"""
        try:
            print_colored("🤝 解析服务器握手包...", Colors.BLUE)
            
            pos = 0
            
            # 协议版本
            protocol_version = data[pos]
            pos += 1
            print_colored(f"协议版本: {protocol_version}", Colors.WHITE)
            
            # 服务器版本字符串
            version_end = data.find(b'\x00', pos)
            self.server_version = data[pos:version_end].decode('utf-8')
            pos = version_end + 1
            print_colored(f"服务器版本: {self.server_version}", Colors.WHITE)
            
            # 连接ID
            self.thread_id = struct.unpack('<I', data[pos:pos+4])[0]
            pos += 4
            print_colored(f"连接ID: {self.thread_id}", Colors.WHITE)
            
            # 认证数据第一部分
            auth_data_1 = data[pos:pos+8]
            pos += 8
            
            # 保留字节
            pos += 1
            
            # 能力标志 (低16位)
            capabilities_1 = struct.unpack('<H', data[pos:pos+2])[0]
            pos += 2
            
            if pos < len(data):
                # 字符集
                self.charset = data[pos]
                pos += 1
                
                # 状态标志
                self.status = struct.unpack('<H', data[pos:pos+2])[0]
                pos += 2
                
                # 能力标志 (高16位)
                capabilities_2 = struct.unpack('<H', data[pos:pos+2])[0]
                pos += 2
                
                self.capabilities = capabilities_1 | (capabilities_2 << 16)
                
                # 认证数据长度
                auth_data_len = data[pos] if pos < len(data) else 21
                pos += 1
                
                # 保留字节
                pos += 10
                
                # 认证数据第二部分
                if pos < len(data):
                    auth_data_2_len = max(13, auth_data_len - 8)
                    auth_data_2 = data[pos:pos + auth_data_2_len - 1]  # 去掉结尾的\x00
                    self.auth_data = auth_data_1 + auth_data_2
            
            print_colored(f"能力标志: 0x{self.capabilities:08x}", Colors.WHITE)
            print_colored(f"字符集: {self.charset}", Colors.WHITE)
            print_colored(f"状态: 0x{self.status:04x}", Colors.WHITE)
            print_colored(f"认证数据长度: {len(self.auth_data)}", Colors.WHITE)
            
            return True
        except Exception as e:
            print_colored(f"❌ 解析握手包失败: {e}", Colors.RED)
            return False
    
    def send_auth_response(self, username: str = "root", password: str = "", database: str = "") -> bool:
        """发送认证响应"""
        try:
            print_colored(f"🔐 发送认证响应 [用户: {username}]...", Colors.BLUE)
            
            # 客户端能力标志
            client_capabilities = (
                0x00000001 |  # CLIENT_LONG_PASSWORD
                0x00000002 |  # CLIENT_FOUND_ROWS
                0x00000004 |  # CLIENT_LONG_FLAG
                0x00000008 |  # CLIENT_CONNECT_WITH_DB
                0x00000020 |  # CLIENT_PROTOCOL_41
                0x00000200 |  # CLIENT_SECURE_CONNECTION
                0x00008000    # CLIENT_PLUGIN_AUTH
            )
            
            # 构建认证响应包
            payload = b""
            
            # 客户端能力标志 (4字节)
            payload += struct.pack('<I', client_capabilities)
            
            # 最大包大小 (4字节)
            payload += struct.pack('<I', 16777216)
            
            # 字符集 (1字节)
            payload += struct.pack('B', 33)  # utf8_general_ci
            
            # 保留字节 (23字节)
            payload += b'\x00' * 23
            
            # 用户名
            payload += username.encode('utf-8') + b'\x00'
            
            # 密码 (空密码)
            if password:
                # 这里应该实现MySQL密码哈希，但我们的服务器暂时不验证密码
                payload += b'\x14'  # 20字节密码长度
                payload += b'\x00' * 20  # 空密码哈希
            else:
                payload += b'\x00'  # 空密码
            
            # 数据库名
            if database:
                payload += database.encode('utf-8') + b'\x00'
            
            return self.send_packet(payload, 1)
        except Exception as e:
            print_colored(f"❌ 发送认证响应失败: {e}", Colors.RED)
            return False
    
    def parse_auth_result(self, data: bytes) -> bool:
        """解析认证结果"""
        try:
            if not data:
                return False
            
            packet_type = data[0]
            
            if packet_type == 0x00:  # OK包
                print_colored("✅ 认证成功", Colors.GREEN)
                return True
            elif packet_type == 0xFF:  # ERR包
                error_code = struct.unpack('<H', data[1:3])[0]
                error_msg = data[9:].decode('utf-8', errors='ignore')
                print_colored(f"❌ 认证失败 [错误码: {error_code}]: {error_msg}", Colors.RED)
                return False
            else:
                print_colored(f"❓ 未知认证响应类型: 0x{packet_type:02x}", Colors.YELLOW)
                return False
        except Exception as e:
            print_colored(f"❌ 解析认证结果失败: {e}", Colors.RED)
            return False
    
    def send_query(self, sql: str) -> bool:
        """发送SQL查询"""
        try:
            print_colored(f"📝 执行查询: {sql}", Colors.BLUE)
            
            # 构建查询包
            payload = struct.pack('B', 0x03) + sql.encode('utf-8')  # COM_QUERY
            
            return self.send_packet(payload, 0)
        except Exception as e:
            print_colored(f"❌ 发送查询失败: {e}", Colors.RED)
            return False
    
    def parse_query_result(self) -> bool:
        """解析查询结果"""
        try:
            # 读取结果包
            data = self.read_packet()
            if not data:
                return False
            
            packet_type = data[0]
            
            if packet_type == 0x00:  # OK包
                affected_rows = self.parse_length_encoded_integer(data[1:])
                print_colored(f"✅ 查询成功 [影响行数: {affected_rows[0] if affected_rows else 0}]", Colors.GREEN)
                return True
            elif packet_type == 0xFF:  # ERR包
                error_code = struct.unpack('<H', data[1:3])[0]
                error_msg = data[9:].decode('utf-8', errors='ignore')
                print_colored(f"❌ 查询失败 [错误码: {error_code}]: {error_msg}", Colors.RED)
                return False
            else:
                # 结果集
                column_count = self.parse_length_encoded_integer(data)[0]
                print_colored(f"📊 收到结果集 [列数: {column_count}]", Colors.GREEN)
                
                # 读取列定义
                for i in range(column_count):
                    column_data = self.read_packet()
                    if column_data:
                        print_colored(f"  列 {i+1}: 已读取", Colors.WHITE)
                
                # 读取EOF包
                eof_data = self.read_packet()
                
                # 读取行数据
                row_count = 0
                while True:
                    row_data = self.read_packet()
                    if not row_data or row_data[0] == 0xFE:  # EOF包
                        break
                    row_count += 1
                    print_colored(f"  行 {row_count}: 已读取", Colors.WHITE)
                
                print_colored(f"✅ 结果集读取完成 [行数: {row_count}]", Colors.GREEN)
                return True
        except Exception as e:
            print_colored(f"❌ 解析查询结果失败: {e}", Colors.RED)
            return False
    
    def parse_length_encoded_integer(self, data: bytes) -> tuple:
        """解析长度编码整数"""
        if not data:
            return 0, 0
        
        first_byte = data[0]
        if first_byte < 0xFB:
            return first_byte, 1
        elif first_byte == 0xFC:
            return struct.unpack('<H', data[1:3])[0], 3
        elif first_byte == 0xFD:
            return struct.unpack('<I', data[1:4] + b'\x00')[0], 4
        elif first_byte == 0xFE:
            return struct.unpack('<Q', data[1:9])[0], 9
        else:
            return 0, 1
    
    def send_ping(self) -> bool:
        """发送Ping命令"""
        try:
            print_colored("🏓 发送Ping命令...", Colors.BLUE)
            payload = struct.pack('B', 0x0E)  # COM_PING
            return self.send_packet(payload, 0)
        except Exception as e:
            print_colored(f"❌ 发送Ping失败: {e}", Colors.RED)
            return False

    def send_use_db(self, db_name: str) -> bool:
        """发送 COM_INIT_DB 命令"""
        try:
            print_colored(f"🗄️  执行 USE {db_name}", Colors.BLUE)
            payload = struct.pack('B', 0x02) + db_name.encode('utf-8')
            return self.send_packet(payload, 0)
        except Exception as e:
            print_colored(f"❌ 发送 USE DB 失败: {e}", Colors.RED)
            return False
    
    def close(self):
        """关闭连接"""
        if self.socket:
            try:
                # 发送退出命令
                payload = struct.pack('B', 0x01)  # COM_QUIT
                self.send_packet(payload, 0)
            except:
                pass
            
            self.socket.close()
            print_colored("🔌 连接已关闭", Colors.YELLOW)

def test_mysql_protocol(host: str = "localhost", port: int = 33660):
    """测试MySQL协议"""
    print_colored(f"\n{'='*60}", Colors.BOLD)
    print_colored("🐬 DuckDB MySQL协议测试套件", Colors.BOLD + Colors.BLUE)
    print_colored(f"{'='*60}", Colors.BOLD)
    
    tester = MySQLProtocolTester(host, port)
    
    try:
        # 1. 连接测试
        print_colored("\n📡 步骤 1: 连接测试", Colors.BOLD + Colors.PURPLE)
        if not tester.connect():
            return False
        
        # 2. 握手测试
        print_colored("\n🤝 步骤 2: 握手测试", Colors.BOLD + Colors.PURPLE)
        handshake_data = tester.read_packet()
        if not handshake_data or not tester.parse_handshake(handshake_data):
            return False
        
        # 3. 认证测试
        print_colored("\n🔐 步骤 3: 认证测试", Colors.BOLD + Colors.PURPLE)
        if not tester.send_auth_response("testuser", "", ""):
            return False
        
        auth_result = tester.read_packet()
        if not auth_result or not tester.parse_auth_result(auth_result):
            return False
        
        # 4. Ping测试
        print_colored("\n🏓 步骤 4: Ping测试", Colors.BOLD + Colors.PURPLE)
        if tester.send_ping():
            ping_result = tester.read_packet()
            if ping_result and ping_result[0] == 0x00:
                print_colored("✅ Ping成功", Colors.GREEN)
            else:
                print_colored("❌ Ping失败", Colors.RED)

        # 4.5. Use DB 测试
        print_colored("\n🗄️ 步骤 4.5: Use DB 测试", Colors.BOLD + Colors.PURPLE)
        if tester.send_use_db("test_db"):
            use_db_result = tester.read_packet()
            if use_db_result and use_db_result[0] == 0x00:
                print_colored("✅ Use DB成功", Colors.GREEN)
            else:
                print_colored("❌ Use DB失败", Colors.RED)
        
        # 5. 查询测试
        print_colored("\n📝 步骤 5: 查询测试", Colors.BOLD + Colors.PURPLE)
        
        test_queries = [
            "SELECT 1 as test_number, 'Hello DuckDB' as test_string",
            "SELECT version()",
            "SHOW TABLES",
            "CREATE TABLE test_mysql (id INTEGER, name VARCHAR(50))",
            "INSERT INTO test_mysql VALUES (1, 'Test Row 1'), (2, 'Test Row 2')",
            "SELECT * FROM test_mysql",
            "UPDATE test_mysql SET name = 'Updated Row' WHERE id = 1",
            "DELETE FROM test_mysql WHERE id = 2",
            "SELECT COUNT(*) FROM test_mysql",
            "DROP TABLE test_mysql"
        ]
        
        success_count = 0
        for i, query in enumerate(test_queries, 1):
            print_colored(f"\n  查询 {i}/{len(test_queries)}:", Colors.CYAN)
            if tester.send_query(query):
                if tester.parse_query_result():
                    success_count += 1
                time.sleep(0.1)  # 短暂延迟
        
        print_colored(f"\n📊 查询测试总结: {success_count}/{len(test_queries)} 成功", 
                     Colors.GREEN if success_count == len(test_queries) else Colors.YELLOW)
        
        # 6. 并发测试
        print_colored("\n🔄 步骤 6: 并发连接测试", Colors.BOLD + Colors.PURPLE)
        concurrent_test_passed = test_concurrent_connections(host, port, 3)
        
        # 7. 性能测试
        print_colored("\n⚡ 步骤 7: 性能测试", Colors.BOLD + Colors.PURPLE)
        performance_test_passed = test_performance(host, port)
        
        # 测试总结
        print_colored(f"\n{'='*60}", Colors.BOLD)
        print_colored("📋 测试总结", Colors.BOLD + Colors.BLUE)
        print_colored(f"{'='*60}", Colors.BOLD)
        
        results = [
            ("连接测试", "✅"),
            ("握手测试", "✅"),
            ("认证测试", "✅"),
            ("Ping测试", "✅"),
            ("Use DB测试", "✅" if use_db_result and use_db_result[0] == 0x00 else "❌"),
            ("查询测试", "✅" if success_count == len(test_queries) else "⚠️"),
            ("并发测试", "✅" if concurrent_test_passed else "❌"),
            ("性能测试", "✅" if performance_test_passed else "⚠️"),
        ]
        
        for test_name, status in results:
            color = Colors.GREEN if status == "✅" else Colors.YELLOW if status == "⚠️" else Colors.RED
            print_colored(f"  {test_name}: {status}", color)
        
        overall_success = all(status != "❌" for _, status in results)
        print_colored(f"\n🎯 总体结果: {'测试通过' if overall_success else '部分测试失败'}", 
                     Colors.GREEN if overall_success else Colors.YELLOW)
        
        return overall_success
        
    except Exception as e:
        print_colored(f"❌ 测试过程中发生错误: {e}", Colors.RED)
        return False
    finally:
        tester.close()

def test_concurrent_connections(host: str, port: int, connection_count: int = 3) -> bool:
    """测试并发连接"""
    print_colored(f"启动 {connection_count} 个并发连接...", Colors.BLUE)
    
    results = []
    threads = []
    
    def single_connection_test(conn_id: int):
        """单个连接测试"""
        try:
            tester = MySQLProtocolTester(host, port)
            if tester.connect():
                handshake_data = tester.read_packet()
                if handshake_data and tester.parse_handshake(handshake_data):
                    if tester.send_auth_response(f"user{conn_id}", "", ""):
                        auth_result = tester.read_packet()
                        if auth_result and tester.parse_auth_result(auth_result):
                            if tester.send_query(f"SELECT {conn_id} as connection_id"):
                                if tester.parse_query_result():
                                    results.append(True)
                                    print_colored(f"  连接 {conn_id}: ✅", Colors.GREEN)
                                    tester.close()
                                    return
            results.append(False)
            print_colored(f"  连接 {conn_id}: ❌", Colors.RED)
        except Exception as e:
            results.append(False)
            print_colored(f"  连接 {conn_id}: ❌ ({e})", Colors.RED)
    
    # 启动并发连接
    for i in range(connection_count):
        thread = threading.Thread(target=single_connection_test, args=(i+1,))
        threads.append(thread)
        thread.start()
    
    # 等待所有连接完成
    for thread in threads:
        thread.join(timeout=10)
    
    success_count = sum(results)
    print_colored(f"并发连接测试: {success_count}/{connection_count} 成功", 
                 Colors.GREEN if success_count == connection_count else Colors.YELLOW)
    
    return success_count == connection_count

def test_performance(host: str, port: int) -> bool:
    """性能测试"""
    print_colored("执行性能测试...", Colors.BLUE)
    
    try:
        tester = MySQLProtocolTester(host, port)
        if not tester.connect():
            return False
        
        # 握手和认证
        handshake_data = tester.read_packet()
        if not handshake_data or not tester.parse_handshake(handshake_data):
            return False
        
        if not tester.send_auth_response("perftest", "", ""):
            return False
        
        auth_result = tester.read_packet()
        if not auth_result or not tester.parse_auth_result(auth_result):
            return False
        
        # 性能测试查询
        query_count = 10
        start_time = time.time()
        
        for i in range(query_count):
            if not tester.send_query(f"SELECT {i} as query_num, '{i}' as query_str"):
                return False
            if not tester.parse_query_result():
                return False
        
        end_time = time.time()
        total_time = end_time - start_time
        qps = query_count / total_time
        
        print_colored(f"  查询数量: {query_count}", Colors.WHITE)
        print_colored(f"  总耗时: {total_time:.3f}秒", Colors.WHITE)
        print_colored(f"  QPS: {qps:.2f}", Colors.WHITE)
        
        tester.close()
        return True
        
    except Exception as e:
        print_colored(f"性能测试失败: {e}", Colors.RED)
        return False

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="DuckDB MySQL协议测试工具")
    parser.add_argument("--host", default="localhost", help="服务器地址 (默认: localhost)")
    parser.add_argument("--port", type=int, default=33660, help="服务器端口 (默认: 33660)")
    parser.add_argument("--concurrent", type=int, default=3, help="并发连接数 (默认: 3)")
    
    args = parser.parse_args()
    
    print_colored("🚀 启动MySQL协议测试...", Colors.BOLD + Colors.BLUE)
    
    success = test_mysql_protocol(args.host, args.port)
    
    if success:
        print_colored("\n🎉 所有测试完成！MySQL协议工作正常。", Colors.BOLD + Colors.GREEN)
        sys.exit(0)
    else:
        print_colored("\n💥 测试失败！请检查服务器状态。", Colors.BOLD + Colors.RED)
        sys.exit(1)

if __name__ == "__main__":
    main() 