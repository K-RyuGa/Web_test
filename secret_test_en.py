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

# --- UI Before Login ---
if not st.session_state.logged_in:
    st.title("Login / Sign Up")
    mode = st.radio("Select Mode", ["Login", "Sign Up"])
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Submit"):
        if mode == "Sign Up":
            if register_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.clear_screen = False
                st.rerun()
            else:
                st.error("This username is already taken.")
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
            "Mission Accomplished" is the keyword for clearing the game, so never output it if the mission has not been achieved.
            Now, let the game begin. Please start talking to the player.
        '''

        story_prompt = [
            [
                '''
                As an airport staff member, guide the player through immigration procedures and ask for their passport. Also, tell them where to pick up their luggage.

                Specific actions are as follows:
                1. Ask the player to present their passport.
                2. Explain the immigration process.
                3. Guide them to the baggage claim area, confirm they understand, and if so, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a cashier at a supermarket, handle the player's checkout process.

                Specific actions are as follows:
                1. Call the player over with "I can help the next person in line."
                2. Process the purchased items and tell them the total amount.
                3. Answer any questions about payment methods.
                4. Once the player completes the payment, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a new friend, introduce yourself to the player and chat about each other's hobbies and plans.

                Specific actions are as follows:
                1. Introduce yourself and encourage the player to do the same.
                2. Ask questions about the player's hobbies and interests.
                3. Suggest a date to meet next, and if the player agrees, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a colleague at work, introduce yourself to the player and enjoy a first-time conversation at the workplace.

                Specific actions are as follows:
                1. Introduce yourself and encourage the player to do the same.
                2. Make small talk about the job to help the player relax.
                3. Once the player successfully introduces themselves, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a doctor at a hospital, listen to the player's symptoms and proceed with the examination.

                Specific actions are as follows:
                1. Ask the player about their symptoms and ask follow-up questions.
                2. Conduct an examination and provide an appropriate diagnosis.
                3. Once the player successfully completes the examination, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a colleague at work, support the player in speaking up during a meeting and provide feedback.

                Specific actions are as follows:
                1. Ask for the player's opinion and give them a chance to speak.
                2. Provide feedback on the player's opinion to advance the discussion.
                3. Once the player successfully states their opinion and moves the discussion forward, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a friend, invite the player to an American festival (e.g., a 4th of July BBQ) and explain the etiquette and cultural background.

                Specific actions are as follows:
                1. Invite the player to the event and explain what it is.
                2. Teach them about cultural etiquette and customs.
                3. Once the player successfully participates and enjoys the event, output "Mission Accomplished".
                ''' 
            ],
            [
                '''
                As a clerk at the DMV, support the player in submitting necessary documents and explain the procedures.

                Specific actions are as follows:
                1. Ask the player what documents they need to submit.
                2. Explain the steps of the procedure and assist if the player is confused.
                3. Once the player successfully completes the procedure, output "Mission Accomplished".
                '''
            ],
            [
                '''
                As a transit employee, help the player by giving appropriate instructions when their train is delayed.

                Specific actions are as follows:
                1. Explain the train delay and suggest the next course of action.
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

            start_prompt = "In line with your role, start a natural conversation with the English learner."
            messages = [
                {"role": "system", "content": final_system_prompt},
                {"role": "user", "content": start_prompt}
            ]
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.25,
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
            You are in charge of the evaluation system for an "English Language Learning Support Game" I am creating.
            Your role is to analyze the player's conversation history and provide fair and educational feedback.

            【IMPORTANT】Evaluation Procedure and Scoring Criteria
            To eliminate ambiguity in evaluation and always provide feedback based on a consistent standard, please strictly adhere to the following procedure and scoring criteria.

            Step 1: Conversation Analysis
            First, analyze the entire conversation in detail from the following three perspectives: "1. Grammar & Vocabulary," "2. TPO & Politeness," and "3. Natural Flow of Conversation."

            Step 2: Scoring
            Next, based on the following scoring criteria, determine which level the conversation falls into and decide on a final score.

            【Scoring Criteria】
            *   **90-100 points (Excellent)**:
                *   Almost no errors in grammar or vocabulary; uses very natural English.
                *   Perfect use of politeness levels appropriate for the TPO and relationship with the other person.
                *   The conversation flows smoothly, and communication to achieve the objective is seamless.

            *   **70-89 points (Good)**:
                *   Some minor grammar/vocabulary errors (e.g., article mistakes), but they do not hinder communication.
                *   Slightly unnatural choices in TPO or politeness, but no major issues.
                *   The conversation's objective is met, but there are occasional hesitations or slightly unnatural pauses.

            *   **40-69 points (Needs Improvement)**:
                *   Many errors in grammar and vocabulary, requiring the other person to guess the meaning at times.
                *   Noticeable use of language inappropriate for the TPO or impolite expressions.
                *   The conversation flow is awkward, with misunderstandings or abrupt statements that confuse the other person.

            *   **0-39 points (Major Issues)**:
                *   So many errors in grammar and vocabulary that communication is difficult.
                *   Language that grossly disregards TPO or is rude.
                *   The conversation does not make sense at all, or completely ignores the process of achieving the mission.

            Step 3: Creating Feedback
            Finally, output the feedback to the player in the following format.

            【Output Format】
            1.  **Score**: (Describe the score in "n/100" format)
            2.  **Overall Comment**: (A positive word of praise or encouragement for the entire conversation)
            3.  **Detailed Feedback**:
                *   **【Good Points】**: (Quote specific parts of the conversation and praise them from the perspectives of grammar, TPO, and conversational flow)
                *   **【Areas for Improvement】**: (Quote specific parts of the conversation, explain why it's a problem, and how it could be improved from the three perspectives above)

            Please output in a tone as if you are speaking directly to the player.
        '''
        summary_prompt = '''
            You are responsible for the **Player's Linguistic Challenge Analysis feature** of an "English Language Learning Support Game" I am creating.
            Your role is to analyze the following conversation history and objectively extract the "challenges" the player faces in English communication.

            【IMPORTANT】Analysis Rules
            *   **NEVER analyze or describe** the player's personality, mood, individuality, or intentions.
            *   The information to be extracted must be limited to **purely linguistic and communication strategy challenges**.
            *   Please output the specific challenges as a concise bulleted list based on the following perspectives.

            【Analysis Perspectives】
            1.  **Grammar & Vocabulary Errors**: Mistakes with articles (a/an/the), verb conjugations, inappropriate word choices.
            2.  **Politeness Level**: Expressions that are too formal or too casual for the situation.
            3.  **Communication Strategy**: Unnaturally short/long responses to questions, abrupt topic changes, overly direct expressions lacking consideration for the other person.
            4.  **Conversation Flow Disruption**: Remarks that ignore the context, actions that deviate from the conversation's purpose.

            Analyze the following conversation history and output only the challenges as a bulleted list from the perspectives above.
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
        st.markdown("### Conversation Evaluation")
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
        with st.form(key="chat_form", clear_on_submit=True):
            col1, col2 = st.columns([5, 1])
            
            with col1:
                user_input = st.text_input("Enter your message", key="input_msg", label_visibility="collapsed")
                components.html(
                    f'''
                        <div>some hidden container</div>
                        <p>{st.session_state.counter if 'counter' in st.session_state else 0}</p>
                        <script>
                            var input = window.parent.document.querySelectorAll("input[type=text]");
                            for (var i = 0; i < input.length; ++i) {{
                                input[i].focus();
                            }}
                    </script>
                    ''',
                    height=0,
                )
                
            with col2:
                submit_button = st.form_submit_button("Send", use_container_width=True)

        if submit_button:
            if user_input.strip():
                client = OpenAI(api_key=st.secrets["openai"]["api_key"])

                system_prompt = st.session_state.get("agent_prompt", "You are a kind English learning teacher.")
                messages = [{"role": "system", "content": system_prompt}]
                for msg in st.session_state.get("chat_history", []):
                    if msg.startswith("User:"):
                        messages.append({"role": "user", "content": msg.replace("User:", "").strip()})
                    elif msg.startswith("AI:"):
                        messages.append({"role": "assistant", "content": msg.replace("AI:", "").strip()})

                messages.append({"role": "user", "content": user_input})

                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.25,
                )
                reply = response.choices[0].message.content
            
                st.session_state.chat_history.append(f"User: {user_input}")
                st.session_state.chat_history.append(f"AI: {reply}")

                if st.session_state["first_session"]:
                    now = datetime.now(UTC).strftime('%Y/%m/%d %H:%M')
                    full_message = st.session_state["style_label"] + now + f"User: {user_input}AI: {reply}"
                    st.session_state["first_session"] = False
                else:
                    full_message = f"User: {user_input}\nAI: {reply}"
                
                record_message(st.session_state.username, full_message, "message")
                
                if "Mission Accomplished" in reply and not st.session_state["home"]:
                    st.session_state["clear_screen"] = True
                    st.session_state["chat"] = False
                    st.session_state["chat_histry"] = []
                    st.session_state["first_session"] = True
                    st.rerun()
                st.rerun()
            else:
                st.warning("Message is empty.")
            
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