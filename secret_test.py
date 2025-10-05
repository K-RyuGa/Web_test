import streamlit as st
import streamlit.components.v1 as components
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

    persona_text = "」プレイヤーの言語的課題リスト" + persona
    
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

# --- ヒント生成機能 ---
def generate_hint(hint_type, user_input=None):
    # 現在のゲーム状況をプロンプトに含める
    game_prompt = st.session_state.get("agent_prompt", "")
    conversation_log = "\n".join(st.session_state.chat_history)

    if hint_type == "action":
        hint_instruction = f'''
        You are a Japanese learning support AI.
        Based on the following game situation and conversation history, please generate a very short hint to prompt the player for their next action.

        **[Important] Rules**
        *   The hint must be a concise suggestion for action, like "Let's try..." or "How about asking about...?"
        *   Do not include specific lines or long explanations.
        *   The output should be only the generated hint. No extra greetings or preambles.

        **[Hint Examples]**
        *   "Let's try introducing yourself first!"
        *   "Let's show them your passport!"
        *   "Let's try speaking more politely!"

        **[Game Situation]**
        {game_prompt}

        **[Conversation So Far]**
        {conversation_log}
        '''
        system_content = "You are a kind Japanese language teacher."

    elif hint_type == "word" and user_input:
        hint_instruction = f'''
        You are a Japanese dictionary.
        Please explain the most common meaning of the word ''{user_input}'' that the player asked about, concisely, like a dictionary.
        Do not include extra explanations or example sentences; only output the definition of the meaning.

        **[Output Format Example]**
        *   (Noun) The fundamental, important part of things.
        *   (Verb) To move from one place to another.
        '''
        system_content = "You are a Japanese dictionary."

    else:
        return "Could not generate a hint."


    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": hint_instruction}
        ],
        temperature=0.25,
    )
    return response.choices[0].message.content

def display_evaluation_result(evaluation_result):
    """評価結果のテキストを解析し、整形してStreamlitに表示する（修正版）"""
    try:
        parts = evaluation_result.split('---', 1)
        conversation_part = parts[0]
        scores_part = parts[1] if len(parts) > 1 else ''

        # [正しい][間違い] のパターン（][ の間に任意の空白を許可）
        pair_pattern = r"\[([^\]]+)\]\s*\[([^\]]+)\]"

        for line in conversation_part.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            # 「ユーザー:」または「ユーザー：」で始まる行
            if re.match(r"^ユーザー[:：]", line):
                # コロンの後ろを取り出す（半角・全角のどちらにも対応）
                msg_content = re.split(r"^ユーザー[:：]\s*", line, maxsplit=1)[1]

                # 末尾の理由（全角／半角の丸括弧）を分離
                reason_match = re.search(r"[（(](.+?)[）)]\s*$", msg_content)
                reason = ""
                if reason_match:
                    reason = reason_match.group(1).strip()
                    msg_content = msg_content[:reason_match.start()].strip()

                # [正しい][間違い] のパターンがあるか
                if re.search(pair_pattern, msg_content):
                    # 取り消し線（誤り）を生成
                    def make_wrong(m):
                        return f"<span style='text-decoration: line-through;'>{m.group(2)}</span>"

                    # 修正（正しい表現）を生成
                    def make_correct(m):
                        return f"<span style='color: #0b6623;'>{m.group(1)}</span>"

                    wrong_line_html = re.sub(pair_pattern, make_wrong, msg_content)
                    correct_line_html = re.sub(pair_pattern, make_correct, msg_content)

                    # 表示用HTMLを作成（理由はボックス表示、絵文字は使用しない）
                    formatted = (
                        "<div style='text-align:left; width:100%;'>"
                        f"<div style='margin-bottom:6px; opacity:0.8;'>{wrong_line_html}</div>"
                        f"<div style='margin-bottom:8px;'>{correct_line_html}</div>"
                    )
                    if reason:
                        formatted += (
                            f"<div style='padding:8px; background-color:#f6f6f6; border-radius:4px; "
                            f"font-size:0.9em; color:#555; margin-top:4px;'>"
                            f"{html.escape(reason)}"
                            "</div>"
                        )
                    formatted += "</div>"
                    msg_html = formatted
                else:
                    # [] を含まない通常行：HTMLエスケープして改行を <br> に変換
                    msg_html = html.escape(msg_content).replace("\n", "<br>")

                # ユーザーの吹き出し（右寄せ）
                st.markdown(
                    "<div style='display:flex; justify-content:flex-end; margin:6px 0;'>"
                    "<div style='background-color:#DCF8C6; padding:10px 14px; border-radius:8px; "
                    "max-width:80%; word-wrap:break-word; text-align:left; font-size:15px; color:black;'>"
                    f"{msg_html}"
                    "</div></div>",
                    unsafe_allow_html=True
                )

            # AIの発言（半角／全角コロン対応）
            elif re.match(r"^AI[:：]", line):
                msg_content = re.split(r"^AI[:：]\s*", line, maxsplit=1)[1]
                msg_html = html.escape(msg_content).replace("\n", "<br>")
                st.markdown(
                    "<div style='display:flex; justify-content:flex-start; margin:6px 0;'>"
                    "<div style='background-color:#E6E6EA; padding:10px 14px; border-radius:8px; "
                    "max-width:80%; word-wrap:break-word; text-align:left; font-size:15px; color:black;'>"
                    f"{msg_html}"
                    "</div></div>",
                    unsafe_allow_html=True
                )

            # プレフィックスがない行はそのまま（エスケープして表示）
            else:
                st.markdown(html.escape(line).replace("\n", "<br>"), unsafe_allow_html=True)

        # スコアパートを表示
        if scores_part:
            st.markdown("---")
            st.markdown(scores_part)

    except Exception as e:
        st.warning(f"評価結果の解析に失敗しました: {e}")
        st.markdown(evaluation_result)

