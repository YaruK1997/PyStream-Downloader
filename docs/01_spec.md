# Python + FFmpeg 智慧串流下載工具 (PyStream-Downloader) 需求規格說明書 (PRD / Spec)

本文件依據 `workflow.md` 階段 1（需求明確化 / 最佳化）之規範制定，定義整合 `yt-dlp`、`FFmpeg` 與 Python 守護進程之影音串流下載工具核心架構、功能邊界與驗收標準。

---

## 1. 系統架構與流程圖 (System Architecture ASCII)

```text
+-------------------------------------------------------------------------------+
|                 PyStream-Downloader 系統資料流與狀態轉移架構                    |
+-------------------------------------------------------------------------------+

                 [ 使用者輸入: 串流/影片網址 (URL) + CLI 參數 ]
                                       │
                                       ▼
       +---------------------------------------------------------------+
       | 模組 1: 開播監聽器 (Live Stream Watcher)                        |
       | - 探測串流狀態: [即時串流 / 預排首播 Upcoming / 離線 Offline]     |
       | - 若為未開播: 啟動定時輪詢 (預設 15s 倒數)，直到偵測到串流訊號   |
       +---------------------------------------------------------------+
                                       │ (串流正式開播 / 一般點播影片)
                                       ▼
       +---------------------------------------------------------------+
       | 模組 2: 格式解析與畫質選擇器 (Quality Selector)                 |
       | - 調用 yt-dlp 提取可用 Formats (解析度、碼率、音訊編碼、容器格式) |
       | - 互動模式: 終端印出格式選單供輸入編號選擇                      |
       | - 靜默模式: 依 CLI `--quality` 或預設最優 (best) 自動匹配        |
       +---------------------------------------------------------------+
                                       │ (解析出目標串流直連 URL)
                                       ▼
       +---------------------------------------------------------------+
       | 模組 3: 下載守護與控制引擎 (Supervisor & Downloader)            |
       |                                                               |
       | [主執行緒 / 背景監控]              [子進程 FFmpeg Worker]      |
       | - 鍵盤監聽 (Space / 'p' 鍵)        - 參數: -reconnect 1        |
       |   調用 psutil 凍結/喚醒進程              -reconnect_streamed 1 |
       | - 監控進程 exit code                    -reconnect_delay_max 10|
       | - 異常中斷觸發斷點重連 (最多 5 次)      -c copy -f mp4 ...     |
       +---------------------------------------------------------------+
                                       │ (下載完成 / 使用者結束)
                                       ▼
       +---------------------------------------------------------------+
       | 模組 4: 檔案整合與輸出檢驗 (File Finalizer)                    |
       | - 檢查輸出檔案完整性 (MOOV Atom / 檔案大小 > 0)                |
       | - 檔名清理 (過濾非法字元) 並保存至指定目錄                      |
       +---------------------------------------------------------------+
                                       │
                                       ▼
                           [ 本地成品影片 (.mp4) ]
+-------------------------------------------------------------------------------+
```

---

## 2. 核心功能規格詳細說明

### F1. 開播監聽模組 (Wait-for-Live Stream Watcher)
- **目標場景**：鎖定尚未開始的 YouTube 直播或即時串流，自動在背景等候，無須人工反覆刷新。
- **核心行為**：
  1. 輸入 URL 後，先以 `yt-dlp --dump-json` 或 Python API 探測來源 `live_status`。
  2. 若狀態為 `is_upcoming` 或 `post_live` 或取得 HTTP 404/串流離線：
     - 提示：「串流尚未開始，已啟動開播監聽...」
     - 啟動非阻塞輪詢計時器（間隔預設 15 秒，可由 `--poll-interval` 自訂）。
     - 終端輸出動態倒數與重試次數，避免使用者誤判卡死。
  3. 一旦檢測到 `is_live` 或 Master Playlist 可正常下載，立即發出提示音（可選）並無縫切入 **F2**。

### F2. 格式解析與畫質選擇器 (Format & Quality Inspector)
- **目標場景**：支援使用者依網路狀況或儲存空間自由選擇畫質。
- **核心行為**：
  1. 利用 `yt-dlp` 解析來源所提供的完整 format 清單。
  2. **過濾與排序**：按解析度（1080p、720p、480p 等）及視頻編碼排序，剔除僅音訊或無效格式（但支援單獨音訊提取選項）。
  3. **互動選單**：若使用者未傳入 `--quality`，在終端條列：
     ```text
     [0] Best Quality (自動選擇最高畫質 + 最佳音軌)
     [1] 1080p (1920x1080, avc1, ~4500k)
     [2] 720p  (1280x720,  avc1, ~2500k)
     [3] 480p  (854x480,   avc1, ~1000k)
     請輸入畫質選項 [0-3] (預設 0):
     ```
  4. 解析出最佳之視訊/音訊流網址（如 HLS m3u8 URL 或直連 CDN URL）。

