import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
import gspread
from google.oauth2.service_account import Credentials
import time
import re
from datetime import datetime, timezone, timedelta

# --- UTC timezone setting ---
UTC = timezone.utc

# --- Google Sheets Authentication ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
gs_client = gspread.authorize(credentials)
sheet = gs_client.open("UserData").sheet1 # Assuming the same sheet is used for user data

# --- Check if user exists ---
def user_exists(username):
    users = sheet.col_values(1)
    return username in users

# --- Check if password matches ---
def check_password(username, password):
    users = sheet.get_all_records()
    for user in users:
        if user["username"] == username and user["password"] == password:
            return True
    return False

# --- Register new user ---
def register_user(username, password):
    if user_exists(username):
        return False
    # Add a row with 5 columns to match the header
    sheet.append_row([username, password, "", "", ""])
    return True

# --- Append message ---
def record_message(username, new_message, where):
    all_users = sheet.get_all_records()
    # Manage column mapping with a dictionary
    col_map = {"message": 3, "eval": 4, "player_summary": 5}
    col_index = col_map.get(where)
    if not col_index:
        return # Do nothing if the target column doesn't exist

    for i, user in enumerate(all_users, start=2):
        if user["username"] == username:
            # For player_summary, always overwrite with new content
            if where == 'player_summary':
                combined = new_message
            else: # For message and eval, append as before
                old_message = user.get(where, "")
                combined = old_message + "\n" + new_message if old_message else new_message
            
            sheet.update_cell(i, col_index, combined)
            break

# --- Load message history ---
def load_message(username, item):
    all_users = sheet.get_all_records()
    for user in all_users:
        if user["username"] == username:
            return user.get(item, "")
    return ""

# --- Dynamic Prompt Generation ---
def make_new_prompt(username, base_prompt_text, selected_prompt_text):
    making_prompt = '''
        You are responsible for the **dynamic prompt generation feature** of an "English Language Learning Support Game" that I am creating.
        This game aims to help non-native English speakers improve their English skills through realistic conversations while simulating life in the United States.
        Your role is to generate optimized conversation scenarios (prompts) for each player based on their past conversation history and a list of their linguistic challenges.

        Below, you are given a base prompt and a list of the player's linguistic challenges. Use these to improve the base prompt into a more natural and high-quality one that maximizes the learning effect.
        However, you must not reduce the specific actions (missions) defined in the original prompt.
        Your output should only be the completed prompt, without any extra text.

        Base Prompt:
        "
    '''
    making_prompt_end = '''
        "
        The "List of Player's Linguistic Challenges" provided to you is a bulleted list of the player's linguistic and communication strategy issues.

        Your task is to **naturally integrate situations optimal for overcoming each challenge** from the list into the base prompt's scenario.

        【Examples of Prompt Generation】
        *   If the challenge list includes "unnatural use of articles 'a/an/the'," have the character ask questions where the meaning is unclear without specifying the subject.
        *   If the challenge list includes "requests are too direct," have the character show a slightly confused reaction, forcing the player to try more polite phrasing (e.g., "Could you please...? ").
        *   If the challenge list includes "word choice errors (e.g., 'tell' vs. 'say')," intentionally create a scene where both words are contextually usable but have different nuances.

        【IMPORTANT】Notes
        *   **Do not explicitly demand** the player to overcome the challenge. Instructions like "Please use the article 'the'" are forbidden. Design a situation where the player is naturally compelled to use the correct expression in a conversation.
        *   Do not fixate on the player's specific past mistakes; instead, encourage the resolution of the underlying fundamental issues.
        *   The game content must not become unnatural. Also, be careful with the phrase "Mission Accomplished" as it is a keyword for clearing the game.
    '''
    
    # Load player summary data from Google Spreadsheet
    persona = load_message(username, "player_summary")
    if not persona:
        # If there is no summary data, return the original prompt without personalization
        return base_prompt_text + selected_prompt_text

    persona_text = "\"List of Player's Linguistic Challenges" + persona
    
    # API call for dynamic prompt generation
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

