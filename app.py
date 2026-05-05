import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="加密貨幣投資日記", page_icon="📈", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SHEET_HEADER = ["timestamp", "asset", "side", "amount", "price", "total", "note"]


@st.cache_resource(show_spinner=False)
def get_worksheet():
    if "gcp_service_account" not in st.secrets:
        return None, "缺少 Streamlit Secret：gcp_service_account"
    if "sheet" not in st.secrets or "id" not in st.secrets["sheet"]:
        return None, "缺少 Streamlit Secret：sheet.id"

    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sh = client.open_by_key(st.secrets["sheet"]["id"])
    ws_name = st.secrets["sheet"].get("worksheet", "trades")
    try:
        ws = sh.worksheet(ws_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=ws_name, rows=1000, cols=len(SHEET_HEADER))
        ws.append_row(SHEET_HEADER)
    if not ws.get_all_values():
        ws.append_row(SHEET_HEADER)
    return ws, None


def load_trades(ws):
    rows = ws.get_all_records()
    if not rows:
        return pd.DataFrame(columns=SHEET_HEADER)
    df = pd.DataFrame(rows)
    for col in ("amount", "price", "total"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def append_trade(ws, asset, side, amount, price, note):
    total = round(amount * price, 4)
    ws.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        asset.upper(),
        side,
        amount,
        price,
        total,
        note,
    ])
    return total


st.title("📈 加密貨幣投資日記")
st.caption("與 Google Sheets 即時同步 — 手動填寫亦可，自動化排程也可寫入同一張表")

ws, err = get_worksheet()

if err:
    st.warning(f"⚠️ {err}")
    with st.expander("如何設定 Google Sheets 連線", expanded=True):
        st.markdown(
            """
1. 在 Google Cloud Console 建立 Service Account 並下載 JSON 憑證。
2. 在 Google Drive 建立一份試算表，**把 SA 的 email 加為「編輯者」**。
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
```
            """
        )
    st.stop()

st.success("✅ 已連線 Google Sheets")

tab_dashboard, tab_new = st.tabs(["📊 儀表板", "➕ 新增交易"])

with tab_dashboard:
    df = load_trades(ws)
    if df.empty:
        st.info("尚無交易紀錄，到右邊「新增交易」分頁開始記錄吧 👉")
    else:
        df["amount"] = df["amount"].astype(float)
        df["total"] = df["total"].astype(float)
        col1, col2, col3 = st.columns(3)
        col1.metric("總交易筆數", len(df))
        buys = df[df["side"] == "buy"]["total"].sum()
        sells = df[df["side"] == "sell"]["total"].sum()
        col2.metric("累計買入金額", f"{buys:,.0f}")
        col3.metric("累計賣出金額", f"{sells:,.0f}")

        st.subheader("各資產持倉概覽")
        pivot = (
            df.assign(signed=df.apply(
                lambda r: r["amount"] if r["side"] == "buy" else -r["amount"], axis=1
            ))
            .groupby("asset")["signed"].sum()
            .reset_index(name="net_amount")
        )
        st.dataframe(pivot, use_container_width=True)

        st.subheader("完整紀錄")
        st.dataframe(df.sort_values("timestamp", ascending=False), use_container_width=True)

with tab_new:
    with st.form("trade_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        asset = c1.text_input("資產名稱", "BTC").strip()
        side = c2.selectbox("買 / 賣", ["buy", "sell"])
        c3, c4 = st.columns(2)
        amount = c3.number_input("數量", min_value=0.0, value=0.0, step=0.0001, format="%.6f")
        price = c4.number_input("單價 (TWD)", min_value=0.0, value=0.0, step=1.0)
        note = st.text_area("備註（策略 / 訊號 / 心得）", "")
        if st.form_submit_button("📝 寫入 Google Sheet", type="primary"):
            if not asset or amount <= 0 or price <= 0:
                st.error("請完整填寫資產、數量、價格")
            else:
                total = append_trade(ws, asset, side, amount, price, note)
                st.success(f"已記錄 {side.upper()} {amount} {asset.upper()} @ {price}（總額 {total}）")
                st.cache_resource.clear()
