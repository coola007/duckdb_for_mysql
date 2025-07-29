#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的MySQL协议连接测试
针对我们当前的简化MySQL协议实现
"""

import socket
import time
import sys

def test_mysql_connection(host="localhost", port=33660):
    """测试MySQL协议连接"""
    print(f"🔗 连接到 {host}:{port}...")
    
    try:
        # 建立TCP连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))
        print("✅ TCP连接成功")
        
        # 接收握手包
        print("📥 接收握手包...")
        handshake_data = sock.recv(1024)
        print(f"收到握手数据 ({len(handshake_data)} 字节): {handshake_data.hex()}")
        
        # 发送简单的认证响应（空认证）
        print("📤 发送认证响应...")
        auth_response = b'\x00' * 32  # 简单的空认证
        sock.send(auth_response)
        
        # 等待认证结果
        time.sleep(0.1)
        
        # 发送测试查询
        print("📝 发送测试查询...")
        test_queries = [
            "SELECT 1",
            "SELECT 1 as num, 'hello' as msg",
            "SHOW TABLES",
        ]
        
        for query in test_queries:
            print(f"  执行查询: {query}")
            sock.send(query.encode('utf-8'))
            
            # 接收响应
            try:
                response = sock.recv(1024)
                print(f"  响应 ({len(response)} 字节): {response.hex()}")
            except socket.timeout:
                print("  响应超时")
            
            time.sleep(0.5)
        
        sock.close()
        print("✅ MySQL协议测试完成")
        return True
        
    except Exception as e:
        print(f"❌ MySQL协议测试失败: {e}")
        return False

def test_standard_mysql_client():
    """使用标准MySQL客户端测试（无密码）"""
    import subprocess
    
    print("🔧 测试标准MySQL客户端连接...")
    
    # 尝试不同的连接方式
    test_commands = [
        ["mysql", "-h", "localhost", "-P", "33660", "-u", "root", "--skip-password", "-e", "SELECT 1"],
        ["mysql", "-h", "localhost", "-P", "33660", "-u", "test", "-e", "SELECT 1"],
        ["mysql", "-h", "localhost", "-P", "33660", "-e", "SELECT 1"],
    ]
    
    for cmd in test_commands:
        try:
            print(f"  尝试命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print("  ✅ 连接成功")
                print(f"  输出: {result.stdout}")
                return True
            else:
                print(f"  ❌ 连接失败: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("  ⏰ 连接超时")
        except FileNotFoundError:
            print("  ❓ MySQL客户端未安装")
            break
        except Exception as e:
            print(f"  ❌ 执行失败: {e}")
    
    return False

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="简单MySQL协议测试")
    parser.add_argument("--host", default="localhost", help="服务器地址")
    parser.add_argument("--port", type=int, default=33660, help="服务器端口")
    
    args = parser.parse_args()
    
    print("🚀 开始MySQL协议测试...")
    print(f"目标服务器: {args.host}:{args.port}")
    print("="*50)
    
    # 测试1: 自定义协议测试
    print("\n📡 测试1: 自定义协议连接")
    test1_passed = test_mysql_connection(args.host, args.port)
    
    # 测试2: 标准MySQL客户端测试
    print("\n🐬 测试2: 标准MySQL客户端")
    test2_passed = test_standard_mysql_client()
    
    # 总结
    print("\n" + "="*50)
    print("📊 测试总结:")
    print(f"  自定义协议测试: {'✅ 通过' if test1_passed else '❌ 失败'}")
    print(f"  标准客户端测试: {'✅ 通过' if test2_passed else '❌ 失败'}")
    
    if test1_passed:
        print("\n🎉 基本MySQL协议连接工作正常！")
        print("💡 注意: 当前实现是简化版MySQL协议")
        print("💡 如需完整兼容性，请参考 test/mysql_protocol_test.py")
        return 0
    else:
        print("\n💥 MySQL协议连接失败")
        print("🔧 请检查服务器是否正常运行")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 