package mysql

import (
	"context"
	"encoding/binary"
	"fmt"
	"log"
	"net"
	"strings"
	"sync"

	"duckdb-server/internal/query"
)

// MySQL协议常量
const (
	COM_QUIT                 = 0x01
	COM_INIT_DB              = 0x02
	COM_QUERY                = 0x03
	COM_PING                 = 0x0e
	SERVER_STATUS_AUTOCOMMIT = 0x0002
	CLIENT_PROTOCOL_41       = 0x00000200
	CLIENT_SECURE_CONNECTION = 0x00008000
)

// Packet MySQL数据包结构
type Packet struct {
	Length     uint32
	SequenceID uint8
	Payload    []byte
}

// Server MySQL协议服务器
type Server struct {
	port     int
	executor *query.Executor
	listener net.Listener
	ctx      context.Context
	cancel   context.CancelFunc
	wg       sync.WaitGroup
}

// NewServer 创建MySQL服务器
func NewServer(port int, executor *query.Executor) *Server {
	ctx, cancel := context.WithCancel(context.Background())

	return &Server{
		port:     port,
		executor: executor,
		ctx:      ctx,
		cancel:   cancel,
	}
}

// Start 启动MySQL服务器
func (s *Server) Start() error {
	listener, err := net.Listen("tcp", fmt.Sprintf(":%d", s.port))
	if err != nil {
		return fmt.Errorf("启动MySQL服务器失败: %v", err)
	}
	s.listener = listener

	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		defer listener.Close()

		log.Printf("MySQL协议服务器启动在端口 %d", s.port)

		for {
			select {
			case <-s.ctx.Done():
				return
			default:
				conn, err := listener.Accept()
				if err != nil {
					if s.ctx.Err() != nil {
						return // 服务正在关闭
					}
					log.Printf("MySQL连接接受错误: %v", err)
					continue
				}
				go s.handleConnection(conn)
			}
		}
	}()

	return nil
}

// Stop 停止MySQL服务器
func (s *Server) Stop() error {
	s.cancel()
	if s.listener != nil {
		s.listener.Close()
	}
	s.wg.Wait()
	return nil
}

// handleConnection 处理客户端连接
func (s *Server) handleConnection(conn net.Conn) {
	defer conn.Close()

	log.Printf("MySQL连接来自 %s", conn.RemoteAddr())

	// 发送握手包
	if err := s.sendHandshake(conn); err != nil {
		log.Printf("发送握手包失败: %v", err)
		return
	}

	// 接收认证响应
	if err := s.handleAuth(conn); err != nil {
		log.Printf("认证失败: %v", err)
		return
	}

	// 处理命令循环
	s.handleCommands(conn)
}

// sendHandshake 发送MySQL握手包
func (s *Server) sendHandshake(conn net.Conn) error {
	var payload []byte

	// 协议版本
	payload = append(payload, 10)

	// 服务器版本字符串
	serverVersion := "5.7.25-DuckDB-1.0.0"
	payload = append(payload, []byte(serverVersion)...)
	payload = append(payload, 0) // null终止符

	// 连接ID (4字节)
	connID := uint32(1)
	connIDBytes := make([]byte, 4)
	binary.LittleEndian.PutUint32(connIDBytes, connID)
	payload = append(payload, connIDBytes...)

	// 认证数据第一部分 (8字节)
	authData1 := []byte{0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0}
	payload = append(payload, authData1...)

	// filler
	payload = append(payload, 0)

	// 能力标志低16位
	capability1 := uint16(CLIENT_PROTOCOL_41 & 0xFFFF)
	cap1Bytes := make([]byte, 2)
	binary.LittleEndian.PutUint16(cap1Bytes, capability1)
	payload = append(payload, cap1Bytes...)

	// 字符集
	payload = append(payload, 33) // utf8_general_ci

	// 状态标志
	statusBytes := make([]byte, 2)
	binary.LittleEndian.PutUint16(statusBytes, SERVER_STATUS_AUTOCOMMIT)
	payload = append(payload, statusBytes...)

	// 能力标志高16位
	capability2 := uint16((CLIENT_PROTOCOL_41 | CLIENT_SECURE_CONNECTION) >> 16)
	cap2Bytes := make([]byte, 2)
	binary.LittleEndian.PutUint16(cap2Bytes, capability2)
	payload = append(payload, cap2Bytes...)

	// 认证数据长度
	payload = append(payload, 21)

	// 保留字节 (10字节)
	payload = append(payload, make([]byte, 10)...)

	// 认证数据第二部分 (12字节 + null终止符)
	authData2 := []byte{0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef, 0x01, 0x23, 0x45, 0x67}
	payload = append(payload, authData2...)
	payload = append(payload, 0) // null终止符

	return s.sendPacket(conn, payload, 0)
}

