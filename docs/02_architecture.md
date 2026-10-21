# PyStream-Downloader 系統架構設計說明書 (Architecture Document)

本文件依據 `workflow.md` 階段 2（架構及功能編寫）之規範編寫，確立專案之模組分層、介面協議、非阻塞進程管理與自我驗證機制。

---

## 1. 系統架構拓撲圖 (Architecture Topology ASCII)

```text
+-------------------------------------------------------------------------------+
|                    PyStream-Downloader 模組分層拓撲圖 (ASCII)                   |
+-------------------------------------------------------------------------------+

                           [ CLI 進入點: main.py ]
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
       [ 1. StreamWatcher ]                    [ 2. StreamExtractor ]
       - 輪詢串流上線狀態                      - yt-dlp 資訊抽取
       - 間隔計時與動態倒數                    - 畫質過濾與直連 URL 解析
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     │ (就緒串流 URL + 輸出路徑)
                                     ▼
                        [ 3. ProcessSupervisor ]
                        - 守護進程生命週期監控
                        - 異常崩潰重試與斷點重連 (指數退避)
                        - 鍵盤監聽線程 (Space / 'p')
                        - psutil 進程掛起 (Freeze) 與恢復 (Resume)
                                     │
                                     ▼ (子進程管線 Subprocess)
                        [ 4. FFmpegDownloader ]
                        - FFmpeg Worker 參數組裝
                        - -reconnect 網路層自動重連
                        - stderr 即時進度過濾 (time/bitrate/speed)
                                     │
                                     ▼
                        [ 5. FileFinalizer ]
                        - 檔名字元安全性過濾
                        - MP4 檔案頭完整性檢查 (MOOV)
                        - 最終成品存檔
+-------------------------------------------------------------------------------+
```

---

## 2. 模組職責與介面契約 (Interface Contracts)

### 模組 1: `src/watcher.py` (`StreamWatcher`)
- **核心職責**：定時輪詢尚未開播之即時串流（如 YouTube Upcoming），直到串流就緒。支援瀏覽器指紋偽裝以避開 Cloudflare 阻斷。
- **公開介面**：
  ```python
  class StreamWatcher:
      def __init__(self, url: str, poll_interval: int = 15, impersonate: Optional[str] = "chrome", cookies_from_browser: Optional[str] = None): ...
      def check_status(self) -> tuple[bool, str, dict]: ...
      def wait_until_live(self, on_tick=None) -> bool: ...
  ```

### 模組 2: `src/extractor.py` (`StreamExtractor`)
- **核心職責**：調用 `yt-dlp` 解析串流標題、可用解析度清單、直連串流 URL 與 HTTP Request Headers。
- **公開介面**：
  ```python
  class StreamExtractor:
      def __init__(self, url: str, impersonate: Optional[str] = "chrome", cookies_from_browser: Optional[str] = None): ...
      def extract_metadata(self) -> dict: ...
      def get_available_formats(self) -> list[dict]: ...
      def get_http_headers(self, selected_format_id: Optional[str] = None) -> dict[str, str]: ...
      def resolve_stream_details(self, selected_format_id: Optional[str] = None) -> tuple[str, str, dict[str, str]]: ...
      def resolve_stream_url(self, format_id: str = None) -> tuple[str, str]: ...
  ```

### 模組 3: `src/downloader.py` (`FFmpegDownloader`)
- **核心職責**：組裝 FFmpeg 參數，以直接流拷貝模式（`-c copy`）啟動子進程並解析進度；注入防禦性 HTTP Headers 防止 403。
- **公開介面**：
  ```python
  class FFmpegDownloader:
      def __init__(self, stream_url: str, output_path: str, headers: Optional[dict[str, str]] = None): ...
      def build_command(self) -> list[str]: ...
      def start_process(self) -> subprocess.Popen: ...
      def parse_progress(self, line: str) -> dict: ...
  ```

