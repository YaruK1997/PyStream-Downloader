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
- **核心職責**：定時輪詢尚未開播之即時串流（如 YouTube Upcoming），直到串流就緒。
- **公開介面**：
  ```python
  class StreamWatcher:
      def __init__(self, url: str, poll_interval: int = 15): ...
      def check_status(self) -> tuple[bool, str]: ...
      def wait_until_live(self, on_tick=None) -> bool: ...
  ```

### 模組 2: `src/extractor.py` (`StreamExtractor`)
- **核心職責**：調用 `yt-dlp` 解析串流標題、可用解析度清單與直連串流 URL。
- **公開介面**：
  ```python
  class StreamExtractor:
      def __init__(self, url: str): ...
      def extract_metadata(self) -> dict: ...
      def get_available_formats(self) -> list[dict]: ...
      def resolve_stream_url(self, format_id: str = None) -> tuple[str, str]: ...
  ```

### 模組 3: `src/downloader.py` (`FFmpegDownloader`)
- **核心職責**：組裝 FFmpeg 參數，以直接流拷貝模式（`-c copy`）啟動子進程並解析進度。
- **公開介面**：
  ```python
  class FFmpegDownloader:
      def __init__(self, stream_url: str, output_path: str): ...
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
- **核心職責**：Windows / Linux 檔名合法化清理、MP4 完整性驗證。
- **公開介面**：
  ```python
  def sanitize_filename(name: str) -> str: ...
  def verify_mp4_integrity(filepath: str) -> bool: ...
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
- 檢驗重點：
  1. 檔名清理器正常過濾 Windows 非法字元（`\ / : * ? " < > |`）。
  2. 格式解析器與 FFmpeg 命令列參數組裝正確性。
  3. 模擬子進程掛起（`psutil.suspend`）與恢復（`resume`）之狀態正確性。
  4. 驗證日誌記錄於 `docs/self_check.log`。
