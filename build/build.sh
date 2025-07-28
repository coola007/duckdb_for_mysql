#!/bin/bash

# DuckDB多协议服务器 Ubuntu编译脚本
# 支持Ubuntu 18.04+, 20.04, 22.04

set -e  # 遇到错误立即退出

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目信息
PROJECT_NAME="duckdb-server"
VERSION="1.0.0"
BUILD_DIR="build"
BINARY_NAME="duckdb-server"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  DuckDB Multi-Protocol Server 编译脚本${NC}"
echo -e "${BLUE}  版本: ${VERSION}${NC}"
echo -e "${BLUE}  目标: Ubuntu 18.04+${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# 检测系统信息
echo "检测系统环境..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
    echo -e "${GREEN}系统: $OS $VER${NC}"
else
    echo -e "${RED}无法检测系统版本${NC}"
    exit 1
fi

# 检查是否为root用户
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}警告: 建议使用非root用户运行${NC}"
fi

# 1. 安装系统依赖
echo -e "\n${BLUE}=== 步骤 1: 安装系统依赖 ===${NC}"

install_dependencies() {
    echo "更新包列表..."
    sudo apt-get update

    echo "安装基础依赖..."
    sudo apt-get install -y \
        curl \
        wget \
        git \
        build-essential \
        pkg-config \
        ca-certificates \
        software-properties-common \
        apt-transport-https \
        gnupg \
        lsb-release

    echo "安装编译工具..."
    sudo apt-get install -y \
        gcc \
        g++ \
        make \
        cmake \
        ninja-build \
        clang

    echo "安装开发库..."
    sudo apt-get install -y \
        libssl-dev \
        libcurl4-openssl-dev \
        zlib1g-dev \
        libbz2-dev \
        liblzma-dev \
        libreadline-dev \
        libsqlite3-dev

    echo "安装工具软件..."
    sudo apt-get install -y \
        jq \
        netcat-openbsd \
        htop \
        tree \
        vim

    echo -e "${GREEN}✓ 系统依赖安装完成${NC}"
}

# 2. 安装Go
echo -e "\n${BLUE}=== 步骤 2: 安装Go环境 ===${NC}"

install_go() {
    # 检查Go是否已安装
    if command -v go &> /dev/null; then
        GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
        echo "Go已安装，版本: $GO_VERSION"
        
        # 检查版本是否满足要求 (需要1.19+)
        REQUIRED_VERSION="1.19"
        if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$GO_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
            echo -e "${GREEN}✓ Go版本满足要求${NC}"
            return 0
        else
            echo -e "${YELLOW}Go版本过低，需要升级${NC}"
        fi
    fi

    echo "安装Go 1.21..."
    
    # 下载Go
    GO_VERSION="1.21.6"
    GO_TARBALL="go${GO_VERSION}.linux-amd64.tar.gz"
    
    cd /tmp
    wget -q "https://golang.org/dl/${GO_TARBALL}"
    
    # 删除旧版本
    sudo rm -rf /usr/local/go
    
    # 安装新版本
    sudo tar -C /usr/local -xzf ${GO_TARBALL}
    
    # 设置环境变量
    if ! grep -q "/usr/local/go/bin" ~/.bashrc; then
        echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
        echo 'export GOPATH=$HOME/go' >> ~/.bashrc
        echo 'export PATH=$PATH:$GOPATH/bin' >> ~/.bashrc
    fi
    
    # 当前会话生效
    export PATH=$PATH:/usr/local/go/bin
    export GOPATH=$HOME/go
    export PATH=$PATH:$GOPATH/bin
    
    # 验证安装
    if command -v go &> /dev/null; then
        echo -e "${GREEN}✓ Go安装成功: $(go version)${NC}"
    else
        echo -e "${RED}✗ Go安装失败${NC}"
        exit 1
    fi
    
    # 清理
    rm -f /tmp/${GO_TARBALL}
}

# 3. 安装DuckDB开发库
echo -e "\n${BLUE}=== 步骤 3: 安装DuckDB开发库 ===${NC}"

