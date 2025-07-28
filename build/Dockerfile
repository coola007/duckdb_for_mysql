# DuckDB Multi-Protocol Server Dockerfile
# 多阶段构建，优化镜像大小

# 构建阶段
FROM ubuntu:22.04 AS builder

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    pkg-config \
    ca-certificates \
    gcc \
    g++ \
    make \
    cmake \
    libssl-dev \
    libcurl4-openssl-dev \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libreadline-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Go
RUN wget -O /tmp/go.tar.gz https://golang.org/dl/go1.21.6.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz

ENV PATH=/usr/local/go/bin:$PATH
ENV GOPATH=/go
ENV PATH=$PATH:$GOPATH/bin

# 安装DuckDB开发库
RUN wget -qO- https://packages.duckdb.org/debian/duckdb.gpg | tee /etc/apt/trusted.gpg.d/duckdb.asc > /dev/null && \
    echo "deb https://packages.duckdb.org/debian/ stable main" | tee /etc/apt/sources.list.d/duckdb.list && \
    apt-get update && \
    apt-get install -y duckdb libduckdb-dev && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /build

# 复制go模块文件
COPY go.mod go.sum ./

# 下载依赖
RUN go mod download

# 复制源代码
COPY . .

# 构建应用
RUN CGO_ENABLED=1 GOOS=linux go build \
    -ldflags "-s -w -X main.Version=1.0.0 -X main.BuildTime=$(date -u '+%Y-%m-%d_%H:%M:%S')" \
    -o duckdb-server .

# 运行阶段
FROM ubuntu:22.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TZ=UTC

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    jq \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# 安装DuckDB运行时库
RUN wget -qO- https://packages.duckdb.org/debian/duckdb.gpg | tee /etc/apt/trusted.gpg.d/duckdb.asc > /dev/null && \
    echo "deb https://packages.duckdb.org/debian/ stable main" | tee /etc/apt/sources.list.d/duckdb.list && \
    apt-get update && \
    apt-get install -y libduckdb && \
    rm -rf /var/lib/apt/lists/*

# 创建应用用户
RUN useradd -r -s /bin/false -m -d /app duckdb

# 创建应用目录
WORKDIR /app

# 从构建阶段复制二进制文件
COPY --from=builder /build/duckdb-server /app/
COPY --from=builder /build/config.json /app/

# 创建数据目录
RUN mkdir -p /app/data && \
    chown -R duckdb:duckdb /app

# 切换到应用用户
USER duckdb

# 暴露端口
EXPOSE 8080 3366

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 启动命令
CMD ["./duckdb-server"] 