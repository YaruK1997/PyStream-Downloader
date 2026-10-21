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
| `src/__init__.py` | 修改 | 版本號升級至 `1.4.1`。 |
| `src/sniffer.py` | 修改 | 新增 `sanitize_locale()`，修正 `locale` 為單一 BCP-47 標籤，多語系改由 `extra_http_headers` 承載，增加 CDP 協定異常自動防禦降級。 |
| `tests/test_cli.py` | 修改 | 更新版本號斷言至 `1.4.1`。 |
| `tests/test_sniffer.py` | 修改 | 新增語系標籤清洗、參數分離檢驗與 CDP 協定異常降級測試（3 項）。 |
| `docs/01_spec.md` | 更新 | 補充 F7 無頭嗅探 CDP 語系設置規範與容錯降級機制。 |
| `docs/02_architecture.md` | 更新 | 更新無頭瀏覽器動態嗅探拓撲之語系配置與標頭約定。 |
| `docs/03_test_plan.md` | 更新 | 擴展測試矩陣（新增 TC-SN-03 與 TC-SN-04）。 |
| `docs/04_test_report.md` | 更新 | 更新測試日誌佐證與測試總數（61/61 PASS）。 |
| `docs/05_security_audit.md` | 更新 | 新增語系字串正則清洗與 CDP 協定防禦審查 (CWE-20)。 |
| `docs/06_deployment_guide.md` | 更新 | 更新常見問題排查（補充 Invalid locale name 處置指引）。 |
| `docs/07_changelog.md` | 更新 | 完整記錄 v1.4.1 版本演進歷程、語系標準化修復與全檔案軌跡。 |
