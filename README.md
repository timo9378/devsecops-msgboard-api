# DevSecOps Pipeline Demo — Message Board API

本專案示範一條 **DevSecOps CI Pipeline**：每次 `git push` 到 GitHub，GitHub Actions 會自動
**安裝相依 → 跑測試 → 打包 → 依賴弱點掃描 → 機密掃描 → 靜態程式碼掃描 → 上傳報告**，
讓團隊在合併前就攔截功能與安全問題。

> 應用本體沿用課程 Kubernetes 作業的後端 API（留言板），本作業聚焦在它的 CI/安全 pipeline。

---

## 1. 程式語言與應用

| 項目 | 說明 |
|---|---|
| 語言 | **Python 3.13** |
| 框架 | FastAPI（REST API）+ uvicorn |
| 資料庫 | PostgreSQL（asyncpg；本 pipeline 的測試不依賴 DB） |
| 認證 | JWT（**PyJWT**）+ bcrypt 密碼雜湊 |
| 功能 | 使用者註冊 / 登入、發留言、列留言、health probe |

主要程式：
- [`app/auth.py`](app/auth.py) — 密碼雜湊與 JWT 簽發 / 驗證（**自動化測試對象**）
- [`app/main.py`](app/main.py) — FastAPI 路由
- [`app/config.py`](app/config.py) — 全部設定走環境變數
- [`tests/test_auth.py`](tests/test_auth.py) — pytest 自動化測試

本機跑測試：
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

---

## 2. Pipeline 設計

定義於 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)，對應作業建議的流程：

```
push to GitHub
  → install dependencies   (pip install)
  → run tests              (pytest)              [硬性 gate]
  → build / package        (docker build)        [硬性 gate]
  → dependency vuln scan   (pip-audit)           [硬性 gate]
  → secret scan            (gitleaks)            [硬性 gate]
  → static code scan       (Bandit)              [report-only]
  → upload scan results    (Actions artifacts)
```

| 階段 | 工具 | 為什麼選它 | 失敗時會擋 build？ |
|---|---|---|---|
| 測試 | **pytest** | Python 標準測試框架 | ✅ |
| 打包 | **docker build** | 多階段、非 root，產出可部署 image | ✅ |
| 依賴弱點 | **pip-audit** | Python 原生、能解析傳遞依賴；不需 NVD API Key（避開 OWASP Dependency-Check 的 key 問題） | ✅ |
| 機密掃描 | **gitleaks** | Marketplace 常用，掃 git 內容是否含金鑰/密碼 | ✅ |
| 靜態掃描 | **Bandit** | Python SAST，抓 hardcoded secret、不安全用法 | report-only（產報告不擋） |

每個掃描階段都把報告以 **Actions artifact** 上傳（`pip-audit-report.json`、`gitleaks-report.sarif`、
`bandit-report.sarif`、`test-results.xml`），可在每次 run 的頁面下載檢視。

---

## 3. 測試過程（繳交用紀錄）

### 紀錄總覽（實際 GitHub Actions runs）

| # | 紀錄 | commit | run | 結果 |
|---|---|---|---|---|
| 1 | 成功（基線） | `31afcdd` | [26959181034](https://github.com/timo9378/devsecops-msgboard-api/actions/runs/26959181034) | ✅ 5 job 全綠 |
| 2 | 故意失敗（功能測試） | `1bfe4de` | [26959686892](https://github.com/timo9378/devsecops-msgboard-api/actions/runs/26959686892) | ❌ test 紅、build 被擋 |
| 3 | 修正後成功 | `923cb74` | [26959810880](https://github.com/timo9378/devsecops-msgboard-api/actions/runs/26959810880) | ✅ 回綠 |
| 4 | 依賴弱點（修補前） | `320ba60` | [26959975464](https://github.com/timo9378/devsecops-msgboard-api/actions/runs/26959975464) | ❌ dependency-scan 紅 |
| 5 | 依賴弱點（修補後） | `527e622` | [26960098370](https://github.com/timo9378/devsecops-msgboard-api/actions/runs/26960098370) | ✅ 回綠 |

> 截圖請到上表對應 run 頁面擷取；建議檔名如下供文件引用。

### 3.1 成功紀錄 ✅（run 26959181034）
- 所有 job 綠燈：test / build / dependency-scan / secret-scan / sast。
- 截圖：`docs/01-success.png`

### 3.2 故意失敗紀錄 ❌（功能測試，run 26959686892）
- 改動：`app/auth.py` 的 `verify_password` 故意改成永遠回傳 `True`，使 `test_wrong_password_rejected` 失敗。
- 結果：**test job 紅燈**，且 **build job 因 `needs: test` 被 skip**——pipeline 在打包前就擋下缺陷。
- 截圖：`docs/02-test-fail.png`

### 3.3 修正後再次成功 ✅（run 26959810880）
- 改動：還原 `verify_password`。
- 結果：test job 恢復綠燈，全 pipeline 回綠。
- 截圖：`docs/03-test-fix.png`

### 3.4 套件弱點 — 修補前 / 後（加分）
- **修補前**（run 26959975464）：`PyJWT==2.10.1`，帶 **7 個 CVE**
  （PYSEC-2026-176/179/175/177/178/120、PYSEC-2025-183）。
  → **dependency-scan job 紅燈**，test/build 仍綠（凸顯掃描階段獨立把關）。
  - 截圖：`docs/04-vuln-before.png`
- **修補後**（run 26960098370）：升級為 `PyJWT==2.13.0`（**只改版號、程式碼零改動**）。
  → pip-audit 乾淨、dependency-scan 回綠。
  - 截圖：`docs/05-vuln-after.png`

---

## 4. 產生的掃描報告與結果

| 報告 | 由哪個 job 產出 | 內容 |
|---|---|---|
| `test-results.xml` | test | pytest JUnit 結果 |
| `pip-audit-report.json` | dependency-scan | 相依套件已知 CVE 清單 |
| `gitleaks-report.sarif` | secret-scan | git 內容機密外洩掃描結果 |
| `bandit-report.sarif` | sast | Python 靜態程式碼弱點 |

> 下載位置：對應 Actions run 頁面下方的 **Artifacts** 區塊。

### 4.1 已接受風險（已處理但暫不升級）
| CVE | 套件 | 類型 | 為何暫不升級 | 緩解 |
|---|---|---|---|---|
| PYSEC-2026-161 | starlette 0.49.3 | Host header 路徑混淆 | fix 在 1.0.1，但目前 fastapi 仍鎖 `starlette <0.50`，無相容版本 | 本服務授權走 JWT（非 `request.url.path`）；k8s 部署前面有 ingress-nginx 正規化 Host header。已在 pip-audit 以 `--ignore-vuln PYSEC-2026-161` 標記並記錄。 |

---

## 5. 組員

- B11109007 楊泰和
- B11109041 吳榮傑
