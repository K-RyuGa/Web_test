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
    # ヘッダーに合わせて5列分のデータを持つ行を追加する
    sheet.append_row([username, password, "", "", ""])
    return True

# --- メッセージを追記 ---
def record_message(username, new_message, where):
    all_users = sheet.get_all_records()
    # 列のマッピングを辞書で管理
    col_map = {"message": 3, "eval": 4, "player_summary": 5}
    col_index = col_map.get(where)
    if not col_index:
        return # 対象の列がなければ何もしない

    for i, user in enumerate(all_users, start=2):
        if user["username"] == username:
            # player_summaryは追記ではなく、常に新しい内容で上書きする
            if where == 'player_summary':
                combined = new_message
            else: # messageとevalは従来通り追記
                old_message = user.get(where, "")
                combined = old_message + "\n" + new_message if old_message else new_message
            
            sheet.update_cell(i, col_index, combined)
            break


# --- メッセージ履歴を取得 ---
def load_message(username,item):
    all_users = sheet.get_all_records()
    for user in all_users:
        if user["username"] == username:
            return user.get(item, "")
    return ""

# --- 動的プロンプト生成機能 (Game.pyから移植・改造) ---
def make_new_prompt(username, base_prompt_text, selected_prompt_text):
    making_prompt = '''
        あなたには、私が作成する「日本語学習者支援ゲーム」のシステムの一部である、**動的プロンプト生成機能**を担当してもらいます。
        このゲームは、日本語学習中の外国人プレイヤーが、架空の日本での生活をシミュレーションしながらリアルな会話を通じて日本語力を向上させることを目的としています。
        あなたには、プレイヤーの過去の会話履歴や言語的課題リストに基づき、一人ひとりに最適化された会話シナリオ（プロンプト）を生成する役割を担っていただきます。

        以下に、ベースとなるプロンプトとプレイヤーの言語的課題リストを与えますので、これらを基に、学習効果が最大化されるような、より自然で質の高いプロンプトへと改善してください。
        ただし、元々のプロンプトに定められている具体的な行動（ミッション）を減らしてはいけません。
        出力は余計な文言を含まず、完成したプロンプトのみを出力してください。

        ベースとなるプロンプト
        「
    '''
    making_prompt_end = '''
        」
        あなたに与えられる「プレイヤーの言語的課題リスト」は、プレイヤーが抱える言語的・コミュニケーション戦略的な課題を箇条書きでリストアップしたものです。

        あなたのタスクは、そのリストにある**個々の課題を克服させるのに最適な状況を、ベースとなるプロンプトのシナリオに自然に組み込む**ことです。

        【プロンプト生成の具体例】
        *   もし課題リストに「助詞『が』の使い方が不自然」とあれば、主語を明確にしないと意味が通じないような質問をキャラクターにさせる。
        *   もし課題リストに「要求が直接的すぎる」とあれば、キャラクターが少し困惑した反応を示し、プレイヤーがより丁寧な言い方（「〜していただけませんか？」など）を試さざるを得ない状況を作る。
        *   もし課題リストに「単語の選択ミス（例：『教える』と『伝える』）」とあれば、その両方の単語が文脈上使えるが、ニュアンスが異なる場面を意図的に作り出す。

        【重要】注意点
        *   課題の克服を**あからさまに要求してはいけません**。「『が』を使って話してください」のような指示は禁止です。あくまで自然な会話の中で、プレイヤーが自発的に正しい表現を使わざるを得ない状況をデザインしてください。
        *   プレイヤーの過去の特定の誤りに固執せず、その背景にある根本的な課題の解決を促してください。
        *   ゲーム内容が不自然になってはいけません。また、「目標達成」はゲームクリアのキーワードなので注意してください。
    '''
    
    # Googleスプレッドシートからプレイヤーの要約データを読み込む
    persona = load_message(username, "player_summary")
    if not persona:
        # 要約データがない場合は、パーソナライズせず元のプロンプトを返す
        return base_prompt_text + selected_prompt_text

    persona_text = "」
