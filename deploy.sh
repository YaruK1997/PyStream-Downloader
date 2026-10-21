#!/usr/bin/env bash
# PyStream-Downloader Linux/macOS 一鍵部署與啟動腳本
set -euo pipefail

echo "=========================================================="
echo " PyStream-Downloader 容器化部署與執行腳本 (Linux/macOS)    "
echo "=========================================================="

# 1. 檢查 Docker
echo "[1/3] 正在檢測 Docker 運行環境..."
if ! docker info > /dev/null 2>&1; then
    echo "[Error] Docker Daemon 尚未運行，請確認 Docker 服務已啟動。" >&2
    exit 1
fi
echo "[OK] Docker 運行中。"

# 2. 建置映像檔
echo "[2/3] 正在建置 pystream-downloader:latest 映像檔..."
docker build -t pystream-downloader:latest .
echo "[OK] 映像檔建置完成。"

# 3. 準備掛載目錄並執行
echo "[3/3] 準備啟動下載任務..."
mkdir -p ./downloads

if [ $# -gt 0 ]; then
    docker run --rm -it -v "$(pwd)/downloads:/app/downloads" pystream-downloader:latest "$@"
else
    docker run --rm -it -v "$(pwd)/downloads:/app/downloads" pystream-downloader:latest
fi
