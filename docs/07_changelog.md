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
  [ v1.2.0 (2026-10-21) 無頭瀏覽器動態串流嗅探升級 ]
    ├── 方案 A 實作: 整合 Playwright 無頭 Chromium 瀏覽器
    ├── 核心功能: 網路層即時攔截 (.m3u8 / .mpd)，抽取 Master Playlist 與即時 Headers
    ├── 智慧回退: yt-dlp 遇 Unsupported URL 時自動接軌嗅探器，無縫串接畫質選擇
    ├── 參數擴充: CLI 支援 --sniff (auto/always/never) 與 --sniff-timeout
    └── 專案規範: 版本升級至 v1.2.0，測試案例擴展至 49 項全數通過
            │
            ▼ (遭遇議題: Docker 映像檔龐大 ~1.4GB 且非所有任務都需要 Chromium)
  [ v1.3.0 (2026-10-21) 雙層容器架構與自適應自動升級 (Two-Phase Adaptive Auto-Escalation) ]
    ├── 解法三實作: Docker Compose 雙服務拆分 (downloader:slim vs downloader-full)
    ├── 兩階段自適應: 預設輕量容器 (~420MB)，遇 Unsupported URL 拋出 Exit Code 42
    ├── 協定封裝: NeedsFullSnifferError 與 EXIT_CODE_NEED_FULL_SNIFFER = 42
    ├── 智慧調度器: deploy.ps1 與 deploy.sh 自動捕獲狀態碼 42 並透明升級全功能容器
    ├── 資源調優: full 服務配置 shm_size: 2gb 與 ipc: host 防範渲染器崩潰
    └── 專案規範: 版本升級至 v1.3.0，測試案例擴充至 52 項全數通過
            │
            ▼ (遭遇議題: YouTube 1080p+ 等 DASH 串流視訊與音訊分離，導致成品影片無聲音或音畫不同步)
  [ v1.4.0 (2026-10-22) 獨立音軌識別、雙串流混流與音畫同步升級 ]
    ├── 核心修復: 獨立音軌智慧探測 (StreamExtractor.get_best_audio_format)
    ├── MP4 最佳化: 優先匹配 AAC (YouTube 140 軌，避開 DRC 壓縮軌)，次選高碼率音軌
    ├── 契約保護: StreamDetails 容器支援向前向下 3-Tuple 解構相容
    ├── 雙輸入混流: FFmpeg 支援 -i <video> -i <audio> -map 0:v:0 -map 1:a:0
    ├── 聲畫嚴格同步: 配置 -fflags +genpts -avoid_negative_ts make_zero -max_interleave_delta 0 -shortest
    ├── 編碼自適應: AAC 直接流拷貝，Opus 轉碼 AAC 並啟用 aresample 重採樣同步
    └── 專案規範: 版本升級至 v1.4.0，測試案例擴充至 58 項全數通過
            │
            ▼ (遭遇議題: 無頭嗅探器啟動時報 Protocol error: Invalid locale name)
  [ v1.4.1 (2026-10-22) Playwright CDP Locale 語系規範化與 Emulation 異常防禦降級 ]
    ├── 協定合規: Playwright locale 嚴格遵循 BCP-47 單一標籤 (zh-TW)，移除複合權重字串
    ├── 標頭分離: Accept-Language 轉置至 extra_http_headers 保全內容協商
    ├── 標籤清洗: sanitize_locale 正則清洗非預期字元防禦
    └── 異常降級: 捕捉 Emulation.setLocaleOverride 協定錯誤時自動移除 locale 降級重試
            │
            ▼ (遭遇議題: MissAV 遭遇 Cloudflare Turnstile 阻擋無頭瀏覽器 + preload="none" 播放器未激活)
  [ v1.5.0 (2026-10-22) Nero 流程專案重構：三層式串流解析管線與靜態混淆解包引擎 ] ─── (當前版本)
    ├── 靜態解包: 新增 src/packer.py，演算法還原 Dean Edwards Packer (Base 10~62)
    ├── 零開銷穿透: 新增 src/static_sniffer.py，以 curl_cffi 繞過 Turnstile，0.5s 提取真實直鏈
    ├── 三層管道: 原生 yt-dlp (Tier 1) -> 靜態解包 (Tier 2) -> 增強型無頭嗅探 (Tier 3)
    ├── 動態增強: src/sniffer.py 注入 Stealth Webdriver 特徵遮蔽 + 自動點擊激活 preload="none"
    ├── 輕量化普惠: 輕量 Slim 容器與本機無 Playwright 環境直接支援 MissAV 等網站
    └── 專案規範: 版本升級至 v1.5.0，新增 11 項測試，測試案例達 72 項全數通過
