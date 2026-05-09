#!/bin/bash
# 转行帮 一键启动脚本
# 构建前端 + 启动后端

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "🔨 构建前端..."
cd web
npm run build
cd ..

echo "🚀 启动后端 (http://localhost:8000)..."
source .venv/bin/activate
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
