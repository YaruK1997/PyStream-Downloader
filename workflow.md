# 系統開發 / 腳本設計 五階段協作工作流程規範

本工作流程整合多模型協作架構（Claude Sonnet 5.5、Gemini 3.8 Flash、Claude Opus 5.5、Gemini 4）與全域技能庫（Skills & Plugins），針對系統開發與自動化腳本設計，建立嚴謹的遞交、驗證、回饋修復與部署閉環。

---

## 1. 流程架構視覺化 (Workflow & Skills ASCII)

```text
+-------------------------------------------------------------------------------+
|                    系統開發 / 腳本設計 五階段工作流程與技能配置                 |
+-------------------------------------------------------------------------------+

  [全域基礎規範 (Global Meta)]
   ├── using-superpowers (各階段前置強制檢查與調用順序)
   ├── i-have-adhd (全流程輸出溝通約束：條列化、時效、禁廢話)
   └── writing-skills (開發流程經驗沉澱為自定義新技能)

  [ 原始需求 / Prompt ]
           |
           v
+----------------------------------+
| 階段 1: 需求明確化與流程最佳化    |  負責模型：Claude Sonnet 5.5
| - 邊界定義、規格收斂、邏輯最佳化   |  綁定技能：brainstorming, writing-plans
| - 交付產出：docs/01_spec.md      |
+----------------------------------+
           |
           | [交付 spec.md / 需求規格書]
           v
+----------------------------------+ <-----------------------------------+
| 階段 2: 架構設計與功能編寫        |                                     |
| - 系統架構圖、程式碼實作、自驗   |  負責模型：Gemini 3.8 Flash         |
| - 綁定技能：using-git-worktrees, |                                     |
|   PWG, executing-plans, TDD,     |                                     |
|   subagent-dev, web-guidance     |                                     |
+----------------------------------+                                     |
           |                                                             |
           | [交付 原始碼 / 模組 / 初驗報告]                              | [修復迴路]
           v                                                             | (Issue Ticket)
+----------------------------------+                                     |
| 階段 3A: 測試計畫設計            |  負責模型：Claude Opus 5.5          |
| - 覆蓋率矩陣、極端邊界推演       |  綁定技能：systematic-debugging     |
| - 交付產出：tests/ 與測試規格書  |                                     |
+----------------------------------+                                     |
           |                                                             |
           | [交付 測試腳本與計畫書]                                      |
           v                                                             |
+----------------------------------+                                     |
| 階段 3B: 測試執行與驗證          |  負責模型：Claude Sonnet 5.5        |
| - 自動化測試執行、產出瑕疵工單   |  綁定技能：                         |
| - 程式碼審查 (Code Review)       |    verification-before-completion,  |
+----------------------------------+    requesting-code-review           |
           |                               |                             |
           | (全數測試通過)                 +--[ 測試未通過 / 邏輯缺失 ]---+
           v
+----------------------------------+
| 階段 4: 資訊安全檢查             |  負責模型：Gemini 4
| - SAST 弱點掃描、憑證外洩檢測    |  綁定技能：PWG, systematic-debugging,
| - 弱點成因分析與修復指引         |    verification-before-completion
+----------------------------------+                               |
           |                                                       |
           | (資安稽核核可)                 +--[ 發現高/中風險弱點 ]---+
           v
+----------------------------------+
| 階段 5: 環境容器化與部署         |  負責模型：Gemini 3.8 Flash
| - Dockerfile、Compose、健康檢查  |  綁定技能：verification-before-completion,
| - 分支整合與發布 (Git Finishing) |    finishing-a-development-branch
+----------------------------------+
           |
           v
  [ 交付與上線完成 (Done) ]
```

---

## 2. 五階段詳細作業與技能配置規範

### 階段 1：需求明確化 / 最佳化 (Requirements Clarification & Optimization)