# --- Hint Generation Function ---
def generate_hint(hint_type, user_input=None):
    # Include current game situation in the prompt
    game_prompt = st.session_state.get("agent_prompt", "")
    conversation_log = "\n".join(st.session_state.chat_history)

    if hint_type == "action":
        hint_instruction = f"""
        あなたは日本語学習支援AIです。
        以下のゲーム状況と会話履歴に基づき、プレイヤーの次の行動を促すための非常に短いヒントを生成してください。

        **[重要] ルール**
        *   ヒントは「〜してみましょう」や「〜について尋ねてみてはどうですか？」のような、行動を促す簡潔な提案である必要があります。
        *   具体的なセリフや長い説明を含めないでください。
        *   出力は生成されたヒントのみにしてください。余計な挨拶や前置きは含めないでください。

        **[ヒントの例]**
        *   「まずは自己紹介をしてみましょう！」
        *   「パスポートを見せてみましょう！」
        *   「もっと丁寧に話してみましょう！」

        **[ゲーム状況]**
        {game_prompt}

        **[これまでの会話]**
        {conversation_log}
        """
        system_content = "あなたは親切な日本語教師です。"

    elif hint_type == "word" and user_input:
        hint_instruction = f"""
        あなたは日本語辞書です。
        プレイヤーが尋ねた単語「{user_input}」の最も一般的な意味を、辞書のように簡潔に説明してください。
        余計な説明や例文を含めず、意味の定義のみを出力してください。

        **[出力形式の例]**
        *   (名詞) 物事の根本となる、重要な部分。
        *   (動詞) ある場所から別の場所へ移動すること。
        """
        system_content = "あなたは日本語辞書です。"

    else:
        return "ヒントを生成できませんでした。"


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

# --- Session State Initialization ---
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("username", "")
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("show_history", False)
st.session_state.setdefault("clear_screen", False)
st.session_state.setdefault("home", True)
st.session_state.setdefault("chat", False)
st.session_state.setdefault("first_session", True)
st.session_state.setdefault("style_label", "Select Situation") # Set initial value
st.session_state.setdefault("eval", False)
st.session_state.setdefault("hint_mode", "chat") # Hint mode management (chat, select, ask_word, show_hint)
st.session_state.setdefault("hint_message", "") # Hint message to display
st.session_state.setdefault("Failed_screen",False)

