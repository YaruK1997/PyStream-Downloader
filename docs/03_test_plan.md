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
| **TC-SN-01** | `tests/test_sniffer.py` | `HeadlessStreamSniffer` 網路攔截與 m3u8/mpd 串流直鏈辨識 | 驗證 Chromium 啟動、`page.on("request")` 事件攔截與標頭抽取。 |
| **TC-SN-02** | `tests/test_extractor.py` | `StreamExtractor` 遇 `Unsupported URL` 自動觸發 Sniffer 回退 | 驗證 yt-dlp 失敗時自動接軌 Playwright 嗅探器並獲取可用格式。 |
| **TC-EX-06** | `tests/test_extractor.py` | 遇動態混淆站點且本機無 Chromium 嗅探器時之自適應升級信號觸發 | 拋出 `NeedsFullSnifferError`（常數 `EXIT_CODE_NEED_FULL_SNIFFER = 42`）。 |
| **TC-CL-02** | `tests/test_cli.py` | CLI `--sniff`（auto/always/never）與 `--sniff-timeout` 參數解析 | 驗證動態嗅探模式與自訂超時解析正確。 |
| **TC-CL-05** | `tests/test_cli.py` | CLI 捕獲 `NeedsFullSnifferError` 與進程退出代碼轉換 | 驗證主程序精準以 `sys.exit(42)` 終止，供外部編排器或 Shell 腳本自動升級。 |
| **TC-UT-04** | `tests/test_utils.py` | 系統依賴檢測加入 `check_playwright_support()` | 正確檢驗 Playwright 庫與本機 Chromium 二進位執行檔可用性。 |
| **TC-SC-12** | `tests/test_stage2_self_check.py` | 階段 2 冒煙自檢：驗證 Exit Code 42 自適應升級協定與異常封裝 | 驗證 `NeedsFullSnifferError` 屬性、例外回溯與主調度器狀態碼對齊。 |
| **TC-EX-07** | `tests/test_extractor.py` | 視訊軌無音訊 (`acodec == 'none'`) 時自動探測最佳 AAC 音軌並封裝 StreamDetails | 驗證 StreamDetails 具備視訊/音訊雙直鏈與專屬標頭，向下相容 3-Tuple 解構。 |
| **TC-EX-08** | `tests/test_extractor.py` | 原生內嵌音軌之串流不額外掛載獨立音訊 (`is_muxed = True`) | 驗證 `audio_url` 為 None，杜絕重複疊加音軌。 |
| **TC-DL-04** | `tests/test_downloader.py` | FFmpeg 雙輸入命令組裝、`-map 0:v:0 -map 1:a:0` 映射與 A/V 時間戳同步參數 | 驗證兩組 `-i` 輸入、`-fflags +genpts`、`-avoid_negative_ts make_zero`、`-max_interleave_delta 0` 與 `-shortest`。 |
| **TC-DL-05** | `tests/test_downloader.py` | 非 AAC 音訊（如 Opus）輸出至 MP4 時自適應轉碼 AAC 與重採樣同步 | 驗證輸出為 MP4 且音訊非 AAC 時自動轉換為 `-c:a aac -b:a 192k -af aresample=async=1:first_pts=0`。 |
| **TC-DL-06** | `tests/test_downloader.py` | 音訊 URL 參數注入防禦（CWE-88） | 傳入以破折號開頭之 `audio_url` 立即引發 `ValueError`。 |
| **TC-SC-13** | `tests/test_stage2_self_check.py` | 階段 2 冒煙自檢：驗證音軌探測、StreamDetails 與雙輸入混流 A/V 同步全鏈路整合 | 驗證格式探測至 FFmpeg 命令組裝之完整流水線一致性。 |
| **TC-SN-03** | `tests/test_sniffer.py` | Playwright `locale` BCP-47 標準語系設定與 `Accept-Language` 分離 | 驗證 context 參數中 `locale` 為純單一語言標籤（如 `"zh-TW"`），多語系權重清單由 `extra_http_headers` 承載。 |
| **TC-SN-04** | `tests/test_sniffer.py` | CDP `Emulation.setLocaleOverride` 協定異常自動防禦降級 | 模擬 `new_page()` 拋出 Invalid locale name 時，自動移除 `locale` 參數並安全重試成功。 |
| **TC-PK-01** | `tests/test_packer.py` | Dean Edwards Packer Base 36 演算法還原 | 驗證標準 0-9a-z 進制符號解析與字典還原無誤。 |
| **TC-PK-02** | `tests/test_packer.py` | Dean Edwards Packer Base 62 演算法還原 | 驗證大寫字母進制 (0-9a-zA-Z) 符號解析與多節點串流直鏈重構。 |
| **TC-PK-03** | `tests/test_packer.py` | 畸形、空字串或非打包 JS 代碼邊界防護 | 驗證異常輸入安全回傳空字串，杜絕正則崩潰或例外逃逸。 |
| **TC-PK-04** | `tests/test_packer.py` | 網頁多個 Packed 區塊批次提取與過濾 | 驗證 `find_packed_scripts` 正確識別多段混淆代碼。 |
| **TC-PK-05** | `tests/test_packer.py` | 靜態 HTML 全文端到端解包與 m3u8 優先級排序 | 驗證主清單 (playlist.m3u8) 與多解析度切片排序回傳。 |
| **TC-SS-01** | `tests/test_static_sniffer.py` | `StaticPackerSniffer` 混淆 HTML 探測與標頭綁定 | 驗證靜態嗅探抽取真實串流直鏈、OG Title 與 Origin/Referer 防盜鏈標頭。 |
| **TC-SS-02** | `tests/test_static_sniffer.py` | 無串流網頁安全回退 | 驗證未包含視訊或混淆之網頁優雅返回 None。 |
| **TC-SS-03** | `tests/test_static_sniffer.py` | 網路連線中斷或抓取異常安全處置 | 驗證請求例外時安全回傳 None，確保調度鏈路不中斷。 |
| **TC-SN-05** | `tests/test_sniffer.py` | 無頭瀏覽器 Stealth 腳本注入與延遲加載播放器激活 | 驗證注入 webdriver 遮蔽腳本與調用 `video.play()` / 點擊激活。 |
| **TC-EX-09** | `tests/test_extractor.py` | Tier 2 靜態解包優先命中驗證 | 驗證 Tier 2 成功提取時，直接回傳結果且不調用 Tier 3 無頭瀏覽器。 |
| **TC-EX-10** | `tests/test_extractor.py` | Tier 2 至 Tier 3 平滑降級驗證 | 驗證 Tier 2 無果時自動平滑切入 Tier 3 無頭動態嗅探。 |

---

## 3. 測試執行環境與工具鏈
- **執行框架**：Python `unittest`（兼具標準無依賴與高相容性）。
- **Mock 策略**：全套測試均具備 Mock 機制，於無 FFmpeg 實體與無網路環境下亦能 100% 獨立運行，杜絕環境相依性測試污染。
