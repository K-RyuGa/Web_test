# app.py
import streamlit as st

st.set_page_config(page_title="チャット風アプリ", layout="centered")

st.title("🗨️ 簡易チャットアプリ")

# チャット履歴の保持
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ユーザーからの入力
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("あなたのメッセージ", placeholder="メッセージを入力してください")
    submitted = st.form_submit_button("送信")

# 入力があったら応答を生成
if submitted and user_input:
    # シンプルな応答ロジック
    if "こんにちは" in user_input:
        response = "こんにちは！今日も元気ですね😊"
    elif "ありがとう" in user_input:
        response = "どういたしまして！またいつでも聞いてください。"
    else:
        response = f"「{user_input}」についてはよくわかりませんが、面白いですね！"

    # 履歴に追加
    st.session_state.chat_history.append(("あなた", user_input))
    st.session_state.chat_history.append(("AI", response))

# チャット履歴を表示
for speaker, message in st.session_state.chat_history:
    if speaker == "あなた":
        st.markdown(f"<div style='text-align:right'><b>{speaker}：</b> {message}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:left'><b>{speaker}：</b> {message}</div>", unsafe_allow_html=True)
