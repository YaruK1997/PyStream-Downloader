# PyStream-Downloader 容器化與環境部署指南 (Deployment Guide)

本文件依據 `workflow.md` 階段 5（容器化及部署 - 負責模型：Gemini 3.8 Flash）之規範編寫，提供 Docker 容器、Docker Compose 與本地裸機之部署作業標準規範。

---

## 1. 部署架構拓撲圖 (Deployment Topology ASCII)

```text
+-------------------------------------------------------------------------------+
|                    PyStream-Downloader 容器部署架構 (ASCII)                     |
+-------------------------------------------------------------------------------+

       [ 使用者終端 CLI (Windows PowerShell / Linux Terminal) ]
                                  │
                                  ▼
       +─────────────────────────────────────────────────────────+
       | Docker Host / Compose 編排層                            |
       | - 映射終端 TTY (-it / stdin_open) 支援互動選單與熱鍵暫停   |
       | - Volume 掛載: ./downloads <───> /app/downloads         |
       +─────────────────────────────────────────────────────────+
                                  │
                                  ▼
       +─────────────────────────────────────────────────────────+
       | 容器內部環境 (pystream-downloader:latest)                |
       | - 基礎映像檔: python:3.10-slim                           |
       | - 系統套件: FFmpeg 6.x+, ca-certificates, curl           |
       | - Python 環境: yt-dlp, psutil, curl_cffi, playwright     |
       | - 安全身份: 非 root 帳號 appuser (UID 1000)              |
       | - 健康檢查 (Healthcheck): 探針檢測 FFmpeg 與模組完整性   |
       +─────────────────────────────────────────────────────────+
                                  │
                                  ▼
                    [ 本地磁碟 ./downloads/*.mp4 ]
+-------------------------------------------------------------------------------+
```

---

## 2. 部署方式一：一鍵腳本部署 (推薦)

### Windows 環境 (PowerShell)
```powershell
# 1. 僅建置映像檔
.\deploy.ps1 -BuildOnly

# 2. 互動式執行下載
.\deploy.ps1

# 3. 帶參數直接下載特定串流與畫質
.\deploy.ps1 -Url "https://www.youtube.com/watch?v=xxxx" -Quality "1080p"
```

### Linux / macOS 環境 (Bash)
```bash
# 賦予執行權限
chmod +x deploy.sh

# 啟動容器
./deploy.sh "https://www.youtube.com/watch?v=xxxx" -q 1080p
```

---

## 3. 部署方式二：Docker Compose 標準編排

### 建置並運行互動模式
```bash
# 互動式執行
docker-compose run --rm pystream-downloader "https://example.com/stream"

# 靜默背景執行 (自動監聽開播 + 最優畫質)
docker-compose run --rm -d pystream-downloader "https://example.com/stream" --wait -q best
```

---

## 4. 部署方式三：本地 Python 原生執行 (無 Docker)

### 系統環境要求
1. **Python**：>= 3.9
2. **FFmpeg**：確保 `ffmpeg` 與 `ffprobe` 已安裝並加入系統 PATH。

### 安裝與啟動
```bash
# 1. 安裝相依套件與 Playwright 嗅探用 Chromium 瀏覽器
pip install -r requirements.txt
playwright install chromium

# 2. 啟動程式 (支援 YouTube、Twitch 與動態混淆站點如 MissAV)
python main.py "https://example.com/stream"
```

---

## 5. 健康檢查與容器監控 (Healthcheck)

容器內建自定義 Healthcheck 探針：
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import yt_dlp, psutil, curl_cffi, playwright, shutil; assert shutil.which('ffmpeg')" || exit 1
```

檢驗指令：
```bash
docker inspect --format='{{json .State.Health}}' pystream-downloader
```
正常回傳狀態為 `"Status": "healthy"`。

---

## 6. 常見問題與排查 (Troubleshooting)

| 異常現象 | 根本原因 | 建議處置方式 |
| :--- | :--- | :--- |
| **Windows 提示 Docker API 未連線** | Docker Desktop 服務尚未啟動 | 啟動 Docker Desktop，等待右下角鯨魚圖標變綠後重試。 |
| **下載檔案未出現在主機** | Volume 掛載路徑錯誤 | 確保命令中包含 `-v "$(pwd)/downloads:/app/downloads"`。 |
| **容器內無法暫停串流** | 未附加 TTY / 終端 | 啟動時必須加上 `-it`（Compose 請確保配置 `stdin_open: true` 與 `tty: true`）。 |
| **遭遇 Cloudflare 403 Challenge** | 目標網站開啟了 WAF 防護 | 容器內預設已安裝 `curl_cffi` 並自動啟用 Chrome 偽裝；若遇硬性 Turnstile 驗證，可傳入 `--cookies-from-browser` 或改用已提取之 m3u8 直鏈。 |

---

## 7. 階段 5 檢核簽署 (Sign-Off)

- [x] **Dockerfile 構建合規**：多階段/輕量化，包含非 root 使用者與 Healthcheck 探針。
- [x] **Compose 配置健全**：Volume 持久化與 TTY 支援完備。
- [x] **多平台腳本就緒**：`deploy.ps1` 與 `deploy.sh` 皆完成撰寫。
- [x] **全流程交付達成**：五階段協作工作流程正式閉環完成 (Done)。
