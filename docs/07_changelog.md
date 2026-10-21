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
  [ v1.4.0 (2026-10-22) 獨立音軌識別、雙串流混流與音畫同步升級 ] ─── (當前版本)
    ├── 核心修復: 獨立音軌智慧探測 (StreamExtractor.get_best_audio_format)
    ├── MP4 最佳化: 優先匹配 AAC (YouTube 140 軌，避開 DRC 壓縮軌)，次選高碼率音軌
    ├── 契約保護: StreamDetails 容器支援向前向下 3-Tuple 解構相容
    ├── 雙輸入混流: FFmpeg 支援 -i <video> -i <audio> -map 0:v:0 -map 1:a:0
    ├── 聲畫嚴格同步: 配置 -fflags +genpts -avoid_negative_ts make_zero -max_interleave_delta 0 -shortest
    ├── 編碼自適應: AAC 直接流拷貝，Opus 轉碼 AAC 並啟用 aresample 重採樣同步
    └── 專案規範: 版本升級至 v1.4.0，測試案例擴充至 58 項全數通過
+-------------------------------------------------------------------------------+
```

---

## 2. 版本詳細異動清單 (Version Details)

### [v1.4.0] - 2026-10-22

#### 🎯 核心修訂主旨
針對 YouTube 1080p/2K/4K 等高畫質串流及 DASH 格式網站將視訊軌（`acodec == 'none'`）與音訊軌分離儲存之架構，實作**獨立音軌智慧探測、雙輸入混流與音畫時間戳嚴格同步機制**，徹底解決「音軌未下載或未同步」議題。

#### 🚀 新增功能 (Features)
1. **獨立音軌智慧匹配模組 (`StreamExtractor.get_best_audio_format`)**
   - 自動過濾無視訊之純音訊串流 (`vcodec in ('none', None, '')`, `acodec not in ('none', None, '')`)。
   - 容器格式相容性優先策略：針對 MP4 輸出容器，優先挑選 AAC/m4a 原生音訊（如 YouTube 140 軌），主動避開 `-drc`（動態範圍壓縮）音軌以維持原音質；若無 AAC 則挑選最高位元率音軌（如 Opus 251 軌）。
   - 在 `get_available_formats` 中為每個無音訊之視訊格式動態掛載最佳音訊直鏈、請求標頭與編碼資訊。
2. **結構化與向下相容容器 (`StreamDetails`)**
   - 封裝 `stream_url`、`quality_label`、`headers`、`audio_url`、`audio_headers`、`audio_codec` 與 `is_muxed`。
   - 繼承 `tuple` 類別，保持原有 3-Tuple `(url, label, headers)` 解構語法 100% 向下相容，既有外層程式碼與測試無痛運作。
3. **FFmpeg 雙輸入混流與時間戳嚴格同步 (`FFmpegDownloader.build_command`)**
   - 雙串流輸入組裝：`-i <VIDEO_URL> -i <AUDIO_URL> -map 0:v:0 -map 1:a:0`。
   - 雙路獨立請求標頭支援：為視訊與音訊分別配置 `-reconnect` 與專屬之 `-headers`，杜絕音訊 CDN 分片取片 403 阻斷。
   - 聲畫時間戳平移與交錯保護：
     - `-fflags +genpts`：補齊串流缺失之封包 PTS 時間戳。
     - `-avoid_negative_ts make_zero`：將視訊與音訊起始時間戳平移對齊至 0，消除起始相對時間差所引起的音畫不同步。
     - `-max_interleave_delta 0`：解除固定交錯佇列逾時限制，適應雙路網路封包延遲抖動，杜絕封包丟棄。
     - `-shortest`：任一串流到達結尾時即刻終止混流，防範畫面凍結或無效靜音片尾。
4. **音訊編碼自適應轉換策略**
   - 若音軌為 AAC：直接流拷貝 (`-c:a copy -bsf:a aac_adtstoasc`)，0% CPU 損耗秒級完成封裝。
   - 若音軌為非 AAC（如 Opus/Vorbis）且輸出容器為 MP4：自適應啟用輕量轉碼 (`-c:a aac -b:a 192k`) 並調用重採樣濾鏡 (`-af aresample=async=1:first_pts=0`)，確保跨裝置/播放器相容性與精準音畫對齊。
5. **CLI 互動選單與狀態提示**
   - 格式選單動態標註 `音軌: 獨立混流 (aac)` 或 `音軌: 內嵌 (mp4a)`。
   - 啟動下載時印出匹配音訊軌資訊與雙串流同步模式。
6. **版本號管理**
   - 版本號躍升至 `1.4.0`，CLI `-v` / `--version` 輸出 `pystream-downloader 1.4.0`。

#### 🛡️ 安全性加固 (Security Hardening)
1. **音訊 URL 參數注入防禦 (CWE-88)**
   - `FFmpegDownloader` 強制校驗 `audio_url` 不得以破折號 `-` 開頭，阻斷參數偽裝攻擊。
2. **音訊標頭 CRLF 注入阻斷 (CWE-113)**
   - 對傳入之 `audio_headers` 執行白名單字元校驗，凡包含 `\r` 或 `\n` 立即引發 `ValueError` 強制阻斷。
3. **雙串流緩衝佇列防溢位 (CWE-400)**
   - 配置 `-max_interleave_delta 0` 與 `-shortest`，杜絕長時間網路雙串流交錯所引起的記憶體無限制膨脹或無限循環。

#### 🧪 測試與驗證擴充 (Testing & Quality)
- 單元與整合測試案例由 52 項增至 **58 項**（+6 項，全數 PASS）：
  - `tests/test_extractor.py`: 新增 TC-EX-07 (獨立音軌智慧探測與 StreamDetails 封裝) 與 TC-EX-08 (內嵌音軌直通校驗)（2 項）。
  - `tests/test_downloader.py`: 新增 TC-DL-04 (雙輸入混流與時間戳同步)、TC-DL-05 (Opus 轉碼 AAC 與重採樣)、TC-DL-06 (音訊 URL 參數注入防護)（3 項）。
  - `tests/test_stage2_self_check.py`: 新增 Test 13 冒煙自檢項（1 項）。
  - `docs/self_check.log`: 13 項階段 2 全鏈路冒煙自檢全數通過。

---

### [v1.3.0] - 2026-10-21

#### 🎯 核心修訂主旨
實作**解法三（Docker Compose 雙服務拆分 + 兩階段自適應自動升級架構 - Two-Phase Adaptive Auto-Escalation via Exit Code 42）**。日常 90%+ 任務以輕量容器（~420MB）秒級啟動，當遇動態 JavaScript 混淆站點（如 MissAV 等 `Unsupported URL`）時，透過標準 POSIX/Windows 退出碼協定（Exit Code 42），由調度腳本自動透明升級至全功能 Chromium 容器（~1.4GB），完美兼顧輕量、效能與通用性。

#### 🚀 新增功能 (Features)
1. **多階段容器建置與雙服務拆分 (Multi-Stage Docker & Compose Dual-Service)**
   - `Dockerfile` 實作多階段目標：`slim`（~420MB）與 `full`（~1.4GB）。
   - `docker-compose.yml` 定義 `downloader`（預設服務）與 `downloader-full`（指定 `profiles: ["full"]`）。
2. **兩階段自適應自動升級協定 (Two-Phase Adaptive Escalation Protocol)**
   - `src/extractor.py` 定義標準例外 `NeedsFullSnifferError` 與狀態碼常數 `EXIT_CODE_NEED_FULL_SNIFFER = 42`。
   - `src/cli.py` 捕獲此例外並調用 `sys.exit(42)` 返回標準狀態碼。
3. **智慧調度腳本自動升級 (Smart Dispatchers)**
   - `deploy.ps1` 與 `deploy.sh` 捕獲 Exit Code 42 時自動透明升級至 `downloader-full`。
4. **版本號管理**
   - 版本號躍升至 `1.3.0`。

---

### [v1.2.0] - 2026-10-21

#### 🎯 核心修訂主旨
針對未被 `yt-dlp` 原生支援、且使用前端 JavaScript 動態混淆加密的各類影音網站，落實**方案 A（Playwright 無頭瀏覽器動態嗅探器 - The Stream Detector 引擎）**。

#### 🚀 新增功能 (Features)
1. **無頭瀏覽器串流嗅探模組 (`src/sniffer.py` / `HeadlessStreamSniffer`)**
2. **智慧自動回退鏈路 (Seamless Fallback Pipeline)**
3. **CLI 參數擴充 (`--sniff`, `--sniff-timeout`)**
4. **版本號躍升為 `1.2.0`**

---

### [v1.1.0] - 2026-10-21

#### 🎯 核心修訂主旨
解決使用 yt-dlp 解析目標串流時遭遇 Cloudflare 防火牆人機驗證（`HTTP Error 403 caused by Cloudflare anti-bot challenge`）之阻斷問題。

#### 🚀 新增功能 (Features)
1. **瀏覽器網路指紋偽裝 (Browser Impersonation)**
2. **本機瀏覽器憑證連動 (Browser Cookies Access)**
3. **HTTP 請求標頭貫穿至 FFmpeg (Header Propagation)**
4. **版本號躍升至 `1.1.0`**

---

### [v1.0.0] - 2026-10-21

#### 📦 初始功能發布
- 依據 `workflow.md` 五階段協作流程完成設計與交付。
- 串流開播輪詢、互動式畫質選單、FFmpeg 串流直接複製、鍵盤熱鍵凍結/恢復、斷線指數退避重試、容器化與一鍵部署腳本。

---

## 3. 檔案變更歷程與追蹤軌跡 (File Audit Trail)

| 檔案路徑 | 變更類型 | 異動行數/重點摘要 |
| :--- | :---: | :--- |
| `src/__init__.py` | 修改 | 版本號升級至 `1.4.0`。 |
| `src/extractor.py` | 修改 | 新增 `StreamDetails`、`get_best_audio_format()`，更新 `get_available_formats()` 與 `resolve_stream_details()` 支援雙流音軌直鏈與標頭。 |
| `src/downloader.py` | 修改 | `FFmpegDownloader` 支援 `audio_url`、`audio_headers`、`audio_codec`，組裝雙輸入混流、A/V 時間戳同步與 Opus->AAC 轉碼。 |
| `src/cli.py` | 修改 | 格式選單標註音軌資訊，解析雙串流直鏈並傳遞至 `FFmpegDownloader`。 |
| `tests/test_cli.py` | 修改 | 更新版本號斷言至 `1.4.0`。 |
| `tests/test_extractor.py` | 修改 | 新增 TC-EX-07 (音軌探測與 StreamDetails 封裝) 與 TC-EX-08 (內嵌音軌直通) 測試。 |
| `tests/test_downloader.py` | 修改 | 新增 TC-DL-04 (雙輸入混流與時間戳同步)、TC-DL-05 (Opus 轉碼 AAC)、TC-DL-06 (音訊參數注入防護) 測試。 |
| `tests/test_stage2_self_check.py` | 修改 | 新增 Test 13 冒煙自檢項（13/13 通過）。 |
| `docs/self_check.log` | 更新 | 記錄 13 項 Stage 2 自檢執行日誌（13/13 OK）。 |
| `docs/01_spec.md` | 更新 | 新增 F9 獨立音軌識別、雙串流混流與音畫時間戳同步規格。 |
| `docs/02_architecture.md` | 更新 | 新增 Section 8 雙串流混流與音畫同步架構拓撲圖。 |
| `docs/03_test_plan.md` | 更新 | 擴展測試矩陣（新增 TC-EX-07, TC-EX-08, TC-DL-04, TC-DL-05, TC-DL-06, TC-SC-13）。 |
| `docs/04_test_report.md` | 更新 | 更新測試日誌佐證與測試總數（58/58 PASS）。 |
| `docs/05_security_audit.md` | 更新 | 新增雙輸入音訊 URL 參數注入防護 (CWE-88)、CRLF 注入 (CWE-113) 與交錯佇列防禦 (CWE-400)。 |
| `docs/06_deployment_guide.md` | 更新 | 更新常見問題排查（補充音軌缺失與音畫不同步之處置指引）。 |
| `docs/07_changelog.md` | 更新 | 完整記錄 v1.4.0 版本演進歷程、雙流同步混流特性與全檔案軌跡。 |
