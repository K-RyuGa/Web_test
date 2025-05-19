import streamlit as st
from openai import OpenAI
import gspread
from google.oauth2.service_account import Credentials

# --- Google Sheets 認証 ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
gs_client = gspread.authorize(credentials)
sheet = gs_client.open("UserData").sheet1

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
    for i, user in enumerate(all_users, start=2):  # 2行目からデータ
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
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
if "show_history" not in st.session_state:
    st.session_state.show_history = False

# --- ログイン後のUI ---
if st.session_state.logged_in:
    st.title(f"{st.session_state.username} さん、こんにちは！")

    # ==== 画面切替 ====
    if not st.session_state.show_history:
        # --- チャット画面 ---
        st.markdown("### 💬 ChatGPTと会話")

        # 会話履歴ボタン
        if st.button("会話履歴を見る"):
            st.session_state.show_history = True
            st.rerun()

        # チャット履歴（最新5件だけ下に表示、不要ならこのブロック消してOK）
        history = load_message(st.session_state.username)
        if history:
            messages = [m for m in history.split("\n") if m.strip()]
            recent_msgs = messages[-10:]  # 直近10行
            for msg in recent_msgs:
                if msg.startswith("ユーザー:"):
                    col1, col2 = st.columns([6,4])
                    with col1:
                        st.markdown(f"<div style='text-align:left; background:#DCF8C6; padding:8px; border-radius:8px; margin:2px 0'>{msg.replace('ユーザー:','')}</div>", unsafe_allow_html=True)
                    with col2:
                        st.write("")
                elif msg.startswith("AI:"):
                    col1, col2 = st.columns([4,6])
                    with col2:
                        st.markdown(f"<div style='text-align:right; background:#E6E6EA; padding:8px; border-radius:8px; margin:2px 0'>{msg.replace('AI:','')}</div>", unsafe_allow_html=True)
                    with col1:
                        st.write("")

        # 入力フォーム
        user_input = st.text_input("あなたのメッセージを入力してください", key="input_msg")

        if st.button("送信", key="send_btn"):
            if user_input.strip():
                client = OpenAI(api_key=st.secrets["openai"]["api_key"])
                full_prompt = [
                    {"role": "system", "content": "あなたは親切な日本語学習の先生です。"},
                    {"role": "user", "content": user_input}
                ]
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=full_prompt,
                    temperature=0.7,
                )
                reply = response.choices[0].message.content

                # 表示（左右分割）
                col1, col2 = st.columns([6,4])
                with col1:
                    st.markdown(f"<div style='text-align:left; background:#DCF8C6; padding:8px; border-radius:8px; margin:4px 0'> {user_input}</div>", unsafe_allow_html=True)
                with col2:
                    st.write("")
                col1, col2 = st.columns([4,6])
                with col2:
                    st.markdown(f"<div style='text-align:right; background:#E6E6EA; padding:8px; border-radius:8px; margin:4px 0'>{reply}</div>", unsafe_allow_html=True)
                with col1:
                    st.write("")

                full_message = f"ユーザー: {user_input}\nAI: {reply}"
                record_message(st.session_state.username, full_message)
                st.rerun()
            else:
                st.warning("メッセージが空です。")

        # ログアウト
        if st.button("ログアウト", key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.show_history = False
            st.rerun()

    else:
        # --- 履歴画面 ---
        st.markdown("**これまでの会話履歴**")
        history = load_message(st.session_state.username)
        if not history.strip():
            st.info("（会話履歴はまだありません）")
        else:
            messages = [m for m in history.split("\n") if m.strip()]
            for msg in messages:
                if msg.startswith("ユーザー:"):
                    col1, col2 = st.columns([6,4])
                    with col1:
                        st.markdown(f"<div style='text-align:left; background:#DCF8C6; padding:8px; border-radius:8px; margin:2px 0'>{msg.replace('ユーザー:','')}</div>", unsafe_allow_html=True)
                    with col2:
                        st.write("")
                elif msg.startswith("AI:"):
                    col1, col2 = st.columns([4,6])
                    with col2:
                        st.markdown(f"<div style='text-align:right; background:#E6E6EA; padding:8px; border-radius:8px; margin:2px 0'>{msg.replace('AI:','')}</div>", unsafe_allow_html=True)
                    with col1:
                        st.write("")

        # チャットに戻るボタン
        if st.button("チャットに戻る"):
            st.session_state.show_history = False
            st.rerun()
        # ログアウト
        if st.button("ログアウト", key="logout2_btn"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.show_history = False
            st.rerun()
            