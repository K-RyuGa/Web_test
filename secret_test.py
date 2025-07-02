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
    sheet.append_row([username, password, ""])
    return True

# --- メッセージを追記 ---
def record_message(username, new_message,where):
    all_users = sheet.get_all_records()
    for i, user in enumerate(all_users, start=2):  # 2行目からデータ
        if user["username"] == username:
            old_message = user.get(where, "")
            combined = old_message + "\n" + new_message if old_message else new_message
            if where == "eval":
                x = 4
            else:
                x = 3
            sheet.update_cell(i, x, combined)
            break

# --- メッセージ履歴を取得 ---
def load_message(username,item):
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
st.session_state.setdefault("clear_screen",False)
st.session_state.setdefault("home",True)
st.session_state.setdefault("chat",False)
st.session_state.setdefault("first_session",True)
st.session_state.setdefault("style_label",False)
st.session_state.setdefault("eval",False)

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
                st.session_state.clear_screen = False
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

        # 会話スタイル選択
        agent_prompts = {
            "シチュエーション選択":"あなたはゲームのアシスタントです。",
            "Chapter 1: 空港での手続き": "あなたはAIです。",
            "Chapter 2: スーパーでの買い物": "あなたはAIです。",
            "Chapter 3: 友人との会話": "あなたはAIです。",
            "Chapter 4: 職場の自己紹介": "あなたはAIです。",
            "Chapter 5: 病院での診察": "あなたはAIです。",
            "Chapter 6: 会議での発言": "あなたはAIです。",
            "Chapter 7: お祭りに参加": "あなたはAIです。",
            "Chapter 8: 市役所での手続き": "あなたはAIです。",
            "Chapter 9: 電車の遅延対応": "あなたはAIです。",
            "Chapter EX: English mode": "私は英語の練習がしたいです。簡単な単語を意識して私と英語で会話してください",
        }
        
        if not st.session_state["style_label"]:
            st.session_state["style_label"] = "シチュエーション選択" 
            st.selectbox("シチュエーション選択", list(agent_prompts.keys()))
        else:
            st.session_state["style_label"] = st.selectbox("シチュエーション選択", list(agent_prompts.keys()))
                
        st.session_state["agent_prompt"] = agent_prompts[st.session_state["style_label"]]
        st.markdown("---")

        # show_historyが未定義ならFalseで初期化
        if "show_history" not in st.session_state:
            st.session_state["show_history"] = False

        # チャット中は「履歴を見る」ボタンを表示、履歴中は「戻る」ボタンを表示
        if not st.session_state["show_history"]:
            if st.button("💬 会話履歴を確認"):
                
                st.session_state["show_history"] = True
                st.session_state["home"] = False
                st.session_state["logged_in"] = True
                st.session_state["chat_history"] = []
                st.session_state["clear_screen"] = False
                st.session_state["chat"] = False
                st.session_state["eval"] = False

                
                st.rerun()
                
        if not st.session_state["eval"]:
            if st.button("🎩 過去のフィードバック"):      
                st.session_state["show_history"] = False
                st.session_state["home"] = False
                st.session_state["logged_in"] = True
                st.session_state["chat_history"] = []
                st.session_state["clear_screen"] = False
                st.session_state["chat"] = False
                st.session_state["eval"] = True
                
                st.rerun()
                
        if  not st.session_state["style_label"] == "シチュエーション選択" and not st.session_state["show_history"] and not st.session_state["eval"]:
            if st.button("🔙 Homeに戻る"):
                st.session_state["show_history"] = False
                st.session_state["home"] = True
                st.session_state["logged_in"] = True
                st.session_state["chat_history"] = []
                st.session_state["clear_screen"] = False
                st.session_state["chat"] = False
                st.session_state["style_label"] = False
                st.session_state["eval"] = False
                st.rerun()
                
        else:
            if not st.session_state["home"]:
                if st.button("🔙 Chatに戻る"):
            
                    st.session_state["show_history"] = False
                    st.session_state["home"] = True
                    st.session_state["logged_in"] = True
                    st.session_state["chat_history"] = []
                    st.session_state["clear_screen"] = False
                    st.session_state["chat"] = False
                    st.session_state["eval"] = False
                    st.rerun()

        # ログアウト
        if st.button("🚪 ログアウト"):
        
            st.session_state["show_history"] = False
            st.session_state["home"] = True
            st.session_state["logged_in"] = False
            st.session_state["clear_screen"] = False
            st.session_state["chat"] = False
            st.session_state["first_session"] = True
            st.session_state["eval"] = False
            st.session_state.username = ""
            #st.session_state["username"] = False
            st.session_state.chat_history = []
            st.session_state["style_label"] = "シチュエーション選択"
            st.rerun()

    if st.session_state["home"]:
        
        st.title("ホーム画面")
    
        st.subheader("🎮 日本語学習シミュレーションゲームへようこそ！")

        st.write("このゲームでは、日本でのさまざまなシチュエーションを通して、自然な日本語での会話を練習できます。")

        st.markdown("### 🧭 遊び方")
        st.markdown("- 画面左の **サイドバー** から、練習したいシチュエーションを選んでください。")
        
        st.markdown("### 📌 ゲームの特徴")
        st.markdown("""
        - AIとの対話を通じてリアルな会話練習ができます  
        - あなたの会話スタイルに合わせてストーリーが変化します  
        - 誤りがあった場合もフィードバックがもらえます
        """)
     
        st.info("まずは左のサイドバーから、練習したいシチュエーションを選んでみましょう！")
        # st.markdown("### 💬 質問がある場合")
        # st.write("画面下のチャット欄に質問を入力してください。できる限り丁寧にお答えします。")
        
        if st.session_state["style_label"] != "シチュエーション選択":
            st.session_state["home"] = False
            st.session_state["chat"] = True
            st.rerun()
        
    # --- 説明文定義 ---
    chapter_descriptions = {
        "シナリオ選択":"",
        "Chapter 1: 空港での手続き": "この章では、日本の空港での入国手続きや質問への受け答えを練習します。",
        "Chapter 2: スーパーでの買い物": "この章では、スーパーでの買い物や店員とのやりとりを学びます。",
        "Chapter 3: 友人との会話": "この章では、友人との日常的な会話を練習します。",
        "Chapter 4: 職場の自己紹介": "この章では、職場での自己紹介や会話を学びます。",
        "Chapter 5: 病院での診察": "この章では、病院での症状説明や診察の会話を練習します。",
        "Chapter 6: 会議での発言": "この章では、会議での発言や意見の伝え方を学びます。",
        "Chapter 7: お祭りに参加": "この章では、日本のお祭りでの体験や会話を練習します。",
        "Chapter 8: 市役所での手続き": "この章では、市役所での各種手続きに関する会話を学びます。",
        "Chapter 9: 電車の遅延対応": "この章では、電車の遅延時の対応や駅員との会話を練習します。",
        "Chapter EX: English mode": "英語モード（試）",
    }
    if not st.session_state["home"] and not st.session_state["show_history"] and not st.session_state["eval"]:
        
        selected_chapter = st.session_state["style_label"] # すでに selectbox で選ばれている
        description = chapter_descriptions.get(selected_chapter, "")
        if description:
            st.info(description)
            
    if st.session_state["clear_screen"]:
        
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
        record_message(st.session_state.username, st.session_state["style_label"] + now  + summary_result,"eval")

      

        # 「もう一度やる」ボタン
        if st.button("🔁 最初からやり直す"):
            
            st.session_state.chat_history = []
            st.session_state["clear_screen"] = False
            st.session_state["show_history"] = False
            st.session_state["home"] = False
            st.session_state["logged_in"] = True
            st.session_state["chat"] = True
            st.session_state["first_session"] = True
            st.rerun()
    
       #st.markdown("### 💬 ")

    # --- セッション中の履歴表示 ---
    if st.session_state.chat_history and not st.session_state["clear_screen"]:
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


    if st.session_state["chat"]:
        # ✅ 初回セッションならAIのメッセージから開始（仮のユーザー入力なし）
        if st.session_state["first_session"]:
            system_prompt = st.session_state.get("agent_prompt", "あなたは親切な日本語学習の先生です。")
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])

            messages = [{"role": "system", "content": system_prompt}]

            # ここが重要：ユーザー入力なしでAPIを呼び出す（AIの第一声）
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
            )
            reply = response.choices[0].message.content

            # ユーザーなしのAI発話のみを履歴に単体で追加
            st.session_state.chat_history = [f"AI: {reply}"]

            # Google Sheetsへの記録（片方だけ記録）
            now = time.strftime('%Y/%m/%d %H:%M')
            full_message = st.session_state["style_label"] + now + "\n" + f"AI: {reply}"
            record_message(st.session_state.username, full_message, "message")

            # セッションフラグ更新
            st.session_state["first_session"] = False

        # ✅ チャットフォーム
        with st.form(key="chat_form", clear_on_submit=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                user_input = st.text_input("あなたのメッセージを入力してください", key="input_msg", label_visibility="collapsed")
            with col2:
                submit_button = st.form_submit_button("送信", use_container_width=True)

        # --- 送信処理 ---
        if submit_button:
            if user_input.strip():
                client = OpenAI(api_key=st.secrets["openai"]["api_key"])

                system_prompt = st.session_state.get("agent_prompt", "あなたは親切な日本語学習の先生です。")
                messages = [{"role": "system", "content": system_prompt}]
                for msg in st.session_state.get("chat_history", []):
                    if msg.startswith("ユーザー:"):
                        messages.append({"role": "user", "content": msg.replace("ユーザー:", "").strip()})
                    elif msg.startswith("AI:"):
                        messages.append({"role": "assistant", "content": msg.replace("AI:", "").strip()})

                messages.append({"role": "user", "content": user_input})

                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.7,
                )
                reply = response.choices[0].message.content

                # ユーザー→AIを1セットで履歴・保存
                st.session_state.chat_history.append(f"ユーザー: {user_input}")
                st.session_state.chat_history.append(f"AI: {reply}")

                full_message = f"ユーザー: {user_input}\nAI: {reply}"
                record_message(st.session_state.username, full_message, "message")

                if "目標達成" in reply and not st.session_state["home"]:
                    st.session_state["clear_screen"] = True
                    st.session_state["chat"] = False
                    st.session_state["chat_histry"] = []
                    st.session_state["first_session"] = True
                    st.rerun()
                st.rerun()
            else:
                st.warning("メッセージが空です。")

        
    elif st.session_state.show_history:
        st.markdown("### 📜 会話履歴")

        history = load_message(st.session_state.username, "message")

        if not history.strip():
            st.info("（会話履歴はまだありません）")
        else:
            # 「Chapter + 日付」ごとのブロックを抽出
            pattern = r"(Chapter \d+: .*?\d{4}/\d{2}/\d{2} \d{2}:\d{2})(.*?)(?=Chapter \d+: |\Z)"
            matches = re.findall(pattern, history, re.DOTALL)

            if not matches:
                st.warning("履歴の解析に失敗しました。")
            else:
                # タイトルだけをリスト化（選択肢）
                options = [title.strip() for title, _ in matches]
                selected = st.selectbox("表示する会話を選んでください", options[::-1])  # 新しい順

                # 選ばれたタイトルのブロックのみ表示
                selected_block = next(((t, c) for t, c in matches if t.strip() == selected), None)

                if selected_block:
                    title, content = selected_block
                    st.markdown(f"#### {title.strip()}")

                    lines = content.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if line.startswith("ユーザー:"):
                            col1, col2 = st.columns([4, 6])
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
                                            {line.replace("ユーザー:", "")}
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                        elif line.startswith("AI:"):
                            col1, col2 = st.columns([6, 4])
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
                                            {line.replace("AI:", "")}
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )


    elif st.session_state["eval"]:
        st.title("🎩過去のフィードバック")

        # メッセージ取得（load_messageは既存関数）
        message = load_message(st.session_state["username"], "eval")

        if not message:
            st.info("フィードバックはまだ登録されていません。")
        else:

            # 「Chapter X: ○○YYYY/MM/DD hh:mm」ごとにフィードバックを抽出
            pattern = r"(Chapter \d+: .*?\d{4}/\d{2}/\d{2} \d{2}:\d{2})\n(.*?)(?=Chapter \d+: |\Z)"
            matches = re.findall(pattern, message, re.DOTALL)

            if not matches:
                st.warning("フィードバックが解析できませんでした。")
            else:
                # セレクトボックスの選択肢用にタイトルだけ使用
                feedback_dict = {title.strip(): body.strip() for title, body in matches}

                # セレクトボックスでフィードバック選択
                selected_title = st.selectbox("表示するフィードバックを選んでください", sorted(feedback_dict.keys(), reverse=True))

                # 表示（タイトルは非表示）
                st.markdown("### フィードバック内容")
                selected_body = feedback_dict[selected_title]

                # パラグラフごとに分けて表示（2重改行で段落分割）
                for para in selected_body.split("\n\n"):
                    st.markdown(para.strip())

#次やること　AIから会話　動的プロンプト
