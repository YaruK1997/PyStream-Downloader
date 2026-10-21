# PyStream-Downloader 版本異動紀錄與功能演進軌跡 (Version History & Changelog)

本文件依據 `workflow.md` 五階段協作流程規範編寫，記錄專案之版本演進、功能異動明細、安全性加固項目與修訂軌跡。

---

## 1. 版本演進里程碑拓撲 (Milestone Roadmap ASCII)

```text
+-------------------------------------------------------------------------------+
|                    PyStream-Downloader 版本歷程拓撲圖 (ASCII)                   |
+-------------------------------------------------------------------------------+

  [ v1.0.0 (2026-10-21) 基礎核心發布 ]
    ├── 核心功能: 串流開播輪詢 (Watcher)、多畫質解析 (Extractor)
    ├── 下載引擎: FFmpeg 原生無損重封裝 (-c copy)、進度解析
    ├── 守護機制: 指數退避重試 (Supervisor)、鍵盤熱鍵凍結/恢復 (psutil)
    └── 部署環境: Dockerfile / Docker Compose / 跨平台部署腳本
            │
            ▼ (遭遇議題: 第三方網頁 Cloudflare WAF Anti-Bot HTTP 403 阻斷)
  [ v1.1.0 (2026-10-21) 反爬蟲穿透與安全強化升級 ]
    ├── 核心修復: 整合 curl_cffi 瀏覽器 TLS 握手指紋偽裝 (Impersonation)
    ├── 自動防禦: generic:impersonate 自動注入 + 瀏覽器 Cookies 提取
    ├── 串流連續性: HTTP Headers 貫穿傳遞至 FFmpeg (-headers)，杜絕分片 403
    ├── 安全加固: HTTP 標頭 CRLF 注入嚴格阻斷防禦
    └── 專案規範: CLI --version 支援、測試案例擴充至 41 項全數通過
            │
            ▼ (遭遇議題: 動態 JS 混淆站點觸發 Unsupported URL)
  [ v1.2.0 (2026-10-21) 無頭瀏覽器動態串流嗅探升級 (The Stream Detector 引擎) ] ─── (當前版本)
    ├── 方案 A 實作: 整合 Playwright 無頭 Chromium 瀏覽器
    ├── 核心功能: 網路層即時攔截 (.m3u8 / .mpd)，抽取 Master Playlist 與即時 Headers
    ├── 智慧回退: yt-dlp 遇 Unsupported URL 時自動接軌嗅探器，無縫串接畫質選擇
    ├── 參數擴充: CLI 支援 --sniff (auto/always/never) 與 --sniff-timeout
    └── 專案規範: 版本升級至 v1.2.0，測試案例擴展至 49 項全數通過
+-------------------------------------------------------------------------------+
```

---

## 2. 版本詳細異動清單 (Version Details)

### [v1.2.0] - 2026-10-21

#### 🎯 核心修訂主旨
針對未被 `yt-dlp` 原生支援、且使用前端 JavaScript 動態混淆加密（如 Dean Edwards packer 混淆加密）的各類影音網站，落實**方案 A（Playwright 無頭瀏覽器動態嗅探器 - The Stream Detector 引擎）**，使下載器具備通殺動態串流網站的能力。

#### 🚀 新增功能 (Features)
1. **無頭瀏覽器串流嗅探模組 (`src/sniffer.py` / `HeadlessStreamSniffer`)**
   - 封裝 Playwright 無頭 Chromium 實例，模擬真實瀏覽器載入目標網頁並執行前端混淆 JavaScript。
   - 透過 `page.on("request")` 事件即時攔截播放器發出的 `.m3u8` 與 `.mpd` 請求。
   - 同步獲取該請求對應的即時 HTTP Request Headers（User-Agent、Referer、Cookie、Origin）。
   - 自動過濾並鎖定 `master.m3u8` 或最高優先級之 Playlist 串流直鏈。
