import streamlit as st
import pandas as pd
import os
import google.generativeai as genai

st.set_page_config(page_title="📦 企業級智能庫存系統 (戰情室版)", page_icon="✨", layout="wide")
st.title("✨ 企業級 AI 庫存戰情室")
st.markdown("---")

# 設定 Gemini API Key
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except Exception:
    st.error("⚠️ 系統找不到 API Key。如果你部署在雲端，請到 Streamlit 儀表板設定 Secrets！")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

default_file_path = "/Users/alice/Downloads/TW Supply status report_dac_0331 (1).xlsx"

@st.cache_data
def load_data(file_context):
    try:
        df = pd.read_excel(file_context, sheet_name='Supply ststus report_1216', header=1)
        df = df.dropna(how='all')
        return df
    except Exception as e:
        st.sidebar.error(f"⚠️ 讀取 Excel 檔案時發生錯誤：{e}")
        return pd.DataFrame()

# 左側邊欄
with st.sidebar:
    st.header("⚙️ 儀表板設定")
    uploaded_file = st.file_uploader("📂 拖拉上傳最新的庫存報表 (Excel)", type=["xlsx", "xls"])
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
        st.markdown("### 🧠 AI 與戰情室雙核心")
        st.markdown("一鍵切換視角，支援數據即時視覺化、與語意化的庫存警示。")

# ================================
# 建立雙分頁架構 (Tabs)
# ================================
tab1, tab2 = st.tabs(["📊 數據戰情室 (Dashboard)", "🤖 AI 庫存智能助理"])

# -----------------
# TAB 1: Dashboard
# -----------------
with tab1:
    st.header("📈 即時庫存預警與分析")
    
    if df.empty:
        st.info("💡 請先從左側上傳您的 Excel 庫存報表以啟用數據戰情室。")
    else:
        # 1. 緊急補貨清單 (Top 3)
        st.subheader("🚨 緊急補貨警示 (狀態為 Insufficient)")
        
        if 'Status' in df.columns:
            # 找出 Status 為 Insufficient 的商品
            insufficient_mask = df['Status'].fillna('').astype(str).str.contains('Insufficient', case=False)
            urgent_items = df[insufficient_mask]
            
            if len(urgent_items) > 0:
                top_items = urgent_items.head(3)
                
                # 建立等比例卡片
                cols = st.columns(len(top_items))
                for i, (_, row) in enumerate(top_items.iterrows()):
                    brand = row.get('Brand', '未標示品牌')
                    desc = str(row.get('Description', '無描述'))
                    if len(desc) > 20: 
                        desc = desc[:20] + "..."
                        
                    demand = row.get('FPC Demand', 0)
                    soh = row.get('FP SOH', 0)
                    coverage = row.get('Coverage', '未知')
                    
                    with cols[i]:
                        st.error(
                            f"#### **{brand}**\n"
                            f"*{desc}*\n\n"
                            f"📦 目前庫存: **{soh}**\n\n"
                            f"📉 預測需求: **{demand}**\n\n"
                            f"⏳ 涵蓋狀態: `{coverage}`"
                        )
            else:
                st.success("🎉 目前系統偵測不到任何需要緊急補貨 (Insufficient) 的商品，庫存非常健康！")
        else:
            st.warning("⚠️ 匯入的資料表中找不到 `Status` 欄位，無法計算緊急情況。")
            
        st.markdown("---")
        
        # 2. 視覺化庫存水位 (Bar Chart)
        st.subheader("📊 各類別：庫存 vs 需求 對比圖")
        
        if 'Category' in df.columns:
            all_categories = sorted(df['Category'].dropna().unique().tolist())
            if all_categories:
                st.markdown("👇 **請選擇要檢視庫存分配比重的分類：**")
                selected_cat = st.selectbox("", all_categories, label_visibility="collapsed")
                
                chart_df = df[df['Category'] == selected_cat].copy()
                
                # 清洗數值，確保能畫成圖表
                chart_df['FPC Demand'] = pd.to_numeric(chart_df['FPC Demand'], errors='coerce').fillna(0)
                chart_df['FP SOH'] = pd.to_numeric(chart_df['FP SOH'], errors='coerce').fillna(0)
                
                # 用 Brand 群組化，把數字加起來看總體
                grouped_df = chart_df.groupby('Brand')[['FPC Demand', 'FP SOH']].sum()
                grouped_df = grouped_df.rename(columns={'FPC Demand': '預測需求量 (Demand)', 'FP SOH': '目前在庫存量 (SOH)'})
                
                st.bar_chart(grouped_df)
                
                with st.expander(f"📝 查看 {selected_cat} 完整細節報表"):
                    display_cols = ['Brand', 'Description', 'FPC Demand', 'FP SOH', 'Coverage', 'Status']
                    valid_cols = [c for c in display_cols if c in chart_df.columns]
                    st.dataframe(chart_df[valid_cols], use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ 匯入的資料表中找不到 `Category` 欄位，無法繪製分類圖表。")

# -----------------
# TAB 2: AI Chatbot
# -----------------
with tab2:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "您好！我是庫存智能管家 👋\n請直接輸入您想查詢的問題。若 AI 卡住，系統會自動切換回關鍵字搜尋喔！"}
        ]

    for message in st.session_state.messages:
        if message["role"] == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(message["content"])
                if message.get("dataframe") is not None:
                    st.dataframe(message["dataframe"], use_container_width=True, hide_index=True)
        else:
            with st.chat_message("user", avatar="👤"):
                st.markdown(message["content"])

    if prompt := st.chat_input("🔍 請輸入您的指令 (例如告訴我 Ariel 缺貨嗎)..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            if df.empty:
                msg = "抱歉，目前系統內沒有資料。請先從左側上傳 Excel 檔案以啟用 AI！"
                st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            else:
                with st.spinner("🧠 AI 正在深度分析報表資料..."):
                    try:
                        target_cols = ['Brand', 'Category', 'Description', 'FPC Demand', 'FP SOH', 'on-hand CTMZ Qty.', 'Coverage', 'Status']
                        available_cols = [col for col in target_cols if col in df.columns]
                        summary_df = df[available_cols].fillna("")
                        csv_data = summary_df.to_csv(index=False)
                        system_prompt = f"你是一台庫存數據分析 AI。下方是 CSV 庫存庫。\n{csv_data}\n請完全根據資料表回答，精準列出名稱、需求、庫存、Coverage 與 Status。"
                        full_prompt = f"{system_prompt}\nUser: {prompt}\nAssistant:"
                        
                        response = model.generate_content(full_prompt)
                        response_content = response.text
                        
                        st.markdown(response_content)
                        st.session_state.messages.append({"role": "assistant", "content": response_content})
                        
                    except Exception as e:
                        fallback_msg = f"*(系統備援中：目前 Google API 達到存取上限，自動切換為【極速關鍵字模式】⚡)*\n\n"
                        
                        query = prompt.lower()
                        mask = (
                            df['Brand'].fillna('').str.lower().str.contains(query, na=False) |
                            df['Description'].fillna('').str.lower().str.contains(query, na=False) |
                            df['Category'].fillna('').astype(str).str.lower().str.contains(query, na=False)
                        )
                        results = df[mask]
                        
                        if len(results) > 0:
                            fallback_msg += f"🎯 為您精準定位，找到 **{len(results)}** 筆包含「**{prompt}**」的商品："
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
                            fallback_msg += f"抱歉，目前報表中完全找不到包含「**{prompt}**」的商品。"
                            st.markdown(fallback_msg)
                            st.session_state.messages.append({"role": "assistant", "content": fallback_msg})