### 模組 4: `src/supervisor.py` (`ProcessSupervisor`)
- **核心職責**：進程守護、熱鍵即時暫停/恢復（利用 `psutil`），崩潰重試與斷點續傳。
- **公開介面**：
  ```python
  class ProcessSupervisor:
      def __init__(self, downloader: FFmpegDownloader, max_retries: int = 5): ...
      def run(self, progress_callback=None) -> bool: ...
      def pause(self) -> bool: ...
      def resume(self) -> bool: ...
      def is_paused(self) -> bool: ...
  ```

### 模組 5: `src/utils.py` (`FileFinalizer`)
- **核心職責**：Windows / Linux 檔名合法化清理、MP4 完整性驗證、相依套件與 Chromium 支援度檢查。
- **公開介面**：
  ```python
  def sanitize_filename(name: str) -> str: ...
  def verify_mp4_integrity(filepath: str) -> bool: ...
  def check_impersonate_support() -> bool: ...
  def check_playwright_support() -> bool: ...
  def check_system_dependencies() -> dict[str, bool]: ...
  ```

### 模組 6: `src/sniffer.py` (`HeadlessStreamSniffer`)
- **核心職責**：以無頭 Chromium 攔截動態網頁請求，嗅探 `.m3u8` / `.mpd` 串流直鏈與 Headers（The Stream Detector 引擎 - v1.2.0）。
- **公開介面**：
  ```python
  class HeadlessStreamSniffer:
      def __init__(self, timeout: int = 15, headless: bool = True): ...
      def is_available(self) -> bool: ...
      def sniff(self, url: str, user_agent: Optional[str] = None, on_detected: Optional[Callable] = None) -> Optional[SniffResult]: ...
  ```

---

## 3. 狀態機與狀態轉移 (State Machine ASCII)

```text
+-------------------------------------------------------------------------------+
|                      下載守護進程狀態轉移圖 (State Machine)                     |
+-------------------------------------------------------------------------------+

      [ INIT ] ──(URL 離線/未開播)──> [ POLLING (輪詢監聽) ]
         │                                    │
         │ (串流上線 / 點播正常)                 │ (偵測到 is_live)
         └─────────────────┬──────────────────┘
                           ▼
                 [ EXTRACTING_FORMATS ]
                           │ (使用者選定畫質)
                           ▼
                  [ DOWNLOADING ] <───────────┐
                    │          │              │
        (熱鍵 'p')  │          │ (網絡崩潰退出)  │ (重試次數 < 5)
                    ▼          ▼              │
               [ PAUSED ]   [ RETRYING ] ─────┘
                    │          │
        (熱鍵 'p')  │          │ (重試超過 5 次)
                    ▼          ▼
               [ DOWNLOADING ] [ FAILED ]
                    │
         (FFmpeg 正常結束 0)
                    ▼
               [ COMPLETED ] ──> [ FINALIZE (.mp4) ]
+-------------------------------------------------------------------------------+
```

---

## 4. 自我驗證設計 (Self-Verification Strategy)
- 建立單元自驗測試腳本 `tests/test_stage2_self_check.py`，於編寫完成後以 Python 執行。
- 檢驗重點（共 10 項全自動驗證）：
  1. 檔名清理器正常過濾 Windows 非法字元（`\ / : * ? " < > |`）。
  2. MP4 檔案頭封裝有效性檢查（atom box 驗證）。
  3. FFmpeg 命令列參數組裝與斷線重連參數正確性。
  4. FFmpeg 正則日誌提取與進度指標過濾。
  5. 格式解析器畫質排序與音訊過濾。
  6. 開播監聽器狀態轉移（Upcoming -> Live）。
  7. 模擬子進程掛起（`psutil.suspend`）與恢復（`resume`）之狀態正確性。
  8. `curl_cffi` 與 `ImpersonateTarget` 偽裝支援檢測。
  9. `FFmpegDownloader` 標頭組裝與 CRLF 注入阻斷防禦。
  10. `StreamExtractor` 反爬蟲參數與 HTTP Headers 傳遞鏈路。