プレイヤーの言語的課題リスト
" + persona
    
    # 動的プロンプト生成のためのAPI呼び出し
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    messages = [{
        "role": "system", 
        "content": making_prompt + base_prompt_text + selected_prompt_text + persona_text + making_prompt_end
    }]
    
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0
    )
    return completion.choices[0].message.content

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

            【重要】会話の原則
            あなたの最も重要な役割は、単に親切な案内役になることではなく、リアルな日本の会話をシミュレートすることです。
            もしプレイヤーの言葉遣いがTPO（時・場所・場面）に合っていなかったり、不自然だったり、無礼だったりした場合、あるいは、会話の自然なステップ（例えば、自己紹介や世間話など）を飛ばして、いきなり最終目的（例：「次に会う約束」）を達成しようとした場合、あなたは安易に「ミッション達成」を許可してはいけません。

            その際は、あなたのキャラクターとして最も自然な反応を返してください。例えば、以下のような対応です。
            ・相手の意図が分からず、困惑する。
            ・丁寧だが、はっきりと要求を断る。（例：「申し訳ありませんが、まだお互いのことをよく知らないので…」）
            ・「どういうことですか？」と、相手の真意を確かめる質問をする。

            プレイヤーが適切なコミュニケーションを段階的に取って初めて、ミッションが達成されるように会話を導いてください。

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
                4. プレイヤーが会計を完了したら、「ミッション達成」と出力。
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
                3. プレイヤーが無事に自己紹介を終えたら「ミッション達成」と出力。
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
                3. プレイヤーが無事に解決策を見つけたら「ミッション達成」と出力。
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
        
        # 1. 現在のセッションのスタイルを取得（これが基準となる）
        current_style_in_session = st.session_state.get("style_label", "シチュエーション選択")

        # 2. selectboxの現在のインデックスを計算
        try:
            current_index = stories.index(current_style_in_session)
        except ValueError:
            current_index = 0 # 万が一見つからない場合はデフォルト

        # 3. セレクトボックスを描画し、ユーザーが選択した新しい値を取得
        selected_style = st.selectbox("シチュエーション選択", stories, index=current_index, key="selectbox_style")

        # 4. ユーザーの選択がセッションの状態と異なるかチェック
        if selected_style != current_style_in_session:
            # 変更があった場合、セッションの状態を更新・リセットする
            st.session_state.style_label = selected_style
            
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
                st.session_state.home = True
                st.session_state.chat = False
                st.session_state.clear_screen = False
                st.session_state.style_label = "シチュエーション選択" # これが重要
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
        "Chapter 1: 空港での手続き": "日本に到着！ 空港スタッフの案内に従って入国手続きを進めましょう。**目標は、荷物を受け取る場所がどこかを聞き取り、理解することです。**",
        "Chapter 2: スーパーでの買い物": "スーパーで買い物をします。店員さんの案内に従って、レジでの会計を体験しましょう。**目標は、支払い方法を伝えて、無事に会計を完了させることです。**",
        "Chapter 3: 友人との会話": "新しくできた友人と会話が弾みます。趣味などについて話し、仲良くなりましょう。**目標は、次に会う約束を取り付けることです。**",
        "Chapter 4: 職場の自己紹介": "新しい職場で、同僚に自己紹介をします。フレンドリーな会話を楽しみましょう。**目標は、相手に失礼なく、自分の名前を伝えて自己紹介を完了させることです。**",
        "Chapter 5: 病院での診察": "病院で診察を受けます。お医者さんに、体の具合が悪いことを伝えましょう。**目標は、自分の症状を正確に説明し、診察を無事に終えることです。**",
        "Chapter 6: 会議での発言": "職場の会議に参加します。同僚から意見を求められるので、自分の考えを述べてみましょう。**目標は、会議の流れを汲んで、自分の意見をしっかりと発言することです。**",
        "Chapter 7: お祭りに参加": "友人と一緒に日本のお祭りにやってきました。文化やマナーについて教わりながら、お祭りを楽しみましょう。**目標は、友人との会話を楽しみ、お祭りを満喫していることを伝えることです。**",
        "Chapter 8: 市役所での手続き": "市役所で行政手続きに挑戦します。窓口担当者の説明をよく聞いてください。**目標は、指示に従って、必要な手続きを完了させることです。**",
        "Chapter 9: 電車の遅延対応": "電車が遅れて困っています。駅員さんに状況を尋ね、どうすればよいか確認しましょう。**目標は、駅員さんの指示を理解し、次の行動を決めることです。**",
    }

    if st.session_state.chat:
        description = chapter_descriptions.get(st.session_state.style_label, "")
        if description:
            st.info(description)

    if not st.session_state["home"] and not st.session_state["show_history"] and not st.session_state["eval"]:

        # --- AIが会話を始める処理 ---
        if st.session_state.first_session and st.session_state.chat:
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])

            # --- ★動的プロンプト生成をここで行う --- #
            # 1. 現在の章の基本プロンプトを取得
            chapter_index = stories.index(st.session_state.style_label) - 1
            selected_story_prompt = story_prompt[chapter_index][0]
            
            # 2. プレイヤーの過去のデータを使って、プロンプトをパーソナライズする
            personalized_prompt = make_new_prompt(
                st.session_state.username, 
                base_prompt, 
                selected_story_prompt
            )
            
            # 3. 最終的なシステムプロンプトを組み立てる
            final_system_prompt = personalized_prompt + end_prompt
            # --- ★動的プロンプト生成ここまで --- #

            # AIに自然な会話開始を促すためのプロンプト
            start_prompt = "あなたの役割に沿って、日本語学習者である相手に自然な形で話しかけ、会話を始めてください。"
            messages = [
                {"role": "system", "content": final_system_prompt},
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
            
    if st.session_state["clear_screen"]:
        
        st.success("ミッション達成！おめでとうございます！")
        
        # --- Game.pyから移植した詳細な評価プロンプト ---
        evaluation_prompt = '''
            あなたには、私が作成する「日本語学習者支援ゲーム」の評価システムを担当してもらいます。
            あなたの役割は、プレイヤーの会話履歴を分析し、公平かつ教育的なフィードバックを提供することです。

            【重要】評価の手順と採点基準
            評価の曖昧さをなくし、常に一貫した基準でフィードバックを提供するため、以下の手順と採点基準を厳格に守ってください。

            手順1: 会話の分析
            まず、会話全体を「1. 文法・語彙」「2. TPO・敬語」「3. 会話の自然な流れ」の3つの観点から詳細に分析します。

            手順2: 採点
            次に、以下の採点基準に照らし合わせ、会話がどのレベルに該当するかを判断し、最終的な点数を決定します。

            【採点基準】
            *   **90～100点（素晴らしい）**:
                *   文法や語彙の誤りがほとんどなく、非常に自然な日本語を使えている。
                *   TPOや相手との関係性に合わせた敬語・丁寧語の使い分けが完璧。
                *   会話の流れがスムーズで、目的達成までのコミュニケーションが円滑。

            *   **70～89点（良い）**:
                *   小さな文法・語彙の誤り（助詞の間違いなど）がいくつか見られるが、コミュニケーションの妨げにはなっていない。
                *   TPOや敬語の選択に少し不自然な点があるが、大きな問題はない。
                *   会話の目的は達成できているが、時々、応答に詰まったり、少し不自然な間があったりする。

            *   **40～69点（要改善）**:
                *   文法・語彙の誤りが多く、相手が意味を推測する必要がある場面が見られる。
                *   TPOに合わない言葉遣いや、不適切な敬語が目立つ。
                *   会話の流れがぎこちなく、話が噛み合わなかったり、唐突な発言で相手を困惑させたりしている。

            *   **0～39点（大きな課題あり）**:
                *   文法・語彙の誤りが非常に多く、コミュニケーションの成立が困難。
                *   TPOを著しく無視した、あるいは無礼な言葉遣いが見られる。
                *   会話が全く成り立っていない、または、ミッション達成のプロセスを完全に無視している。

            手順3: フィードバックの作成
            最後に、以下の形式に従って、プレイヤーへのフィードバックを出力してください。

            【出力形式】
            1.  **点数**: (採点結果を「n/100」の形式で記述)
            2.  **総評**: (会話全体を称賛、または、励ますような、ポジティブな一言)
            3.  **詳細フィードバック**:
                *   **【良かった点】**: (具体的な会話の一部を引用し、文法、TPO、会話の流れの観点から良かった点を褒める)
                *   **【改善できる点】**: (具体的な会話の一部を引用し、なぜそれが問題なのか、どうすればもっと良くなるのかを、上記の3つの観点から丁寧に説明する)

            この形式で、プレイヤーに語りかける口調で出力してください。
        '''
        # --- Game.pyから移植した要約プロンプト ---
        summary_prompt = '''
            あなたには、私が作成する「日本語学習者支援ゲーム」のシステムの一部である、**プレイヤーの言語的課題分析機能**を担当してもらいます。
            あなたの役割は、以下の会話履歴を分析し、プレイヤーが日本語でのコミュニケーションにおいて抱えている「課題」を客観的に抽出することです。

            【重要】分析のルール
            *   プレイヤーの性格、気分、個性、意図などを**絶対に分析・記述してはいけません**。
            *   抽出する情報は、**純粋に言語的・コミュニケーション戦略的な課題**に限定してください。
            *   以下の観点に沿って、具体的な課題を簡潔な箇条書きで出力してください。

            【分析の観点】
            1.  **文法・語彙の誤り**: 助詞（は/が/を/に等）の間違い、動詞の活用ミス、不適切な単語の選択。
            2.  **敬語・丁寧語のレベル**: 場面にそぐわない丁寧すぎる、または、くだけすぎた表現。
            3.  **コミュニケーション戦略**: 質問への応答が不自然に短い/長い、話の展開が唐突、相手への配慮が欠けた直接的すぎる表現など。
            4.  **会話の流れの阻害**: 文脈を無視した発言、会話の目的から逸脱した言動など。

            以下の会話履歴を分析し、上記の観点から課題のみを箇条書きで出力してください。
        '''
        
        conversation_log = "\n".join(st.session_state.chat_history)
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])

        # --- 評価を生成して表示・記録 ---
        evaluation_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": evaluation_prompt},
                {"role": "user", "content": conversation_log}
            ],
            temperature=0.5,
        )
        evaluation_result = evaluation_response.choices[0].message.content
        st.markdown("### 会話の評価")
        st.markdown(evaluation_result)
        now_str = datetime.now(JST).strftime('%Y/%m/%d %H:%M\n')
        record_message(st.session_state.username, st.session_state["style_label"] + " " + now_str + evaluation_result, "eval")

        # --- 行動履歴の要約を生成して記録 ---
        summary_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": conversation_log}
            ],
            temperature=0.5,
        )
        summary_result = summary_response.choices[0].message.content
        # この要約は画面には表示せず、裏側で記録する
        record_message(st.session_state.username, summary_result, 'player_summary')

      

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
    if st.session_state.chat_history and not st.session_state["clear_screen"] and not st.session_state["home"]:
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
                
                if "目標達成" in reply and not st.session_state["home"] or "ミッション達成" in reply and not st.session_state["home"]:
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

