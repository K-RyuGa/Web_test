import streamlit as st
import openai

# OpenAI APIキーを Streamlit Cloud 上の secrets から取得
openai.api_key = st.secrets["openai"]["api_key"]

st.set_page_config(page_title="Chat Agent", page_icon="🤖")
st.title("🤖 Chat Agent - OpenAI")

# セッション履歴の初期化
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "あなたは親切で丁寧な日本語の会話エージェントです。"}
    ]

# ユーザー入力
user_input = st.chat_input("メッセージを入力してください")

# 過去のメッセージを表示
for msg in st.session_state.messages[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 入力があれば会話処理
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("考え中..."):
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=st.session_state.messages
            )
            reply = response["choices"][0]["message"]["content"]
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
