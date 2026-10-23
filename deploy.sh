#!/usr/bin/env bash
# PyStream-Downloader Linux/macOS 一鍵部署與自適應啟動腳本
set -uo pipefail

echo "=========================================================="
echo " PyStream-Downloader 容器化智慧調度腳本 (Linux/macOS)     "
echo "=========================================================="

# 1. 檢查 Docker
echo "[1/3] 正在檢測 Docker 運行環境..."
if ! docker info > /dev/null 2>&1; then
    echo "[Error] Docker Daemon 尚未運行，請確認 Docker 服務已啟動。" >&2
    exit 1
fi
echo "[OK] Docker 運行中。"

# 2. 準備下載目錄
mkdir -p ./downloads

# 檢查是否帶有 --full 參數強制走完整版
USE_FULL=false
FILTERED_ARGS=()
for arg in "$@"; do
    if [ "$arg" == "--full" ]; then
        USE_FULL=true
    else
        FILTERED_ARGS+=("$arg")
    fi
done

# 3. 執行容器
if [ "$USE_FULL" = true ]; then
    echo "[INFO] 以完整版容器直接啟動 (--profile full)..."
    docker-compose --profile full run --rm downloader-full "${FILTERED_ARGS[@]}"
    exit $?
fi

# 預設以輕量版容器執行
echo "[INFO] 啟動預設輕量容器 (downloader:slim)..."
docker-compose run --rm downloader "${FILTERED_ARGS[@]}"
EXIT_STATUS=$?

# 雙階段自適應晉升：若捕獲狀態碼 42，自動升級至 full 容器
if [ $EXIT_STATUS -eq 42 ]; then
    echo -e "\n\033[1;33m[Auto-Detect] 捕獲晉升信號 (Exit Code 42)：目標網頁需無頭瀏覽器動態嗅探。\033[0m"
    echo -e "\033[1;36m[Auto-Detect] 自動升級為完整版容器 (profile: full) 接續執行...\033[0m"
    docker-compose --profile full run --rm downloader-full "${FILTERED_ARGS[@]}"
    exit $?
fi

exit $EXIT_STATUS
