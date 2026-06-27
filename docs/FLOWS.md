# 操作與業務流程

## 1. Streamlit 啟動與 Google Sheets 連線

```mermaid
flowchart TD
    Open["使用者開啟 Streamlit App"] --> Cache["get_spreadsheet() @st.cache_resource"]
    Cache --> CheckSecrets{"st.secrets 有 gcp_service_account 與 sheet.id？"}
    CheckSecrets -->|否| Missing["render_sidebar() 顯示等待設定"]
    Missing --> Warning["st.warning() 顯示 Secrets 設定方式"]
    Warning --> Stop["st.stop()"]
    CheckSecrets -->|是| Creds["Credentials.from_service_account_info()"]
    Creds --> Gspread["gspread.authorize()"]
    Gspread --> Sheet["client.open_by_key(sheet.id)"]
    Sheet --> Load["load_trades() / load_journals()"]
```

`app.py` 先檢查 Streamlit Secrets，再用 Google Service Account 建立 readonly 連線。缺少 secrets 時不載入資料，直接顯示設定說明並停止頁面流程。

## 2. Dashboard 分類篩選與總覽彙總

```mermaid
flowchart TD
    LoadTrades["load_trades(spreadsheet, worksheet)"] --> Normalize["轉 numeric / timestamp_dt / side"]
    Normalize --> Classify["classify_asset(asset)"]
    LoadJournals["load_journals(spreadsheet, journal_worksheet)"] --> DateParse["轉 date_dt"]
    Classify --> Sidebar["render_sidebar() st.multiselect"]
    DateParse --> Sidebar
    Sidebar --> Filter["filter_categories()"]
    Filter --> Metrics["st.metric: 交易數 / 日記數 / 淨投入 / 最新交易"]
    Filter --> Overview["總覽 tab"]
    Overview --> Summary["groupby category, asset"]
    Overview --> Charts["st.bar_chart / st.line_chart"]
    Overview --> Cards["render_recent_decision_cards()"]
```

總覽依 sidebar 選取分類過濾交易與日記。交易會依資產代號分類並計算持有量、淨現金流、分類買賣金額與每日淨現金流。

## 3. 每日排程日記閱讀

```mermaid
flowchart TD
    JournalsTab["每日排程日記 tab"] --> Sort["sort_journals_desc()"]
    Sort --> LabelMap["建立 date/category/title 選單 label"]
    LabelMap --> Select["st.selectbox 選擇日記"]
    Select --> Metrics["st.metric 顯示日期與分類"]
    Select --> Metadata["st.expander 顯示 github_path / cron_output_path / run_time"]
    Select --> Panel["render_journal_panel()"]
    Panel --> Markdown{"content_markdown 有內容？"}
    Markdown -->|是| RenderMarkdown["st.markdown(content_markdown)"]
    Markdown -->|否| Warning["st.warning()"]
```

日記頁只讀取 `journal_entries`。使用者可從下拉選單切換日記，查看摘要、metadata 與完整 Markdown 內容。

## 4. 完整交易紀錄檢視

```mermaid
flowchart TD
    TradesTab["交易紀錄 tab"] --> Empty{"filtered_trades 是否空？"}
    Empty -->|是| Info["st.info() 顯示無資料"]
    Empty -->|否| DropInternal["移除 timestamp_dt 顯示欄"]
    DropInternal --> Sort["依 timestamp 或第一欄倒序"]
    Sort --> Dataframe["st.dataframe() 顯示 amount / price / total 格式化欄位"]
```

交易紀錄頁顯示 Google Sheet `trades` 的完整資料。程式只做格式化、排序與欄位顯示，不提供新增或更新交易的 UI。

## 5. 歷史投資日記匯入

```mermaid
sequenceDiagram
    actor Operator as 維運者
    participant Script as scripts/import_investment_journals.py
    participant FS as 本機 Markdown 來源
    participant Sheet as Google Sheet journal_entries

    Operator->>Script: python scripts/import_investment_journals.py
    Script->>Sheet: get_worksheet()
    Sheet-->>Script: 現有 records
    Script->>FS: collect_rows() 掃 daily / shadow / cron output
    Script->>Script: extract_date / first_heading / summarize / response_section
    Script->>Script: existing_keys() 去重
    Script->>Sheet: append_rows(rows, USER_ENTERED)
    Script-->>Operator: print Imported N new journal rows
```

匯入腳本是本機維運工具，會用可寫入的 Google Sheets / Drive scopes。它只寫入 `journal_entries`，並用 `(date, source, github_path, cron_output_path)` 避免重複匯入。
