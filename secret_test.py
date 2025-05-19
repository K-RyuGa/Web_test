import streamlit as st
import openai
import gspread
from google.oauth2.service_account import Credentials
import json

# --- Google Sheets 認証 ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(credentials)
sheet = client.open("UserData").sheet1

# --- OpenAI APIキー ---
openai.api_key = st.secrets["openai"]["api_key"]

# --- ユーザーが存在するかチェック ---
def user_exists(username):
    users = sheet.col_values(1)
    return username in users

# --- パスワード一致をチェック ---
def check_password(username, password):
    users = sheet.get_all_records()
    for user in users:
        if user["username"] == username and user["password"] == password:
            return True
    return False

# --- 新規登録 ---
def register_user(username, password):
    if user_exists(username):
        return False
    sheet.append_row([username, password, ""])
    return True

# --- メッセージを追記 ---
def record_message(username, new_message):
    all_users = sheet.get_all_records()
    for i, user in enumerate(all_users, start=2):
        if user["username"] == username:
            old_message = user.get("message", "")
            combined = old_message + "\n" + new_message if old_message else new_message
            sheet.update_cell(i, 3, combined)
            break

# --- メッセージ履歴を取得 ---
def load_message(username):
    all_users = sheet.get_all_records()
    for user in all_users:
        if user["username"] == username:
            return user.get("message", "")
    return ""

# --- セッション管理 ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- ログイン前のUI ---
if not st.session_state.logged_in:
    st.title("ログイン / 新規登録")
    mode = st.radio("モードを選択", ["ログイン", "新規登録"])
    username = st.text_input("ユーザー名")
    password = st.text_input("パスワード", type="password")
    if st.button("送信"):
        if mode == "新規登録":
            if register_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("そのユーザー名は既に使われています。")
        else:
            if check_password(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("ユーザー名またはパスワードが間違っています。")

# --- ログイン後のUI ---
else:
    st.title(f"{st.session_state.username} さん、こんにちは！")
    st.markdown("**これまでの会話履歴**")
    history = load_message(st.session_state.username)
    st.code(history or "（会話履歴はまだありません）")

    st.markdown("### 💬 ChatGPTと会話")
    user_input = st.text_input("あなたのメッセージを入力してください", key="input_msg")
    if st.button("送信"):
        if user_input.strip():
            # Chat API呼び出し
            full_prompt = [{"role": "system", "content": "あなたは親切な日本語学習の先生です。"},
                           {"role": "user", "content": user_input}]
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=full_prompt,
                temperature=0.7,
            )
            reply = response["choices"][0]["message"]["content"]

            # 表示と保存
            st.markdown("**ChatGPTの返信：**")
            st.success(reply)

            full_message = f"ユーザー: {user_input}\nAI: {reply}"
            record_message(st.session_state.username, full_message)

            st.rerun()
        else:
            st.warning("メッセージが空です。")

    if st.button("ログアウト"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.chat_history = []
        st.rerun()