// handleAuth 处理认证
func (s *Server) handleAuth(conn net.Conn) error {
	packet, err := s.readPacket(conn)
	if err != nil {
		return err
	}

	log.Printf("收到认证包，长度: %d", len(packet.Payload))

	// 发送OK包表示认证成功
	okPayload := []byte{
		0x00,       // OK标识
		0x00,       // affected rows
		0x00,       // last insert id
		0x02, 0x00, // status flags (SERVER_STATUS_AUTOCOMMIT)
		0x00, 0x00, // warnings
	}

	return s.sendPacket(conn, okPayload, packet.SequenceID+1)
}

// handleCommands 处理客户端命令
func (s *Server) handleCommands(conn net.Conn) {
	for {
		packet, err := s.readPacket(conn)
		if err != nil {
			log.Printf("读取命令包失败: %v", err)
			return
		}

		if len(packet.Payload) == 0 {
			continue
		}

		command := packet.Payload[0]

		switch command {
		case COM_QUIT:
			log.Printf("客户端发送退出命令")
			return

		case COM_INIT_DB:
			dbName := string(packet.Payload[1:])
			log.Printf("客户端尝试切换数据库 (USE %s)，已忽略", dbName)
			okPayload := s.buildOKPacket(0, 0)
			s.sendPacket(conn, okPayload, packet.SequenceID+1)

		case COM_PING:
			log.Printf("客户端发送Ping命令")
			okPayload := []byte{0x00}
			s.sendPacket(conn, okPayload, packet.SequenceID+1)

		case COM_QUERY:
			if len(packet.Payload) < 2 {
				s.sendError(conn, "空查询", packet.SequenceID+1)
				continue
			}

			query := string(packet.Payload[1:])
			log.Printf("执行SQL: %s", query)

			s.executeSQL(conn, query, packet.SequenceID+1)

		default:
			log.Printf("不支持的命令: 0x%02x", command)
			s.sendError(conn, fmt.Sprintf("不支持的命令: 0x%02x", command), packet.SequenceID+1)
		}
	}
}

// executeSQL 执行SQL查询
func (s *Server) executeSQL(conn net.Conn, query string, sequenceID uint8) {
	// 处理MySQL兼容性命令
	if s.handleMySQLCompatibilityCommand(conn, query, sequenceID) {
		return
	}

	response := s.executor.Execute(query)

	if response.Error != "" {
		s.sendError(conn, response.Error, sequenceID)
		return
	}

	data, ok := response.Data.(map[string]interface{})
	if !ok {
		s.sendError(conn, "无效的响应数据格式", sequenceID)
		return
	}

	columns, ok := data["columns"].([]string)
	if !ok {
		// DDL/DML语句，发送OK包
		affectedRows := uint64(0)
		if response.RowsAffected > 0 {
			affectedRows = uint64(response.RowsAffected)
		}

		okPayload := s.buildOKPacket(affectedRows, 0)
		s.sendPacket(conn, okPayload, sequenceID)
		return
	}

	rows, ok := data["rows"].([]map[string]interface{})
	if !ok {
		rows = []map[string]interface{}{}
	}

	s.sendResultSet(conn, columns, rows, sequenceID)
}