- **負責模型**：Claude Sonnet 5.5 / Gemini 3.8 Flash
- **核心目標**：杜絕模糊需求，釐清邊界條件與潛在邏輯衝突，產出具備可執行性的設計規格。
- **輸入依據**：使用者初始任務描述、業務場景、現有環境限制。
- **調用技能 (Skills Allocation)**：
  1. `brainstorming` (`skills/brainstorming/SKILL.md`)：
     - **使用時機**：任務啟動初始階段。
     - **職責**：協作對話探討架構約束、替代方案與邊界條件，收斂出精確 PRD/規格文件。
  2. `writing-plans` (`skills/writing-plans/SKILL.md`)：
     - **使用時機**：需求明確收斂後。
     - **職責**：將規格拆解為高內聚、低耦合、包含具體驗證指令的小顆粒度實作計畫。
- **執行重點**：
  1. 需求拆解：將大目標拆解為可驗證的最小功能單元（Bounded Context）。
  2. 邊界與異常梳理：定義極端輸入、網路逾時、資料遺失等邊際情況（Edge Cases）。
  3. 流程最佳化：評估演算法複雜度與作業鏈路，剔除不必要的中繼步驟。
- **產出文件**：`docs/01_spec.md`（包含功能範圍、非功能需求、介面定義與資料流）。

---

### 階段 2：架構及功能編寫 (Architecture & Implementation)

- **負責模型**：Gemini 3.8 Flash
- **核心目標**：高速度、高品質產出模組化程式碼，並完成模型自驗（Self-Verification）。
- **輸入依據**：`docs/01_spec.md`。
- **調用技能 (Skills Allocation)**：
  1. `using-git-worktrees` (`skills/using-git-worktrees/SKILL.md`)：
     - **使用時機**：編碼前準備。
     - **職責**：建立乾淨獨立的 Workspace，防止干擾現行開發分支。
  2. `PWG` (`skills/PWG/core-governance.md`)：
     - **使用時機**：架構設計與主體編碼全程。
     - **職責**：啟動 `[DEV]` 治理模式，約束架構分層、介面隔離，防止過度工程化循環。
  3. `executing-plans` (`skills/executing-plans/SKILL.md`)：
     - **使用時機**：執行實作任務時。
     - **職責**：逐項依據階段 1 計畫清單嚴格執行，於各檢查點回報進度。
  4. `test-driven-development` (`skills/test-driven-development/SKILL.md`)：
     - **使用時機**：編寫核心功能模組時。
     - **職責**：落實「測試先行 → 觀察失敗 → 編寫最少通過碼」紅綠循環。
  5. `subagent-driven-development` / `dispatching-parallel-agents` (`skills/subagent-driven-development/SKILL.md`, `skills/dispatching-parallel-agents/SKILL.md`)：
     - **使用時機**：面對大型模組拆解或多個無相依獨立任務時。
     - **職責**：派發隔離上下文的 Implementer 子代理人平行實作，防止主對話記憶體污染。
  6. `modern-web-guidance` / `chrome-extensions` (`plugins/modern-web-guidance-plugin/skills/modern-web-guidance/SKILL.md`, `plugins/modern-web-guidance-plugin/skills/chrome-extensions/SKILL.md`)：
     - **使用時機**：涉及現代 Web 前端（UI、動畫、CWV）或 Chrome 擴充套件開發時。
     - **職責**：強制依循最新標準 API 與 MV3 安全架構。
  7. `receiving-code-review` (`skills/receiving-code-review/SKILL.md`)：
     - **使用時機**：接收階段 3B 測試瑕疵工單或階段 4 資安漏洞建議時。
     - **職責**：以嚴謹技術實質為導向重構修復程式碼，杜絕表面敷衍修改。
- **執行重點**：
  1. 架構設計：繪製模組依賴圖與系統元件交互圖（採用 ASCII / 純文字結構）。
  2. 編碼實作：依據規格落實模組化設計，禁止單一巨大函數（Monolithic blocks）。
  3. 自主驗證：編寫完成後立即執行靜態語法檢查與基本冒煙測試（Smoke Test），確認無語法與執行錯誤。
- **產出文件**：專案原始碼（`src/`）、架構說明文件（`docs/02_architecture.md`）、自驗紀錄（`docs/self_check.log`）。

---

### 階段 3：測試計畫設計及執行 (Test Plan Design & Execution)

