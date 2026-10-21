# PyStream-Downloader 容器化與環境部署指南 (Deployment Guide)

本文件依據 `workflow.md` 階段 5（容器化及部署 - 負責模型：Gemini 3.8 Flash）之規範編寫，提供 Docker 雙層容器架構、Docker Compose 與本地裸機之部署作業標準規範。

---

## 1. 雙層自適應部署架構拓撲圖 (Dual-Tier Adaptive Architecture ASCII)

```text
+-------------------------------------------------------------------------------+
|             PyStream-Downloader 雙層自適應容器部署架構 (v1.3.0) (ASCII)        |
+-------------------------------------------------------------------------------+

       [ 使用者調度進入點: deploy.ps1 / deploy.sh / CLI ]
                                   │
                                   ▼
             ┌───────────────────────────────────────────┐
             │ 第一階段: 預設輕量容器 (downloader:slim) │
             │ 體積: ~420MB | 啟動: 瞬時 (<1s)           │
             │ 特性: yt-dlp + curl_cffi + FFmpeg 6.x     │
             └─────────────────────┬─────────────────────┘
                                   │
                     網址是否支援原生解析？
                      ├──────────────────────────┐
                      ▼ 是                       ▼ 否 (Unsupported URL)
             [ 正常下載串流 .mp4 ]         [ 拋出 NeedsFullSnifferError ]
                                                 │
                                                 ▼ (Exit Code 42)
             ┌───────────────────────────────────────────┐
             │ 第二階段: 自動觸發全功能嗅探容器升級      │
             │ docker-compose --profile full run         │
             │                 downloader-full           │
             │ 體積: ~1.4GB | 特性: Playwright Chromium  │
             │ 配置: shm_size: 2gb, ipc: host            │
             └─────────────────────┬─────────────────────┘
                                   │
                                   ▼ (嗅探獲取動態直鏈 & Headers)
             [ 正常下載混淆動態串流 .mp4 (無縫落盤 ./downloads) ]
+-------------------------------------------------------------------------------+
```

---

## 2. 部署方式一：一鍵自適應腳本部署 (推薦)

智慧調度腳本（`deploy.ps1` 與 `deploy.sh`）具備自動感應機制：
- 預設先以輕量 `downloader` 執行。
- 若偵測到 **Exit Code 42**（動態混淆站點需要無頭瀏覽器），調度器自動透明切換至 `downloader-full`，使用者無須手動重複輸入指令。

### Windows 環境 (PowerShell)
```powershell
# 1. 互動式執行下載 (自動偵測並自適應升級)
.\deploy.ps1

# 2. 帶參數直接下載特定串流 (遇動態混淆站點如 MissAV 自動升級)
.\deploy.ps1 -Url "https://missav.ai/gvh-852" -Quality "1080p"

# 3. 明確指定使用全功能 Chromium 容器 (跳過一階段輕量嘗試)
.\deploy.ps1 -Url "https://missav.ai/gvh-852" -Full

# 4. 僅建置映像檔
.\deploy.ps1 -BuildOnly
```

### Linux / macOS 環境 (Bash)
```bash
# 賦予執行權限
chmod +x deploy.sh

# 1. 啟動自適應下載
./deploy.sh "https://www.youtube.com/watch?v=xxxx" -q 1080p

# 2. 直接指定全功能容器
./deploy.sh --full "https://missav.ai/gvh-852"
```

---

## 3. 部署方式二：Docker Compose 標準編排

### 1. 輕量快速下載 (適用 90%+ 主流標準站點)
```bash
# 互動式執行輕量容器 (~420MB)
docker-compose run --rm downloader "https://www.youtube.com/watch?v=xxxx"

# 背景守護監聽開播
docker-compose run --rm -d downloader "https://www.youtube.com/watch?v=xxxx" --wait -q best
```

