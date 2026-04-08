#!/usr/bin/env bash
set -euo pipefail

# 切换到脚本所在目录（项目根目录）
cd "$(dirname "$0")"

DEFAULT_HOST="${HOST:-0.0.0.0}"
DEFAULT_PORT="${PORT:-8023}"
PID_FILE="server.pid"
LOG_FILE="nohup.out"

# 检查 Python 虚拟环境，不存在则自动创建
if [ ! -d ".venv" ]; then
    echo ">>> 未检测到虚拟环境，正在创建 .venv ..."
    python3 -m venv .venv
fi

# 激活虚拟环境
# shellcheck disable=SC1091
source .venv/bin/activate

# 安装/更新依赖
echo ">>> 安装依赖..."
python -m pip install -q -r requirements.txt

# 加载 .env 文件（如果存在）
if [ -f ".env" ]; then
    echo ">>> 加载 .env 配置..."
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

HOST="${HOST:-$DEFAULT_HOST}"
PORT="${PORT:-$DEFAULT_PORT}"
APP_MODULE="${APP_MODULE:-app.main:app}"

# 杀掉占用当前端口的所有进程
PIDS="$(lsof -ti :"${PORT}" 2>/dev/null || true)"
if [ -n "${PIDS:-}" ]; then
    echo ">>> 杀掉占用 ${PORT} 端口的进程（PID: ${PIDS}）"
    echo "${PIDS}" | xargs kill -9
fi
rm -f "${PID_FILE}"

# 询问是否为生产环境
IS_PROD="${IS_PROD:-}"
if [ -t 0 ]; then
    read -r -p ">>> 是否以生产模式启动？[y/N] " IS_PROD || true
else
    IS_PROD="${IS_PROD:-N}"
    echo ">>> 未检测到交互终端，默认以开发模式启动（可通过 IS_PROD=y 覆盖）"
fi

echo ""
echo "=========================================="
echo "  GEO Audit Service 启动中..."
echo "  访问地址: http://127.0.0.1:${PORT}"
echo "  API 文档: http://127.0.0.1:${PORT}/docs"
echo "  健康检查: http://127.0.0.1:${PORT}/health"

if [[ "${IS_PROD}" =~ ^[Yy]$ ]]; then
    echo "  模式: 生产（后台常驻进程）"
    echo "  日志: ${LOG_FILE}"
    echo "  停止: kill \$(cat ${PID_FILE})"
else
    echo "  模式: 开发（--reload，按 Ctrl+C 停止）"
fi

echo "=========================================="
echo ""

# 启动服务
if [[ "${IS_PROD}" =~ ^[Yy]$ ]]; then
    nohup uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}" > "${LOG_FILE}" 2>&1 &
    echo $! > "${PID_FILE}"
    echo ">>> 服务已在后台启动，PID: $(cat "${PID_FILE}")"
else
    exec uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}" --reload
fi
