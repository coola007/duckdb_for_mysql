#!/usr/bin/env python3
"""
DuckDB MySQL协议测试脚本
测试MySQL TCP协议的连接和基本功能
"""

import socket
import struct
import time
import sys

class MySQLProtocolTester:
    def __init__(self, host='localhost', port=3366):
        self.host = host
        self.port = port
        self.socket = None
    
    def connect(self):
        """连接到MySQL协议服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            print(f"✓ 成功连接到 {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False
    
    def receive_handshake(self):
        """接收MySQL握手包"""
        try:
            # 读取握手包
            data = self.socket.recv(1024)
            if len(data) > 0:
                print(f"✓ 收到握手包，长度: {len(data)} 字节")
                print(f"  握手包内容: {data.hex()}")
                return True
            else:
                print("✗ 未收到握手包")
                return False
        except Exception as e:
            print(f"✗ 接收握手包失败: {e}")
            return False
    
    def send_auth_response(self):
        """发送认证响应"""
        try:
            # 简化的认证响应包
            auth_packet = b'\x01\x00\x00\x01\x00'  # 简单的OK响应
            self.socket.send(auth_packet)
            print("✓ 发送认证响应")
            return True
        except Exception as e:
            print(f"✗ 发送认证响应失败: {e}")
            return False
    
    def send_query(self, sql):
        """发送SQL查询"""
        try:
            # MySQL查询包格式：长度(3) + 序号(1) + 命令(1) + SQL
            query_data = sql.encode('utf-8')
            packet_length = len(query_data) + 1
            
            packet = struct.pack('<I', packet_length)[:3]  # 3字节长度
            packet += b'\x00'  # 序号
            packet += b'\x03'  # COM_QUERY命令
            packet += query_data
            
            self.socket.send(packet)
            print(f"✓ 发送查询: {sql}")
            return True
        except Exception as e:
            print(f"✗ 发送查询失败: {e}")
            return False
    
    def receive_response(self):
        """接收查询响应"""
        try:
            data = self.socket.recv(1024)
            if len(data) > 0:
                print(f"✓ 收到响应，长度: {len(data)} 字节")
                print(f"  响应内容: {data.hex()}")
                return True
            else:
                print("✗ 未收到响应")
                return False
        except Exception as e:
            print(f"✗ 接收响应失败: {e}")
            return False
    
    def test_connection_lifecycle(self):
        """测试完整的连接生命周期"""
        print("\n=== MySQL协议连接生命周期测试 ===")
        
        # 1. 连接
        if not self.connect():
            return False
        
        # 2. 接收握手包
        if not self.receive_handshake():
            return False
        
        # 3. 发送认证响应
        if not self.send_auth_response():
            return False
        
        # 4. 发送测试查询
        queries = [
            "SELECT 1",
            "SELECT 'Hello MySQL Protocol'",
            "SHOW TABLES"
        ]
        
        for query in queries:
            print(f"\n--- 测试查询: {query} ---")
            if self.send_query(query):
                self.receive_response()
            time.sleep(0.1)
        
        return True
    
    def test_multiple_connections(self, count=5):
        """测试多连接"""
        print(f"\n=== 测试多连接 ({count}个连接) ===")
        
        connections = []
        success_count = 0
        
        for i in range(count):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((self.host, self.port))
                connections.append(sock)
                success_count += 1
                print(f"✓ 连接 {i+1}/{count} 成功")
            except Exception as e:
                print(f"✗ 连接 {i+1}/{count} 失败: {e}")
        
        # 关闭所有连接
        for sock in connections:
            try:
                sock.close()
            except:
                pass
        
        print(f"成功建立 {success_count}/{count} 个连接")
        return success_count == count
    
    def test_port_availability(self):
        """测试端口可用性"""
        print(f"\n=== 测试端口 {self.port} 可用性 ===")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            
            if result == 0:
                print(f"✓ 端口 {self.port} 可访问")
                return True
            else:
                print(f"✗ 端口 {self.port} 不可访问")
                return False
        except Exception as e:
            print(f"✗ 端口测试失败: {e}")
            return False
    
    def close(self):
        """关闭连接"""
        if self.socket:
            try:
                self.socket.close()
                print("✓ 连接已关闭")
            except:
                pass

def main():
    print("DuckDB MySQL协议测试工具")
    print("=" * 50)
    
    tester = MySQLProtocolTester()
    
    # 测试序列
    tests = [
        ("端口可用性", tester.test_port_availability),
        ("连接生命周期", tester.test_connection_lifecycle),
        ("多连接测试", lambda: tester.test_multiple_connections(3))
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"✓ {test_name} 通过")
            else:
                print(f"✗ {test_name} 失败")
        except Exception as e:
            print(f"✗ {test_name} 异常: {e}")
            results.append((test_name, False))
        finally:
            tester.close()
    
    # 测试结果汇总
    print("\n" + "="*50)
    print("测试结果汇总:")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有MySQL协议测试通过!")
        sys.exit(0)
    else:
        print("⚠️  部分测试失败，请检查服务状态")
        sys.exit(1)

if __name__ == "__main__":
    main() 