# --- 評価＆要約実行関数 ---
def run_post_game_analysis():
    evaluation_prompt = '''あなたは、日本語学習者の会話ログを分析・評価する高性能なAIシステムです。
あなたのタスクは、後続のプログラムが解析しやすいように、極めて厳格なフォーマットに従って評価結果を出力することです。

【最重要ルール】
あなたの出力は、後続のプログラムによって自動的に解析され、HTML/CSSで整形されてユーザーに表示されます。
そのため、これから指示する出力形式のルールを**絶対に、100%厳守**してください。
指定されたフォーマット以外のテキスト（挨拶、前置き、後書き、言い訳、注釈など）は**一切含めないでください**。

以下の【ステップ1】と【ステップ2】を順番に実行してください。

---
**【ステップ1：会話のインライン添削】**

与えられた会話ログを一行ずつ添削します。

**[添削のルール]**
1.  会話ログ全体を、まず一言一句変えずにそのまま出力します。
2.  学習者（「ユーザー:」で始まる行）の発言を精査し、少しでも改善の余地がある場合は、必ず以下の**[添削フォーマット]**に従って添削してください。
3.  間違いのない行、およびAI（「AI:」で始まる行）は、絶対に書き換えず、そのまま出力してください。

**[添削フォーマット]**
*   修正箇所は `[正しい/より良い表現][元の表現]` という形式で必ず書き換えます。
*   修正した行の直後に、括弧 `（）` を使い、修正理由を具体的に説明します。
*   この形式以外のいかなる方法でも添削や説明を行ってはいけません。

**（添削の実行例）**
元の会話：
ユーザー: ピッチャーはしています。週を3かいくらい

あなたの出力（ステップ1）：
ユーザー: [ピッチャーを][ピッチャーは]しています。[週に][週を]3回くらい （助詞の誤りが2つあります。動詞「する」の目的語を示す助詞は「を」が適切です。「週3回」のように頻度を表す場合は、助詞「に」を使います。）

---
**【ステップ2：総合評価】**

ステップ1の完了後、必ず `---` という区切り文字を**一行だけ**出力してください。
その後、以下のフォーマットに**寸分違わず**従って、3つの観点から会話全体を厳格に採点してください。`###`、`**スコア:**`、改行などを完全に維持してください。

**[総合評価の出力フォーマット]**
### 1. 文法と語彙の正確さ
**スコア:** XX/100
（ここに詳細な理由と具体的な改善アドバイスを記述）

### 2. 表現の自然さと適切さ
**スコア:** XX/100
（ここに詳細な理由と具体的な改善アドバイスを記述）

### 3. 会話の論理性と流暢さ
**スコア:** XX/100
（ここに詳細な理由と具体的な改善アドバイスを記述）

【採点基準】
*   90～100点（ほぼ完璧）: ネイティブスピーカーと遜色ないレベル。
*   70～89点（良い）: 細かい癖や不自然さはあるが、コミュニケーションは円滑。
*   40～69点（要改善）: 明確な誤りが散見され、意味の推測が必要な場面がある。
*   0～39点（大きな課題あり）: コミュニケーションに支障をきたすレベルの誤りが多数ある。
*   採点は非常に厳しく行ってください。安易に高得点を与えないでください。
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

    # --- 評価を生成 ---
    scenario_title = st.session_state.style_label
    # chapter_descriptions はグローバルスコープにある想定
    scenario_description = chapter_descriptions.get(scenario_title, "")
    eval_user_content = f"""**[評価対象の状況]**\nシナリオ: {scenario_title}\n状況設定: {scenario_description}\n\n**[会話ログ]**\n{conversation_log}"""

    evaluation_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": evaluation_prompt},
            {"role": "user", "content": eval_user_content}
        ],
        temperature=0.25,
    )
    evaluation_result = evaluation_response.choices[0].message.content

    # --- 結果をパースして表示 ---
    st.markdown("### Conversation Evaluation")
    display_evaluation_result(evaluation_result)

    # --- 結果をDBに記録 ---
    now_str = datetime.now(JST).strftime('%Y/%m/%d %H:%M\n')
    record_message(st.session_state.username, st.session_state["style_label"] + " " + now_str + evaluation_result, "eval")

    # --- 行動履歴の要約を生成して記録 ---
    summary_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": conversation_log}
        ],
        temperature=0.25,
    )
    summary_result = summary_response.choices[0].message.content
    record_message(st.session_state.username, summary_result, 'player_summary')




# --- セッション管理初期化 ---
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("username", "")
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("show_history", False)
st.session_state.setdefault("clear_screen",False)
st.session_state.setdefault("Failed_screen",False)
st.session_state.setdefault("home",True)
st.session_state.setdefault("chat",False)
st.session_state.setdefault("first_session",True)
st.session_state.setdefault("style_label", "ホーム") # 初期値を設定
st.session_state.setdefault("eval",False)
st.session_state.setdefault("hint_mode", "chat") # ヒント機能のモード管理（chat, select, ask_word, show_hint）
st.session_state.setdefault("hint_message", "") # 表示するヒントメッセージ

# --- ログイン前のUI ---
if not st.session_state.logged_in:
    st.title("ログイン / 新規登録")
    mode = st.radio("モードを選択", ["ログイン", "新規登録"])

    with st.form(key='login_form'):
        username = st.text_input("ユーザー名")
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("送信")

        if submitted:
            if mode == "新規登録":
                if register_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.home = True
                    st.session_state.chat = False
                    st.session_state.clear_screen = False
                    st.session_state.Failed_screen = False
                    st.rerun()
                else:
                    st.error("そのユーザー名は既に使われています。")
            else:
                if check_password(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.chat_history = []
                    st.session_state.home = True
                    st.session_state.chat = False
                    st.session_state.clear_screen = False
                    st.session_state.Failed_screen = False
                    st.rerun()
                else:
                    st.error("ユーザー名またはパスワードが間違っています。")
                            
# --- ログイン後のUI ---
if st.session_state.logged_in:
    def on_selectbox_change():
        # selectbox のキーから現在の選択値を取得し、style_label を更新
        st.session_state.style_label = st.session_state.selectbox_style

        # 状態のリセット
        st.session_state.chat_history = [] 
        st.session_state.first_session = True 
        st.session_state.clear_screen = False
        st.session_state.Failed_screen = False

        # ホームかチャットかを判断
        if st.session_state.style_label == "ホーム":
            st.session_state.home = True
            st.session_state.chat = False
        else:
            st.session_state.home = False
            st.session_state.chat = True
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
            あなたは、プレイヤーがミッションを達成できるように、会話を積極的に誘導してください。
            もしプレイヤーの言葉遣いがTPO（時・場所・場面）に合っていなかったり、不自然だったり、無礼だったりした場合、あるいは、会話の自然なステップ（例えば、自己紹介や世間話など）を飛ばして、いきなり最終目的（例：「次に会う約束」）を達成しようとした場合、あなたは安易に「ミッション達成」を許可してはいけません。

            その際は、あなたのキャラクターとして最も自然な反応を返してください。例えば、以下のような対応です。
            ・相手の意図が分からず、困惑する。
            ・丁寧だが、はっきりと要求を断る。（例：「申し訳ありませんが、まだお互いのことをよく知らないので…」）
            ・「どういうことですか？」と、相手の真意を確かめる質問をする。

            【「ミッション失敗」の条件】
            以下の状況では、会話を打ち切り「ミッション失敗」と出力してください。
            *   プレイヤーがキャラクターの指示に全く従わない場合。（例：パスポートの提示を求めているのに、3回連続で無関係な話をする）
            *   会話の文脈と全く関係のない発言を繰り返す場合。
            *   著しく無礼な態度を取り、キャラクターが会話の継続を困難だと感じた場合。

            プレイヤーが適切なコミュニケーションを段階的に取って初めて、ミッションが達成されるように会話を導いてください。

            テンポの良い、短めのフレーズで会話を進め、自然な流れを意識してください。プレイヤーが質問しやすいように工夫しながら、リアクションを交え、実際の生活のような自然な会話をしてください。
            何を言われても、与えられた役を演じ続けてください。

            今回は、以下の役を演じてください。
        '''

        end_prompt = '''
            「ミッション達成」はゲームクリアの合言葉です。プレイヤーがミッションを達成した場合、**必ず**「ミッション達成」と出力してください。その際、**他の余計な会話は一切含めないでください。** それまでは、プレイヤーがミッションを達成するための行動を促し続けてください。
            逆に、プレイヤーの言動が著しく不適切であったり、会話が完全に破綻してしまったりした場合は、「ミッション失敗」と出力してください。
            それではゲームスタートです。プレイヤーに話しかけてください。
        '''

        story_prompt = [
            [ # Chapter 1
                '''
                [あなたの役割]
                あなたは空港の係員です。到着したばかりのプレイヤーに、入国手続きの案内をしてください。

                [ミッション達成の条件]
                プレイヤーが「入国目的」「滞在期間」「宿泊先」など、入国カードに必要な情報を正しく伝えられたら達成。

                [最初の行動]
                「こんにちは。日本へようこそ。入国手続きのご案内をしますので、パスポートをご提示いただけますか？」と話しかけてください。
                '''
            ],
            [ # Chapter 2
                '''
                [あなたの役割]
                あなたはスーパーの店員です。プレイヤーに話しかけられたので、応対してください。

                [ミッション達成の条件]
                プレイヤーが探している商品の場所などについて質問し、あなたの説明をプレイヤーが理解したことを示す応答（例：「わかりました、ありがとうございます」）をすること。

                [最初の行動]
                「いらっしゃいませ、どうされましたか？」と話しかけてください。
                '''
            ],
            [ # Chapter 3
                '''
                [あなたの役割]
                あなたはプレイヤーの新しい友人です。お互いのことをもっと知るために、趣味や週末の予定について話してください。

                [ミッション達成の条件]
                次に会う約束を取り付けること。

                [最初の行動]
                「来てくれてありがとう！このカフェ、雰囲気が良くて好きなんだ。週末はいつも何をして過ごしているの？」と話しかけてください。
                '''
            ],
            [ # Chapter 4
                '''
                [あなたの役割]
                あなたはプレイヤーの同僚です。緊張している様子のプレイヤーに、フレンドリーに自己紹介をしてください。

                [ミッション達成の条件]
                プレイヤーが「名前」「出身」「担当業務」などを含めた自己紹介を行い、同僚と良い印象のやり取りができたら達成。

                [最初の行動]
                「はじめまして！今日から一緒に働くことになった田中です。よろしくお願いします。緊張しますよね。少しずつ慣れていけば大丈夫ですよ。」と話しかけてください。
                '''
            ],
            [ # Chapter 5
                '''
                [あなたの役割]
                あなたは医師です。プレイヤーの症状を正確に把握するため、丁寧に問診を進めてください。

                [ミッション達成の条件]
                プレイヤーが「症状の部位」「痛みの程度」「発症時期」などを日本語で説明できたら達成。

                [最初の行動]
                「こんにちは。今日はどうされましたか？どこか具合が悪いところがあれば、詳しく教えてください。」と話しかけてください。
                '''
            ],
            [ # Chapter 6
                '''
                [あなたの役割]
                あなたはプレイヤーの同僚です。プレイヤーが会議で意見を述べやすいように、サポートしてください。

                [ミッション達成の条件]
                プレイヤーが会議中に自分の意見を一度以上発言し、相手と簡単な意見交換ができたら達成。

                [最初の行動]
                「この件についてどう思いますか？ぜひ意見を聞かせてください。」と話しかけてください。
                '''
            ],
            [ # Chapter 7
                '''
                [あなたの役割]
                あなたはプレイヤーの友人です。今度行われる夏祭りについて話し、一緒に行こうと誘ってください。

                [ミッション達成の条件]
                プレイヤーがお祭りに興味を示し、あなたと一緒に行く約束をすること。

                [会話の進め方]
                1. まず「ねえ、今週末、近くの神社で夏祭りがあるんだけど、一緒に行かない？日本の夏祭り、体験したことある？」と話しかけてください。
                2. プレイヤーの返答に応じて、以下のように対応を変えてください。
                   - **知らない場合:** プレイヤーがお祭りを知らない様子であれば、屋台の食べ物や盆踊りなど、お祭りがどんなものか楽しく説明してあげてください。
                   - **知っている場合:** プレイヤーが既にお祭りを知っている、または行ったことがある様子であれば、「本当！じゃあ話が早いね！」「何が一番楽しかった？」のように、基本的な説明は省略し、経験を共有する会話に発展させてください。
                3. 最終的に、どちらの会話からでも「今度の土曜日、一緒に行こうよ」と誘い、約束を取り付けてください。
                '''
            ],
            [ # Chapter 8
                '''
                [あなたの役割]
                あなたは市役所の窓口担当者です。プレイヤーが必要な手続きをスムーズに進められるように、分かりやすく説明してください。

                [ミッション達成の条件]
                プレイヤーが「手続き内容（例：住所変更、在留カード更新など）」を説明し、必要な書類や手順を理解できたら達成。

                [最初の行動]
                「こんにちは。本日はどのようなご用件でしょうか？」と話しかけてください。
                '''
            ],
            [ # Chapter 9
                '''
                [あなたの役割]
                あなたは駅員です。電車の遅延で困っているプレイヤーに、状況を説明し、代替案を提案してください。

                [ミッション達成の条件]
                プレイヤーが「目的地」や「予定時刻」を伝え、駅員の案内に沿って代替手段を理解・選択できたら達成。

                [最初の行動]
                「申し訳ございません、ただいま人身事故の影響で、運転を見合わせております。お急ぎのところ大変恐縮ですが、復旧までしばらくお待ちいただくか、バスなどの代替交通機関をご利用ください。」と話しかけてください。
                '''
            ]
        ]

        # Game.pyのstoriesを元に、selectboxの選択肢を定義
        stories = [
            "ホーム", # ホーム画面用
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
        current_style_in_session = st.session_state.get("style_label", "ホーム")

        # 2. selectboxの現在のインデックスを計算
        try:
            current_index = stories.index(current_style_in_session)
        except ValueError:
            current_index = 0 # 万が一見つからない場合はデフォルト

        # 3. セレクトボックスを描画し、変更時にコールバックを呼び出す
        st.selectbox(
            "シチュエーション選択", 
            stories, 
            index=current_index, 
            key="selectbox_style",
            on_change=on_selectbox_change
        )
        
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
                

                
        if not st.session_state["home"]:
            if st.button("🔙 HOMEに戻る"):
        
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
            st.session_state["Failed_screen"] = False
            st.session_state["chat"] = False
            st.session_state["first_session"] = True
            st.session_state["eval"] = False
            st.session_state.username = ""
            #st.session_state["username"] = False
            st.session_state.chat_history = []
            st.session_state["style_label"] = "ホーム"
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
        """, unsafe_allow_html=True)
     
        st.info("まずは左のサイドバーから、練習したいシチュエーションを選んでみましょう！")
        # st.markdown("### 💬 質問がある場合")
        # st.write("画面下のチャット欄に質問を入力してください。できる限り丁寧にお答えします。")
        

        
    # --- 説明文定義 ---
    chapter_descriptions = {
        "Chapter 1: 空港での手続き": "ここは東京国際空港の到着ロビー。長旅の疲れを感じながらも、あなたは「到着」のゲートをくぐり抜けた。目の前には、きびきびと働く空港の係員が立っている。\n\n---\n\n**今回のミッション：**「入国目的」「滞在期間」「宿泊先」を正しく伝えましょう。",
        "Chapter 2: スーパーでの買い物": "あなたはスーパーで買い物をしています。何か作りたい料理（例えばカレーや肉じゃが）を心に思い浮かべて、それを作るのに必要な材料がどこにあるか、店員さんに質問してみましょう。\n\n---\n\n**今回のミッション：** 探している商品の場所を店員に質問し、説明を理解しましょう。",
        "Chapter 3: 友人との会話": "あなたは、最近知り合った友人とカフェで会っている。窓の外には公園の緑が広がり、店内には落ち着いた音楽が流れている。\n\n---\n\n**今回のミッション：** 会話を楽しみ、次に会う約束を取り付けましょう。",
        "Chapter 4: 職場の自己紹介": "今日からあなたは新しい職場で働くことになった。オフィスに足を踏み入れると、一人の同僚があなたに気づき、笑顔で近づいてきた。\n\n---\n\n**今回のミッション：**「名前」「出身」「担当業務」を伝えて自己紹介をしましょう。",
        "Chapter 5: 病院での診察": "あなたは体調が悪く、近所の病院に来ている。待合室でしばらく待っていると、看護師に呼ばれ、診察室に入った。中では、白衣を着た医師があなたを待っている。\n\n---\n\n**今回のミッション：**「症状の部位」「痛みの程度」「発症時期」を詳しく説明しましょう。",
        "Chapter 6: 会議での発言": "あなたは職場の会議に参加している。会議が進行する中、上司があなたの意見を求めてきた。周りの同僚たちが、あなたに注目している。\n\n---\n\n**今回のミッション：** 会議の議題について、あなたの意見を一度以上発言しましょう。",
        "Chapter 7: お祭りに参加": "あなたは友人と話しています。友人が、今週末に行われる夏祭りに誘ってくれるようです。友人の話を聞いて、お祭りに興味が湧いたら、一緒に行く約束をしてみましょう。\n\n---\n\n**今回のミッション：** 友人の話を聞いてお祭りの内容を理解し、一緒に行く約束をしましょう。",
        "Chapter 8: 市役所での手続き": "あなたは行政手続きのため、市役所の窓口に来ている。番号札を持って待っていると、自分の番号が呼ばれた。あなたは少し緊張しながら、指定された窓口へ向かう。\n\n---\n\n**今回のミッション：**「手続き内容」を説明し、必要な書類や手順を理解しましょう。",
        "Chapter 9: 電車の遅延対応": "あなたは駅のホームで電車を待っているが、予定の時間を過ぎても電車が来る気配がない。電光掲示板には「遅延」の文字が表示されている。\n\n---\n\n**今回のミッション：**「目的地」と「予定時刻」を伝え、駅員の案内に沿って代替手段を理解・選択しましょう。",
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
            st.session_state.agent_prompt = final_system_prompt #役割を記憶させる
            # --- ★動的プロンプト生成ここまで --- #

            # AIが最初の発言をする
            messages = [
                {"role": "system", "content": final_system_prompt}
            ]
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0, # 最初の発言は固定なので、ランダム性をなくす
            )
            reply = response.choices[0].message.content
            
            st.session_state.chat_history.append(f"AI: {reply}")
            st.session_state.first_session = False # AIが話したので、次はユーザーの番

            now = datetime.now(JST).strftime('%Y/%m/%d %H:%M')            
            full_message = st.session_state["style_label"] + " " + now + "\n" + f"AI: {reply}"
            record_message(st.session_state.username, full_message, "message")
            
    if st.session_state["clear_screen"]:
        st.success("ミッション達成！おめでとうございます！")
        run_post_game_analysis()
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
    if st.session_state.chat_history and not st.session_state["clear_screen"] and not st.session_state["home"] and not st.session_state["Failed_screen"]:
        for msg in st.session_state.chat_history:
            if msg.startswith("ユーザー:"):
                # ユーザー → 右寄せ（グリーン）
                st.markdown(
                    f"""
                    <div style='display: flex; justify-content: flex-end; margin: 4px 0'>
                        <div style='background-color: #DCF8C6; padding: 8px 12px; border-radius: 8px; max-width: 80%; word-wrap: break-word; text-align: left; font-size: 16px; color:black;'>
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
                        <div style='background-color: #E6E6EA; padding: 8px 12px; border-radius: 8px; max-width: 80%; word-wrap: break-word; text-align: left; font-size: 16px; color:black;'>
                            {msg.replace("AI:", "")}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


    # --- 入力フォーム ---
    if st.session_state["chat"] and not st.session_state.first_session:
        # --- ヒントメッセージがセッションにあれば表示し、その後クリアする ---
        if st.session_state.get("hint_message"):
            st.info(st.session_state.hint_message)
            st.session_state.hint_message = ""

        # --- ヒント選択画面 ---
        if st.session_state.hint_mode == "select":
            st.markdown("What kind of hint do you need?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Look up word meaning", use_container_width=True):
                    st.session_state.hint_mode = "ask_word"
                    st.rerun()
            with col2:
                if st.button("Hint for next action", use_container_width=True):
                    hint = generate_hint("action")
                    st.session_state.hint_message = hint
                    st.session_state.hint_mode = "chat" # ヒント生成後はチャットモードに戻す
                    st.rerun()

        # --- 単語質問画面 ---
        elif st.session_state.hint_mode == "ask_word":
            with st.form(key="word_hint_form", clear_on_submit=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    word_to_ask = st.text_input("Enter the word you want to look up", label_visibility="collapsed", placeholder="Enter the word you want to look up")
                with col2:
                    submit_word = st.form_submit_button("Submit", use_container_width=True)

            if submit_word and word_to_ask:
                hint = generate_hint("word", word_to_ask)
                st.session_state.hint_message = hint
                st.session_state.hint_mode = "chat"  # ヒント生成後はチャットモードに戻す
                st.rerun()

        # --- 通常のチャット入力フォーム ---
        elif st.session_state.hint_mode == "chat":
            with st.form(key="chat_form", clear_on_submit=True, border=False):
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    user_input = st.text_input("あなたのメッセージを入力してください", key="input_msg", label_visibility="collapsed", placeholder="メッセージを入力...")
                with col2:
                    submit_button = st.form_submit_button("送信", use_container_width=True)
                with col3:
                    if st.form_submit_button("💡 Hint", use_container_width=True):
                        st.session_state.hint_mode = "select"
                        st.rerun()
            
            # オートフォーカス用のJavaScript
            components.html(
                """
                <script>
                    var input = parent.document.querySelector('input[aria-label="あなたのメッセージを入力してください"]');
                    if (input) {
                        setTimeout(function() {
                            input.focus();
                        }, 0);
                    }
                </script>
                """,
                height=0
            )

            if submit_button and user_input.strip():
                # (既存の送信処理)
                client = OpenAI(api_key=st.secrets["openai"]["api_key"])
                system_prompt = st.session_state.get("agent_prompt", "あなたは親切な日本語学習の先生です。")
                messages = [{"role": "system", "content": system_prompt}]
                for msg in st.session_state.get("chat_history", []):
                    if msg.startswith("ユーザー:"):
                        messages.append({"role": "user", "content": msg.replace("ユーザー:", "").strip()})
                    elif msg.startswith("AI:"):
                        messages.append({"role": "assistant", "content": msg.replace("AI:", "").strip()})
                messages.append({"role": "user", "content": user_input})
                response = client.chat.completions.create(model="gpt-4o", messages=messages, temperature=0.25)
                reply = response.choices[0].message.content
                st.session_state.chat_history.append(f"ユーザー: {user_input}")
                st.session_state.chat_history.append(f"AI: {reply}")
                full_message = f"ユーザー: {user_input}\nAI: {reply}"
                record_message(st.session_state.username, full_message,"message")
                
                if "ミッション達成" in reply:
                    st.session_state.clear_screen = True
                    st.session_state.chat = False
                elif "ミッション失敗" in reply:
                    st.session_state.Failed_screen = True
                    st.session_state.chat = False
                st.rerun()
            
            
        
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
                                        <div style='background-color: #DCF8C6; padding: 8px 12px; border-radius: 8px; max-width: 80%; word-wrap: break-word; text-align: left; font-size: 16px; color:black;'>
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
                                        <div style='background-color: #E6E6EA; padding: 8px 12px; border-radius: 8px; max-width: 80%; word-wrap: break-word; text-align: left; font-size: 16px; color:black;'>
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
                display_evaluation_result(selected_body)
    
    elif st.session_state.Failed_screen:
        st.error("ミッション失敗...")
        run_post_game_analysis()
        # 「もう一度やる」ボタン
        if st.button("🔁 最初からやり直す"):
            st.session_state.chat_history = []
            st.session_state["clear_screen"] = False
            st.session_state["Failed_screen"] = False
            st.session_state["show_history"] = False
            st.session_state["home"] = False
            st.session_state["logged_in"] = True
            st.session_state["chat"] = True
            st.session_state["first_session"] = True
            st.rerun()