### 2. 全功能嗅探下載 (適用 MissAV 等動態 JS 混淆站點)
```bash
# 啟動含 Playwright Chromium 的全功能容器 (~1.4GB)
docker-compose --profile full run --rm downloader-full "https://missav.ai/gvh-852"
```

### 服務配置對比

| 配置項 | `downloader` (輕量服務) | `downloader-full` (全功能服務) |
| :--- | :--- | :--- |
| **Dockerfile Target** | `slim` | `full` |
| **映像檔預估大小** | ~420 MB | ~1.4 GB |
| **啟動開銷** | 瞬時 (< 1 秒) | 較重 (~2-3 秒) |
| **Playwright/Chromium**| ❌ 無 | ✔️ 內建 Chromium + 依賴 |
| **記憶體/IPC 設置** | 預設標準 | `shm_size: 2gb`, `ipc: host` |
| **預設啟動** | ✔️ 是 (`docker-compose run`) | 需 `--profile full` 啟用 |

---

## 4. 部署方式三：本地 Python 原生執行 (無 Docker)

### 系統環境要求
1. **Python**：>= 3.9
2. **FFmpeg**：確保 `ffmpeg` 與 `ffprobe` 已安裝並加入系統 PATH。

### 安裝選擇

#### 選擇 A：僅標準輕量功能
```bash
pip install -r requirements.txt
python main.py "https://www.youtube.com/watch?v=xxxx"
```

#### 選擇 B：含動態嗅探全功能
```bash
pip install -r requirements-full.txt
playwright install chromium
python main.py "https://missav.ai/gvh-852"
```

---

## 5. 健康檢查與容器監控 (Healthcheck)

容器內建自定義 Healthcheck 探針：
- **Slim 容器**：
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
      CMD python -c "import yt_dlp, psutil, curl_cffi, shutil; assert shutil.which('ffmpeg')" || exit 1
  ```
- **Full 容器**：
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
      CMD python -c "import yt_dlp, psutil, curl_cffi, playwright, shutil; assert shutil.which('ffmpeg')" || exit 1
  ```

檢驗指令：
```bash
docker inspect --format='{{json .State.Health}}' pystream-downloader-slim
```
正常回傳狀態為 `"Status": "healthy"`。

---

## 6. 常見問題與排查 (Troubleshooting)

| 異常現象 | 根本原因 | 建議處置方式 |
| :--- | :--- | :--- |
| **退出代碼 42 (Exit Code 42)** | 輕量容器解析遇動態混淆站點 | 正常現象。調度腳本會自動升級至 `downloader-full`，或直接使用 `deploy.ps1 -Full`。 |
| **Chromium 崩潰 (Aw, Snap!)** | Docker 預設 `/dev/shm` (64MB) 耗盡 | 確保使用 `docker-compose.yml` 中的 `shm_size: '2gb'` 或啟動 Docker 時加上 `--shm-size=2gb`。 |
| **Windows 提示 Docker API 未連線** | Docker Desktop 服務尚未啟動 | 啟動 Docker Desktop，等待右下角圖標變綠後重試。 |
| **下載檔案未出現在主機** | Volume 掛載路徑錯誤 | 確保命令中包含 `-v "$(pwd)/downloads:/app/downloads"`。 |
| **容器內無法暫停串流** | 未附加 TTY / 終端 | 啟動時必須加上 `-it`（Compose 請確保配置 `stdin_open: true` 與 `tty: true`）。 |

---

## 7. 階段 5 檢核簽署 (Sign-Off)

- [x] **Dockerfile 多階段構建合規**：`slim`（420MB）與 `full`（1.4GB）分離，非 root 使用者與獨立健康探針。
- [x] **Compose 雙 Profile 健全**：`downloader` 與 `downloader-full` 職責分明，共享記憶體安全調優。
- [x] **智慧升級腳本就緒**：`deploy.ps1` 與 `deploy.sh` 支援 Exit Code 42 捕獲與自適應調度。
- [x] **全流程交付達成**：五階段協作工作流程正式閉環完成 (Done)。
