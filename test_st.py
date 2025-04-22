import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import altair as alt
from datetime import datetime, time
from PIL import Image
import time as tm

st.set_page_config(page_title="Streamlit多機能デモ", layout="wide")

# タイトル・見出し
st.title("🧪 Streamlit 多機能デモアプリ")
st.subheader("さまざまなUIコンポーネント・データ表示・可視化を体験できます")

# サイドバー
with st.sidebar:
    st.header("📌 サイドバー")
    name = st.text_input("名前を入力してください")
    agree = st.checkbox("利用規約に同意しますか？")
    if agree:
        st.success(f"{name} さん、ありがとうございます！")

# ボタン・入力・選択
st.header("🎛️ 入力系ウィジェット")

col1, col2, col3 = st.columns(3)

with col1:
    age = st.slider("年齢", 0, 100, 25)
    st.write(f"あなたの年齢は {age} 歳です。")

with col2:
    color = st.selectbox("好きな色", ["赤", "青", "緑", "黄"])
    st.write(f"選んだ色：{color}")

with col3:
    hobby = st.multiselect("趣味を選択", ["音楽", "読書", "旅行", "映画"])
    st.write(f"選択した趣味：{hobby}")

# ファイルアップロード・画像表示
st.header("📁 ファイルアップロード・画像表示")
uploaded_file = st.file_uploader("画像ファイルをアップロード", type=["png", "jpg", "jpeg"])
if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="アップロードされた画像", use_column_width=True)

# データ表示
st.header("📊 データフレーム表示")
data = pd.DataFrame({
    "列A": np.random.randn(10),
    "列B": np.random.rand(10),
})
st.dataframe(data)

# プロット表示
st.header("📈 プロット各種")

tab1, tab2, tab3 = st.tabs(["Matplotlib", "Plotly", "Altair"])

with tab1:
    fig, ax = plt.subplots()
    ax.plot(data["列A"], label="列A")
    st.pyplot(fig)

with tab2:
    fig2 = px.line(data, y="列B", title="Plotlyの折れ線グラフ")
    st.plotly_chart(fig2)

with tab3:
    chart = alt.Chart(data.reset_index()).mark_line().encode(
        x="index", y="列A"
    ).interactive()
    st.altair_chart(chart, use_container_width=True)

# 日時入力
st.header("🕒 日時入力")
date = st.date_input("日付を選択")
time = st.time_input("時間を選択")
st.write(f"選択された日時: {date} {time}")

# プログレスバーとスピナー
st.header("⏳ プログレスバーとスピナー")

progress_bar = st.progress(0)
for i in range(100):
    tm.sleep(0.01)
    progress_bar.progress(i + 1)

with st.spinner("少々お待ちください..."):
    tm.sleep(2)
st.success("完了しました！")

# メトリクスとトースト
st.header("📊 メトリクスと通知")
col1, col2, col3 = st.columns(3)
col1.metric("温度", "70 °C", "+1.2 °C")
col2.metric("風速", "10 m/s", "-0.5 m/s")
col3.metric("湿度", "65%", "+3%")

# キャッシュの利用
st.header("⚡ キャッシュの利用")

@st.cache_data
def get_data(n):
    st.toast("データを読み込み中...", icon="🔄")
    tm.sleep(1)
    return pd.DataFrame(np.random.randn(n, 2), columns=["X", "Y"])

n = st.number_input("データ数", min_value=10, max_value=1000, step=10)
df_cached = get_data(int(n))
st.line_chart(df_cached)

# 終わり
st.markdown("---")
st.caption("🛠️ 作成者: Streamlit学習用デモ - すべての主要機能を網羅しました")
