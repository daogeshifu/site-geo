#!/usr/bin/env bash
set -euo pipefail

# 切换到脚本所在目录（项目根目录）
cd "$(dirname "$0")"

DEFAULT_HOST="${HOST:-0.0.0.0}"
DEFAULT_PORT="${PORT:-8023}"
PID_FILE="server.pid"
LOG_FILE="nohup.out"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo ">>> 未找到 ${PYTHON_BIN}，请先安装 Python 3，或通过 PYTHON_BIN=/path/to/python3 指定解释器"
    exit 1
fi

if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
    echo ">>> 当前 ${PYTHON_BIN} 版本过低：$("${PYTHON_BIN}" --version 2>&1)"
    echo ">>> 本项目要求 Python 3.10+，推荐 Python 3.11"
    echo ">>> 可选方案："
    echo ">>> 1) 安装 python3.10 / python3.11 后用 PYTHON_BIN=python3.11 ./start.sh"
    echo ">>> 2) 直接使用 Docker 启动（Dockerfile 基于 python:3.11-slim）"
    exit 1
fi

# 检查 Python 虚拟环境，不存在则自动创建
if [ ! -d ".venv" ]; then
    echo ">>> 未检测到虚拟环境，正在创建 .venv ..."
    "${PYTHON_BIN}" -m venv .venv
fi

# 激活虚拟环境
# shellcheck disable=SC1091
source .venv/bin/activate

VENV_PYTHON=".venv/bin/python"

if ! "${VENV_PYTHON}" -c 'import sys; raise SystemExit(0 if sys.version_info.major == 3 else 1)' >/dev/null 2>&1; then
    echo ">>> 当前 .venv 不是 Python 3 环境，请删除 .venv 后重试，或重新指定正确的 PYTHON_BIN"
    exit 1
fi

if ! "${VENV_PYTHON}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
    echo ">>> 当前 .venv Python 版本过低：$("${VENV_PYTHON}" --version 2>&1)"
    echo ">>> 请删除 .venv 后，使用 Python 3.10+ 重新创建，例如："
    echo ">>> rm -rf .venv && PYTHON_BIN=python3.11 ./start.sh"
    exit 1
fi

echo ">>> 当前 Python: $("${VENV_PYTHON}" --version 2>&1)"

has_runtime_deps() {
    "${VENV_PYTHON}" - <<'PY' >/dev/null 2>&1
import fastapi
import uvicorn
import pydantic
import httpx
import bs4
import lxml
import tenacity
import tldextract
import orjson
import dotenv
import pythonjsonlogger
PY
}

SKIP_PIP_INSTALL="${SKIP_PIP_INSTALL:-}"
FORCE_PIP_INSTALL="${FORCE_PIP_INSTALL:-}"

if [[ "${SKIP_PIP_INSTALL}" =~ ^([Yy]|1|true|TRUE)$ ]]; then
    echo ">>> 已设置 SKIP_PIP_INSTALL，跳过依赖安装"
elif [[ "${FORCE_PIP_INSTALL}" =~ ^([Yy]|1|true|TRUE)$ ]]; then
    echo ">>> 强制安装依赖..."
    "${VENV_PYTHON}" -m pip install -q -r requirements.txt
elif has_runtime_deps; then
    echo ">>> 检测到运行依赖已存在，跳过依赖安装（如需强制更新可设置 FORCE_PIP_INSTALL=1）"
else
    echo ">>> 安装依赖..."
    if ! "${VENV_PYTHON}" -m pip install -q -r requirements.txt; then
        echo ">>> 依赖安装失败：服务器可能无法访问 PyPI / DNS 不通"
        echo ">>> 如果依赖其实已经装好，可使用 SKIP_PIP_INSTALL=1 ./start.sh"
        echo ">>> 如果是离线环境，请先准备 wheel 包或可访问的私有镜像源"
        exit 1
    fi
fi

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
    nohup "${VENV_PYTHON}" -m uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}" > "${LOG_FILE}" 2>&1 &
    echo $! > "${PID_FILE}"
    echo ">>> 服务已在后台启动，PID: $(cat "${PID_FILE}")"
else
    exec "${VENV_PYTHON}" -m uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}" --reload
fi