- 驗證日誌記錄於 `docs/self_check.log`。

---

## 5. 反爬蟲防禦與網路指紋偽裝架構 (Anti-Bot & Impersonation Pipeline - v1.1.0)

```text
+-------------------------------------------------------------------------------+
|             Cloudflare 反爬蟲穿透與 HTTP Headers 傳遞管線 (Pipeline)            |
+-------------------------------------------------------------------------------+

  [ 目標 URL / 串流來源 ]
            │
            ▼ (遭遇 Cloudflare WAF / Anti-Bot 403)
  [ StreamExtractor / StreamWatcher ]
            │
            ├─► 1. 啟用 curl_cffi 網路層驅動
            │      - 偽造真實瀏覽器 TLS 握手指紋 (JA3 / JA4)
            │      - 模擬 HTTP/2 幀序列與加密套件
            │      - ydl_opts: impersonate = ImpersonateTarget.from_str('chrome')
            │
            ├─► 2. Generic Extractor 參數注入
            │      - extractor_args = {'generic': {'impersonate': ['chrome']}}
            │
            ├─► 3. 瀏覽器 Cookies 提取 (可選)
            │      - 讀取 Chrome / Firefox / Edge 本機憑證以通過驗證碼挑戰
            │
            ▼ (解析成功，取得 Master Playlist 與請求標頭)
  [ HTTP Request Headers (User-Agent, Referer, Cookie) ]
            │
            ▼ (CRLF 注入安全檢驗)
  [ FFmpegDownloader ]
            │
            ├─► 格式化為: -headers "Header1: Val1\r\nHeader2: Val2\r\n"
            │   (置於 -i 參數之前以作用於串流協定請求)
            │
            ▼
  [ FFmpeg Worker Subprocess ]
            │ (拉取 m3u8 分片，保持與瀏覽器相同憑證特徵)
            ▼
  [ 成功錄製，杜絕分片 403 阻斷 ]
+-------------------------------------------------------------------------------+
```

---

## 6. 無頭瀏覽器動態串流嗅探拓撲 (Headless Stream Sniffer Topology - v1.2.0)

```text
+-------------------------------------------------------------------------------+
|             The Stream Detector 引擎：無頭瀏覽器動態嗅探拓撲 (ASCII)            |
+-------------------------------------------------------------------------------+

  [ 目標網址 (如: https://missav.ai/gvh-852) ]
                      │
                      ▼
            [ StreamExtractor ]
                      │
        (1. 呼叫 yt-dlp 標準解析)
                      │
         [ 觸發 Unsupported URL / JS 混淆 ]
                      │
                      ▼ (2. 自動觸發回退管線 Fallback)
         [ HeadlessStreamSniffer ]
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
  [ 啟動無頭 Chromium ]     [ 設定 Viewport / Locale ]
         │
         ▼
  [ 導覽至目標頁面 page.goto() ]
         │
         ▼ (網頁前端執行 Dean Edwards packed JS 解密)
  [ HLS.js 播放器被觸發，發出媒體分片請求 ]
         │
         ▼ (page.on("request") 事件攔截)
  [ 捕獲: https://surrit.com/.../playlist.m3u8 ]
  [ 同步捕獲: User-Agent, Referer, Cookie, Origin ]
         │
         ▼ (關閉無頭瀏覽器實例)
  [ 將嗅探直鏈傳回 StreamExtractor ]
         │
         ▼ (yt-dlp 解析 Master Playlist 規格多畫質 1080p / 720p)
  [ 使用者互動選定畫質 ]
         │
         ▼ (帶入嗅探所得 Headers)
  [ FFmpegDownloader 進行分片直接流拷貝 (.mp4) ]
+-------------------------------------------------------------------------------+
```