### F3. 下載守護引擎 (Downloader Engine & FFmpeg Worker)
- **目標場景**：以最低 CPU/記憶體消耗錄製串流，不進行二次轉碼（Remux Only）。
- **FFmpeg 核心參數**：
  ```bash
  ffmpeg -y \
    -reconnect 1 \
    -reconnect_at_eof 1 \
    -reconnect_streamed 1 \
    -reconnect_delay_max 10 \
    -i "<TARGET_STREAM_URL>" \
    -c copy \
    -bsf:a aac_adtstoasc \
    -movflags +faststart \
    "<OUTPUT_PATH>.mp4"
  ```
- **進度回饋**：解析 FFmpeg stderr 之 `time=... bitrate=... speed=...` 格式日誌，於終端以單行刷新顯示目前下載時長與檔案累積大小。

### F4. 斷線重試與斷點續傳機制 (Disconnection Retry & Auto-Recovery)
- **雙層容錯架構**：
  - **第一層 (FFmpeg 原生)**：配置 `-reconnect_streamed 1 -reconnect_delay_max 10`，因應短暫封包遺失或小於 10 秒之網路震盪，FFmpeg 自行恢復。
  - **第二層 (Python 守護進程)**：
    - 若網路中斷超時導致 FFmpeg 子進程異常退出（exit code != 0 且非使用者主動中止）：
    - Python 守護進程捕獲異常，保留已下載之暫存檔 `<filename>.part.mp4`。
    - 取得目前已寫入時間戳，自動重新呼叫 `yt-dlp` 更新可能已過期之 Token/CDN URL。
    - 重新調度 FFmpeg 連接續傳，最多重試 5 次（指數退避：2s, 4s, 8s, 16s, 30s）。

### F5. 串流暫停 / 恢復機制 (Process Freeze / Resume)
- **目標場景**：下載進行中臨時需要釋放頻寬或 CPU，能瞬間凍結下載而不斷線損壞檔案。
- **核心實作**：
  - 使用 Python `psutil` 庫控制 FFmpeg 子進程：
    - 暫停：`psutil.Process(ffmpeg_pid).suspend()`
    - 恢復：`psutil.Process(ffmpeg_pid).resume()`
  - **熱鍵觸發**：監聽鍵盤輸入（`p` 鍵或 `Space` 空白鍵）。
  - **狀態提示**：終端進度條切換為黃色標籤 `[PAUSED - 按 'p' 或空白鍵繼續]`，恢復時變更為綠色 `[DOWNLOADING]`。

### F6. Cloudflare 反爬蟲繞過機制與瀏覽器指紋偽裝 (Anti-Bot Bypass & Impersonation - v1.1.0 新增)
- **目標場景**：目標串流網站掛載 Cloudflare WAF / Anti-Bot 防禦時，防止 yt-dlp 通用解析器觸發 HTTP 403 Forbidden 挑戰。
- **核心實作**：
  1. **TLS / HTTP2 網路指紋偽裝**：整合 `curl_cffi`，透過 `yt_dlp.networking.impersonate.ImpersonateTarget` 模擬真實桌面瀏覽器（預設 `chrome`，亦支援 `firefox`、`safari`、`edge`）。
  2. **Generic Extractor 參數注入**：自動注入 `--extractor-args "generic:impersonate=<target>"`，確保第三方網頁提取串流時通過 Cloudflare 被動式驗證。
  3. **本機瀏覽器 Cookies 連動**：支援 `--cookies-from-browser`，自動讀取指定瀏覽器之安全憑證（如 `cf_clearance`），因應主動式 JavaScript 挑戰。
  4. **Downloader HTTP Headers 貫穿**：將 yt-dlp 解析出的 HTTP Request Headers（含 User-Agent、Referer、Cookie）貫穿傳遞至 FFmpeg 下載指令之 `-headers`，杜絕 TS / m4s 媒體分片取片階段之 403 連線拒絕。
  5. **安全防護防禦**：對傳入 FFmpeg 之標頭鍵值實施嚴格 CRLF 注入過濾，防止標頭走私或非預期命令注入。