+-------------------------------------------------------------------------------+
```

---

## 2. 版本詳細異動清單 (Version Details)

### [v1.5.0] - 2026-10-22

#### 🎯 核心修訂主旨
依據 **Nero 流程規範**（`/plan`、`/grill-with-doc`、`/code-review`、`/tdd`）執行專案架構重構與效能優化，解決動態影音串流站點（如 MissAV 等）因前端 Cloudflare Turnstile 人機驗證阻擋無頭瀏覽器與 `<video preload="none">` 延遲加載導致動態嗅探逾時（15s）之重大痛點。實作**「三層式自適應串流提取管線 (Three-Tier Extraction Pipeline)」**與**「靜態 Dean Edwards Packer 演算法混淆解包引擎」**，達成 0.5 秒極速穿透與 100% 免疫人機驗證。

#### 🚀 新增功能 (Features)
1. **三層式自適應解析管線架構 (Three-Tier Extraction Pipeline - `src/extractor.py`)**
   - **Tier 1 (原生解析)**：優先調用 `yt-dlp` 高速解析 YouTube/Twitch 等主流標準影音平台。
   - **Tier 2 (靜態混淆解包器)**：當 yt-dlp 回報不支援時，優先調用 `StaticPackerSniffer`，透過 TLS 指紋穿透獲取 HTML 並進行純演算法靜態解碼，0.5 秒提取 CDN 串流直鏈 (`https://surrit.com/[UUID]/playlist.m3u8`)，完全不啟動重型瀏覽器。
   - **Tier 3 (增強型無頭動態嗅探器)**：若靜態無混淆特徵，自動平滑切入 `HeadlessStreamSniffer` (Playwright Chromium) 進行底層封包攔截。
2. **純演算法 Dean Edwards Packer 解碼器 (`src/packer.py`)**
   - 實作無動態執行 (`eval`/`exec`) 之純數學 Base 10 至 Base 62 多進制符號解析與字典還原演算法。
   - 提供 `unpack_dean_edwards()`、`find_packed_scripts()` 與 `extract_m3u8_from_html()` 介面，支援多代碼區塊掃描與主清單/高畫質優先級排序。
3. **靜態指紋穿透與防盜鏈標頭綁定 (`src/static_sniffer.py`)**
   - 整合 `curl_cffi` 模擬 Chrome 120 TLS (JA3/JA4) 握手指紋與 HTTP/2 協議特徵，直接繞過 Cloudflare WAF/Turnstile。
   - 自動提取 OpenGraph `og:title` 或 `<title>` 標籤，並自動解析綁定目標站點之 `Referer` 與 `Origin` 防盜鏈標頭。
4. **增強型無頭動態嗅探與播放器自動激活 (`src/sniffer.py`)**
   - **Stealth 遮蔽**：注入 `Object.defineProperty(navigator, 'webdriver', {get: () => undefined})`，消除自動化特徵。
   - **播放器激活**：加載頁面後自動調用 `video.play()` 並點擊常見播放控制項（如 `.plyr__control--overlaid`、`.player`、`video`），強制觸發延遲加載 (`preload="none"`) 播放器之 HLS.js 串流請求。
5. **版本號管理**
   - 版本號躍升至 `1.5.0`，CLI `--version` 輸出 `pystream-downloader 1.5.0`。

#### ⚡ 效能與架構優化 (Performance & Architecture)
1. **解析耗時指數級縮短**：動態混淆站點由原本的無頭瀏覽器逾時 15 秒驟降至 **< 1 秒**（靜態解包耗時僅 0.01 秒）。
2. **輕量容器普及**：Docker 輕量鏡像（Slim ~420MB）及未安裝 Playwright 之環境，即可直接下載此類靜態混淆站點，無需調度升級至 ~1.4GB 之 Full 鏡像。
3. **單一職責解耦 (SRP)**：將演算法解包（`packer`）、靜態嗅探（`static_sniffer`）、動態渲染（`sniffer`）與調度管線（`extractor`）徹底模組化。

#### 🛡️ 安全性加固 (Security Hardening)
1. **零動態執行 (No Eval/Exec - CWE-94 / CWE-95)**：
   - 嚴格禁止使用 Python `eval()` 或調用外部 JS runtime 執行非信任代碼，全演算法純基於字串正則與數值映射，杜絕遠端代碼執行 (RCE) 漏洞。
2. **ReDoS 災難性回溯防禦 (CWE-1333 / CWE-400)**：
   - 解碼正則採用嚴格邊界限定，關鍵替換使用單趟 O(N) 正則回呼查表，消除指數級回溯風險。