install_duckdb() {
    echo "安装DuckDB..."
    
    # 添加DuckDB APT仓库
    wget -qO- https://packages.duckdb.org/debian/duckdb.gpg | sudo tee /etc/apt/trusted.gpg.d/duckdb.asc > /dev/null
    echo "deb https://packages.duckdb.org/debian/ stable main" | sudo tee /etc/apt/sources.list.d/duckdb.list
    
    sudo apt-get update
    
    # 安装DuckDB CLI和开发库
    sudo apt-get install -y duckdb libduckdb-dev
    
    # 验证安装
    if command -v duckdb &> /dev/null; then
        echo -e "${GREEN}✓ DuckDB安装成功: $(duckdb --version)${NC}"
    else
        echo -e "${YELLOW}⚠ DuckDB CLI安装失败，尝试手动编译...${NC}"
        install_duckdb_from_source
    fi
}

install_duckdb_from_source() {
    echo "从源码编译DuckDB..."
    
    cd /tmp
    git clone https://github.com/duckdb/duckdb.git
    cd duckdb
    
    # 编译DuckDB
    make release
    
    # 安装
    sudo cp build/release/duckdb /usr/local/bin/
    sudo cp build/release/src/libduckdb*.so /usr/local/lib/
    sudo ldconfig
    
    echo -e "${GREEN}✓ DuckDB源码编译安装完成${NC}"
    
    # 清理
    cd /
    rm -rf /tmp/duckdb
}

# 4. 编译项目
echo -e "\n${BLUE}=== 步骤 4: 编译项目 ===${NC}"

build_project() {
    echo "准备编译环境..."
    
    # 确保在项目目录
    PROJECT_DIR=$(pwd)
    echo "项目目录: $PROJECT_DIR"
    
    # 创建构建目录
    mkdir -p $BUILD_DIR
    
    echo "下载Go依赖..."
    go mod tidy
    go mod download
    
    echo "编译项目..."
    
    # 设置编译参数
    export CGO_ENABLED=1
    export GOOS=linux
    export GOARCH=amd64
    
    # 编译标志
    BUILD_TIME=$(date -u '+%Y-%m-%d_%H:%M:%S')
    GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    
    LDFLAGS="-X main.Version=${VERSION} -X main.BuildTime=${BUILD_TIME} -X main.GitCommit=${GIT_COMMIT} -s -w"
    
    # 编译
    go build -ldflags "$LDFLAGS" -o ${BUILD_DIR}/${BINARY_NAME} .
    
    if [ -f "${BUILD_DIR}/${BINARY_NAME}" ]; then
        echo -e "${GREEN}✓ 编译成功${NC}"
        
        # 显示二进制文件信息
        ls -lh ${BUILD_DIR}/${BINARY_NAME}
        file ${BUILD_DIR}/${BINARY_NAME}
        
        # 测试运行
        echo "测试二进制文件..."
        ${BUILD_DIR}/${BINARY_NAME} --version 2>/dev/null || echo "版本信息获取失败(正常)"
        
    else
        echo -e "${RED}✗ 编译失败${NC}"
        exit 1
    fi
}

# 5. 创建部署包
echo -e "\n${BLUE}=== 步骤 5: 创建部署包 ===${NC}"