---

## 3. CLI 介面與參數設計 (Command Line Interface)

```text
使用範例：
  python main.py <URL> [OPTIONS]

選項說明：
  <URL>                                目標影片或直播網址（必填）
  -v, --version                        顯示工具版本號 (v1.1.0)
  -q, --quality <QUALITY>              指定畫質 (例如: 1080p, 720p, best) [預設: 互動選擇]
  -o, --output <DIR>                   指定儲存目錄 [預設: ./downloads]
  --wait                               啟用開播監聽模式（若未開播則自動等待）
  --poll-interval <SEC>                開播監聽輪詢間隔秒數 [預設: 15]
  --max-retries <NUM>                  下載斷線最大重試次數 [預設: 5]
  --no-pause                           停用鍵盤熱鍵監聽（適用於背景無頭模式運行）
  --impersonate <BROWSER>              啟用瀏覽器網路指紋偽裝 (預設: chrome，設為 none 關閉)
  --cookies-from-browser <BROWSER>     從指定瀏覽器讀取 Cookies (chrome/firefox/edge/safari)
```

---

## 4. 模組職責拆解與介面約定 (Module Architecture)

| 模組檔案 | 核心類別 / 函數 | 職責定義 |
| :--- | :--- | :--- |
| `src/watcher.py` | `StreamWatcher` | 負責探測串流狀態 (`is_live`)，支援 Impersonate 與 Cookies 輪詢防 403。 |
| `src/extractor.py` | `StreamExtractor` | 包裝 `yt-dlp`，支援瀏覽器指紋偽裝、提取可用畫質、解析目標 URL 與 HTTP Headers。 |
| `src/downloader.py` | `FFmpegDownloader` | 封裝 FFmpeg 進程、注入安全 HTTP Headers、進程隔離與進度回報。 |
| `src/supervisor.py` | `ProcessSupervisor` | 負責進程生命週期管理、崩潰自動重啟、以及調用 `psutil` 執行 suspend/resume。 |
| `src/utils.py` | 工具函數群 | 檔名安全清理、MP4 封裝完整性校驗、外部依賴與 `curl_cffi` 偽裝支援檢測。 |
| `src/cli.py` | `run_app()` | 參數解析（`argparse`）、選單呈現、版本回報、反爬蟲參數協調。 |

---

## 5. 異常處理與邊界測試矩陣 (Edge Cases)

| 異常情境 (Edge Case) | 系統預期防禦行為 |
| :--- | :--- |
| **目標網站觸發 Cloudflare 403** | 預設啟用 `impersonate=chrome` 與 `curl_cffi` 模擬瀏覽器 TLS 指紋；未安裝時主動警告引導安裝。 |
| **HTTP 標頭存在 CRLF 注入嘗試** | `FFmpegDownloader` 檢驗標頭鍵值，發現 `\r` 或 `\n` 立即引發 `ValueError` 阻斷。 |
| **系統未安裝 ffmpeg / ffprobe** | 啟動時即刻檢查 `shutil.which('ffmpeg')`，若缺失則印出明確安裝指引並優雅退出（Exit 1）。 |
| **目標串流開播前被創作者取消** | 輪詢期間若偵測到影片狀態轉為 `private`、`deleted` 或 `rejected`，主動終止監聽並發出告警。 |
| **影片標題包含作業系統非法字元** | 檔名自動調用安全清理函數，過濾 `\ / : * ? " < > \|` 等字元，防止磁碟寫入崩潰。 |
| **硬碟空間不足** | 下載前及下載中定時檢查磁碟可用容量，低於 500MB 時主動停止下載並保留現存檔案。 |
| **使用者強制發送 Ctrl+C** | 捕獲 `SIGINT`，向 FFmpeg 發送 `q` 正常結束信號以閉合 MP4 檔案頭（MOOV），確保已下載部分可正常播放。 |

---

## 6. 階段 1 交付檢核表 (Stage 1 Sign-Off Checklist)

- [x] 功能範圍已定義明確（Wait-for-Live + Quality Select + FFmpeg Copy + Retry + Suspend）。
- [x] 無任何未解之 TBD 或模糊待辦項。
- [x] 介面參數與模組分工已解耦（5 大獨立模組）。
- [x] 符合 `workflow.md` 規範，具備完善的邊界異常防禦機制。
