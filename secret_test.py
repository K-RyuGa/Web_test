import streamlit as st
from openai import OpenAI
import gspread
from google.oauth2.service_account import Credentials
import time
import re
from datetime import datetime, timezone, timedelta

# --- 日本時間(JST)設定 ---
JST = timezone(timedelta(hours=+9), 'JST')

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
st.session_state.setdefault("style_label", "シチュエーション選択") # 初期値を設定
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

        # --- Game.pyから移植したプロンプト設定 ---
        base_prompt = '''
            あなたには、私が作成する「日本語学習者支援ゲーム」の登場人物を演じてもらいます。
            このゲームは、日本語学習中の外国人プレイヤーが、架空の日本での生活をシミュレーションしながらリアルな会話を通じて日本語力を向上させることを目的としています。
            プレイヤーは、さまざまなシチュエーションで登場するキャラクターと会話を重ね、日本での生活を疑似体験しながら、語彙や文法、そして自然な表現を学んでいきます。
            テンポの良い、短めのフレーズで会話を進め、自然な流れを意識してください。プレイヤーが質問しやすいように工夫しながら、リアクションを交え、実際の生活のような自然な会話をしてください。

            今回は、以下の役を演じてください。
        '''

        end_prompt = '''
            「ミッション達成」はゲームクリアの合言葉ですので、ミッションを達成していない場合、決して出力しないでください。
            それではゲームスタートです。プレイヤーに話しかけてください。
        '''

        story_prompt = [
            [
                '''
                空港の係員として、プレイヤーに入国手続きの案内を行い、パスポートの提示を求めてください。さらに、荷物の受け取り場所についても案内してください。

                具体的な行動は以下です
                1. プレイヤーにパスポートの提示を依頼。
                2. 入国審査の手続きについて説明。
                3. 荷物の場所を案内し、プレイヤーに理解したか確認し、理解していれば「ミッション達成」と出力。
                '''
            ],
            [
                '''
                スーパーの店員として、プレイヤーにレジでの会計を担当してください。

                具体的な行動は以下です
                1. プレイヤーに「次のお客様どうぞ」と声をかける。
                2. 購入した商品の会計を進め、合計金額を伝える。
                3. 支払い方法について質問があれば対応。
                4. プレイヤーが会計を完了したら、次のエージェントに引き継ぐ。
                ''',
                '''
                スーパーで買い物を終えたプレイヤーが帰宅し、家に入ろうとしたところに遭遇した隣人を演じてもらいます。
                引っ越してきたばかりの外国人に遭遇した驚きを表し、初対面のプレイヤーからの自己紹介を受け入れ、簡単な会話を交わしてください。

                具体的な行動は以下です
                1. プレイヤーに挨拶を返し、名前を名乗る。
                2. 住んでいる場所や日常生活について簡単な会話を進める。
                3. プレイヤーが無事に自己紹介を終えたら「ミッション達成」と出力。
                '''
            ],
            [
                '''
                新しい友人として、プレイヤーと自己紹介を交わし、お互いの趣味や予定について話し合ってください。

                具体的な行動は以下です
                1. 自己紹介を行い、プレイヤーにも自己紹介を促す。
                2. プレイヤーの趣味や興味について質問を投げかける。
                3. 次に会う日程を提案し、プレイヤーが同意したら「ミッション達成」と出力。
                '''
            ],
            [
                '''
                職場の同僚として、プレイヤーと自己紹介を交わし、職場での初対面の会話を楽しんでください。

                具体的な行動は以下です
                1. 自己紹介を行い、プレイヤーにも自己紹介を促す。
                2. 仕事について簡単に会話をし、プレイヤーが緊張しないようリラックスさせる。
                3. プレイヤーが無事に自己紹介を終えたら次のエージェントに引き継ぐ。
                ''',
                '''
                上司として、プレイヤーからの敬語を使った自己紹介を受け、適切な敬語表現について助言を行ってください。

                具体的な行動は以下です
                1. プレイヤーから敬語を使った自己紹介を受ける。
                2. プレイヤーの自己紹介に対してフィードバックを与える。
                3. プレイヤーが無事に敬語を使いこなせたら「ミッション達成」と出力。
                '''
            ],
            [
                '''
                病院の医師として、プレイヤーの症状を聞き、診察を進めてください。

                具体的な行動は以下です
                1. プレイヤーに症状を尋ね、症状について質問をする。
                2. 診察を行い、適切な診断を下す。
                3. プレイヤーが無事に診察を終えたら「ミッション達成」と出力。
                '''
            ],
            [
                '''
                職場の同僚として、プレイヤーが会議で発言する場面をサポートし、フィードバックを提供してください。

                具体的な行動は以下です
                1. プレイヤーに意見を求め、発言の機会を与える。
                2. プレイヤーの意見に対してフィードバックを行い、議論を進める。
                3. プレイヤーが無事に意見を述べ、議論を進められたら次のエージェントに引き継ぐ。
                ''',
                '''
                上司として、プレイヤーの発言を評価し、アドバイスを提供してください。

                具体的な行動は以下です
                1. プレイヤーに会議での意見を求め、サポート。
                2. プレイヤーの発言に対する具体的なフィードバックを提供。
                3. プレイヤーが無事に意見を述べ、議論を進められたら「ミッション達成」と出力。
                '''
            ],
            [
                '''
                友人として、プレイヤーを日本のお祭りに招待し、行事のマナーや文化的な背景を説明してください。

                具体的な行動は以下です
                1. プレイヤーをお祭りに招待し、行事の説明をする。
                2. 文化的なマナーや行事の習慣について教える。
                3. プレイヤーが無事に行事に参加し、楽しんだら「ミッション達成」と出力。
                ''' 
            ],
            [
                '''
                市役所の窓口担当者として、プレイヤーが必要な書類を提出する場面をサポートし、手続きについて説明してください。

                具体的な行動は以下です
                1. プレイヤーに必要な書類を尋ねる。
                2. 手続きのステップを説明し、プレイヤーが困った場合にサポート。
                3. プレイヤーが手続きを無事に完了したら「ミッション達成」と出力。
                '''
            ],
            [
                '''
                駅員として、プレイヤーが電車の遅延に対処する際、適切な指示を出して助けてください。

                具体的な行動は以下です
                1. 電車の遅延を説明し、次の行動を提案する。
                2. プレイヤーの質問に対して明確に答える。
                3. プレイヤーが無事に解決策を見つけたら次のエージェントに引き継ぐ
                ''',
                '''
                警察官として、プレイヤーが迷子になった場合、適切な助言を与え、安全に目的地に戻れるようサポートしてください。

                具体的な行動は以下です
                1. 迷子になったプレイヤーに現在地を尋ね、助け舟を出す。
                2. 目的地までの道順を説明し、プレイヤーが無事に戻れるようサポート。
                3. プレイヤーが無事に解決すれば「ミッション達成」と出力。
                '''
            ]
        ]

        # Game.pyのstoriesを元に、selectboxの選択肢を定義
        stories = [
            "シチュエーション選択", # ホーム画面用
            "Chapter 1: 空港での手続き",
            "Chapter 2: スーパーでの買い物",
            "Chapter 3: 友人との会話",
            "Chapter 4: 職場の自己紹介",
            "Chapter 5: 病院での診察",
            "Chapter 6: 会議での発言",
            "Chapter 7: お祭りに参加",
            "Chapter 8: 市役所での手続き",
            "Chapter 9: 電車の遅延対応",
        ]
        
        # 1. 現在（変更前）のシチュエーションを覚えておく
        previous_style = st.session_state.style_label

        # 2. セレクトボックスを描画し、ユーザーが選択した新しいシチュエーションを取得する
        current_style = st.selectbox("シチュエーション選択", stories, key="selectbox_style")

        # 3. 「変更前」と「変更後」が異なるかチェック
        if current_style != previous_style:
            # 変更があった場合、セッションの状態を更新・リセットする
            st.session_state.style_label = current_style
            
            st.session_state.chat_history = [] 
            st.session_state.first_session = True 
            
            # 画面の状態を正しく設定
            if current_style == "シチュエーション選択":
                st.session_state.home = True
                st.session_state.chat = False
            else:
                st.session_state.home = False
                st.session_state.chat = True
            
            # 変更を画面に反映させるために、スクリプトを再実行
            st.rerun()
        
        # 選択された章に応じて、AIに渡すプロンプトを組み立てる
        if st.session_state.style_label != "シチュエーション選択":
            chapter_index = stories.index(st.session_state.style_label) - 1
            # story_promptはリストのリストなので、章のプロンプトを取得
            selected_story_prompts = story_prompt[chapter_index]
            # 複数のプロンプトがある場合も考慮（現状は最初のプロンプトのみ使用）
            st.session_state.agent_prompt = base_prompt + selected_story_prompts[0] + end_prompt
        else:
            st.session_state.agent_prompt = "あなたはゲームのアシスタントです。"
    
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
                
        if not st.session_state["style_label"] == "シチュエーション選択" and not st.session_state["show_history"] and not st.session_state["eval"]:
            if st.button("🔙 Homeに戻る"):
                st.session_state["show_history"] = False
                st.session_state["home"] = True
                st.session_state["logged_in"] = True
                st.session_state["chat_history"] = []
                st.session_state["clear_screen"] = False
                st.session_state["chat"] = False
                st.session_state["style_label"] = "シチュエーション選択"
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
        "Chapter 1": "空港での手続き\n日本に到着し、いよいよ入国手続きへ。空港スタッフの案内を受け、パスポートを提示し、入国審査を進めてください。荷物の受け取り場所も確認し、スムーズに空港を出るための準備をしましょう。",
        
        "Chapter 2": "スーパーでの買い物\n生活に必要なものを揃えるため、近所のスーパーで買い物をします。店員とのやり取りを通じて、レジでの会計を体験し、支払い方法を選んでスムーズに買い物を完了しましょう。",
        
        "Chapter 3": "友人との会話\n新しい友人と初めての会話を楽しみます。お互いの自己紹介から始め、趣味や今後の予定について話し合いながら、友人関係を深めていきましょう。",
        
        "Chapter 4": "職場の自己紹介\n新しい職場での初日。自己紹介を通じて同僚との関係を築き、職場の雰囲気に慣れましょう。緊張感を和らげつつ、上手に自己紹介をしていくことが目標です。",
        
        "Chapter 5": "病院での診察\n体調不良の際に病院を訪れ、医師との診察を受けます。症状をしっかり伝え、診察を受けることで適切な治療を受けられるよう、自然な会話を意識しましょう。",
        
        "Chapter 6": "会議での発言\n職場の会議に参加し、自分の意見を述べる場面です。議論に参加しながら、適切なフィードバックを受け、職場での存在感を高めることを目指します。",
        
        "Chapter 7": "お祭りに参加\n日本のお祭りに参加し、友人と一緒に日本の伝統文化を体験します。イベントのマナーや背景を理解しながら、楽しい時間を過ごしましょう。",
        
        "Chapter 8": "市役所での手続き\n日本での生活には、さまざまな手続きが必要です。市役所を訪れ、必要な書類を提出して手続きを進め、円滑に生活の基盤を整えていきましょう。",
        
        "Chapter 9": "電車の遅延対応\n通勤や外出中に電車が遅延してしまった場合の対応を学びます。駅員とのやり取りを通じて、次の行動を考え、無事に目的地に到着できるように対処しましょう。"
    }
    if not st.session_state["home"] and not st.session_state["show_history"] and not st.session_state["eval"]:
        
        selected_chapter = st.session_state["style_label"] # すでに selectbox で選ばれている
        description = chapter_descriptions.get(selected_chapter, "")
        if description:
            st.info(description)

        # --- AIが会話を始める処理 ---
        if st.session_state.first_session and st.session_state.chat:
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])
            # AIに自然な会話開始を促すためのプロンプト
            start_prompt = "あなたの役割に沿って、日本語学習者である相手に自然な形で話しかけ、会話を始めてください。"
            messages = [
                {"role": "system", "content": st.session_state.agent_prompt},
                {"role": "user", "content": start_prompt}
            ]
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
            )
            reply = response.choices[0].message.content
            
            st.session_state.chat_history.append(f"AI: {reply}")
            st.session_state.first_session = False # AIが話したので、次はユーザーの番

            now = datetime.now(JST).strftime('%Y/%m/%d %H:%M')            
            full_message = st.session_state["style_label"] + " " + now + "\n" + f"AI: {reply}"
            record_message(st.session_state.username, full_message, "message")
            st.rerun()
            
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
                            color:black;
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
                            color:black;
                        '>
                            {msg.replace("AI:", "")}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


    # --- 入力フォーム ---
    if st.session_state["chat"] and not st.session_state.first_session:
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

                # ✅ 過去のチャット履歴を messages に変換
                system_prompt = st.session_state.get("agent_prompt", "あなたは親切な日本語学習の先生です。")
                messages = [{"role": "system", "content": system_prompt}]
                for msg in st.session_state.get("chat_history", []):
                    if msg.startswith("ユーザー:"):
                        messages.append({"role": "user", "content": msg.replace("ユーザー:", "").strip()})
                    elif msg.startswith("AI:"):
                        messages.append({"role": "assistant", "content": msg.replace("AI:", "").strip()})

                # ✅ 新しい入力を追加
                messages.append({"role": "user", "content": user_input})

                # ✅ API 呼び出し
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.7,
                )
                reply = response.choices[0].message.content
            
                # 履歴に追加
                st.session_state.chat_history.append(f"ユーザー: {user_input}")
                st.session_state.chat_history.append(f"AI: {reply}")

                # Google Sheetsに記録（関数が定義されている前提）
                if st.session_state["first_session"]:
                    now = datetime.now(JST).strftime('%Y/%m/%d %H:%M')
                    full_message = st.session_state["style_label"] + now + f"ユーザー: {user_input}AI: {reply}"
                    st.session_state["first_session"] = False
                else:
                    full_message = f"ユーザー: {user_input}\nAI: {reply}"
                
                record_message(st.session_state.username, full_message,"message")
                
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
                                            color:black;
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
                                            color:black;
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