2. **智慧自動回退鏈路 (Seamless Fallback Pipeline)**
   - 在 `src/extractor.py` 中整合嗅探器：
     - 若 yt-dlp 拋出 `Unsupported URL` 或判定非標準網站時，系統自動提示並切換至無頭瀏覽器進行動態嗅探。
     - 嗅探成功取得 `.m3u8` 直鏈後，再度交由 yt-dlp 進行二級格式分解，使用者依然享有互動式多解析度選單（1080p, 720p 等）。
     - 嗅探獲得之 Headers 自動傳遞至 `FFmpegDownloader`，徹底解決媒體分片 403 阻斷。
3. **CLI 參數擴充**
   - `--sniff {auto,always,never}`：控制動態嗅探觸發策略（預設 `auto`：遇不支援網站自動觸發；`always`：強制嗅探；`never`：停用）。
   - `--sniff-timeout <SEC>`：自訂無頭嗅探最長等候秒數（預設 15 秒）。
4. **版本號管理**
   - 版本號躍升為 `1.2.0`，CLI `-v` / `--version` 輸出 `pystream-downloader 1.2.0`。

#### 🛡️ 安全性加固 (Security Hardening)
1. **沙盒隔離與暫時性上下文 (CWE-250)**
   - 每次嗅探均使用全新且獨立之 `BrowserContext`（相當於無痕無狀態視窗），不保留快取與個人資料。
2. **防範資源耗盡與殭屍行程 (CWE-400)**
   - `HeadlessStreamSniffer` 採用 Context Manager 與 `finally: browser.close()`，保證無論任務超時或例外終止，背景 Chromium 進程皆被 100% 關閉。
   - 一旦偵測到目標串流立即早退釋放瀏覽器，大幅節約 CPU 與記憶體。

#### 🧪 測試與驗證擴充 (Testing & Quality)
- 單元與整合測試案例由 41 項增至 **49 項**（+8 項）：
  - `tests/test_sniffer.py`: 建立 Sniffer 初始化、結果封裝、網路攔截模擬與依賴缺失檢查（4 項）。
  - `tests/test_extractor.py`: 新增 Unsupported URL 自動回退與 Never 模式阻斷測試（2 項）。
  - `tests/test_cli.py`: 新增 `--sniff` 與 `--sniff-timeout` 參數解析測試（1 項）。
  - `tests/test_utils.py`: 新增 `check_playwright_support` 模組支援度測試（1 項）。
  - `tests/test_stage2_self_check.py`: 階段 2 自檢項目擴增至 11 項全數通過。

---

### [v1.1.0] - 2026-10-21

#### 🎯 核心修訂主旨
解決使用 yt-dlp 解析目標串流時遭遇 Cloudflare 防火牆人機驗證（`HTTP Error 403 caused by Cloudflare anti-bot challenge`）之阻斷問題，建立端到端之真實瀏覽器網路指紋偽裝與 HTTP Request Headers 傳遞鏈路。

#### 🚀 新增功能 (Features)
1. **瀏覽器網路指紋偽裝 (Browser Impersonation)**
   - 整合 `curl_cffi` C 語言擴展函式庫，支援 JA3/JA4 TLS 握手特徵與 HTTP/2 序列偽裝。
   - 封裝 `yt_dlp.networking.impersonate.ImpersonateTarget`，預設以 `chrome` 指紋發起連線。
   - 自動配置 generic extractor 偽裝參數：`--extractor-args "generic:impersonate=chrome"`。
2. **本機瀏覽器憑證連動 (Browser Cookies Access)**
   - CLI 新增 `--cookies-from-browser` 參數（支援 `chrome`, `firefox`, `edge`, `safari`, `brave`, `opera`）。
   - 支援讀取本機登入或已通過驗證之 `cf_clearance`，以應對嚴格之 Cloudflare Turnstile 主動挑戰。
3. **HTTP 請求標頭貫穿至 FFmpeg (Header Propagation)**
   - `StreamExtractor` 新增 `get_http_headers()` 與 `resolve_stream_details()`，完整擷取 yt-dlp 解析串流所使用之 HTTP Headers（含 User-Agent、Referer、Cookie）。
   - `FFmpegDownloader` 於 `-i` 串流輸入前動態附加 `-headers` 參數，防止 FFmpeg 在下載 HLS/DASH TS 媒體分片時遭遇二次 403 阻斷。
