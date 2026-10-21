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
  [ v1.1.0 (2026-10-21) 反爬蟲穿透與安全強化升級 ] ─── (當前版本)
    ├── 核心修復: 整合 curl_cffi 瀏覽器 TLS 握手指紋偽裝 (Impersonation)
    ├── 自動防禦: generic:impersonate 自動注入 + 瀏覽器 Cookies 提取
    ├── 串流連續性: HTTP Headers 貫穿傳遞至 FFmpeg (-headers)，杜絕分片 403
    ├── 安全加固: HTTP 標頭 CRLF 注入嚴格阻斷防禦
    └── 專案規範: CLI --version 支援、測試案例擴充至 41 項全數通過
+-------------------------------------------------------------------------------+
```

---

## 2. 版本詳細異動清單 (Version Details)

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
   - CLI 註冊 `-v` 與 `--version` 參數，執行即刻回傳版本字串：`pystream-downloader 1.1.0`。
   - CLI 新增 `--impersonate` 參數，允許使用者切換不同模擬目標或傳入 `none` 關閉偽裝。

#### 🛡️ 安全性加固 (Security Hardening)
1. **CRLF 標頭注入防護 (CWE-113)**
   - 在 `FFmpegDownloader._validate_and_sanitize_headers` 中對傳入的標頭鍵與值實施嚴格檢查。
   - 凡包含 `\r` 或 `\n` 之標頭字元，立即引發 `ValueError` 強制終止，杜絕標頭走私（Header Smuggling）與非預期參數截斷。
2. **優雅降級與依賴檢查 (Graceful Fallback)**
   - `src/utils.py` 新增 `check_impersonate_support()`。
   - 若執行環境未安裝 `curl_cffi`，系統於啟動時印出友善警示指引（`pip install curl_cffi`），並安全降級為標準網路模式，不影響一般無反爬蟲網站之正常解析。

#### 🧪 測試與驗證擴充 (Testing & Quality)
- 單元與整合測試案例由 29 項增至 **41 項**（+12 項）：
  - `tests/test_cli.py`: 新增版本號與反爬蟲 CLI 參數解析測試。
  - `tests/test_downloader.py`: 新增 `-headers` 組裝與 CRLF 注入阻斷防禦測試。
  - `tests/test_extractor.py`: 新增 ImpersonateTarget、Generic 參數、Cookies 與標頭提取測試。
  - `tests/test_watcher.py`: 新增開播輪詢防 403 偽裝參數注入測試。
  - `tests/test_stage2_self_check.py`: 階段 2 全鏈路回歸冒煙自檢擴充至 10 項全數通過。
  - `tests/test_utils.py`: 新增 `check_impersonate_support` 模組可用性檢測。

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
| `src/__init__.py` | 修改 | 版本號升級至 `1.1.0`。 |
| `requirements.txt` | 修改 | 新增 `curl_cffi>=0.7.0` 依賴。 |
| `Dockerfile` | 修改 | 更新容器健康檢查探針（納入 `curl_cffi` 完整性校驗）。 |
| `src/utils.py` | 修改 | 新增 `check_impersonate_support()` 與相依性檢查整合。 |
| `src/extractor.py` | 修改 | 建構 `ImpersonateTarget`、`cookiesfrombrowser`、HTTP Headers 抽取。 |
| `src/watcher.py` | 修改 | 開播輪詢器加入反爬蟲指紋偽裝與 Cookies 參數支援。 |
| `src/downloader.py` | 修改 | 加入 `headers` 參數、`-headers` 格式化與 CRLF 注入防禦。 |
| `src/cli.py` | 修改 | 新增 `-v/--version`、`--impersonate`、`--cookies-from-browser` 與標頭傳遞。 |
| `tests/test_cli.py` | 修改 | 覆蓋 `--version`、`--impersonate` 與 `--cookies-from-browser` 驗證。 |
| `tests/test_downloader.py` | 修改 | 覆蓋 `-headers` 組裝與 CRLF 注入例外攔截驗證。 |
| `tests/test_extractor.py` | 修改 | 覆蓋 ImpersonateTarget、Cookies 與 `http_headers` 提取驗證。 |
| `tests/test_watcher.py` | 修改 | 覆蓋 Watcher 反爬蟲選項組裝驗證。 |
| `tests/test_utils.py` | 修改 | 覆蓋 `check_impersonate_support` 判定邏輯。 |
| `tests/test_stage2_self_check.py` | 修改 | 自檢項目由 7 項擴展至 10 項（覆蓋偽裝與防注入）。 |
| `docs/self_check.log` | 更新 | 記錄 10 項 Stage 2 自檢執行日誌（10/10 OK）。 |
| `docs/01_spec.md` | 更新 | 補充 F6 功能規格、CLI 參數更新與 Cloudflare 邊界情境。 |
| `docs/02_architecture.md` | 更新 | 補充反爬蟲穿透拓撲圖、介面規格與自檢策略更新。 |
| `docs/03_test_plan.md` | 更新 | 擴展測試矩陣（新增 TC-EX-03, TC-EX-04, TC-DL-03, TC-CL-01, TC-UT-03）。 |
| `docs/04_test_report.md` | 更新 | 更新測試日誌佐證與測試總數（41/41 PASS）。 |
| `docs/05_security_audit.md` | 更新 | 新增 CRLF 標頭防護 (CWE-113) 與 Cookies 存取安全審計。 |
| `docs/06_deployment_guide.md` | 更新 | 更新容器 Python 套件清單、健康檢查探針與排查指南。 |
| `docs/07_changelog.md` | 新增 | 建立版本異動歷程、功能矩陣與軌跡追蹤報告。 |
| `workflow.md` | 更新 | 交付產出清單納入 `docs/07_changelog.md`。 |