3. **CORS 與防盜鏈安全隔離**：
   - `Referer` 與 `Origin` 嚴格依據輸入 URL 進行標準 `urlparse` 規格化抽取，杜絕換行或非法協定走私。

#### 🧪 測試與驗證擴充 (Testing & Quality)
- 全套單元與整合測試案例由 61 項擴展至 **72 項**（+11 項，100% PASS，0 失敗、0 錯誤）：
  - `tests/test_packer.py` (新增 5 項):
    - `test_unpack_dean_edwards_base36`: 驗證 Base 36 演算法還原。
    - `test_unpack_dean_edwards_base62`: 驗證 Base 62 大寫字母進制與 UUID 重組。
    - `test_unpack_invalid_or_non_packed`: 驗證畸形、空字串或非打包 JS 之安全防禦。
    - `test_find_packed_scripts`: 驗證多個 Packed 區塊批次識別。
    - `test_extract_m3u8_from_html`: 驗證 HTML 端到端直鏈萃取與畫質排序。
  - `tests/test_static_sniffer.py` (新增 3 項):
    - `test_sniff_successful_packed_stream`: 驗證混淆 HTML 探測、OG Title 與 Referer/Origin 標頭注入。
    - `test_sniff_no_stream_returns_none`: 驗證無串流頁面安全回傳 None。
    - `test_sniff_fetch_error_returns_none`: 驗證網路例外安全捕獲。
  - `tests/test_sniffer.py` (擴充至 8 項，+1 項):
    - `test_sniffer_stealth_and_player_activation`: 驗證 Stealth 腳本注入與 `video.play()` 激活呼叫。
  - `tests/test_extractor.py` (擴充至 13 項，+2 項):
    - `test_extractor_static_packer_sniffer_tier2`: 驗證 Tier 2 優先命中並阻止無頭瀏覽器啟動。
    - `test_extractor_tier2_to_tier3_fallback`: 驗證 Tier 2 無果時平滑降級至 Tier 3 無頭嗅探。
- **實體驗收**：針對目標測試網址（如 `https://missav.ai/gvh-852`）進行實體驗證，成功解出 1080p、720p、480p、360p 格式階層與完整標題，並經由 FFmpeg 成功下載 1080p 完整影音。

---
### [v1.4.1] - 2026-10-22

#### 🎯 核心修訂主旨
修復無頭瀏覽器動態嗅探器在建立頁面時因 Chrome DevTools Protocol (CDP) `Emulation.setLocaleOverride` 無法解析複合式 `Accept-Language` 標頭格式而拋出之 `Protocol error: Invalid locale name` 錯誤，建立協定層標準化語系與異常容錯降級機制。

#### 🚀 新增功能 (Features)
1. **CDP BCP-47 標準語系設定 (`src/sniffer.py`)**
   - 將 Playwright `locale` 參數規範為單一語言標籤（`zh-TW`），移除逗號及品質權重參數（`q=0.9`），符合 CDP 底層協定規範。
2. **多語系偏好分離**
   - 將完整的語言偏好清單移轉至 `extra_http_headers` 中的標準 `Accept-Language` 標頭，兼顧瀏覽器渲染與遠端伺服器內容協商。
3. **語系字串自動防禦清理 (`sanitize_locale`)**
   - 自動截取第一個合法語言標籤並過濾非法字元，保證傳入 Chromium 的語系標籤絕對合規。
4. **協定層異常自動防禦降級**
   - 封裝 `try-except` 防禦區塊，一旦捕獲 `setLocaleOverride` 協定錯誤，自動移除 `locale` 重新建立上下文，徹底消滅無頭瀏覽器因語系環境引發的單點故障。
5. **版本號管理**
   - 版本號躍升至 `1.4.1`，CLI `-v` / `--version` 輸出 `pystream-downloader 1.4.1`。

#### 🛡️ 安全性加固 (Security Hardening)
1. **語系字串嚴格清洗 (CWE-20)**
   - 正則過濾 `[^a-zA-Z0-9_\-]`，防止格式字元或換行符號逃逸至底層 CDP 指令。

#### 🧪 測試與驗證擴充 (Testing & Quality)
- 單元與整合測試案例由 58 項增至 **61 項**（+3 項，全數 PASS）：
  - `tests/test_sniffer.py`:
    - `test_sniffer_sanitize_locale`: 檢驗複合標籤、空值與特殊字元之清洗正確性。
    - `test_sniffer_context_locale_and_headers`: 檢驗 context 參數中 `locale` 與 `extra_http_headers` 分離傳遞。
    - `test_sniffer_locale_fallback_on_protocol_error`: 檢驗 CDP 協定報錯時自動降級重試邏輯。