create_package() {
    echo "创建部署包..."
    
    PACKAGE_DIR="${BUILD_DIR}/package"
    mkdir -p $PACKAGE_DIR
    
    # 复制二进制文件
    cp ${BUILD_DIR}/${BINARY_NAME} $PACKAGE_DIR/
    
    # 复制配置文件
    cp config.json $PACKAGE_DIR/
    
    # 复制文档
    cp README.md $PACKAGE_DIR/
    cp TESTING.md $PACKAGE_DIR/
    
    # 复制测试脚本
    cp quick_test.sh $PACKAGE_DIR/
    cp test_mysql_protocol.py $PACKAGE_DIR/
    cp mysql_compatibility_test.py $PACKAGE_DIR/
    
    # 创建启动脚本
    cat > $PACKAGE_DIR/start.sh << 'EOF'
#!/bin/bash
# DuckDB服务启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查配置文件
if [ ! -f "config.json" ]; then
    echo "错误: config.json 不存在"
    exit 1
fi

# 启动服务
echo "启动DuckDB多协议服务器..."
./duckdb-server
EOF
    
    chmod +x $PACKAGE_DIR/start.sh
    
    # 创建systemd服务文件
    cat > $PACKAGE_DIR/duckdb-server.service << EOF
[Unit]
Description=DuckDB Multi-Protocol Server
After=network.target

[Service]
Type=simple
User=duckdb
Group=duckdb
WorkingDirectory=/opt/duckdb-server
ExecStart=/opt/duckdb-server/duckdb-server
Restart=always
RestartSec=5
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
EOF
    
    # 创建安装脚本
    cat > $PACKAGE_DIR/install.sh << 'EOF'
#!/bin/bash
# DuckDB服务安装脚本

set -e

echo "安装DuckDB多协议服务器..."

# 创建用户
if ! id "duckdb" &>/dev/null; then
    sudo useradd -r -s /bin/false duckdb
    echo "✓ 创建用户 duckdb"
fi

# 创建目录
sudo mkdir -p /opt/duckdb-server
sudo chown duckdb:duckdb /opt/duckdb-server

# 复制文件
sudo cp duckdb-server /opt/duckdb-server/
sudo cp config.json /opt/duckdb-server/
sudo cp *.sh /opt/duckdb-server/
sudo cp *.py /opt/duckdb-server/ 2>/dev/null || true
sudo cp *.md /opt/duckdb-server/ 2>/dev/null || true

# 设置权限
sudo chown -R duckdb:duckdb /opt/duckdb-server
sudo chmod +x /opt/duckdb-server/duckdb-server
sudo chmod +x /opt/duckdb-server/*.sh

# 安装systemd服务
sudo cp duckdb-server.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "✓ 安装完成"
echo
echo "启动服务:"
echo "  sudo systemctl start duckdb-server"
echo "  sudo systemctl enable duckdb-server"
echo
echo "查看状态:"
echo "  sudo systemctl status duckdb-server"
echo
echo "查看日志:"
echo "  sudo journalctl -u duckdb-server -f"
EOF
    
    chmod +x $PACKAGE_DIR/install.sh
    
    # 创建压缩包
    cd $BUILD_DIR
    tar -czf ${PROJECT_NAME}-${VERSION}-linux-amd64.tar.gz package
    
    echo -e "${GREEN}✓ 部署包创建完成${NC}"
    echo "部署包位置: ${BUILD_DIR}/${PROJECT_NAME}-${VERSION}-linux-amd64.tar.gz"
    ls -lh ${PROJECT_NAME}-${VERSION}-linux-amd64.tar.gz
}

# 6. 运行测试
echo -e "\n${BLUE}=== 步骤 6: 运行测试 ===${NC}"

run_tests() {
    echo "运行编译后测试..."
    
    # 启动服务 (后台)
    echo "启动测试服务..."
    ${BUILD_DIR}/${BINARY_NAME} &
    SERVER_PID=$!
    
    # 等待启动
    sleep 3
    
    # 检查进程
    if ps -p $SERVER_PID > /dev/null; then
        echo -e "${GREEN}✓ 服务启动成功 (PID: $SERVER_PID)${NC}"
        
        # 运行快速测试
        if [ -f "quick_test.sh" ]; then
            echo "运行HTTP API测试..."
            ./quick_test.sh
        fi
        
        # 关闭服务
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
        echo "✓ 测试服务已关闭"
        
    else
        echo -e "${RED}✗ 服务启动失败${NC}"
        return 1
    fi
}

# 主函数
main() {
    # 检查参数
    SKIP_DEPS=false
    SKIP_TESTS=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            --help|-h)
                echo "用法: $0 [选项]"
                echo "选项:"
                echo "  --skip-deps   跳过依赖安装"
                echo "  --skip-tests  跳过测试"
                echo "  --help       显示帮助"
                exit 0
                ;;
            *)
                echo "未知选项: $1"
                exit 1
                ;;
        esac
    done
    
    # 执行构建步骤
    if [ "$SKIP_DEPS" = false ]; then
        install_dependencies
        install_go
        install_duckdb
    else
        echo -e "${YELLOW}跳过依赖安装${NC}"
    fi
    
    build_project
    create_package
    
    if [ "$SKIP_TESTS" = false ]; then
        run_tests
    else
        echo -e "${YELLOW}跳过测试${NC}"
    fi
    
    echo
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  编译完成!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo "编译产物:"
    echo "  二进制文件: ${BUILD_DIR}/${BINARY_NAME}"
    echo "  部署包: ${BUILD_DIR}/${PROJECT_NAME}-${VERSION}-linux-amd64.tar.gz"
    echo
    echo "安装部署:"
    echo "  1. 解压部署包到目标服务器"
    echo "  2. 运行 ./install.sh 安装系统服务"
    echo "  3. 配置 config.json 文件"
    echo "  4. 启动服务: sudo systemctl start duckdb-server"
    echo
    echo "本地测试:"
    echo "  ${BUILD_DIR}/${BINARY_NAME}"
}

# 执行主函数
main "$@" 