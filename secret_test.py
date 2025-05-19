import streamlit as st
import openai

# OpenAI API キー設定（secretsから取得）
client = openai.OpenAI(api_key=st.secrets["openai"]["api_key"])

st.title("🤖 Chat Agent")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "あなたは親切で丁寧な日本語の会話エージェントです。"}
    ]

user_input = st.chat_input("メッセージを入力してください")

for msg in st.session_state.messages[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("考え中..."):
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=st.session_state.messages
            )
            reply = response.choices[0].message.content
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
