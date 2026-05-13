from __future__ import annotations

import html
from typing import Iterable

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from streamlit.errors import StreamlitSecretNotFoundError

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


APP_CSS = """
<style>
    :root {
        --diary-bg: #f2f6f3;
        --diary-panel: #ffffff;
        --diary-panel-soft: #f8fbf9;
        --diary-ink: #101815;
        --diary-muted: #34443d;
        --diary-line: #aabbb1;
        --diary-line-strong: #6f867a;
        --diary-green: #007a5a;
        --diary-green-dark: #00583f;
        --diary-teal: #006b73;
        --diary-amber: #8a5200;
        --diary-warning-bg: #fff2b8;
        --diary-warning-border: #b77900;
        --diary-shadow: rgba(16, 24, 21, 0.10);
    }

    .stApp {
        background: var(--diary-bg);
        color: var(--diary-ink);
    }

    .block-container {
        max-width: 1240px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] {
        background: #e7f0eb;
        border-right: 2px solid var(--diary-line);
    }

    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {
        color: var(--diary-ink);
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] label {
        color: var(--diary-muted);
    }

    [data-testid="stAlert"] {
        background: var(--diary-warning-bg);
        border: 2px solid var(--diary-warning-border);
        border-radius: 8px;
        color: #422b00;
    }

    [data-testid="stAlert"] p {
        color: #422b00;
        font-weight: 760;
    }

    [data-testid="stExpander"] {
        background: var(--diary-panel);
        border: 1px solid var(--diary-line);
        border-radius: 8px;
    }

    [data-testid="stCodeBlock"] pre {
        background: #f6f8fb;
        border: 1px solid #a8b3c2;
        color: #0b1824;
    }

    div[data-testid="stMetric"] {
        background: var(--diary-panel);
        border: 1px solid var(--diary-line);
        border-top: 4px solid var(--diary-green);
        border-radius: 8px;
        padding: 1rem 1.05rem;
        box-shadow: 0 10px 22px var(--diary-shadow);
        min-height: 118px;
    }

    div[data-testid="stMetricLabel"] p {
        color: var(--diary-muted);
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0;
    }

    div[data-testid="stMetricValue"] {
        color: var(--diary-ink);
        font-size: 1.75rem;
        font-weight: 820;
    }

    .diary-hero {
        border: 1px solid var(--diary-line);
        border-left: 8px solid var(--diary-green);
        border-radius: 8px;
        background: var(--diary-panel);
        padding: 1.35rem 1.4rem;
        margin-bottom: 1rem;
        box-shadow: 0 18px 38px var(--diary-shadow);
    }

    .diary-hero-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
        margin-bottom: 0.9rem;
    }

    .diary-eyebrow {
        color: var(--diary-green-dark);
        font-size: 0.78rem;
        font-weight: 860;
        letter-spacing: 0;
        text-transform: uppercase;
    }

    .diary-title {
        color: var(--diary-ink);
        font-size: 3rem;
        line-height: 1.05;
        font-weight: 840;
        letter-spacing: 0;
        margin: 0.1rem 0 0.35rem;
    }

    .diary-subtitle {
        color: var(--diary-muted);
        font-size: 1.05rem;
        font-weight: 620;
        margin: 0;
        max-width: 760px;
    }

    .diary-badge-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-wrap: wrap;
    }

    .diary-badge {
        display: inline-flex;
        align-items: center;
        min-height: 2rem;
        border: 1px solid var(--diary-green-dark);
        border-radius: 8px;
        background: var(--diary-green);
        color: #ffffff;
        font-size: 0.82rem;
        font-weight: 820;
        padding: 0.35rem 0.7rem;
        white-space: nowrap;
    }

    .diary-badge.secondary {
        border-color: #6b3e00;
        background: var(--diary-warning-bg);
        color: #4a2d00;
    }

    .diary-status {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
    }

    .diary-status-item {
        background: var(--diary-panel-soft);
        border: 1px solid var(--diary-line);
        border-radius: 8px;
        padding: 0.75rem 0.85rem;
    }

    .diary-status-label {
        color: var(--diary-muted);
        display: block;
        font-size: 0.78rem;
        font-weight: 780;
        margin-bottom: 0.25rem;
    }

    .diary-status-value {
        color: var(--diary-ink);
        display: block;
        font-size: 0.95rem;
        font-weight: 820;
        overflow-wrap: anywhere;
    }

    .diary-section-title {
        color: var(--diary-ink);
        font-size: 1.22rem;
        font-weight: 860;
        margin: 1.2rem 0 0.55rem;
    }

    .diary-note {
        border: 1px solid var(--diary-line-strong);
        border-left: 6px solid var(--diary-green);
        background: #eaf7f1;
        border-radius: 0 8px 8px 0;
        color: var(--diary-ink);
        padding: 0.85rem 1rem;
        margin: 1rem 0;
    }

    .diary-note strong {
        color: var(--diary-green-dark);
    }

    .journal-panel {
        background: var(--diary-panel);
        border: 1px solid var(--diary-line);
        border-radius: 8px;
        padding: 1.1rem 1.15rem;
        box-shadow: 0 10px 22px var(--diary-shadow);
    }

    .journal-title {
        color: var(--diary-ink);
        font-size: 1.5rem;
        line-height: 1.25;
        font-weight: 820;
        letter-spacing: 0;
        margin: 0 0 0.55rem;
    }

    .journal-meta {
        color: var(--diary-muted);
        font-size: 0.9rem;
        font-weight: 620;
        margin-bottom: 0.75rem;
    }

    .journal-summary {
        background: #e6f4f4;
        border: 1px solid #80aeb2;
        border-radius: 8px;
        color: #073f45;
        padding: 0.8rem 0.9rem;
        margin-bottom: 1rem;
        font-weight: 620;
    }

    [data-testid="stTabs"] button {
        color: var(--diary-muted);
        font-weight: 820;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--diary-green-dark);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--diary-line);
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 10px 22px var(--diary-shadow);
    }

    @media (max-width: 760px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .diary-hero {
            padding: 1.1rem;
        }

        .diary-title {
            font-size: 2.2rem;
        }

        .diary-status {
            grid-template-columns: 1fr;
        }
    }
</style>
"""


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    try:
        secrets = st.secrets
        has_gcp_secret = "gcp_service_account" in secrets
        has_sheet_id = "sheet" in secrets and "id" in secrets["sheet"]
    except StreamlitSecretNotFoundError:
        return None, "缺少 Streamlit Secrets 設定檔"

    if not has_gcp_secret:
        return None, "缺少 Streamlit Secret：gcp_service_account"
    if not has_sheet_id:
        return None, "缺少 Streamlit Secret：sheet.id"

    creds = Credentials.from_service_account_info(
        dict(secrets["gcp_service_account"]), scopes=READONLY_SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(secrets["sheet"]["id"]), None


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


def format_date(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value) or "—"
    return parsed.strftime("%Y-%m-%d")


def format_datetime(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value) or "—"
    return parsed.strftime("%Y-%m-%d %H:%M")


def safe_text(value: object, fallback: str = "—") -> str:
    text = "" if value is None else str(value)
    text = text.strip()
    return html.escape(text or fallback)


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


def latest_trade_label(df: pd.DataFrame) -> str:
    if df.empty or "timestamp_dt" not in df:
        return "尚無交易紀錄"
    latest = df["timestamp_dt"].dropna().max()
    return format_datetime(latest)


def latest_journal_label(df: pd.DataFrame) -> str:
    if df.empty or "date_dt" not in df:
        return "尚無排程日記"
    latest = df["date_dt"].dropna().max()
    return format_date(latest)


def sort_journals_desc(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "date_dt" not in df:
        return df
    return df.sort_values("date_dt", ascending=False, na_position="last")


def render_hero(
    trade_worksheet: str,
    journal_worksheet: str,
    trade_count: int,
    journal_count: int,
    latest_journal_date: str,
) -> None:
    st.markdown(
        f"""
<section class="diary-hero">
  <div class="diary-hero-top">
    <div>
      <div class="diary-eyebrow">Investment Journal</div>
      <h1 class="diary-title">投資日記</h1>
      <p class="diary-subtitle">集中閱讀每日投資決策、交易紀錄與分類概覽；資料由 Google Sheets 唯讀同步。</p>
    </div>
    <div class="diary-badge-row">
      <span class="diary-badge">Google Sheets 已連線</span>
      <span class="diary-badge secondary">唯讀模式</span>
    </div>
  </div>
  <div class="diary-status">
    <div class="diary-status-item">
      <span class="diary-status-label">交易工作表</span>
      <span class="diary-status-value">{safe_text(trade_worksheet)}</span>
    </div>
    <div class="diary-status-item">
      <span class="diary-status-label">日記工作表</span>
      <span class="diary-status-value">{safe_text(journal_worksheet)}</span>
    </div>
    <div class="diary-status-item">
      <span class="diary-status-label">目前資料</span>
      <span class="diary-status-value">{trade_count:,} 筆交易 / {journal_count:,} 篇日記，最新 {safe_text(latest_journal_date)}</span>
    </div>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_note(title: str, body: str) -> None:
    st.markdown(
        f"""
<div class="diary-note">
  <strong>{safe_text(title)}</strong><br>
  {safe_text(body)}
</div>
        """,
        unsafe_allow_html=True,
    )


def render_journal_panel(row: pd.Series) -> None:
    title = row.get("title", "每日投資決策")
    date = row.get("date", "—")
    source = row.get("source", "—")
    tags = row.get("tags", "—")
    summary = row.get("summary", "")
    st.markdown(
        f"""
<div class="journal-panel">
  <h3 class="journal-title">{safe_text(title, "每日投資決策")}</h3>
  <div class="journal-meta">日期：{safe_text(date)}｜來源：{safe_text(source)}｜標籤：{safe_text(tags)}</div>
  {f'<div class="journal-summary">{safe_text(summary)}</div>' if str(summary).strip() else ''}
</div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(APP_CSS, unsafe_allow_html=True)

spreadsheet, err = get_spreadsheet()

if err:
    st.markdown(
        """
<section class="diary-hero">
  <div class="diary-hero-top">
    <div>
      <div class="diary-eyebrow">Investment Journal</div>
      <h1 class="diary-title">投資日記</h1>
      <p class="diary-subtitle">先把 Google Sheets 連線補上，儀表板就會載入交易與每日排程日記。</p>
    </div>
    <div class="diary-badge-row">
      <span class="diary-badge secondary">等待設定</span>
    </div>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )
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

all_categories = ["Crypto", "ETF", "其他"]
with st.sidebar:
    st.markdown("### 篩選")
    selected_categories = st.multiselect(
        "顯示分類",
        all_categories,
        default=all_categories,
        help="Crypto / ETF / 其他投資日記會集中顯示，也可單獨篩選。",
    )
    st.markdown("### 資料來源")
    st.caption(f"交易 worksheet：`{trade_worksheet}`")
    st.caption(f"日記 worksheet：`{journal_worksheet}`")
    st.caption("連線狀態：Google Sheets 唯讀")

filtered_trades = filter_categories(trades, selected_categories)
filtered_journals = filter_categories(journals, selected_categories)

latest_journal = None
if not filtered_journals.empty:
    latest_journal = sort_journals_desc(filtered_journals).iloc[0]

buy_total = 0.0
sell_total = 0.0
if not filtered_trades.empty and {"side", "total"}.issubset(filtered_trades.columns):
    buy_total = filtered_trades[filtered_trades["side"] == "buy"]["total"].sum()
    sell_total = filtered_trades[filtered_trades["side"] == "sell"]["total"].sum()
net_invested = buy_total - sell_total

render_hero(
    trade_worksheet=trade_worksheet,
    journal_worksheet=journal_worksheet,
    trade_count=len(filtered_trades),
    journal_count=len(filtered_journals),
    latest_journal_date=latest_journal_label(filtered_journals),
)

metric_cols = st.columns(4)
metric_cols[0].metric("交易紀錄", f"{len(filtered_trades):,} 筆")
metric_cols[1].metric("每日排程日記", f"{len(filtered_journals):,} 篇")
metric_cols[2].metric("淨投入", format_twd(net_invested) if not filtered_trades.empty else "—")
metric_cols[3].metric("最新交易", latest_trade_label(filtered_trades))

if latest_journal is not None:
    render_note(
        "最新排程",
        f"{latest_journal.get('date', '—')}｜{latest_journal.get('category', '—')}｜"
        f"{latest_journal.get('title', '每日投資決策')}",
    )


tab_overview, tab_journals, tab_trades, tab_sheet = st.tabs(
    ["📊 總覽", "🗓️ 每日排程日記", "📈 交易紀錄", "🧾 Sheet 寫入說明"]
)

with tab_overview:
    st.markdown('<div class="diary-section-title">分類總覽</div>', unsafe_allow_html=True)
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
        summary_display = summary.rename(
            columns={
                "category": "分類",
                "asset": "資產",
                "net_amount": "淨持有數量",
                "net_cashflow_twd": "淨現金流 TWD",
                "trades": "交易筆數",
            }
        )
        st.dataframe(
            summary_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "淨持有數量": st.column_config.NumberColumn(format="%.8f"),
                "淨現金流 TWD": st.column_config.NumberColumn(format="NT$ %d"),
                "交易筆數": st.column_config.NumberColumn(format="%d"),
            },
        )

        chart_cols = st.columns(2)
        with chart_cols[0]:
            st.markdown('<div class="diary-section-title">分類買賣金額</div>', unsafe_allow_html=True)
            if {"category", "side", "total"}.issubset(filtered_trades.columns):
                category_cashflow = (
                    filtered_trades.groupby(["category", "side"], as_index=False)["total"]
                    .sum()
                    .pivot(index="category", columns="side", values="total")
                    .fillna(0)
                )
                st.bar_chart(category_cashflow, use_container_width=True)
            else:
                st.info("交易紀錄欄位不足，暫時無法顯示分類圖。")
        with chart_cols[1]:
            st.markdown('<div class="diary-section-title">每日淨現金流</div>', unsafe_allow_html=True)
            if "timestamp_dt" in filtered_trades:
                timeline = (
                    filtered_trades.dropna(subset=["timestamp_dt"])
                    .assign(
                        date=lambda df: df["timestamp_dt"].dt.date,
                        net_cashflow=lambda df: df.apply(signed_total, axis=1),
                    )
                    .groupby("date", as_index=False)["net_cashflow"]
                    .sum()
                )
                if timeline.empty:
                    st.info("交易時間尚未整理成可畫圖的格式。")
                else:
                    st.line_chart(timeline, x="date", y="net_cashflow", use_container_width=True)
            else:
                st.info("交易紀錄沒有 timestamp 欄位，暫時無法顯示走勢。")

    st.markdown('<div class="diary-section-title">最近排程決策</div>', unsafe_allow_html=True)
    if filtered_journals.empty:
        st.info("尚未在 Google Sheet 的 journal_entries 工作表看到排程日記。")
    else:
        preview_cols = ["date", "category", "title", "summary", "source"]
        preview = sort_journals_desc(filtered_journals)[preview_cols].head(10)
        st.dataframe(
            preview.rename(
                columns={
                    "date": "日期",
                    "category": "分類",
                    "title": "標題",
                    "summary": "摘要",
                    "source": "來源",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

with tab_journals:
    st.markdown('<div class="diary-section-title">每日排程歷史紀錄</div>', unsafe_allow_html=True)
    if filtered_journals.empty:
        st.info("尚未匯入每日排程日記。")
    else:
        ordered = sort_journals_desc(filtered_journals).reset_index(drop=True)
        label_to_index = {
            f"{idx + 1:02d}. {row.get('date', '')} · {row.get('category', '')} · {row.get('title', '')}": idx
            for idx, row in ordered.iterrows()
        }
        nav_col, content_col = st.columns([0.34, 0.66], gap="large")
        with nav_col:
            selected_label = st.selectbox("選擇一篇日記", list(label_to_index.keys()))
            selected_row = ordered.iloc[label_to_index[selected_label]]
            st.metric("目前閱讀", format_date(selected_row.get("date_dt")))
            st.metric("分類", str(selected_row.get("category", "—") or "—"))
            with st.expander("原始紀錄 metadata"):
                meta_cols = ["github_path", "cron_output_path", "run_time"]
                st.json({col: selected_row.get(col, "") for col in meta_cols})

        with content_col:
            render_journal_panel(selected_row)
            content = selected_row.get("content_markdown", "")
            if content:
                st.markdown(content)
            else:
                st.warning("這筆日記沒有 content_markdown。")

with tab_trades:
    st.markdown('<div class="diary-section-title">完整交易紀錄</div>', unsafe_allow_html=True)
    if filtered_trades.empty:
        st.info("目前沒有符合篩選條件的交易紀錄。")
    else:
        display = filtered_trades.drop(columns=[c for c in ["timestamp_dt"] if c in filtered_trades], errors="ignore")
        sort_col = "timestamp" if "timestamp" in display else display.columns[0]
        display = display.sort_values(sort_col, ascending=False)
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "amount": st.column_config.NumberColumn("amount", format="%.8f"),
                "price": st.column_config.NumberColumn("price", format="NT$ %d"),
                "total": st.column_config.NumberColumn("total", format="NT$ %d"),
            },
        )

with tab_sheet:
    st.markdown('<div class="diary-section-title">寫入規則</div>', unsafe_allow_html=True)
    render_note("資料安全", "這個網頁只讀取 Google Sheet，不提供新增交易或任何寫入按鈕。")
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
