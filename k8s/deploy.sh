#!/bin/bash

# DuckDB Multi-Protocol Server Kubernetes 部署脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
NAMESPACE="duckdb-system"
IMAGE_NAME="duckdb-server"
IMAGE_TAG="latest"
REGISTRY=""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  DuckDB K8s 部署脚本${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl 未安装${NC}"
    exit 1
fi

# 检查集群连接
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ 无法连接到Kubernetes集群${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Kubernetes集群连接正常${NC}"

# 函数定义
deploy_resources() {
    echo -e "\n${BLUE}=== 部署Kubernetes资源 ===${NC}"
    
    # 1. 创建命名空间
    echo "创建命名空间..."
    kubectl apply -f k8s/namespace.yaml
    
    # 2. 创建存储
    echo "创建存储资源..."
    kubectl apply -f k8s/pv.yaml
    
    # 3. 创建配置
    echo "创建配置映射..."
    kubectl apply -f k8s/configmap.yaml
    
    # 4. 创建部署
    echo "创建应用部署..."
    kubectl apply -f k8s/deployment.yaml
    
    # 5. 创建服务
    echo "创建服务..."
    kubectl apply -f k8s/service.yaml
    
    # 6. 创建Ingress (可选)
    if [ -f "k8s/ingress.yaml" ]; then
        echo "创建Ingress..."
        kubectl apply -f k8s/ingress.yaml
    fi
    
    echo -e "${GREEN}✅ 所有资源部署完成${NC}"
}

build_and_push_image() {
    echo -e "\n${BLUE}=== 构建和推送镜像 ===${NC}"
    
    if [ -n "$REGISTRY" ]; then
        FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    else
        FULL_IMAGE_NAME="$IMAGE_NAME:$IMAGE_TAG"
    fi
    
    echo "构建镜像: $FULL_IMAGE_NAME"
    docker build -t $FULL_IMAGE_NAME .
    
    if [ -n "$REGISTRY" ]; then
        echo "推送镜像到注册表..."
        docker push $FULL_IMAGE_NAME
    fi
    
    echo -e "${GREEN}✅ 镜像构建完成${NC}"
}

wait_for_deployment() {
    echo -e "\n${BLUE}=== 等待部署就绪 ===${NC}"
    
    echo "等待DuckDB服务器就绪..."
    kubectl wait --for=condition=available --timeout=300s deployment/duckdb-server -n $NAMESPACE
    
    echo "等待Nginx代理就绪..."
    kubectl wait --for=condition=available --timeout=300s deployment/nginx-proxy -n $NAMESPACE
    
    echo -e "${GREEN}✅ 所有部署就绪${NC}"
}

show_status() {
    echo -e "\n${BLUE}=== 部署状态 ===${NC}"
    
    echo "Pod状态:"
    kubectl get pods -n $NAMESPACE -o wide
    
    echo -e "\n服务状态:"
    kubectl get services -n $NAMESPACE
    
    echo -e "\n部署状态:"
    kubectl get deployments -n $NAMESPACE
    
    # 获取访问信息
    echo -e "\n${BLUE}=== 访问信息 ===${NC}"
    
    # HTTP API端口转发
    echo "HTTP API访问 (端口转发):"
    echo "  kubectl port-forward -n $NAMESPACE service/duckdb-server 8080:8080"
    echo "  然后访问: http://localhost:8080/health"
    
    # MySQL协议端口转发
    echo -e "\nMySQL协议访问 (端口转发):"
    echo "  kubectl port-forward -n $NAMESPACE service/duckdb-server 3366:3366"
    echo "  然后使用: mysql -h localhost -P 3366 -u root"
    
    # NodePort访问 (如果配置了)
    MYSQL_NODEPORT=$(kubectl get service duckdb-mysql-nodeport -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "")
    if [ -n "$MYSQL_NODEPORT" ]; then
        echo -e "\nMySQL协议访问 (NodePort):"
        echo "  mysql -h <NODE_IP> -P $MYSQL_NODEPORT -u root"
    fi
    
    # LoadBalancer访问 (如果配置了)
    LB_IP=$(kubectl get service nginx-proxy -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    if [ -n "$LB_IP" ]; then
        echo -e "\nLoadBalancer访问:"
        echo "  http://$LB_IP/"
    fi
}

run_tests() {
    echo -e "\n${BLUE}=== 运行测试 ===${NC}"
    
    # 创建测试Pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: duckdb-test-runner
  namespace: $NAMESPACE
spec:
  restartPolicy: Never
  containers:
  - name: test-client
    image: ubuntu:22.04
    command: ["/bin/bash"]
    args: ["-c", "apt-get update && apt-get install -y curl python3 python3-pip mysql-client && pip3 install requests && sleep 3600"]
    volumeMounts:
    - name: test-scripts
      mountPath: /tests
  volumes:
  - name: test-scripts
    configMap:
      name: test-scripts
      defaultMode: 0755
EOF
    
    # 等待测试Pod就绪
    kubectl wait --for=condition=ready pod/duckdb-test-runner -n $NAMESPACE --timeout=120s
    
    # 运行HTTP API测试
    echo "运行HTTP API测试..."
    kubectl exec -n $NAMESPACE duckdb-test-runner -- curl -f http://duckdb-server:8080/health
    
    # 运行MySQL协议测试 (如果有测试脚本)
    if [ -f "test/mysql_protocol_test.py" ]; then
        echo "运行MySQL协议测试..."
        kubectl cp test/mysql_protocol_test.py $NAMESPACE/duckdb-test-runner:/tmp/mysql_test.py
        kubectl exec -n $NAMESPACE duckdb-test-runner -- python3 /tmp/mysql_test.py --host duckdb-server --port 3366
    fi
    
    # 清理测试Pod
    kubectl delete pod duckdb-test-runner -n $NAMESPACE --ignore-not-found=true
    
    echo -e "${GREEN}✅ 测试完成${NC}"
}

cleanup() {
    echo -e "\n${BLUE}=== 清理资源 ===${NC}"
    
    read -p "确定要删除所有DuckDB相关资源吗? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete namespace $NAMESPACE --ignore-not-found=true
        echo -e "${GREEN}✅ 资源清理完成${NC}"
    else
        echo "取消清理操作"
    fi
}

scale_deployment() {
    local replicas=${1:-2}
    echo -e "\n${BLUE}=== 扩缩容部署 ===${NC}"
    
    echo "扩缩容DuckDB服务器到 $replicas 个副本..."
    kubectl scale deployment duckdb-server --replicas=$replicas -n $NAMESPACE
    
    echo "等待扩缩容完成..."
    kubectl wait --for=condition=available --timeout=300s deployment/duckdb-server -n $NAMESPACE
    
    echo -e "${GREEN}✅ 扩缩容完成${NC}"
}

show_logs() {
    echo -e "\n${BLUE}=== 查看日志 ===${NC}"
    
    echo "DuckDB服务器日志:"
    kubectl logs -n $NAMESPACE -l app=duckdb-server --tail=20
    
    echo -e "\nNginx代理日志:"
    kubectl logs -n $NAMESPACE -l app=nginx-proxy --tail=20
}

# 主函数
main() {
    case "${1:-deploy}" in
        "build")
            build_and_push_image
            ;;
        "deploy")
            deploy_resources
            wait_for_deployment
            show_status
            ;;
        "status")
            show_status
            ;;
        "test")
            run_tests
            ;;
        "logs")
            show_logs
            ;;
        "scale")
            scale_deployment ${2:-2}
            ;;
        "cleanup")
            cleanup
            ;;
        "all")
            build_and_push_image
            deploy_resources
            wait_for_deployment
            show_status
            run_tests
            ;;
        *)
            echo "用法: $0 {build|deploy|status|test|logs|scale|cleanup|all}"
            echo ""
            echo "命令说明:"
            echo "  build    - 构建和推送Docker镜像"
            echo "  deploy   - 部署到Kubernetes"
            echo "  status   - 查看部署状态"
            echo "  test     - 运行测试"
            echo "  logs     - 查看日志"
            echo "  scale    - 扩缩容 (用法: scale <副本数>)"
            echo "  cleanup  - 清理所有资源"
            echo "  all      - 执行完整部署流程"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@" 