---

### [v1.4.0] - 2026-10-22

#### 🎯 核心修訂主旨
針對 YouTube 1080p/2K/4K 等高畫質串流及 DASH 格式網站將視訊軌（`acodec == 'none'`）與音訊軌分離儲存之架構，實作**獨立音軌智慧探測、雙輸入混流與音畫時間戳嚴格同步機制**，徹底解決「音軌未下載或未同步」議題。

#### 🚀 新增功能 (Features)
1. **獨立音軌智慧匹配模組 (`StreamExtractor.get_best_audio_format`)**
2. **結構化與向下相容容器 (`StreamDetails`)**
3. **FFmpeg 雙輸入混流與時間戳嚴格同步 (`FFmpegDownloader.build_command`)**
4. **音訊編碼自適應轉換策略**
5. **CLI 互動選單與狀態提示**
6. **版本號管理**：版本號躍升至 `1.4.0`。

---

### [v1.3.0] - 2026-10-21

#### 🎯 核心修訂主旨
實作**解法三（Docker Compose 雙服務拆分 + 兩階段自適應自動升級架構 - Two-Phase Adaptive Auto-Escalation via Exit Code 42）**。

---

### [v1.2.0] - 2026-10-21

#### 🎯 核心修訂主旨
落實**方案 A（Playwright 無頭瀏覽器動態嗅探器 - The Stream Detector 引擎）**。

---

### [v1.1.0] - 2026-10-21

#### 🎯 核心修訂主旨
解決 Cloudflare 防火牆人機驗證（`HTTP Error 403`）阻斷問題。

---

### [v1.0.0] - 2026-10-21

#### 📦 初始功能發布
- 依據 `workflow.md` 五階段協作流程完成設計與交付。

---

## 3. 檔案變更歷程與追蹤軌跡 (File Audit Trail)

| 檔案路徑 | 變更類型 | 異動行數/重點摘要 |
| :--- | :---: | :--- |
| `src/__init__.py` | 修改 | 版本號升級至 `1.5.0`。 |
| `src/packer.py` | 新增 | 實作純演算法 Dean Edwards Packer (Base 10~62) 解碼、多區塊提取與 m3u8 優先級排序。 |
| `src/static_sniffer.py` | 新增 | 實作 `StaticPackerSniffer`，整合 `curl_cffi` TLS 指紋穿透與 Referer/Origin 防盜鏈標頭綁定。 |
| `src/sniffer.py` | 修改 | 注入 Stealth Webdriver 特徵遮蔽，加入延遲加載播放器（`preload="none"`）自動點擊與播放激活。 |
| `src/extractor.py` | 修改 | 實作三層解析管線（Tier 1 原生 -> Tier 2 靜態解包 -> Tier 3 增強動態嗅探），重構格式階層構建。 |
| `tests/test_packer.py` | 新增 | 新增 5 項 Dean Edwards Packer 演算法解碼、進制解析與邊界防護測試。 |
| `tests/test_static_sniffer.py` | 新增 | 新增 3 項靜態混淆嗅探、標頭生成與安全回退測試。 |
| `tests/test_sniffer.py` | 修改 | 擴充測試案例至 8 項，新增 Stealth 注入與播放器激活驗證。 |
| `tests/test_extractor.py` | 修改 | 擴充測試案例至 13 項，新增 Tier 2 優先命中與平滑降級驗證。 |
| `tests/test_cli.py` | 修改 | 更新版本號斷言至 `1.5.0`。 |
| `docs/01_spec.md` | 更新 | 新增 F10（靜態混淆解包嗅探器）與 F11（延遲加載播放器激活）功能規格與模組表。 |
| `docs/02_architecture.md` | 更新 | 新增第 9 節「三層式串流提取管道拓撲圖 (Three-Tier Pipeline)」。 |
| `docs/03_test_plan.md` | 更新 | 擴展測試矩陣，納入 TC-PK-01~05、TC-SS-01~03、TC-SN-05 與 TC-EX-09~10。 |
| `docs/04_test_report.md` | 更新 | 更新 72/72 測試通過報告與執行日誌佐證。 |
| `docs/05_security_audit.md` | 更新 | 新增第 3.15 節「靜態解包演算法安全與 ReDoS 防禦審核 (CWE-1333/CWE-400)」。 |
| `docs/06_deployment_guide.md` | 更新 | 補充輕量容器直接支援靜態混淆站點說明。 |
| `docs/07_changelog.md` | 更新 | 完整記錄 v1.5.0 版本演進歷程、Nero 流程重構細節與全檔案審計軌跡。 |
