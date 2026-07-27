#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

CONTAINER_NAME="geo-audit-service"
COMPOSE=(docker compose -f compose.yaml)

if ! command -v docker >/dev/null 2>&1; then
    echo "错误：未安装 Docker。"
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "错误：未安装 Docker Compose v2（docker compose）。"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "错误：缺少 ${SCRIPT_DIR}/.env。"
    echo "请先执行：cp .env.example .env，并填写数据库及 API 密钥。"
    exit 1
fi

echo ">>> 1/5 拉取最新代码"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git pull --ff-only
else
    echo "当前目录不是 Git 仓库，跳过 git pull。"
fi

echo ">>> 2/5 校验 Compose 配置"
"${COMPOSE[@]}" config --quiet

echo ">>> 3/5 检查旧容器"
if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
    COMPOSE_PROJECT="$(
        docker container inspect \
          --format '{{ index .Config.Labels "com.docker.compose.project" }}' \
          "${CONTAINER_NAME}" 2>/dev/null || true
    )"
    if [ "${COMPOSE_PROJECT}" != "site-geo" ]; then
        echo "发现手工创建的旧容器，移除后迁移到 Compose 管理。"
        docker container rm --force "${CONTAINER_NAME}"
    fi
fi

echo ">>> 4/5 重建镜像并启动容器"
"${COMPOSE[@]}" build --pull
"${COMPOSE[@]}" up \
    --detach \
    --force-recreate \
    --remove-orphans

echo ">>> 5/5 等待健康检查"
for attempt in $(seq 1 18); do
    HEALTH="$(
        docker container inspect \
          --format '{{ if .State.Health }}{{ .State.Health.Status }}{{ else }}unknown{{ end }}' \
          "${CONTAINER_NAME}" 2>/dev/null || true
    )"
    case "${HEALTH}" in
        healthy)
            echo "部署完成：http://127.0.0.1:8023"
            "${COMPOSE[@]}" ps
            exit 0
            ;;
        unhealthy)
            echo "容器健康检查失败，最近日志如下："
            "${COMPOSE[@]}" logs --tail 100 "${CONTAINER_NAME}"
            exit 1
            ;;
        *)
            printf '等待容器启动（%s/18，状态：%s）...\n' "${attempt}" "${HEALTH:-starting}"
            sleep 5
            ;;
    esac
done

echo "等待健康检查超时，最近日志如下："
"${COMPOSE[@]}" logs --tail 100 "${CONTAINER_NAME}"
exit 1
