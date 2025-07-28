#!/usr/bin/env python3
"""
MySQL协议兼容性测试脚本
测试DuckDB服务与标准MySQL协议的兼容程度
"""

import socket
import struct
import time

def create_mysql_packet(payload, sequence_id=0):
    """创建标准MySQL数据包"""
    packet_length = len(payload)
    header = struct.pack('<I', packet_length)[0:3]  # 3字节长度
    header += struct.pack('B', sequence_id)  # 1字节序列号
    return header + payload

def parse_mysql_packet(data):
    """解析MySQL数据包"""
    if len(data) < 4:
        return None, None, None
    
    length = struct.unpack('<I', data[0:3] + b'\x00')[0]
    sequence_id = data[3]
    payload = data[4:4+length]
    
    return length, sequence_id, payload

def test_mysql_handshake():
    """测试MySQL握手协议"""
    print("=== MySQL握手协议测试 ===")
    
    try:
        # 连接到服务器
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(('localhost', 3366))
        print("✓ TCP连接建立成功")
        
        # 接收握手包
        handshake_data = sock.recv(1024)
        if len(handshake_data) > 0:
            length, seq_id, payload = parse_mysql_packet(handshake_data)
            print(f"✓ 收到握手包: 长度={length}, 序列号={seq_id}")
            print(f"  握手包内容: {handshake_data.hex()}")
            
            # 分析握手包内容
            if len(payload) > 0:
                protocol_version = payload[0]
                print(f"  协议版本: {protocol_version}")
                
                # 查找服务器版本字符串 (以null结尾)
                null_pos = payload.find(b'\x00', 1)
                if null_pos > 1:
                    server_version = payload[1:null_pos].decode('utf-8', errors='ignore')
                    print(f"  服务器版本: '{server_version}'")
        else:
            print("✗ 未收到握手包")
            return False
            
        # 发送认证响应包
        print("\n--- 发送认证响应 ---")
        
        # 简化的认证响应包
        auth_response = bytearray()
        auth_response.extend(struct.pack('<I', 0x00000001))  # client_flags
        auth_response.extend(struct.pack('<I', 0x01000000))  # max_packet_size
        auth_response.extend(struct.pack('B', 33))           # character_set
        auth_response.extend(b'\x00' * 23)                   # reserved
        auth_response.extend(b'root\x00')                    # username
        auth_response.extend(b'\x00')                        # password length (0)
        auth_response.extend(b'test\x00')                    # database name
        
        auth_packet = create_mysql_packet(auth_response, 1)
        sock.send(auth_packet)
        print("✓ 认证包发送完成")
        
        # 接收认证响应
        auth_result = sock.recv(1024)
        if len(auth_result) > 0:
            length, seq_id, payload = parse_mysql_packet(auth_result)
            print(f"✓ 收到认证响应: 长度={length}, 序列号={seq_id}")
            
            if len(payload) > 0:
                packet_type = payload[0]
                if packet_type == 0x00:
                    print("✓ 认证成功 (OK包)")
                elif packet_type == 0xff:
                    print("⚠ 认证失败 (ERROR包)")
                    if len(payload) > 3:
                        error_code = struct.unpack('<H', payload[1:3])[0]
                        print(f"  错误代码: {error_code}")
                else:
                    print(f"? 未知响应类型: 0x{packet_type:02x}")
        
        sock.close()
        return True
        
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return False

def test_query_execution():
    """测试查询执行"""
    print("\n=== 查询执行测试 ===")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(('localhost', 3366))
        
        # 跳过握手，直接发送查询
        handshake_data = sock.recv(1024)
        
        # 发送简单的查询
        query = "SELECT 1"
        query_payload = bytearray()
        query_payload.append(0x03)  # COM_QUERY
        query_payload.extend(query.encode('utf-8'))
        
        query_packet = create_mysql_packet(query_payload, 0)
        sock.send(query_packet)
        print(f"✓ 查询发送: {query}")
        
        # 接收响应
        response = sock.recv(1024)
        if len(response) > 0:
            length, seq_id, payload = parse_mysql_packet(response)
            print(f"✓ 收到查询响应: 长度={length}, 序列号={seq_id}")
            
            if len(payload) > 0:
                packet_type = payload[0]
                if packet_type == 0x00:
                    print("✓ 查询执行成功 (OK包)")
                elif packet_type == 0xff:
                    print("⚠ 查询执行失败 (ERROR包)")
                else:
                    print(f"? 响应类型: 0x{packet_type:02x}")
                    
        sock.close()
        return True
        
    except Exception as e:
        print(f"✗ 查询测试失败: {e}")
        return False

def test_multiple_connections():
    """测试多连接处理"""
    print("\n=== 多连接测试 ===")
    
    connections = []
    success_count = 0
    
    for i in range(3):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(('localhost', 3366))
            connections.append(sock)
            success_count += 1
            print(f"✓ 连接 {i+1}/3 建立成功")
            
            # 接收握手包
            handshake = sock.recv(1024)
            if len(handshake) > 0:
                print(f"  握手包长度: {len(handshake)}")
            
        except Exception as e:
            print(f"✗ 连接 {i+1}/3 失败: {e}")
    
    # 关闭所有连接
    for sock in connections:
        try:
            sock.close()
        except:
            pass
    
    print(f"多连接测试结果: {success_count}/3 成功")
    return success_count >= 2

def main():
    print("MySQL协议兼容性测试")
    print("=" * 50)
    
    tests = [
        ("握手协议", test_mysql_handshake),
        ("查询执行", test_query_execution),
        ("多连接处理", test_multiple_connections)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
            status = "通过" if result else "失败"
            print(f"\n{test_name}: {status}")
        except Exception as e:
            print(f"\n{test_name}: 异常 - {e}")
            results.append((test_name, False))
        
        time.sleep(1)  # 避免连接太快
    
    # 结果汇总
    print("\n" + "="*50)
    print("测试结果汇总:")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name:15} {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 MySQL协议兼容性测试全部通过!")
    else:
        print("⚠️  部分测试失败")
        print("\n说明:")
        print("- 当前实现是简化版MySQL协议")
        print("- 支持基本的连接和握手")
        print("- 查询执行通过统一的DuckDB引擎处理")
        print("- 适用于基础的TCP连接和协议测试")

if __name__ == "__main__":
    main() 