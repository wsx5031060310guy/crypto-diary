import streamlit as st
import json
import os

st.title("加密貨幣投資日記")

# 假設 state.json 格式如下：
# {"BTC": 0.000808, "cash": 8000}
STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"BTC": 0.0, "cash": 0.0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

state = load_state()

st.subheader("目前持倉")
st.write(state)

st.subheader("新增交易")
with st.form("trade_form"):
    asset = st.text_input("資產名稱", "BTC")
    amount = st.number_input("數量", value=0.0, step=0.0001)
    price = st.number_input("價格", value=0.0, step=1.0)
    if st.form_submit_button("新增記錄"):
        # 簡單邏輯：更新 state 並儲存
        state[asset] = state.get(asset, 0) + amount
        save_state(state)
        st.success("記錄已更新！")
        st.rerun()
