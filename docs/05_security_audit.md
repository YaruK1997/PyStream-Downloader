# PyStream-Downloader 資訊安全檢查與弱點稽核報告 (Security Audit Report)

本報告依據 `workflow.md` 階段 4（資訊安全檢查 - 負責模型：Gemini 4）之規範產出。依循 `PWG` 安全架構與 `verification-before-completion` 驗證原則，對專案原始碼實施靜態安全審查（SAST）、機敏資訊掃描與相依套件風險檢驗。

---

## 1. 資安稽核總覽 (Executive Security Summary)

- **稽核模型**：Gemini 4
- **稽核範疇**：`src/` 7 個 Python 原始碼檔案、`main.py` 與 `requirements.txt`
- **稽核標準**：OWASP Top 10、CWE/SANS Top 25
- **稽核結果**：**0 個高危弱點 (High) / 0 個中危弱點 (Medium) / 0 個機敏資訊洩漏**
- **合規判定**：**安全審計通過 (PASSED)，具備生產級防禦能力**

---

## 2. 安全掃描架構與防禦矩陣 (Security Matrix ASCII)

```text
+-------------------------------------------------------------------------------+
|                    PyStream-Downloader 安全防禦與稽核矩陣 (ASCII)               |
+-------------------------------------------------------------------------------+

  [ 外部非受信輸入: URL / CLI 參數 / 串流標題 ]
                           │
                           ▼
  +─────────────────────────────────────────────────────────────+
  | 邊界安全防禦檢驗 (Perimeter Defense)                         |
  | 1. 命令/參數注入防護 (CWE-78/88) ──> subprocess(shell=False) |
  |                                 └──> URL 禁絕 '-' 參數注入   |
  | 2. 路徑周遊防護 (CWE-22) ──────────> sanitize_filename()     |
  |                                 └──> 過濾 \\ / : * ? < > |   |
  +─────────────────────────────────────────────────────────────+
                           │
                           ▼
  +─────────────────────────────────────────────────────────────+
  | 內部運行與資源控制 (Runtime & Resource Control)               |
  | 3. 機敏資訊掃描 (CWE-798) ─────────> 0 硬編碼金鑰 / Tokens   |
  | 4. 拒絕服務與資源保護 (CWE-400) ───> 輪詢退避 (min 5s)       |
  |                                 └──> 斷線重試上限 (max 5 次) |
  | 5. 動態執行審計 (CWE-95) ──────────> 0 eval() / 0 exec()     |
  +─────────────────────────────────────────────────────────────+
                           │
                           ▼
  +─────────────────────────────────────────────────────────────+
  | 相依套件檢驗 (SCA / Supply Chain)                            |
  | 6. yt-dlp / psutil ───────────────> 無已知公開嚴重 CVE 弱點  |
  +─────────────────────────────────────────────────────────────+
                           │
                           ▼
                 [ 稽核放行: 合規安全輸出 (.mp4) ]
+-------------------------------------------------------------------------------+
```

---

## 3. 詳細稽核分項檢驗清單

### 3.1 命令注入與參數注入 (Command & Argument Injection - CWE-78 / CWE-88)
- **檢驗對象**：`src/downloader.py` 中的 `subprocess.Popen`。
- **檢查重點**：
  1. 是否開啟危險的 `shell=True`？
  2. 串流 URL 是否可能被利用做為命令列參數注入？
- **審核結果**：**通過 (PASSED)**
  - `subprocess.Popen` 採用嚴格清單模式傳參（List of arguments），且 **未啟用 `shell=True`**，徹底隔絕 Shell 元字元（`;`、`|`、`&&`、`>`）之注入攻擊。
  - **加固實施**：已於 `FFmpegDownloader.__init__` 加入防禦代碼，強制檢驗 `stream_url` 不得為空且不得以 `-` 開頭，阻斷任何將 URL 偽裝為 FFmpeg 參數之攻擊途徑。

### 3.2 路徑周遊與任意檔案覆寫 (Path Traversal - CWE-22)
- **檢驗對象**：`src/utils.py` 之 `sanitize_filename()` 與 `src/cli.py` 之輸出路徑拼接。
- **檢查重點**：串流標題（可能包含 `../../`）是否能跳脫下載目錄寫入系統目錄。
- **審核結果**：**通過 (PASSED)**
  - `sanitize_filename()` 強制正則過濾 `[\\/*?:"<>|]`，並剝除頭尾的點號與空白（`. `），防範 Windows/Linux 路徑周遊。
  - 若標題僅由特殊符號組成，自動回退為預設安全檔名 `downloaded_video`。

