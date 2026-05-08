from __future__ import annotations

from datetime import datetime
from typing import Iterable

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="投資日記", page_icon="📒", layout="wide")

READONLY_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
TRADE_HEADER = ["timestamp", "asset", "side", "amount", "price", "total", "note"]
JOURNAL_HEADER = [
    "date",
    "run_time",
    "category",
    "source",
    "title",
    "summary",
    "content_markdown",
    "github_path",
    "cron_output_path",
    "tags",
]

CRYPTO_ASSETS = {"BTC", "ETH", "SOL", "BNB", "ADA", "USDT", "USDC"}
ETF_ASSETS = {"SPY", "QQQ", "VOO", "VTI", "VT", "DIA", "IWM", "TLT", "BND"}


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    if "gcp_service_account" not in st.secrets:
        return None, "缺少 Streamlit Secret：gcp_service_account"
    if "sheet" not in st.secrets or "id" not in st.secrets["sheet"]:
        return None, "缺少 Streamlit Secret：sheet.id"

    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=READONLY_SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["sheet"]["id"]), None


def _worksheet_records(spreadsheet, name: str, expected_header: list[str]) -> pd.DataFrame:
    try:
        worksheet = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        return pd.DataFrame(columns=expected_header)

    rows = worksheet.get_all_records()
    if not rows:
        return pd.DataFrame(columns=expected_header)
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False, ttl=300)
def load_trades(_spreadsheet, worksheet_name: str) -> pd.DataFrame:
    df = _worksheet_records(_spreadsheet, worksheet_name, TRADE_HEADER)
    if df.empty:
        return df

    for col in ("amount", "price", "total"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "timestamp" in df:
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if "asset" in df:
        df["asset"] = df["asset"].astype(str).str.upper().str.strip()
        df["category"] = df["asset"].map(classify_asset)
    if "side" in df:
        df["side"] = df["side"].astype(str).str.lower().str.strip()
    return df


@st.cache_data(show_spinner=False, ttl=300)
def load_journals(_spreadsheet, worksheet_name: str) -> pd.DataFrame:
    df = _worksheet_records(_spreadsheet, worksheet_name, JOURNAL_HEADER)
    if df.empty:
        return df
    if "date" in df:
        df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    for col in JOURNAL_HEADER:
        if col not in df:
            df[col] = ""
    return df


def classify_asset(asset: str) -> str:
    normalized = str(asset).upper().strip()
    if normalized in CRYPTO_ASSETS:
        return "Crypto"
    if normalized in ETF_ASSETS:
        return "ETF"
    return "其他"


def signed_amount(row: pd.Series) -> float:
    amount = float(row.get("amount", 0) or 0)
    return amount if row.get("side") == "buy" else -amount


def signed_total(row: pd.Series) -> float:
    total = float(row.get("total", 0) or 0)
    return total if row.get("side") == "buy" else -total


def format_twd(value: float) -> str:
    return f"NT$ {value:,.0f}"


def filter_categories(df: pd.DataFrame, selected: Iterable[str]) -> pd.DataFrame:
    if df.empty or "category" not in df:
        return df
    selected = set(selected)
    if not selected:
        return df.iloc[0:0]

    def matches(value: object) -> bool:
        parts = [part.strip() for part in str(value).replace("/", ",").split(",")]
        return any(part in selected for part in parts)

    return df[df["category"].map(matches)]


st.title("📒 投資日記")
st.caption("唯讀展示 Google Sheet 內容；新增與修改請直接在 Google Sheet 或自動排程寫入。")

spreadsheet, err = get_spreadsheet()

if err:
    st.warning(f"⚠️ {err}")
    with st.expander("如何設定 Google Sheets 連線", expanded=True):
        st.markdown(
            """
1. 在 Google Cloud Console 建立 Service Account 並下載 JSON 憑證。
2. 在 Google Drive 建立試算表，並把 Service Account email 加為讀取者或編輯者。
3. 在 Streamlit Cloud → App → Settings → Secrets 貼上：

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"

[sheet]
id = "你的試算表 ID（網址 /d/ 後面那串）"
worksheet = "trades"
journal_worksheet = "journal_entries"
```
            """
        )
    st.stop()

trade_worksheet = st.secrets["sheet"].get("worksheet", "trades")
journal_worksheet = st.secrets["sheet"].get("journal_worksheet", "journal_entries")

trades = load_trades(spreadsheet, trade_worksheet)
journals = load_journals(spreadsheet, journal_worksheet)

st.success("✅ 已連線 Google Sheets（唯讀模式）")

all_categories = ["Crypto", "ETF", "其他"]
selected_categories = st.multiselect(
    "顯示分類",
    all_categories,
    default=all_categories,
    help="Crypto / ETF / 其他投資日記會集中顯示，也可單獨篩選。",
)
filtered_trades = filter_categories(trades, selected_categories)
filtered_journals = filter_categories(journals, selected_categories)

latest_journal = None
if not filtered_journals.empty:
    latest_journal = filtered_journals.sort_values("date_dt", ascending=False).iloc[0]

metric_cols = st.columns(4)
metric_cols[0].metric("交易紀錄", f"{len(filtered_trades):,} 筆")
metric_cols[1].metric("每日排程日記", f"{len(filtered_journals):,} 篇")
if not filtered_trades.empty:
    buy_total = filtered_trades[filtered_trades["side"] == "buy"]["total"].sum()
    sell_total = filtered_trades[filtered_trades["side"] == "sell"]["total"].sum()
    metric_cols[2].metric("累計買入", format_twd(buy_total))
    metric_cols[3].metric("累計賣出", format_twd(sell_total))
else:
    metric_cols[2].metric("累計買入", "—")
    metric_cols[3].metric("累計賣出", "—")

if latest_journal is not None:
    st.info(
        f"最新排程：{latest_journal.get('date', '—')}｜"
        f"{latest_journal.get('category', '—')}｜{latest_journal.get('title', '每日投資決策')}"
    )


tab_overview, tab_journals, tab_trades, tab_sheet = st.tabs(
    ["📊 總覽", "🗓️ 每日排程日記", "📈 交易紀錄", "🧾 Sheet 寫入說明"]
)

with tab_overview:
    st.subheader("分類總覽")
    if filtered_trades.empty:
        st.info("目前沒有符合篩選條件的交易紀錄。")
    else:
        summary = (
            filtered_trades.assign(
                signed_amount=filtered_trades.apply(signed_amount, axis=1),
                signed_total=filtered_trades.apply(signed_total, axis=1),
            )
            .groupby(["category", "asset"], as_index=False)
            .agg(
                net_amount=("signed_amount", "sum"),
                net_cashflow_twd=("signed_total", "sum"),
                trades=("asset", "count"),
            )
            .sort_values(["category", "asset"])
        )
        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("最近排程決策")
    if filtered_journals.empty:
        st.info("尚未在 Google Sheet 的 journal_entries 工作表看到排程日記。")
    else:
        preview_cols = ["date", "category", "title", "summary", "source"]
        st.dataframe(
            filtered_journals.sort_values("date_dt", ascending=False)[preview_cols].head(10),
            use_container_width=True,
            hide_index=True,
        )

with tab_journals:
    st.subheader("每日排程歷史紀錄")
    if filtered_journals.empty:
        st.info("尚未匯入每日排程日記。")
    else:
        ordered = filtered_journals.sort_values("date_dt", ascending=False).reset_index(drop=True)
        labels = [
            f"{row.get('date', '')} · {row.get('category', '')} · {row.get('title', '')}"
            for _, row in ordered.iterrows()
        ]
        selected_label = st.selectbox("選擇一篇日記", labels)
        selected_row = ordered.iloc[labels.index(selected_label)]
        st.markdown(f"### {selected_row.get('title', '每日投資決策')}")
        st.caption(
            f"日期：{selected_row.get('date', '—')}｜來源：{selected_row.get('source', '—')}｜標籤：{selected_row.get('tags', '—')}"
        )
        summary = selected_row.get("summary", "")
        if summary:
            st.info(summary)
        content = selected_row.get("content_markdown", "")
        if content:
            st.markdown(content)
        else:
            st.warning("這筆日記沒有 content_markdown。")

        with st.expander("原始紀錄 metadata"):
            meta_cols = ["github_path", "cron_output_path", "run_time"]
            st.json({col: selected_row.get(col, "") for col in meta_cols})

with tab_trades:
    st.subheader("完整交易紀錄")
    if filtered_trades.empty:
        st.info("目前沒有符合篩選條件的交易紀錄。")
    else:
        display = filtered_trades.drop(columns=[c for c in ["timestamp_dt"] if c in filtered_trades], errors="ignore")
        sort_col = "timestamp" if "timestamp" in display else display.columns[0]
        st.dataframe(display.sort_values(sort_col, ascending=False), use_container_width=True, hide_index=True)

with tab_sheet:
    st.subheader("寫入規則")
    st.markdown(
        f"""
- 這個網頁現在是 **唯讀模式**，不提供「新增交易」或任何會寫入 Google Sheet 的按鈕。
- 手動新增 / 修改請直接在 Google Sheet 裡操作：
  - 交易 worksheet：`{trade_worksheet}`
  - 每日排程日記 worksheet：`{journal_worksheet}`
- 自動投資排程會把每日決策 / 歷史紀錄寫入 `journal_entries`，網頁只負責讀取與顯示。

`journal_entries` 欄位：
`date`, `run_time`, `category`, `source`, `title`, `summary`, `content_markdown`, `github_path`, `cron_output_path`, `tags`
        """
    )