- **負責模型**：
  - **階段 3A（測試計畫設計）**：Claude Opus 5.5
  - **階段 3B（測試執行與驗證）**：Claude Sonnet 5.5
- **核心目標**：由 Claude Opus 5.5 發揮深度推理設計極限測試矩陣，再交付 Claude Sonnet 5.5 高效執行自動化測試、收集終端日誌並產出瑕疵反饋。
- **輸入依據**：`docs/01_spec.md` 與 階段 2 產出之原始碼。
- **子階段分工與調用技能 (Skills Allocation)**：
  1. **階段 3A：測試計畫設計 (Claude Opus 5.5)**：
     - `systematic-debugging` (`skills/systematic-debugging/SKILL.md`)：
       - **使用時機**：測試架構規劃時。
       - **職責**：預先推演失敗模式、極端邊界條件（Edge Cases）與異常注入情境。
     - **產出文件**：`tests/` 自動化測試腳本套件、`docs/03_test_plan.md`（測試規格與覆蓋率矩陣）。
  2. **階段 3B：測試執行與驗證 (Claude Sonnet 5.5)**：
     - `verification-before-completion` (`skills/verification-before-completion/SKILL.md`)：
       - **使用時機**：執行測試套件與判定結果時。
       - **職責**：實測自動化腳本，無最新實際終端執行日誌（stdout/stderr 0 錯誤）絕不判定通過。
     - `requesting-code-review` (`skills/requesting-code-review/SKILL.md`)：
       - **使用時機**：單元與整合測試全數通過後。
       - **職責**：派發乾淨上下文的審查代理人（Reviewer Subagent），針對架構品質與規格合規發起獨立 Code Review。
     - **產出文件**：`docs/04_test_report.md`（通過清單與失敗清單 / 瑕疵工單）。
- **執行重點**：
  1. 測試設計（Opus 5.5）：規劃黑箱、白箱、單元與整合測試，覆蓋正常路徑與極端異常路徑。
  2. 執行與收集（Sonnet 5.5）：在乾淨環境批次執行測試腳本，完整收集運行日誌。
  3. 瑕疵反饋（Sonnet 5.5）：若測試失敗，精準整理失敗行號、重現步驟、預期與實際結果，產出修正工單發回 **Gemini 3.8 Flash** 進行程式碼修改。

---

### 階段 4：資訊安全檢查 (Security Audit & Vulnerability Assessment)

- **負責模型**：Gemini 4
- **核心目標**：深入掃描系統安全性盲點，確保符合安全編碼規範與最小權限原則。
- **輸入依據**：通過測試之專案原始碼與相依套件清單。
- **調用技能 (Skills Allocation)**：
  1. `PWG` (`skills/PWG/core-governance.md`)：
     - **使用時機**：系統安全架構審查。
     - **職責**：核驗服務架構是否落實最小權限原則、無敏感資訊硬編碼。
  2. `systematic-debugging` (`skills/systematic-debugging/SKILL.md`)：
     - **使用時機**：掃描發現 CWE 弱點或 CVE 威脅時。
     - **職責**：分析弱點攻擊鏈，給出確定性修復邏輯建議與重構工單。
  3. `verification-before-completion` (`skills/verification-before-completion/SKILL.md`)：
     - **使用時機**：漏洞修復複查時。
     - **職責**：強制比對複檢掃描日誌，確認 0 弱點方可核可放行。
- **執行重點**：
  1. 靜態原始碼安全審查（SAST）：檢查注入攻擊（SQLi / Command Injection）、路徑周遊（Path Traversal）、記憶體洩漏與反序列化風險。
  2. 機敏資訊檢驗：掃描硬編碼金鑰（Hardcoded Secrets）、API Token、連線密碼與未授權端點。
  3. 相依套件檢驗（SCA）：核對相依函式庫之已知 CVE 漏洞。
  4. 漏洞派工：發現任何中高風險弱點時，列出弱點成因、CWE 編號與修補建議，退回 **Gemini 3.8 Flash** 實施安全重構。
- **產出文件**：`docs/05_security_audit.md`（資安合規報告與修復檢核表）。

---

### 階段 5：容器化及部署 (Containerization & Deployment)

