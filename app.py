import streamlit as st
import pandas as pd
import os
import google.generativeai as genai

# ================================
# 配置設定區
# ================================
st.set_page_config(page_title="P&G 智能庫存系統 (AI大腦版)", page_icon="✨", layout="wide")

st.title("✨ 企業級 AI 庫存智能管家")
st.markdown("---")

# 設定 Gemini API Key (從安全的 Secrets 讀取)
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except Exception:
    st.error("⚠️ 系統找不到 API Key。如果你部署在雲端，請到 Streamlit 儀表板設定 Secrets！")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

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

# ================================
# 左側邊欄 (Sidebar) - 加入上傳區
# ================================
with st.sidebar:
    st.header("⚙️ 儀表板設定")
    uploaded_file = st.file_uploader("📂 拖曳上傳最新的庫存報表 (Excel)", type=["xlsx", "xls"])
    st.markdown("---")
    st.header("📊 系統狀態儀表板")

# 讀取資料
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
        else:
            st.sidebar.error("🔴 尚未準備好檔案")

with st.sidebar:
    if not df.empty:
        st.metric(label="總追蹤 SKU 數 (商品數量)", value=f"{len(df)} 筆")
        st.markdown("---")
        st.markdown("### 🧠 AI 語意理解已啟動")
        st.markdown("""
        **現在您可以直接「用聊天的」問我！**
        
        💡 **問題範例：**
        - *"幫我查一下 Ariel 最近庫存夠不夠應付需求？"*
        - *"目前有哪些產品是處於 Insufficient 缺貨狀態的？"*
        - *"Baby Care 分類裡面庫存數量最多的是哪三個？"*
        """)

# ================================
# 聊天對話區 (LLM 邏輯)
# ================================
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "您好！我是正式接上 Google Gemini 大大腦的 **AI 庫存管家** 🚀\n我現在不僅看得懂你的關鍵字，還聽得懂你的整段話喔！\n\n您可以隨時問我如：「*幫我比較一下 Lenor 某產品的需求和在手庫存是否吻合？*」"}
    ]

# 顯示所有先前的對話
for message in st.session_state.messages:
    if message["role"] == "assistant":
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(message["content"])
    else:
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])

# 搜尋處理邏輯
if prompt := st.chat_input("🔍 請輸入您的問題 (例如：幫我看一下 Ariel 的庫存狀態？)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        if df.empty:
            response_content = "抱歉，目前系統內沒有資料。請先從左側上傳 Excel 檔案喔！"
            st.markdown(response_content)
            st.session_state.messages.append({"role": "assistant", "content": response_content})
        else:
            with st.spinner("🧠 AI 正在深度分析報表與調閱數據中... (需要幾秒鐘)"):
                try:
                    # 1. 將 DataFrame 提供給 LLM 前先做輕量化處理
                    target_cols = ['Brand', 'Category', 'Description', 'FPC Demand', 'FP SOH', 'on-hand CTMZ Qty.', 'Coverage', 'Status']
                    available_cols = [col for col in target_cols if col in df.columns]
                    summary_df = df[available_cols].fillna("")
                    
                    # 轉為文字格式 (CSV 結構對於 LLM 非常敏感且容易解讀)
                    csv_data = summary_df.to_csv(index=False)
                    
                    # 2. 撰寫強大的 System Prompt
                    system_prompt = f"""
                    你是一位專業、高階的供應鏈與庫存管理 AI 領域專家。
                    你的任務是根據下方我提供給你的【最新企業庫存資料庫】來精準回答使用者的問題。
                    
                    【最新企業庫存資料庫 (CSV格式)】
                    ---
                    {csv_data}
                    ---
                    
                    【重要指示與規則】
                    1. 你的回答必須『100% 基於上述提供的資料』。絕對不可以編造資料。若查無此商品，請明白告訴使用者。
                    2. 當使用者詢問「庫存與需求是否吻合」或「供貨狀態」時，請綜合比較 'FP SOH' (在手庫存)、 'FPC Demand' (需求預測)，並重點參考 'Coverage' 週數與 'Status' (例如 Fulfill 滿足 或 Insufficient 缺貨)。
                    3. 請直接切入重點，並將相關數據明確列出（例如用粗體標示數字）。
                    4. 排版必須美觀、易讀，可以多使用條列式 (- ) 和適當的 Emoji 來讓報表看起來不死板。
                    5. 請使用繁體中文(zh-TW)做回答。
                    """
                    
                    # 3. 帶入上下文對話紀錄
                    history_text = ""
                    # 擷取最近幾則對話作為前後文
                    for msg in st.session_state.messages[-4:-1]:
                        r = "User" if msg["role"] == "user" else "Assistant"
                        history_text += f"{r}: {msg['content']}\n"
                        
                    full_prompt = f"{system_prompt}\n\n【近期對話紀錄】\n{history_text}\n\n【使用者最新提問】\nUser: {prompt}\n\n請開始你的回答 Assistant:"
                    
                    # 4. 呼叫 Gemini API
                    response = model.generate_content(full_prompt)
                    response_content = response.text
                    
                    # 輸出結果
                    st.markdown(response_content)
                    st.session_state.messages.append({"role": "assistant", "content": response_content})
                    
                except Exception as e:
                    error_msg = f"⚠️ 連結到 AI 大大腦時發生錯誤：{e}\n請確認您的網路連線或是 API Key 權限。"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
