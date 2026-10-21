# PyStream-Downloader 系統測試計畫與覆蓋率矩陣 (Test Plan & Coverage Matrix)

本文件依據 `workflow.md` 階段 3A（測試計畫設計 - 負責模型：Claude Opus 5.5）之規範編寫，基於 `systematic-debugging` 理念，預先推演系統極限邊界、失敗模式與異常注入情境，建立全覆蓋測試矩陣。

---

## 1. 測試架構拓撲圖 (Test Architecture ASCII)

```text
+-------------------------------------------------------------------------------+
|                    PyStream-Downloader 測試套件架構圖 (ASCII)                   |
+-------------------------------------------------------------------------------+

                             [ 測試執行進入點: pytest / unittest ]
                                               │
         ┌───────────────────┬─────────────────┴───────────────────┬────────────┐
         ▼                   ▼                                     ▼            ▼
  [ 1. utils 測試 ]   [ 2. extractor 測試 ]                 [ 3. watcher 測試 ] [ 4. downloader 測試 ]
  - 檔名極限注入      - yt-dlp 欄位缺失/畸形結構            - Upcoming 倒數     - FFmpeg 參數組裝
  - 萬國碼/Emoji/非法 - 格式排序與畫質篩選                  - 輪詢異常中斷      - 正則日誌提取容錯
  - MP4 Box 邊界截斷  - 預設值回退驗證                      - 開播狀態即時判定  - 缺失二進位檔防禦
         │                   │                                     │            │
         └───────────────────┴─────────────────┬───────────────────┴────────────┘
                                               │
                                               ▼
                                 [ 5. supervisor 核心控制測試 ]
                                 - 斷線重試計數與指數退避 (Backoff)
                                 - psutil 進程掛起 (Freeze) 與喚醒驗證
                                 - 子進程優雅退場與資源釋放 (Clean SIGINT)
                                               │
                                               ▼
                                  [ 6. 端到端模擬整合測試 ]
                                  - 完整下載模擬流 (Mock Pipeline)
                                  - 完整性檢驗閉環
+-------------------------------------------------------------------------------+
```

---

## 2. 測試案例分類與覆蓋率矩陣 (Test Matrix)

| 測試模組編號 | 測試模組檔案 | 測試案例目標與邊界條件 | 預期測試行為 |
| :--- | :--- | :--- | :--- |
| **TC-UT-01** | `tests/test_utils.py` | 檔名包含 Windows 特殊保留字元、Emoji、超長字串（>200字元）、全空白字串 | 正常清理，無任何危險字元，若為空則安全回退為 `downloaded_video`。 |
| **TC-UT-02** | `tests/test_utils.py` | MP4 檔案不存在、檔案大小 < 32 位元組、隨機二進位亂碼、僅包含 ftyp/moov box | 精準判定有效性，防範偽造或損壞檔案通過驗收。 |
| **TC-EX-01** | `tests/test_extractor.py` | 來源格式為空、無解析度標籤、單純音訊軌、多畫質排序（1080p > 720p > 480p） | 依畫質高度降序排列，支援指定 format_id 或預設自動提取最優流。 |
| **TC-EX-02** | `tests/test_extractor.py` | 目標網址解析異常（HTTP 404 / 私人影片） | 拋出友善錯誤訊息，阻止未定義崩潰。 |
| **TC-WA-01** | `tests/test_watcher.py` | 串流狀態為 `is_upcoming`（未開播）、`is_live`（開播）、網路異常 | 正確觸發倒數計時回調，開播時返回 True，支援中途取消。 |
| **TC-DL-01** | `tests/test_downloader.py` | FFmpeg 命令組裝：檢查 `-reconnect 1`、`-c copy`、`-movflags +faststart` | 參數列表符合標準無損錄製規範。 |
| **TC-DL-02** | `tests/test_downloader.py` | FFmpeg stderr 進度日誌解析：標準行、缺少 speed 行、隨機非進度行 | 正確擷取 time、bitrate 與 speed，無解析異常。 |
| **TC-SV-01** | `tests/test_supervisor.py` | 模擬 FFmpeg 異常崩潰（Exit code != 0）觸發自動重試 | 重試次數遞增，觸發指數退避睡眠，超限後回傳 False。 |
| **TC-SV-02** | `tests/test_supervisor.py` | 模擬 psutil 進程掛起（suspend）與恢復（resume）狀態流轉 | `is_paused` 狀態精確切換，重複掛起不重複調用。 |
| **TC-EX-03** | `tests/test_extractor.py` | 瀏覽器指紋偽裝選項（`impersonate=chrome` / `none`）與 generic extractor 參數組裝 | 驗證 `ImpersonateTarget` 實例及 `extractor_args` 正確配置。 |
| **TC-EX-04** | `tests/test_extractor.py` | 讀取 Cookies 與提取串流專屬 HTTP Request Headers | 驗證 `cookiesfrombrowser` 元組與 `http_headers` 字典完整回傳。 |
| **TC-DL-03** | `tests/test_downloader.py` | FFmpeg `-headers` 組裝與 CRLF 注入安全性防禦 | 格式化 `\r\n` 串列且置於 `-i` 之前；遇換行字元時阻斷並拋出 `ValueError`。 |
| **TC-CL-01** | `tests/test_cli.py` | CLI 參數解析、`--version` 顯示、`--impersonate` 與 `--cookies-from-browser` | 驗證預設值（chrome）與自訂瀏覽器設定解析無誤。 |
| **TC-UT-03** | `tests/test_utils.py` | 系統依賴檢測加入 `check_impersonate_support()` | 正確識別 `curl_cffi` 與 `yt-dlp` 指紋庫就緒狀態。 |

---

## 3. 測試執行環境與工具鏈
- **執行框架**：Python `unittest`（兼具標準無依賴與高相容性）。
- **Mock 策略**：全套測試均具備 Mock 機制，於無 FFmpeg 實體與無網路環境下亦能 100% 獨立運行，杜絕環境相依性測試污染。
