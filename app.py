import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# 設定 Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# 這裡需要您的 service_account.json，後續會處理
# creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
# client = gspread.authorize(creds)

st.title("加密貨幣投資日記 (雲端版)")

st.subheader("功能說明")
st.write("此版本已準備好連接 Google Sheets，請於部署後設定環境變數以啟用連線。")

st.subheader("新增交易")
with st.form("trade_form"):
    asset = st.text_input("資產名稱", "BTC")
    amount = st.number_input("數量", value=0.0, step=0.0001)
    price = st.number_input("價格", value=0.0, step=1.0)
    if st.form_submit_button("新增至雲端表格"):
        st.info("請先完成 Google Cloud Service Account 設定以啟用此功能。")
