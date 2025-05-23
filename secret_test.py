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

# --- セッション管理初期化 ---
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("username", "")
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("show_history", False)

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
                st.session_state.chat_history = []
                st.rerun()
            else:
                st.error("ユーザー名またはパスワードが間違っています。")

# --- ログイン後のUI ---
if st.session_state.logged_in:
    st.title(f"{st.session_state.username} さん、こんにちは！")

    if not st.session_state.show_history:
        st.markdown("### 💬 ChatGPTと会話")

        # 会話履歴を見るボタン
        if st.button("会話履歴を見る"):
            st.session_state.show_history = True
            st.rerun()

        # --- セッション中の履歴表示 ---
        if st.session_state.chat_history:
            for msg in st.session_state.chat_history:
                if msg.startswith("ユーザー:"):
                    # ユーザー → 右寄せ（グリーン）
                    st.markdown(
                        f"""
                        <div style='display: flex; justify-content: flex-end; margin: 4px 0'>
                            <div style='
                                background-color: #DCF8C6;
                                padding: 8px 12px;
                                border-radius: 8px;
                                max-width: 80%;
                                word-wrap: break-word;
                                text-align: left;
                                font-size: 16px;
                            '>
                                {msg.replace("ユーザー:", "")}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                elif msg.startswith("AI:"):
                    # AI → 左寄せ（グレー）
                    st.markdown(
                        f"""
                        <div style='display: flex; justify-content: flex-start; margin: 4px 0'>
                            <div style='
                                background-color: #E6E6EA;
                                padding: 8px 12px;
                                border-radius: 8px;
                                max-width: 80%;
                                word-wrap: break-word;
                                text-align: left;
                                font-size: 16px;
                            '>
                                {msg.replace("AI:", "")}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


        # --- 入力フォーム ---
        if "input_msg" not in st.session_state:
            st.session_state.input_msg = ""
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

                # ローカル履歴に追加
                st.session_state.chat_history.append(f"ユーザー: {user_input}")
                st.session_state.chat_history.append(f"AI: {reply}")

                # Google Sheetsに記録
                full_message = f"ユーザー: {user_input}\nAI: {reply}"
                record_message(st.session_state.username, full_message)
                st.experimental_rerun()
            else:
                st.warning("メッセージが空です。")

        # ログアウト
        if st.button("ログアウト", key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.show_history = False
            st.session_state.chat_history = []
            st.rerun()

    else:
        # --- 履歴画面 ---
        st.markdown("### 📜 会話履歴")
        history = load_message(st.session_state.username)

        if not history.strip():
            st.info("（会話履歴はまだありません）")
        else:
            messages = [m for m in history.split("\n") if m.strip()]
            for msg in messages:
                if msg.startswith("ユーザー:"):
                    col1, col2 = st.columns([4, 6])  # ユーザーを右に
                    with col2:
                        st.markdown(
                            f"""
                            <div style='display: flex; justify-content: flex-end; margin: 4px 0'>
                                <div style='
                                    background-color: #DCF8C6;
                                    padding: 8px 12px;
                                    border-radius: 8px;
                                    max-width: 80%;
                                    word-wrap: break-word;
                                    text-align: left;
                                    font-size: 16px;
                                '>
                                    {msg.replace("ユーザー:", "")}
                                </div>
                            </div>
                            """,
                                unsafe_allow_html=True
                        )

                elif msg.startswith("AI:"):
                    col1, col2 = st.columns([6, 4])  # AIを左に
                    with col1:
                        st.markdown(
                             f"""
                                <div style='display: flex; justify-content: flex-start; margin: 4px 0'>
                                    <div style='
                                        background-color: #E6E6EA;
                                        padding: 8px 12px;
                                        border-radius: 8px;
                                        max-width: 80%;
                                        word-wrap: break-word;
                                        text-align: left;
                                        font-size: 16px;
                                    '>
                                        {msg.replace("AI:", "")}
                                    </div>
                                </div>
                                """,
                            unsafe_allow_html=True
                        )


        # 戻るボタン
        if st.button("チャットに戻る"):
            st.session_state.show_history = False
            st.rerun()

        # ログアウト
        if st.button("ログアウト", key="logout2_btn"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.show_history = False
            st.session_state.chat_history = []
            st.rerun()