// handleMySQLCompatibilityCommand 处理MySQL兼容性命令
func (s *Server) handleMySQLCompatibilityCommand(conn net.Conn, query string, sequenceID uint8) bool {
	// 转换为小写以便匹配
	lowerQuery := strings.ToLower(strings.TrimSpace(query))

	// 添加调试日志
	// log.Printf("🔍 检查兼容性命令: [%s]", query)

	// MySQL客户端连接时常用的设置命令
	compatibilityCommands := []string{
		"set names utf8mb4",
		"set names utf8",
		"set character_set_client=utf8mb4",
		"set character_set_connection=utf8mb4",
		"set character_set_results=utf8mb4",
		"set character_set_server=utf8mb4",
		"set collation_connection=utf8mb4_general_ci",
		"set collation_server=utf8mb4_general_ci",
		"set sql_mode=",
		"set autocommit=1",
		"set autocommit=0",
		"set autocommit = 1",
		"set autocommit = 0",
		"set @@autocommit=1",
		"set @@autocommit=0",
		"set @@autocommit = 1",
		"set @@autocommit = 0",
		"set @@session.autocommit=1",
		"set @@session.autocommit=0",
		"set @@session.autocommit = 1",
		"set @@session.autocommit = 0",
		"set session autocommit=1",
		"set session autocommit=0",
		"set session autocommit = 1",
		"set session autocommit = 0",
		"set global autocommit=1",
		"set global autocommit=0",
		"set global autocommit = 1",
		"set global autocommit = 0",
		"set session transaction isolation level read committed",
		"set session transaction isolation level repeatable read",
		"show warnings",
		"show variables like 'character_set%'",
		"show variables like 'collation%'",
		"show variables like 'autocommit%'",
		"show variables like '%autocommit%'",
		"show collation",
		"show charset",
		"select @@version_comment",
		"select @@sql_mode",
		"select @@autocommit",
		"select @@session.autocommit",
		"select @@global.autocommit",
		"select @@character_set_server",
		"select @@collation_server",
		"select connection_id()",
		"select database()",
		"select user()",
		"select current_user()",
	}

	// 检查是否是兼容性命令
	for _, cmd := range compatibilityCommands {
		if strings.HasPrefix(lowerQuery, cmd) {
			log.Printf("处理MySQL兼容性命令: %s", query)

			// 对于某些查询命令，返回合理的默认值
			if strings.HasPrefix(lowerQuery, "select @@version_comment") {
				s.sendSimpleResult(conn, "version_comment", "DuckDB MySQL Protocol", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "select @@sql_mode") {
				s.sendSimpleResult(conn, "@@sql_mode", "", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "select @@autocommit") {
				s.sendSimpleResult(conn, "@@autocommit", "1", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "select @@session.autocommit") {
				s.sendSimpleResult(conn, "@@session.autocommit", "1", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "select @@global.autocommit") {
				s.sendSimpleResult(conn, "@@global.autocommit", "1", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "select @@character_set_server") {
				s.sendSimpleResult(conn, "@@character_set_server", "utf8mb4", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "select @@collation_server") {
				s.sendSimpleResult(conn, "@@collation_server", "utf8mb4_general_ci", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "select connection_id()") {
				s.sendSimpleResult(conn, "connection_id()", "1", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "select database()") {
				s.sendSimpleResult(conn, "database()", "duckdb", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "select user()") || strings.HasPrefix(lowerQuery, "select current_user()") {
				s.sendSimpleResult(conn, "user()", "root@localhost", sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "show warnings") {
				// 返回空的warnings结果集
				columns := []string{"Level", "Code", "Message"}
				rows := []map[string]interface{}{}
				s.sendResultSet(conn, columns, rows, sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "show variables like 'character_set%'") {
				columns := []string{"Variable_name", "Value"}
				rows := []map[string]interface{}{
					{"Variable_name": "character_set_client", "Value": "utf8mb4"},
					{"Variable_name": "character_set_connection", "Value": "utf8mb4"},
					{"Variable_name": "character_set_database", "Value": "utf8mb4"},
					{"Variable_name": "character_set_results", "Value": "utf8mb4"},
					{"Variable_name": "character_set_server", "Value": "utf8mb4"},
					{"Variable_name": "character_set_system", "Value": "utf8"},
				}
				s.sendResultSet(conn, columns, rows, sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "show variables like 'collation%'") {
				columns := []string{"Variable_name", "Value"}
				rows := []map[string]interface{}{
					{"Variable_name": "collation_connection", "Value": "utf8mb4_general_ci"},
					{"Variable_name": "collation_database", "Value": "utf8mb4_general_ci"},
					{"Variable_name": "collation_server", "Value": "utf8mb4_general_ci"},
				}
				s.sendResultSet(conn, columns, rows, sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "show variables like") && (strings.Contains(lowerQuery, "autocommit") || strings.Contains(lowerQuery, "%autocommit%")) {
				columns := []string{"Variable_name", "Value"}
				rows := []map[string]interface{}{
					{"Variable_name": "autocommit", "Value": "ON"},
				}
				s.sendResultSet(conn, columns, rows, sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "show collation") {
				columns := []string{"Collation", "Charset", "Id", "Default", "Compiled", "Sortlen"}
				rows := []map[string]interface{}{
					{"Collation": "utf8mb4_general_ci", "Charset": "utf8mb4", "Id": "45", "Default": "Yes", "Compiled": "Yes", "Sortlen": "1"},
					{"Collation": "utf8_general_ci", "Charset": "utf8", "Id": "33", "Default": "Yes", "Compiled": "Yes", "Sortlen": "1"},
				}
				s.sendResultSet(conn, columns, rows, sequenceID)
				return true
			}
			if strings.HasPrefix(lowerQuery, "show charset") {
				columns := []string{"Charset", "Description", "Default collation", "Maxlen"}
				rows := []map[string]interface{}{
					{"Charset": "utf8mb4", "Description": "UTF-8 Unicode", "Default collation": "utf8mb4_general_ci", "Maxlen": "4"},
					{"Charset": "utf8", "Description": "UTF-8 Unicode", "Default collation": "utf8_general_ci", "Maxlen": "3"},
				}
				s.sendResultSet(conn, columns, rows, sequenceID)
				return true
			}

			// 对于其他设置命令，直接返回OK
			okPayload := s.buildOKPacket(0, 0)
			s.sendPacket(conn, okPayload, sequenceID)
			return true
		}
	}

	// 额外的灵活匹配 - 用于处理各种格式的SET命令
	if strings.HasPrefix(lowerQuery, "set ") {
		// 匹配所有autocommit相关的SET命令
		if strings.Contains(lowerQuery, "autocommit") {
			log.Printf("处理AUTOCOMMIT设置命令: %s", query)
			okPayload := s.buildOKPacket(0, 0)
			s.sendPacket(conn, okPayload, sequenceID)
			return true
		}

		// 匹配字符集相关的SET命令
		if strings.Contains(lowerQuery, "character_set") || strings.Contains(lowerQuery, "charset") ||
			strings.Contains(lowerQuery, "collation") || strings.Contains(lowerQuery, "names") {
			log.Printf("处理字符集设置命令: %s", query)
			okPayload := s.buildOKPacket(0, 0)
			s.sendPacket(conn, okPayload, sequenceID)
			return true
		}

		// 匹配SQL模式相关的SET命令
		if strings.Contains(lowerQuery, "sql_mode") {
			log.Printf("处理SQL模式设置命令: %s", query)
			okPayload := s.buildOKPacket(0, 0)
			s.sendPacket(conn, okPayload, sequenceID)
			return true
		}

		// 匹配事务隔离级别
		if strings.Contains(lowerQuery, "transaction") && strings.Contains(lowerQuery, "isolation") {
			log.Printf("处理事务隔离级别设置命令: %s", query)
			okPayload := s.buildOKPacket(0, 0)
			s.sendPacket(conn, okPayload, sequenceID)
			return true
		}
	}

	// 不是兼容性命令
	return false
}

// sendSimpleResult 发送简单的单值结果
func (s *Server) sendSimpleResult(conn net.Conn, columnName, value string, sequenceID uint8) {
	columns := []string{columnName}
	rows := []map[string]interface{}{
		{columnName: value},
	}
	s.sendResultSet(conn, columns, rows, sequenceID)
}

// sendResultSet 发送结果集
func (s *Server) sendResultSet(conn net.Conn, columns []string, rows []map[string]interface{}, sequenceID uint8) {
	currentSeq := sequenceID

	// 1. 发送列数量
	columnCountPayload := s.encodeLengthEncodedInteger(uint64(len(columns)))
	s.sendPacket(conn, columnCountPayload, currentSeq)
	currentSeq++

	// 2. 发送列定义
	for _, column := range columns {
		columnDefPayload := s.buildColumnDefinition(column)
		s.sendPacket(conn, columnDefPayload, currentSeq)
		currentSeq++
	}

	// 3. 发送列定义结束EOF包
	eofPayload := []byte{0xfe, 0x00, 0x00, 0x02, 0x00}
	s.sendPacket(conn, eofPayload, currentSeq)
	currentSeq++

	// 4. 发送数据行
	for _, row := range rows {
		rowPayload := s.buildRowData(columns, row)
		s.sendPacket(conn, rowPayload, currentSeq)
		currentSeq++
	}

	// 5. 发送最终EOF包
	s.sendPacket(conn, eofPayload, currentSeq)
}

// buildColumnDefinition 构建列定义
func (s *Server) buildColumnDefinition(columnName string) []byte {
	var payload []byte

	payload = append(payload, s.encodeLengthEncodedString("def")...)      // catalog
	payload = append(payload, s.encodeLengthEncodedString("duckdb")...)   // schema
	payload = append(payload, s.encodeLengthEncodedString("result")...)   // table
	payload = append(payload, s.encodeLengthEncodedString("result")...)   // org_table
	payload = append(payload, s.encodeLengthEncodedString(columnName)...) // name
	payload = append(payload, s.encodeLengthEncodedString(columnName)...) // org_name

	payload = append(payload, 0x0c)                   // length of fixed-length fields
	payload = append(payload, 0x21, 0x00)             // character set (utf8_general_ci)
	payload = append(payload, 0xff, 0xff, 0xff, 0xff) // column length
	payload = append(payload, 0xfd)                   // column type (VARCHAR)
	payload = append(payload, 0x00, 0x00)             // flags
	payload = append(payload, 0x00)                   // decimals
	payload = append(payload, 0x00, 0x00)             // filler

	return payload
}

// buildRowData 构建行数据
func (s *Server) buildRowData(columns []string, row map[string]interface{}) []byte {
	var payload []byte

	for _, column := range columns {
		value := row[column]
		if value == nil {
			payload = append(payload, 0xfb) // NULL
		} else {
			valueStr := fmt.Sprintf("%v", value)
			payload = append(payload, s.encodeLengthEncodedString(valueStr)...)
		}
	}

	return payload
}

// buildOKPacket 构建OK包
func (s *Server) buildOKPacket(affectedRows, lastInsertID uint64) []byte {
	var payload []byte

	payload = append(payload, 0x00) // OK标识
	payload = append(payload, s.encodeLengthEncodedInteger(affectedRows)...)
	payload = append(payload, s.encodeLengthEncodedInteger(lastInsertID)...)
	payload = append(payload, 0x02, 0x00) // status flags (SERVER_STATUS_AUTOCOMMIT)
	payload = append(payload, 0x00, 0x00) // warnings

	return payload
}

// encodeLengthEncodedInteger 编码长度编码整数
func (s *Server) encodeLengthEncodedInteger(value uint64) []byte {
	if value < 251 {
		return []byte{byte(value)}
	} else if value < 65536 {
		result := []byte{0xfc}
		buf := make([]byte, 2)
		binary.LittleEndian.PutUint16(buf, uint16(value))
		result = append(result, buf...)
		return result
	} else if value < 16777216 {
		result := []byte{0xfd}
		buf := make([]byte, 4)
		binary.LittleEndian.PutUint32(buf, uint32(value))
		result = append(result, buf[:3]...)
		return result
	} else {
		result := []byte{0xfe}
		buf := make([]byte, 8)
		binary.LittleEndian.PutUint64(buf, value)
		result = append(result, buf...)
		return result
	}
}

// encodeLengthEncodedString 编码长度编码字符串
func (s *Server) encodeLengthEncodedString(s2 string) []byte {
	data := []byte(s2)
	length := s.encodeLengthEncodedInteger(uint64(len(data)))
	return append(length, data...)
}

// sendError 发送错误包
func (s *Server) sendError(conn net.Conn, message string, sequenceID uint8) {
	var payload []byte

	payload = append(payload, 0xff)               // ERROR标识
	payload = append(payload, 0x10, 0x04)         // 错误码
	payload = append(payload, '#')                // SQL状态标记
	payload = append(payload, []byte("HY000")...) // SQL状态
	payload = append(payload, []byte(message)...) // 错误消息

	s.sendPacket(conn, payload, sequenceID)
}

// readPacket 读取MySQL数据包
func (s *Server) readPacket(conn net.Conn) (*Packet, error) {
	header := make([]byte, 4)
	if _, err := conn.Read(header); err != nil {
		return nil, err
	}

	length := uint32(header[0]) | uint32(header[1])<<8 | uint32(header[2])<<16
	sequenceID := header[3]

	payload := make([]byte, length)
	if length > 0 {
		if _, err := conn.Read(payload); err != nil {
			return nil, err
		}
	}

	return &Packet{
		Length:     length,
		SequenceID: sequenceID,
		Payload:    payload,
	}, nil
}

// sendPacket 发送MySQL数据包
func (s *Server) sendPacket(conn net.Conn, payload []byte, sequenceID uint8) error {
	length := uint32(len(payload))
	header := []byte{
		byte(length & 0xff),
		byte((length >> 8) & 0xff),
		byte((length >> 16) & 0xff),
		sequenceID,
	}

	if _, err := conn.Write(header); err != nil {
		return err
	}

	if len(payload) > 0 {
		if _, err := conn.Write(payload); err != nil {
			return err
		}
	}

	return nil
}
