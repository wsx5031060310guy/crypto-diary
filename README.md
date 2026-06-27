# Crypto Diary / 投資日記

Streamlit + Google Sheets 的唯讀投資日記儀表板。狀態：已部署於 Streamlit Cloud；網頁端是 read-only / 唯讀模式。

Crypto Diary 集中展示加密貨幣交易紀錄、ETF 投資紀錄、其他投資紀錄，以及每日自動投資排程產生的投資計劃與歷史日記。所有新增與修改都透過 Google Sheet、外部排程或匯入腳本完成，Streamlit app 只負責讀取與呈現。

## Live App

- Streamlit Cloud: https://crypto-diary-bvprx9psuxdvbuyrmohhgr.streamlit.app/
- GitHub repo: https://github.com/wsx5031060310guy/crypto-diary

## 📚 專案文件

```mermaid
graph TD
    README["README.md"] --> Architecture["docs/ARCHITECTURE.md"]
    README --> Flows["docs/FLOWS.md"]
    README --> Pages["docs/PAGES.md"]
    README --> Operations["docs/OPERATIONS.md"]
```

- [系統架構](docs/ARCHITECTURE.md)：專案總覽、技術棧、元件關係、目錄與資料模型。
- [操作與業務流程](docs/FLOWS.md)：Streamlit 連線、總覽彙總、日記閱讀、交易檢視與匯入流程。
- [頁面 / 路由 / 模組清單](docs/PAGES.md)：單頁 Streamlit 結構、tabs、外部 API 呼叫與主要函式。
- [安裝、執行、部署、維運](docs/OPERATIONS.md)：本機啟動、Secrets、環境變數、Streamlit Cloud 與常見維運操作。

## 快速開始

```bash
git clone https://github.com/wsx5031060310guy/crypto-diary.git
cd crypto-diary
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

本機需建立 `.streamlit/secrets.toml`，或在 Streamlit Cloud App Settings → Secrets 設定 Google Service Account 與 Sheet 資訊。

## 功能

- **總覽 Dashboard**
  - 交易筆數
  - 每日排程日記篇數
  - 累計買入 / 賣出金額與淨投入
  - 各分類、各資產持倉摘要

- **每日排程日記**
  - 顯示 `daily-investment-journal` cron 的歷史紀錄
  - 可閱讀完整 Markdown 投資計劃
  - 支援 Crypto / ETF / 其他分類篩選

- **交易紀錄**
  - 讀取 Google Sheet `trades` worksheet
  - 顯示 `asset`, `side`, `amount`, `price`, `total`, `note`

- **唯讀資料流**
  - Streamlit app 使用 `spreadsheets.readonly` scope
  - App 內沒有新增交易或寫入 Google Sheet 的 UI
  - 寫入統一由 Google Sheet 本身、排程或匯入腳本完成

## 架構

```text
每日投資排程 / 手動 Google Sheet 編輯
        │
        ├── Google Sheet: trades
        │     └── 交易紀錄 canonical store
        │
        ├── Google Sheet: journal_entries
        │     └── 每日排程投資計劃 / 歷史日記
        │
        └── Streamlit App
              └── 唯讀讀取 + dashboard / journal viewer
```

## Google Sheet Schema

### `trades`

| 欄位 | 說明 |
|---|---|
| `timestamp` | 交易時間，例如 `2026-05-08 09:00:00` |
| `asset` | 資產代號，例如 `BTC`, `ETH`, `SPY`, `QQQ` |
| `side` | `buy` 或 `sell` |
| `amount` | 數量 |
| `price` | 單價（TWD） |
| `total` | 總額（TWD） |
| `note` | 策略、訊號或備註 |

### `journal_entries`

| 欄位 | 說明 |
|---|---|
| `date` | 日記日期 |
| `run_time` | 排程執行時間 |
| `category` | `Crypto`, `ETF`, `其他`，可用逗號分隔 |
| `source` | 來源，例如 `Hermes cron daily-investment-journal` |
| `title` | 日記標題 |
| `summary` | 摘要 |
| `content_markdown` | 完整 Markdown 內容 |
| `github_path` | 對應 GitHub journal path，例如 `daily/YYYY-MM-DD.md` |
| `cron_output_path` | 本機 cron output path，如有 |
| `tags` | 標籤，例如 `daily-schedule,investment-plan,crypto,etf` |

## Streamlit Secrets

在 Streamlit Cloud 或本機 `.streamlit/secrets.toml` 設定：

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"

[sheet]
id = "Google Sheet ID"
worksheet = "trades"
journal_worksheet = "journal_entries"
```

> 不要把 service account JSON、`.streamlit/secrets.toml`、private key 或 token commit 到 GitHub。

## 匯入每日排程歷史紀錄

`scripts/import_investment_journals.py` 會把既有投資日記匯入 Google Sheet `journal_entries`，並自動去重。

預設匯入來源：

- `~/ai-investment-journal/daily/*.md`
- `~/ai-investment-journal/shadow/*.md`
- `~/.hermes/cron/output/751ec9850858/*.md`

執行：

```bash
python scripts/import_investment_journals.py
```

在 Mike 的 Hermes 環境中可使用既有 crypto bot venv：

```bash
/Users/mike-hermes-ai/.hermes/crypto_bot/venv/bin/python \
  /Users/mike-hermes-ai/projects/crypto-diary/scripts/import_investment_journals.py
```

可用環境變數覆蓋預設路徑與設定：

- `CRYPTO_BOT_SHEET_ID`
- `CRYPTO_BOT_GCP_CRED`
- `CRYPTO_BOT_JOURNAL_WORKSHEET`
- `AI_INVESTMENT_JOURNAL_DIR`
- `HERMES_INVESTMENT_CRON_OUTPUT`

## 每日排程整合

Hermes cron `daily-investment-journal` 每天 09:00 會：

1. 研究 World Monitor / Finance Monitor、BTC、ETH、SPY、QQQ 等市場資訊。
2. 產生 Crypto + ETF 投資策略。
3. 更新 `ai-investment-journal` repo 的 `daily/YYYY-MM-DD.md` 與 portfolio 狀態。
4. 同步日記內容到 Google Sheet `journal_entries`。
5. 本 Streamlit app 讀取 Google Sheet 並展示結果。

## 安全原則

- Web app 只讀取 Google Sheet，不提供寫入按鈕。
- Google API 憑證只放在 Streamlit Secrets 或本機安全路徑。
- Repo 不保存 service account JSON、Telegram token 或其他 secret。
- 若需要手動新增資料，請直接改 Google Sheet；不要在 app 內新增寫入能力。