4. **版本號管理與 CLI 查詢**
   - 於 `src/__init__.py` 定義統一版本常數 `__version__ = "1.1.0"`。
   - CLI 註冊 `-v` 與 `--version` 參數。

---

### [v1.0.0] - 2026-10-21

#### 📦 初始功能發布
- 依據 `workflow.md` 五階段協作流程完成設計與交付。
- 支援 YouTube 及主流串流平台之即時開播監聽（Watcher 輪詢）。
- 互動式畫質選單與最佳串流解析（`StreamExtractor`）。
- FFmpeg 守護進程，支援直接串流複製（Remux `-c copy`）。
- 即時鍵盤熱鍵掛起/恢復（`psutil.suspend` / `resume`）。
- 斷線自動指數退避重試（最長 30 秒，上限 5 次）。
- Dockerfile、Docker Compose 與跨平台一鍵部署腳本（`deploy.ps1` / `deploy.sh`）。

---

## 3. 檔案變更歷程與追蹤軌跡 (File Audit Trail)

| 檔案路徑 | 變更類型 | 異動行數/重點摘要 |
| :--- | :---: | :--- |
| `src/__init__.py` | 修改 | 版本號升級至 `1.2.0`。 |
| `requirements.txt` | 修改 | 新增 `playwright>=1.40.0` 依賴。 |
| `Dockerfile` | 修改 | 安裝 Playwright 及 Chromium 二進位檔 (`playwright install chromium --with-deps`)。 |
| `src/sniffer.py` | **新增** | 實作 `HeadlessStreamSniffer` 與 `SniffResult`，完成動態網路層串流攔截。 |
| `src/utils.py` | 修改 | 新增 `check_playwright_support()` 支援度檢測。 |
| `src/extractor.py` | 修改 | 整合 Sniffer 自動回退、二級格式分解與標頭合併機制。 |
| `src/cli.py` | 修改 | 新增 `--sniff` 與 `--sniff-timeout` 參數及調度整合。 |
| `tests/test_sniffer.py` | **新增** | 新增 Sniffer 初始化、結果封裝、事件攔截與依賴缺失測試 (4 項)。 |
| `tests/test_extractor.py` | 修改 | 覆蓋 Unsupported URL 自動回退與 Never 模式測試。 |
| `tests/test_cli.py` | 修改 | 覆蓋 `--version` (v1.2.0)、`--sniff` 與 `--sniff-timeout` 驗證。 |
| `tests/test_utils.py` | 修改 | 覆蓋 `check_playwright_support()` 邏輯檢驗。 |
| `tests/test_stage2_self_check.py` | 修改 | 自檢項目由 10 項擴展至 11 項（納入 Sniffer 整合檢測）。 |
| `docs/self_check.log` | 更新 | 記錄 11 項 Stage 2 自檢執行日誌（11/11 OK）。 |
| `docs/01_spec.md` | 更新 | 補充 F7 功能規格、CLI 參數更新與 Unsupported URL 邊界情境。 |
| `docs/02_architecture.md` | 更新 | 新增 Sniffer 模組介面契約與動態串流嗅探拓撲圖。 |
| `docs/03_test_plan.md` | 更新 | 擴展測試矩陣（新增 TC-SN-01, TC-SN-02, TC-CL-02, TC-UT-04）。 |
| `docs/04_test_report.md` | 更新 | 更新測試日誌佐證與測試總數（49/49 PASS）。 |
| `docs/05_security_audit.md` | 更新 | 新增無頭瀏覽器沙盒隔離與資源保護審查 (CWE-250 / CWE-400)。 |
| `docs/06_deployment_guide.md` | 更新 | 更新 Playwright Chromium 安裝步驟與容器健康檢查探針。 |
| `docs/07_changelog.md` | 更新 | 完整記錄 v1.2.0 版本變更里程碑、功能矩陣與軌跡。 |