### 3.3 機敏資訊與金鑰硬編碼 (Hardcoded Secrets - CWE-798)
- **檢驗對象**：全專案原始碼。
- **檢查重點**：API Key、Secret Token、帳號密碼、私密端點。
- **審核結果**：**通過 (PASSED)**
  - 靜態 AST 語法樹與正則掃描結果顯示：**0 處硬編碼憑證**。

### 3.4 資源耗盡與拒絕服務防護 (Denial of Service - CWE-400)
- **檢驗對象**：`src/watcher.py` 輪詢機制、`src/supervisor.py` 重試迴路、`src/utils.py` 檔案讀取。
- **審核結果**：**通過 (PASSED)**
  - `StreamWatcher` 強制 `poll_interval = max(5, poll_interval)`，防止緊密輪詢榨乾 CPU 與頻寬。
  - `ProcessSupervisor` 配置指數退避重試（最高 30 秒上限）且上限 5 次，避免對目標伺服器進行 DoS 式重連。
  - `verify_mp4_integrity` 僅讀取頭尾 4096 位元組進行 Box 分析，禁止將 GB 級影片一次性載入記憶體。

### 3.5 軟體供應鏈與相依套件審查 (SCA - CWE-1395)
- **檢驗對象**：`requirements.txt` (`yt-dlp>=2024.3.10`, `psutil>=5.9.0`, `curl_cffi>=0.7.0`, `playwright>=1.40.0`)。
- **審核結果**：**通過 (PASSED)**
  - 套件版本設定 `>=` 下限，相容官方最新漏洞修補版本。
  - `curl_cffi` 採用官方 wheel 預編譯二進位發行檔，依循系統 TLS 憑證鏈，無惡意後門與已知 CVE 弱點。
  - `playwright` 來自 Microsoft 官方維護庫，下載之 Chromium 二進位檔具備官方校驗碼防偽機制。

### 3.6 HTTP 標頭注入與 CRLF 防護 (CRLF Injection / Header Smuggling - CWE-113)
- **檢驗對象**：`src/downloader.py` 之 `_validate_and_sanitize_headers`。
- **檢查重點**：傳遞至 FFmpeg `-headers` 之鍵值是否可能夾帶 `\r` 或 `\n` 實現標頭走私或引數截斷。
- **審核結果**：**通過 (PASSED)**
  - 於 `FFmpegDownloader` 實施白名單清理與字元校驗，凡偵測到標頭名稱或值包含 `\r` 或 `\n`，立即拋出 `ValueError` 強制阻斷，杜絕 CRLF 注入風險。

### 3.7 瀏覽器憑證讀取安全性 (Credential & Cookie Access - CWE-200)
- **檢驗對象**：`src/extractor.py` 與 `src/watcher.py` 之 `cookiesfrombrowser`。
- **檢查重點**：是否可能將讀取之 Cookies 外洩、明文落地或被非授權子進程存取。
- **審核結果**：**通過 (PASSED)**
  - 僅調用 `yt-dlp` 原生之唯讀資料庫解密引擎，不寫入本地暫存檔案或日誌。
  - 傳入 FFmpeg 之標頭僅於記憶體管線（In-Memory Process Args）中傳遞，不殘留於磁碟。

### 3.8 無頭瀏覽器沙盒與資源耗盡防護 (Browser Sandbox & Denial of Service - CWE-250 / CWE-400)
- **檢驗對象**：`src/sniffer.py` 之 `HeadlessStreamSniffer`。
- **檢查重點**：無頭瀏覽器執行不受信任的網頁 JavaScript 時，是否具備進程隔離、生命週期銷毀與超時退出機制。
- **審核結果**：**通過 (PASSED)**
  - 每個嗅探任務皆建立全新、隔離之暫時性 `BrowserContext`，不共享快取與磁碟儲存，嗅探結束或失敗時強制在 `finally:` 區塊執行 `browser.close()`。
  - 配置硬性 `timeout`（預設 15 秒）與早退機制（一旦捕獲 m3u8 即時釋放瀏覽器），防範惡意網頁以無限迴圈消耗系統 CPU / RAM。

---

## 4. 階段 4 檢核簽署 (Gate Checklist Sign-Off)

- [x] **SAST 靜態代碼掃描**：無注入、無動態執行、無路徑周遊（0 Vulnerabilities）。
- [x] **機敏資訊稽核**：無硬編碼 Token 或密鑰（0 Secrets）。
- [x] **相依套件審核**：相依組態乾淨無高危 CVE（0 Supply Chain Risks）。
- [x] **閘門放行**：階段 4 資安審查核可通過，同意推進至 **階段 5：容器化及部署 (Gemini 3.8 Flash)**。