- **負責模型**：Gemini 3.8 Flash
- **核心目標**：標準化運作環境，封裝服務容器，落實一鍵部署與健康檢查機制。
- **輸入依據**：通過資安審查之穩定原始碼與執行環境參數。
- **調用技能 (Skills Allocation)**：
  1. `verification-before-completion` (`skills/verification-before-completion/SKILL.md`)：
     - **使用時機**：容器啟動與探針檢測。
     - **職責**：實測 Docker 容器啟動、Healthcheck 端點響應（HTTP 200/Healthy），取得明確運算證據。
  2. `finishing-a-development-branch` (`skills/finishing-a-development-branch/SKILL.md`)：
     - **使用時機**：部署驗證完成後。
     - **職責**：引導執行 Git 工作空間清理、分支整合決策（Merge / PR / Delete Worktree）。
- **執行重點**：
  1. 輕量化映像檔建置：撰寫符合最佳實踐的 `Dockerfile`（多階段構建 Multi-stage build、非 root 使用者權限）。
  2. 服務編排：撰寫 `docker-compose.yml`，定義網路隔離、資料持久化（Volume）與資源限制。
  3. 部署驗證：執行容器啟動測試與 Healthcheck 探針，驗證腳本自動重啟與環境變數載入。
- **產出文件**：`Dockerfile`、`docker-compose.yml`、`deploy.sh` / `deploy.ps1`、`docs/06_deployment_guide.md`、`docs/07_changelog.md`。

---

## 3. 全域與跨階段基礎技能配置 (Global & Meta Skills)

| 技能名稱              | 相對路徑                            | 作用範圍       | 調用時機與職責                                                         |
| :-------------------- | :---------------------------------- | :------------- | :--------------------------------------------------------------------- |
| **using-superpowers** | `skills/using-superpowers/SKILL.md` | 全階段對話前置 | 於任何對話初始階段強制觸發，嚴守「先流程技能再實作技能」之調用紀律。   |
| **i-have-adhd**       | `skills/i-have-adhd/SKILL.md`       | 全流程輸出風格 | 確保各階段輸出直指下一步行動、條列化步驟、重申當前狀態、抑制發散旁支。 |
| **writing-skills**    | `skills/writing-skills/SKILL.md`    | 流程複盤與沉澱 | 開發完成後將可複用的特定腳本或架構規範標準化為新技能，擴充團隊工具箱。 |

---

## 4. 跨階段回饋與修正協作矩陣

| 觸發來源 (階段)                 | 判定條件                       | 退回處理角色         | 修正閉環動作                                           | 重新推進閘門                          |
| :------------------------------ | :----------------------------- | :------------------- | :----------------------------------------------------- | :------------------------------------ |
| **階段 3B (Claude Sonnet 5.5)** | 測試案例未通過 / 邊界異常      | **Gemini 3.8 Flash** | 依循 `systematic-debugging` 進行根本原因定位並重構修復 | 重跑階段 3B 失敗案例直至全數通過      |
| **階段 4 (Gemini 4)**           | 發現 CWE 弱點 / 憑證洩漏 / CVE | **Gemini 3.8 Flash** | 依循資安修復建議重構程式碼，移除機敏金鑰或升級套件     | 重新執行階段 4 掃描取得無高危風險標記 |

---

## 5. 階段交付檢核清單 (Gate Checklist)

- [ ] **階段 1 檢核點**：需求範圍已明確，無任何開放性待定義項（No Ambiguity）。
- [ ] **階段 2 檢核點**：模組結構清晰，自驗無語法錯誤（Self-check passed）。
- [ ] **階段 3A 檢核點**：測試計畫覆蓋率與邊界極限案例推演完備（Test plan completed）。
- [ ] **階段 3B 檢核點**：測試執行通過率達標，邊界與失敗案例清單皆已清空（0 Failures）。
- [ ] **階段 4 檢核點**：資安審計通過，無高危弱點與明文機敏資料（0 High/Medium Vulnerabilities）。
- [ ] **階段 5 檢核點**：容器映像檔可正常建置啟動，健康檢查回傳 200/Healthy（Ready to Deploy）。
