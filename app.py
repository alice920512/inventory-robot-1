import streamlit as st
import pandas as pd
import os
import google.generativeai as genai

st.set_page_config(page_title="📦 企業級智能庫存系統 (AI大腦版)", page_icon="✨", layout="wide")
st.title("✨ 企業級 AI 庫存管家 (自動備援機制)")
st.markdown("---")

# 設定 Gemini API Key
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except Exception:
    st.error("⚠️ 系統找不到 API Key。")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)
# 使用比較大眾版/最新版的模型，因為 2.0 遇到了 limit 0，切換到最新的 Gemini 3 系列測試
model = genai.GenerativeModel('gemini-3-flash-preview')

default_file_path = "/Users/alice/Downloads/TW Supply status report_dac_0331 (1).xlsx"

@st.cache_data
def load_data(file_context):
    try:
        df = pd.read_excel(file_context, sheet_name='Supply ststus report_1216', header=1)
        df = df.dropna(how='all')
        return df
    except Exception as e:
        st.sidebar.error(f"⚠️ 讀出 Excel 檔案時發生錯誤：{e}")
        return pd.DataFrame()

with st.sidebar:
    st.header("⚙️ 儀表板設定")
    uploaded_file = st.file_uploader("📂 拖曳上傳最新的庫存報表 (Excel)", type=["xlsx", "xls"])
    st.markdown("---")
    st.header("📊 系統狀態儀表板")

with st.spinner("📦 正在與資料庫連線載入資料中..."):
    df = pd.DataFrame()
    if uploaded_file is not None:
        df = load_data(uploaded_file)
        if not df.empty:
            st.sidebar.success(f"🟢 已更新為最新上傳資料")
    else:
        if os.path.exists(default_file_path):
            df = load_data(default_file_path)
            if not df.empty:
                st.sidebar.warning("🟡 目前使用：本地預設備用報表")

with st.sidebar:
    if not df.empty:
        st.metric(label="總追蹤 SKU 數", value=f"{len(df)} 筆")
        st.markdown("---")
        st.markdown("### 🧠 AI 與快速搜尋雙引擎")
        st.markdown("若系統偵測到 AI 超過每日額度，會自動為您啟動「**極速關鍵字備援系統**」，不間斷提供庫存報表服務！")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "您好！我是庫存智能管家 👋\n請直接輸入您想查詢的問題 (例如 Brand 或 Description)。若 AI 卡住，系統會自動切換回關鍵字搜尋喔！"}
    ]

# 顯示所有先前的對話與表格
for message in st.session_state.messages:
    if message["role"] == "assistant":
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(message["content"])
            if message.get("dataframe") is not None:
                st.dataframe(message["dataframe"], use_container_width=True, hide_index=True)
    else:
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])

if prompt := st.chat_input("🔍 請輸入您的問題..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        if df.empty:
            msg = "抱歉，目前系統內沒有資料。請先從左側上傳 Excel 檔案喔！"
            st.markdown(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
        else:
            with st.spinner("🧠 AI 正在深度分析中..."):
                try:
                    # 1. 嘗試透過 AI 處理
                    target_cols = ['Brand', 'Category', 'Description', 'FPC Demand', 'FP SOH', 'on-hand CTMZ Qty.', 'Coverage', 'Status']
                    available_cols = [col for col in target_cols if col in df.columns]
                    summary_df = df[available_cols].fillna("")
                    csv_data = summary_df.to_csv(index=False)
                    system_prompt = f"你是一位庫存管理 AI。下方是 CSV 庫存庫。\n{csv_data}\n請完全根據資料表回答，精準列出名稱、需求、庫存、Coverage 與 Status。"
                    full_prompt = f"{system_prompt}\nUser: {prompt}\nAssistant:"
                    
                    response = model.generate_content(full_prompt)
                    response_content = response.text
                    
                    st.markdown(response_content)
                    st.session_state.messages.append({"role": "assistant", "content": response_content})
                    
                except Exception as e:
                    # 2. 如果碰到 Quota Errors，動態切換成備援模式 - 關鍵字搜尋
                    fallback_msg = f"*(系統提示：目前 Google 帳號 API 額度限制異常，自動切換為無限制的【極速關鍵字模式】⚡)*\n\n"
                    
                    query = prompt.lower()
                    mask = (
                        df['Brand'].fillna('').str.lower().str.contains(query, na=False) |
                        df['Description'].fillna('').str.lower().str.contains(query, na=False) |
                        df['Category'].fillna('').str.lower().str.contains(query, na=False)
                    )
                    results = df[mask]
                    
                    if len(results) > 0:
                        fallback_msg += f"🎯 為您精準比對，找到 **{len(results)}** 筆包含「**{prompt}**」的商品："
                        st.markdown(fallback_msg)
                        
                        display_cols = ['Brand', 'Description', 'Category', 'FP SOH', 'on-hand CTMZ Qty.', 'Coverage', 'Status']
                        display_df = results[display_cols].copy()
                        display_df = display_df.rename(columns={'Brand': '品牌 🏷️', 'Description': '商品描述 📦', 'Category': '類別 📂', 'FP SOH': '目前庫存量 🟢', 'on-hand CTMZ Qty.': '可改包數量 🔧', 'Coverage': '可涵蓋週數 📅', 'Status': '庫存狀態 ⚠️'})
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": fallback_msg,
                            "is_result": True,
                            "dataframe": display_df
                        })
                    else:
                        fallback_msg += f"抱歉，目前庫存庫中**完全找不到**包含「**{prompt}**」的商品。"
                        st.markdown(fallback_msg)
                        st.session_state.messages.append({"role": "assistant", "content": fallback_msg})
