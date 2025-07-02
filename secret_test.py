import streamlit as st
from openai import OpenAI
import gspread
from google.oauth2.service_account import Credentials
import time
import re

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
    sheet.append_row([username, password, "", ""])
    return True

# --- メッセージを追記 ---
def record_message(username, new_message, where):
    all_users = sheet.get_all_records()
    for i, user in enumerate(all_users, start=2):  # 2行目からデータ
        if user["username"] == username:
            old_message = user.get(where, "")
            combined = old_message + "\n" + new_message if old_message else new_message
            if where == "eval":
                col_index = 4
            else:
                col_index = 3
            sheet.update_cell(i, col_index, combined)
            break

# --- メッセージ履歴を取得 ---
def load_message(username, item):
    all_users = sheet.get_all_records()
    for user in all_users:
        if user["username"] == username:
            return user.get(item, "")
    return ""

# --- セッション管理初期化 ---
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("username", "")
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("show_history", False)
st.session_state.setdefault("clear_screen", False)
st.session_state.setdefault("home", True)
st.session_state.setdefault("chat", False)
st.session_state.setdefault("first_session", True)
st.session_state.setdefault("style_label", False)
st.session_state.setdefault("eval", False)

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
if st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🗾 NihonGO❕</h1>", unsafe_allow_html=True)

    st.markdown(
        """
        <style>
        [data-testid="stSidebarCollapseControl"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.sidebar:
        st.title("OPTION")

        agent_prompts = {
            "シチュエーション選択": "あなたはゲームのアシスタントです。",
            "Chapter 1: 空港での手続き": "あなたは日本の空港の親切なスタッフです。相手は日本語を学ぶ旅行者なので、自然に会話を始めてください。",
            "Chapter 2: スーパーでの買い物": "あなたはスーパーの経験豊富な店員です。困っている様子の外国人を見かけたので、親切に話しかけてあげてください。",
            "Chapter 3: 友人との会話": "あなたは日本人で、最近できた外国人の友人です。週末の予定について、気軽に話しかけてください。",
            "Chapter 4: 職場の自己紹介": "あなたは日本の会社の同僚です。新しく入社した外国人の同僚に、フレンドリーに自己紹介をしてください。",
            "Chapter 5: 病院での診察": "あなたは病院の受付スタッフです。初めて来た様子の外国人に、どうしましたかと優しく尋ねてください。",
            "Chapter 6: 会議での発言": "あなたは会議のファシリテーターです。参加している外国人のメンバーに、意見を求めてみてください。",
            "Chapter 7: お祭りに参加": "あなたはお祭りに来ている日本人です。珍しそうに屋台を見ている外国人に、おすすめの食べ物を教えてあげましょう。",
            "Chapter 8: 市役所での手続き": "あなたは市役所の職員です。手続きで困っている外国人をサポートするため、丁寧に話しかけてください。",
            "Chapter 9: 電車の遅延対応": "あなたは駅員です。電車の遅延で困っている外国人に、状況を説明し、手助けを申し出てください。",
            "Chapter EX: English mode": "You are an English teacher. Please start a conversation with me, a student, using simple words.",
        }

        if not st.session_state["style_label"]:
            st.session_state["style_label"] = "シチュエーション選択"
        
        selected_style = st.selectbox("シチュエーション選択", list(agent_prompts.keys()), key="style_selectbox")
        
        if selected_style != st.session_state["style_label"]:
            st.session_state["style_label"] = selected_style
            st.session_state.chat_history = []
            st.session_state.first_session = True
            st.session_state.clear_screen = False
            if selected_style == "シチュエーション選択":
                st.session_state.home = True
                st.session_state.chat = False
            else:
                st.session_state.home = False
                st.session_state.chat = True
            st.rerun()

        st.session_state["agent_prompt"] = agent_prompts[st.session_state["style_label"]]
        st.markdown("---")

        if not st.session_state.home:
            if st.button("🔙 Homeに戻る"):
                st.session_state.home = True
                st.session_state.chat = False
                st.session_state.show_history = False
                st.session_state.eval = False
                st.session_state.style_label = "シチュエーション選択"
                st.session_state.chat_history = []
                st.rerun()

        if st.session_state.home:
            if st.button("💬 会話履歴を確認"):
                st.session_state.show_history = True
                st.session_state.home = False
                st.rerun()
            if st.button("🎩 過去のフィードバック"):
                st.session_state.eval = True
                st.session_state.home = False
                st.rerun()
        
        if not st.session_state.home:
             if st.button("🔙 Chatに戻る"):
                st.session_state.chat = True
                st.session_state.show_history = False
                st.session_state.eval = False
                st.rerun()

        if st.button("🚪 ログアウト"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    if st.session_state.home:
        st.title("ホーム画面")
        st.subheader("🎮 日本語学習シミュレーションゲームへようこそ！")
        st.write("このゲームでは、日本でのさまざまなシチュエーションを通して、自然な日本語での会話を練習できます。")
        st.markdown("### 🧭 遊び方")
        st.markdown("- 画面左の **サイドバー** から、練習したいシチュエーションを選んでください。")
        st.markdown("### 📌 ゲームの特徴")
        st.markdown("- AIとの対話を通じてリアルな会話練習ができます\n- あなたの会話スタイルに合わせてストーリーが変化します\n- 誤りがあった場合もフィードバックがもらえます")
        st.info("まずは左のサイドバーから、練習したいシチュエーションを選んでみましょう！")

    chapter_descriptions = {
        "Chapter 1: 空港での手続き": "この章では、日本の空港での入国手続きや質問への受け答えを練習します。",
        "Chapter 2: スーパーでの買い物": "この章では、スーパーでの買い物や店員とのやりとりを学びます。",
        "Chapter 3: 友人との会話": "この章では、友人との日常的な会話を練習します。",
        "Chapter 4: 職場の自己紹介": "この章では、職場での自己紹介や会話を学びます。",
        "Chapter 5: 病院での診察": "この章では、病院での症状説明や診察の会話を練習します。",
        "Chapter 6: 会議での発言": "この章では、会議での発言や意見の伝え方を学びます。",
        "Chapter 7: お祭りに参加": "この章では、日本のお祭りでの体験や会話を練習します。",
        "Chapter 8: 市役所での手続き": "この章では、市役所での各種手続きに関する会話を学びます。",
        "Chapter 9: 電車の遅延対応": "この章では、電車の遅延時の対応や駅員との会話を練習します。",
        "Chapter EX: English mode": "This is English mode (trial). Let's practice English conversation!",
    }

    if st.session_state.chat:
        selected_chapter = st.session_state.style_label
        description = chapter_descriptions.get(selected_chapter, "")
        if description:
            st.info(description)

        # --- ★改良点：AIから会話を開始する ---
        if st.session_state.first_session:
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])
            system_prompt = st.session_state.agent_prompt
            
            initial_user_prompt = "さあ、あなたが会話の相手です。設定に基づいて、会話を始めてください。"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": initial_user_prompt}
            ]
            
            response = client.chat.completions.create(
                model="gpt-4o", messages=messages, temperature=0.7
            )
            reply = response.choices[0].message.content
            
            st.session_state.chat_history.append(f"AI: {reply}")
            st.session_state.first_session = False
            
            now = time.strftime('%Y/%m/%d %H:%M')
            full_message = f"{st.session_state.style_label} {now}\nAI: {reply}"
            record_message(st.session_state.username, full_message, "message")
            
            st.rerun()

    if st.session_state.clear_screen:
        st.success("目標達成！おめでとうございます！")
        summary_input = "\n".join(st.session_state.chat_history)
        summary_prompt = "以下は日本語学習者とAIとの会話です。この会話を日本語教育の観点から評価して"
        
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])
        summary_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": summary_input}
            ],
            temperature=0.5,
        )
        summary_result = summary_response.choices[0].message.content
        st.markdown("### 会話の評価")
        st.markdown(summary_result)
        now = time.strftime('%Y/%m/%d %H:%M\n')
        record_message(st.session_state.username, f"{st.session_state.style_label} {now}{summary_result}", "eval")

        if st.button("🔁 最初からやり直す"):
            st.session_state.chat_history = []
            st.session_state.clear_screen = False
            st.session_state.first_session = True
            st.rerun()

    if st.session_state.chat and not st.session_state.clear_screen:
        for msg in st.session_state.chat_history:
            align = "flex-end" if msg.startswith("ユーザー:") else "flex-start"
            bg_color = "#DCF8C6" if msg.startswith("ユーザー:") else "#E6E6EA"
            content = msg.replace("ユーザー:", "").replace("AI:", "").strip()
            st.markdown(
                f"""
                <div style='display: flex; justify-content: {align}; margin: 4px 0'>
                    <div style='background-color: {bg_color}; padding: 8px 12px; border-radius: 8px; max-width: 80%; word-wrap: break-word; text-align: left; font-size: 16px;'>
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True
            )

        with st.form(key="chat_form", clear_on_submit=True):
            user_input = st.text_input("あなたのメッセージを入力してください", key="input_msg", label_visibility="collapsed")
            submit_button = st.form_submit_button("送信")

        if submit_button and user_input.strip():
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])
            system_prompt = st.session_state.agent_prompt
            messages = [{"role": "system", "content": system_prompt}]
            for msg in st.session_state.chat_history:
                role = "user" if msg.startswith("ユーザー:") else "assistant"
                content = msg.replace("ユーザー:", "").replace("AI:", "").strip()
                messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_input})

            response = client.chat.completions.create(
                model="gpt-4o", messages=messages, temperature=0.7
            )
            reply = response.choices[0].message.content
            
            st.session_state.chat_history.append(f"ユーザー: {user_input}")
            st.session_state.chat_history.append(f"AI: {reply}")

            full_message = f"ユーザー: {user_input}\nAI: {reply}"
            record_message(st.session_state.username, full_message, "message")
            
            if "目標達成" in reply:
                st.session_state.clear_screen = True
            
            st.rerun()

    elif st.session_state.show_history:
        st.markdown("### 📜 会話履歴")
        history = load_message(st.session_state.username, "message")
        if not history.strip():
            st.info("（会話履歴はまだありません）")
        else:
            pattern = r"(Chapter .*?\d{4}/\d{2}/\d{2} \d{2}:\d{2})(.*?)(?=Chapter |\Z)"
            matches = re.findall(pattern, history, re.DOTALL)
            if matches:
                options = [title.strip() for title, _ in matches]
                selected = st.selectbox("表示する会話を選んでください", options[::-1])
                selected_block = next(((t, c) for t, c in matches if t.strip() == selected), None)
                if selected_block:
                    title, content = selected_block
                    st.markdown(f"#### {title.strip()}")
                    for line in content.strip().split("\n"):
                        align = "flex-end" if line.startswith("ユーザー:") else "flex-start"
                        bg_color = "#DCF8C6" if line.startswith("ユーザー:") else "#E6E6EA"
                        content_line = line.replace("ユーザー:", "").replace("AI:", "").strip()
                        st.markdown(f"<div style='display: flex; justify-content: {align};'><div style='background-color:{bg_color}; padding: 8px 12px; border-radius: 8px; max-width: 80%;'>{content_line}</div></div>", unsafe_allow_html=True)

    elif st.session_state.eval:
        st.title("🎩過去のフィードバック")
        message = load_message(st.session_state.username, "eval")
        if not message:
            st.info("フィードバックはまだ登録されていません。")
        else:
            pattern = r"(Chapter .*?\d{4}/\d{2}/\d{2} \d{2}:\d{2})\n(.*?)(?=Chapter |\Z)"
            matches = re.findall(pattern, message, re.DOTALL)
            if matches:
                feedback_dict = {title.strip(): body.strip() for title, body in matches}
                selected_title = st.selectbox("表示するフィードバックを選んでください", sorted(feedback_dict.keys(), reverse=True))
                st.markdown("### フィードバック内容")
                for para in feedback_dict[selected_title].split("\n\n"):
                    st.markdown(para.strip())