# --- UI Before Login ---
if not st.session_state.logged_in:
    st.title("Login / Register")
    mode = st.radio("Select Mode", ["Login", "Register"])

    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Submit")

        if submitted:
            if mode == "Register":
                if register_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.clear_screen = False
                    st.rerun()
                else:
                    st.error("That username is already taken.")
            else:
                if check_password(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.chat_history = []
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")
                            
# --- UI After Login ---
if st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🇺🇸 EngliGO❕</h1>", unsafe_allow_html=True)
    
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
        st.title("OPTIONS")

        # --- Prompt settings ---
        base_prompt = '''
            You will role-play a character in an "English Language Learning Support Game" that I am creating.
            This game aims to help non-native English speakers improve their English skills through realistic conversations while simulating life in the United States.
            The player will interact with characters in various situations, experiencing life in the U.S. vicariously while learning vocabulary, grammar, and natural expressions.

            【IMPORTANT】Conversation Principles
            Your most important role is not just to be a helpful guide, but to simulate realistic American conversations.
            If the player's language is not appropriate for the TPO (Time, Place, Occasion), is unnatural, or rude, or if they try to achieve the final objective (e.g., "making the next appointment") by skipping natural conversation steps (like introductions or small talk), you must not easily allow them to achieve the "mission."

            In such cases, respond in the most natural way for your character. For example:
            ・Be confused because you don't understand their intention.
            ・Politely but firmly decline the request. (e.g., "I'm sorry, but we don't know each other well enough for that...")
            ・Ask for clarification. (e.g., "What do you mean by that?")

            Guide the conversation so that the mission is achieved only after the player engages in appropriate, step-by-step communication.

            Keep the conversation moving with short, snappy phrases and maintain a natural flow. Use reactions and try to make the conversation feel real, making it easy for the player to ask questions.
            Continue playing your assigned role no matter what is said.

            This time, please play the following role.
        '''

        end_prompt = '''
            "Mission Accomplished" is the keyword for clearing the game. If the player achieves the mission, you **must** output "Mission Accomplished". At that time, **do not include any other unnecessary conversation.** Until then, continue to encourage the player to take actions to achieve the mission.
            Conversely, if the player's words and actions are significantly inappropriate, or if the conversation completely breaks down, output "Mission Failed".
            Now, let the game begin. Please start talking to the player.
        '''

        story_prompt = [
            [
                '''
                As an airport staff member, guide the player through immigration procedures and ask for their passport. Also, tell them where to pick up their luggage.

                Specific actions are as follows:
                1. "Ask the player to present their passport."
                2. Explain the immigration process.
                3. Guide them to the baggage claim area, confirm they understand, and if so, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a cashier at a supermarket, handle the player's checkout process.

                Specific actions are as follows:
                1. "Call the player over with \"I can help the next person in line.\""
                2. Process the purchased items and tell them the total amount.
                3. Answer any questions about payment methods.
                4. Once the player completes the payment, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a new friend, introduce yourself to the player and chat about each other's hobbies and plans.

                Specific actions are as follows:
                1. "Introduce yourself and encourage the player to do the same."
                2. Ask questions about the player's hobbies and interests.
                3. Suggest a date to meet next, and if the player agrees, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a colleague at work, introduce yourself to the player and enjoy a first-time conversation at the workplace.

                Specific actions are as follows:
                1. "Introduce yourself and encourage the player to do the same."
                2. Make small talk about the job to help the player relax.
                3. Once the player successfully introduces themselves, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a doctor at a hospital, listen to the player's symptoms and proceed with the examination.

                Specific actions are as follows:
                1. "Ask the player about their symptoms and ask follow-up questions."
                2. Conduct an examination and provide an appropriate diagnosis.
                3. Once the player successfully completes the examination, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a colleague at work, support the player in speaking up during a meeting and provide feedback.

                Specific actions are as follows:
                1. "Ask for the player's opinion and give them a chance to speak."
                2. Provide feedback on the player's opinion to advance the discussion.
                3. Once the player successfully states their opinion and moves the discussion forward, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a friend, invite the player to an American festival (e.g., a 4th of July BBQ) and explain the etiquette and cultural background.

                Specific actions are as follows:
                1. "Invite the player to the event and explain what it is."
                2. Teach them about cultural etiquette and customs.
                3. Once the player successfully participates and enjoys the event, output "Mission Accomplished".
                ''' 
            ],
            [
                '''
                As a clerk at the DMV, support the player in submitting necessary documents and explain the procedures.

                Specific actions are as follows:
                1. "Ask the player what documents they need to submit."
                2. Explain the steps of the procedure and assist if the player is confused.
                3. Once the player successfully completes the procedure, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a transit employee, help the player by giving appropriate instructions when their train is delayed.

                Specific actions are as follows:
                1. "Explain the train delay and suggest the next course of action."
                2. Clearly answer the player's questions.
                3. Once the player successfully finds a solution, output "Mission Accomplished".
                '''
            ]
        ]

        stories = [
            "Select Situation", # For home screen
            "Chapter 1: Airport Procedures",
            "Chapter 2: Grocery Shopping",
            "Chapter 3: Conversation with a Friend",
            "Chapter 4: Workplace Introduction",
            "Chapter 5: Doctor's Visit",
            "Chapter 6: Speaking in a Meeting",
            "Chapter 7: Attending a Festival",
            "Chapter 8: DMV Procedures",
            "Chapter 9: Handling a Train Delay",
        ]
        
        current_style_in_session = st.session_state.get("style_label", "Select Situation")

        try:
            current_index = stories.index(current_style_in_session)
        except ValueError:
            current_index = 0

        selected_style = st.selectbox("Select Situation", stories, index=current_index, key="selectbox_style")

        if selected_style != current_style_in_session:
            st.session_state.style_label = selected_style
            
            st.session_state.chat_history = [] 
            st.session_state.first_session = True 
            st.session_state.clear_screen = False
            
            if selected_style == "Select Situation":
                st.session_state.home = True
                st.session_state.chat = False
            else:
                st.session_state.home = False
                st.session_state.chat = True
            
            st.rerun()
        
        st.markdown("---")

        if "show_history" not in st.session_state:
            st.session_state["show_history"] = False

        if not st.session_state["show_history"]:
            if st.button("💬 View Chat History"):
                st.session_state["show_history"] = True
                st.session_state["home"] = False
                st.session_state["logged_in"] = True
                st.session_state["chat_history"] = []
                st.session_state["clear_screen"] = False
                st.session_state["chat"] = False
                st.session_state["eval"] = False
                st.rerun()
                
        if not st.session_state["eval"]:
            if st.button("🎩 View Past Feedback"):
                st.session_state["show_history"] = False
                st.session_state["home"] = False
                st.session_state["logged_in"] = True
                st.session_state["chat_history"] = []
                st.session_state["clear_screen"] = False
                st.session_state["chat"] = False
                st.session_state["eval"] = True
                st.rerun()
                
        if not st.session_state["style_label"] == "Select Situation" and not st.session_state["show_history"] and not st.session_state["eval"]:
            if st.button("🔙 Back to Home"):
                st.session_state.home = True
                st.session_state.chat = False
                st.session_state.clear_screen = False
                st.session_state.style_label = "Select Situation"
                st.rerun()
                
        else:
            if not st.session_state["home"]:
                if st.button("🔙 Back to Chat"):
                    st.session_state["show_history"] = False
                    st.session_state["home"] = True
                    st.session_state["logged_in"] = True
                    st.session_state["chat_history"] = []
                    st.session_state["clear_screen"] = False
                    st.session_state["chat"] = False
                    st.session_state["eval"] = False
                    st.rerun()

        if st.button("🚪 Logout"):
            st.session_state["show_history"] = False
            st.session_state["home"] = True
            st.session_state["logged_in"] = False
            st.session_state["clear_screen"] = False
            st.session_state["chat"] = False
            st.session_state["first_session"] = True
            st.session_state["eval"] = False
            st.session_state.username = ""
            st.session_state.chat_history = []
            st.session_state["style_label"] = "Select Situation"
            st.rerun()

    if st.session_state["home"]:
        st.title("Home Screen")
        st.subheader("🎮 Welcome to the English Learning Simulation Game!")
        st.write("In this game, you can practice natural English conversation through various situations in the United States.")
        st.markdown("### 🧭 How to Play")
        st.markdown("- Select a situation you want to practice from the **sidebar** on the left.")
        st.markdown("### 📌 Game Features")
        st.markdown('''
        - Practice realistic conversation with an AI.
        - The story changes based on your conversation style.
        - Receive feedback even if you make mistakes.
        ''')
        st.info("First, let's choose a situation you want to practice from the sidebar on the left!")
        
        if st.session_state["style_label"] != "Select Situation":
            st.session_state["home"] = False
            st.session_state["chat"] = True
            st.rerun()
        
    chapter_descriptions = {
        "Chapter 1: Airport Procedures": "You've arrived in the USA! Follow the airport staff's instructions to get through immigration. **Goal: Understand where to pick up your luggage.**",
        "Chapter 2: Grocery Shopping": "You're shopping at a supermarket. Follow the cashier's instructions to check out. **Goal: State your payment method and complete the purchase.**",
        "Chapter 3: Conversation with a Friend": "You're hitting it off with a new friend. Talk about hobbies and get to know each other. **Goal: Make plans to meet up again.**",
        "Chapter 4: Workplace Introduction": "Introduce yourself to a colleague at your new job. Enjoy a friendly conversation. **Goal: Introduce yourself politely and successfully.**",
        "Chapter 5: Doctor's Visit": "You're at the doctor's office. Explain your symptoms to the doctor. **Goal: Accurately describe your symptoms and complete the visit.**",
        "Chapter 6: Speaking in a Meeting": "You're in a work meeting. A colleague asks for your opinion. **Goal: Share your thoughts clearly and contribute to the discussion.**",
        "Chapter 7: Attending a Festival": "You're at an American festival with a friend. Learn about the culture and etiquette. **Goal: Enjoy the conversation and show you're having a good time.**",
        "Chapter 8: DMV Procedures": "You're at the DMV to handle some paperwork. Listen carefully to the clerk's instructions. **Goal: Follow the instructions and complete the necessary procedure.**",
        "Chapter 9: Handling a Train Delay": "Your train is delayed. Ask a transit employee for information. **Goal: Understand the employee's instructions and decide on your next action.**",
    }

    if st.session_state.chat:
        description = chapter_descriptions.get(st.session_state.style_label, "")
        if description:
            st.info(description)

    if not st.session_state["home"] and not st.session_state["show_history"] and not st.session_state["eval"]:
        if st.session_state.first_session and st.session_state.chat:
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])

            chapter_index = stories.index(st.session_state.style_label) - 1
            selected_story_prompt = story_prompt[chapter_index][0]
            
            personalized_prompt = make_new_prompt(
                st.session_state.username, 
                base_prompt, 
                selected_story_prompt
            )
            
            final_system_prompt = personalized_prompt + end_prompt
            st.session_state.agent_prompt = final_system_prompt

            messages = [
                {"role": "system", "content": final_system_prompt}
            ]
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0,
            )
            reply = response.choices[0].message.content
            
            st.session_state.chat_history.append(f"AI: {reply}")
            st.session_state.first_session = False

            now = datetime.now(UTC).strftime('%Y/%m/%d %H:%M')            
            full_message = st.session_state["style_label"] + " " + now + "\n" + f"AI: {reply}"
            record_message(st.session_state.username, full_message, "message")
            
    if st.session_state["clear_screen"]:
        st.success("Mission Accomplished! Congratulations!")
        
        evaluation_prompt = '''
            あなたは私が作成する日本語学習ゲームの評価システムです。
            プレイヤーの会話履歴を分析し、以下の3つの観点から評価とフィードバックを提供してください。

            **[重要] 評価手順**
            1.  まず、「1. 文法・語彙」「2. TPO・丁寧さ」「3. 会話の自然な流れ」の3つの観点から、会話全体を詳細に分析してください。
            2.  次に、採点基準に基づいて各観点を100点満点で採点してください。
            3.  最後に、以下の[出力形式]に従って、プレイヤーへのフィードバックを生成してください。

            **[観点別採点基準]**

            **1. 文法・語彙**
            *   90-100点: 文法や語彙にほとんど誤りがなく、非常に自然で適切。
            *   70-89点: 軽微な誤り（例: 助詞）はあるが、意図は明確に伝わる。
            *   40-69点: 誤りが多く、相手が意味を推測する必要がある場面が時々ある。
            *   0-39点: 誤りが非常に多く、コミュニケーションが困難。

            **2. TPO・丁寧さ**
            *   90-100点: TPO（時・場所・場面）や相手との関係性に合わせた言葉遣いが完璧。
            *   70-89点: 丁寧さの選択にやや不自然な点があるが、大きな問題はない。
            *   40-69点: TPOに不適切な言葉遣いや、不適切な丁寧さが目立つ。
            *   0-39点: TPOを著しく無視した言葉遣いや、失礼な表現。

            **3. 会話の自然な流れ**
            *   90-100点: 会話がスムーズに進行し、目標達成に向けたやり取りが滞りない。
            *   70-89点: 目標は達成されているが、時折、応答に詰まったり、不自然な間があったりする。
            *   40-69点: 会話がぎこちなく、話が繋がらない場面がある。
            *   0-39点: 会話が全く成立しない、または目的から大きく逸脱している。

            **[出力形式]**
            以下のMarkdown形式を厳守し、各観点の点数とフィードバックを出力してください。

            **[総合評価]**
            （会話全体に対する肯定的で励ましとなるコメント）

            ---

            ### 1. 文法・語彙
            **点数:** XX/100
            **フィードバック:**
            *   **良かった点:** （会話の特定の部分を引用し、何が良かったかを簡潔に説明）
            *   **改善点:** （会話の特定の部分を引用し、どのように改善できるかを簡潔に説明）

            ---

            ### 2. TPO・丁寧さ
            **点数:** XX/100
            **フィードバック:**
            *   **良かった点:** （会話の特定の部分を引用し、何が良かったかを簡潔に説明）
            *   **改善点:** （会話の特定の部分を引用し、どのように改善できるかを簡潔に説明）

            ---

            ### 3. 会話の自然な流れ
            **点数:** XX/100
            **フィードバック:**
            *   **良かった点:** （会話の特定の部分を引用し、何が良かったかを簡潔に説明）
            *   **改善点:** （会話の特定の部分を引用し、どのように改善できるかを簡潔に説明）
        '''
        summary_prompt = '''
            あなたは私が作成する日本語学習ゲームのシステムの一部である、**プレイヤーの言語的課題分析機能**を担当してもらいます。
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

        evaluation_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": evaluation_prompt},
                {"role": "user", "content": conversation_log}
            ],
            temperature=0.25,
        )
        evaluation_result = evaluation_response.choices[0].message.content
                st.markdown("### 会話の評価")
        st.markdown(evaluation_result)
        now_str = datetime.now(UTC).strftime('%Y/%m/%d %H:%M\n')
        record_message(st.session_state.username, st.session_state["style_label"] + " " + now_str + evaluation_result, "eval")

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

        if st.button("🔁 Try Again"):
            st.session_state.chat_history = []
            st.session_state["clear_screen"] = False
            st.session_state["show_history"] = False
            st.session_state["home"] = False
            st.session_state["logged_in"] = True
            st.session_state["chat"] = True
            st.session_state["first_session"] = True
            st.rerun()
    
    if st.session_state.chat_history and not st.session_state["clear_screen"] and not st.session_state["home"]:
        for msg in st.session_state.chat_history:
            if msg.startswith("User:"):
                st.markdown(
                    f'''
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
                            {msg.replace("User:", "")}
                        </div>
                    </div>
                    ''',
                    unsafe_allow_html=True
                )
            elif msg.startswith("AI:"):
                st.markdown(
                    f'''
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
                    ''',
                    unsafe_allow_html=True
                )

    if st.session_state["chat"] and not st.session_state.first_session:
        # --- ヒントメッセージがセッションにあれば表示し、その後クリアする ---
        if st.session_state.get("hint_message"):
            st.info(st.session_state.hint_message)
            st.session_state.hint_message = ""

        # --- ヒント選択画面 ---
        if st.session_state.hint_mode == "select":
            st.markdown("どのようなヒントが必要ですか？")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("言葉の意味を調べる", use_container_width=True):
                    st.session_state.hint_mode = "ask_word"
                    st.rerun()
            with col2:
                if st.button("次の行動のヒント", use_container_width=True):
                    hint = generate_hint("action")
                    st.session_state.hint_message = hint
                    st.session_state.hint_mode = "chat" # ヒント生成後はチャットモードに戻す
                    st.rerun()

        # --- 単語質問画面 ---
        elif st.session_state.hint_mode == "ask_word":
            with st.form(key="word_hint_form", clear_on_submit=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    word_to_ask = st.text_input("意味を調べたい言葉を入力してください", label_visibility="collapsed", placeholder="意味を調べたい言葉を入力してください")
                with col2:
                    submit_word = st.form_submit_button("送信", use_container_width=True)

            if submit_word and word_to_ask:
                hint = generate_hint("word", word_to_ask)
                st.session_state.hint_message = hint
                st.session_state.hint_mode = "chat"  # ヒント生成後はチャットモードに戻す
                st.rerun()

        # --- 通常のチャット入力フォーム ---
        elif st.session_state.hint_mode == "chat":
            with st.form(key="chat_form", clear_on_submit=True):
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    user_input = st.text_input("Enter your message", key="input_msg", label_visibility="collapsed")
                    components.html(f'''<div>...</div><script>...</script>''', height=0)
                with col2:
                    submit_button = st.form_submit_button("Send", use_container_width=True)
                with col3:
                    if st.form_submit_button("💡 ヒント", use_container_width=True):
                        st.session_state.hint_mode = "select"
                        st.rerun()

            if submit_button and user_input.strip():
                # (既存の送信処理)
                client = OpenAI(api_key=st.secrets["openai"]["api_key"])
                system_prompt = st.session_state.get("agent_prompt", "You are a kind English learning teacher.")
                messages = [{"role": "system", "content": system_prompt}]
                for msg in st.session_state.get("chat_history", []):
                    if msg.startswith("User:"):
                        messages.append({"role": "user", "content": msg.replace("User:", "").strip()})
                    elif msg.startswith("AI:"):
                        messages.append({"role": "assistant", "content": msg.replace("AI:", "").strip()})
                messages.append({"role": "user", "content": user_input})
                response = client.chat.completions.create(model="gpt-4o", messages=messages, temperature=0.25)
                reply = response.choices[0].message.content
                st.session_state.chat_history.append(f"User: {user_input}")
                st.session_state.chat_history.append(f"AI: {reply}")
                full_message = f"User: {user_input}\nAI: {reply}"
                record_message(st.session_state.username, full_message,"message")
                
                if "Mission Accomplished" in reply:
                    st.session_state.clear_screen = True
                    st.session_state.chat = False
                elif "Mission Failed" in reply:
                    st.session_state.Failed_screen = True
                    st.session_state.chat = False
                st.rerun()
            
    elif st.session_state.show_history:
        st.markdown("### 📜 Chat History")
        history = load_message(st.session_state.username, "message")

        if not history.strip():
            st.info("(No chat history yet)")
        else:
            pattern = r"(Chapter \d+: .*?\d{4}/\d{2}/\d{2} \d{2}:\d{2})(.*?)(?=Chapter \d+: |\Z)"
            matches = re.findall(pattern, history, re.DOTALL)

            if not matches:
                st.warning("Failed to parse history.")
            else:
                options = [title.strip() for title, _ in matches]
                selected = st.selectbox("Select a conversation to display", options[::-1])

                selected_block = next(((t, c) for t, c in matches if t.strip() == selected), None)

                if selected_block:
                    title, content = selected_block
                    st.markdown(f"#### {title.strip()}")

                    lines = content.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if line.startswith("User:"):
                            col1, col2 = st.columns([4, 6])
                            with col2:
                                st.markdown(
                                    f'''
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
                                            {line.replace("User:", "")}
                                        </div>
                                    </div>
                                    ''',
                                    unsafe_allow_html=True
                                )
                        elif line.startswith("AI:"):
                            col1, col2 = st.columns([6, 4])
                            with col1:
                                st.markdown(
                                    f'''
                                    <div style='display: flex; justify: flex-start; margin: 4px 0'>
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
                                    ''',
                                    unsafe_allow_html=True
                                )

    elif st.session_state["eval"]:
        st.title("🎩 Past Feedback")
        message = load_message(st.session_state["username"], "eval")

        if not message:
            st.info("No feedback has been registered yet.")
        else:
            pattern = r"(Chapter \d+: .*?\d{4}/\d{2}/\d{2} \d{2}:\d{2})\n(.*?)(?=Chapter \d+: |\Z)"
            matches = re.findall(pattern, message, re.DOTALL)

            if not matches:
                st.warning("Could not parse feedback.")
            else:
                feedback_dict = {title.strip(): body.strip() for title, body in matches}
                selected_title = st.selectbox("Select feedback to display", sorted(feedback_dict.keys(), reverse=True))
                st.markdown("### Feedback Content")
                selected_body = feedback_dict[selected_title]
                for para in selected_body.split("\n\n"):
                    st.markdown(para.strip())