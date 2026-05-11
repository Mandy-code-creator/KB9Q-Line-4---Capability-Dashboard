import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. 頁面配置與專業樣式 (Power BI Style) ---
st.set_page_config(page_title="KB9Q Line 4 - 質量管理看板", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    /* 圖表容器樣式：白底、黑框、輕微陰影 */
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 5px;
        border: 2px solid #cfd8dc;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    /* 標題加粗 */
    h1, h2, h3 {
        color: #0d47a1 !important;
        font-weight: 800 !important;
        font-family: 'Segoe UI', Tahoma, sans-serif;
    }
    /* 數據卡片樣式 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-left: 5px solid #0d47a1;
        border-radius: 5px;
        padding: 10px;
        box-shadow: 1px 1px 3px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 數據讀取與側邊欄控制 ---
st.sidebar.header("📂 數據源管理")
uploaded_file = st.sidebar.file_uploader("上傳生產數據 (Excel/CSV)", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        # 清理列名空格
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        # 用途碼過濾
        if "用途碼" in df.columns:
            usage_list = sorted(df["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("過濾用途碼:", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        # --- 智能列搜索函數 ---
        def find_col(key_word, exclude_list=[]):
            for col in df.columns:
                if re.search(key_word, col, re.IGNORECASE) and not any(ex in col for ex in exclude_list):
                    return col
            return None

        metrics_map = {"YS (降伏強度)": "YS", "TS (抗拉強度)": "TS", "EL (伸長率)": "EL", "Hardness (硬度)": "HRB", "YPE": "YPE"}
        available_metrics = [k for k, v in metrics_map.items() if find_col(v, ["要求", "管制", "規格"])]
        
        selected_label = st.sidebar.selectbox("選擇分析項目:", available_metrics)
        view_mode = st.sidebar.radio("切換視圖:", ["View 1: 分佈與趨勢圖", "View 2: SPC 控制圖"])
        
        # --- 核心邏輯：匹配各層界限 ---
        short_key = metrics_map[selected_label]
        # 1. 實際量測值
        data_col = find_col(short_key, ["要求", "管制", "規格"])
        
        # 2. 中文關鍵字定位
        zh_key = "降伏強度" if "YS" in short_key else "抗拉強度" if "TS" in short_key else "伸長率" if "EL" in short_key else "硬度" if "HRB" in short_key else "降伏點"
        
        # 3. 獲取內部管制值 (LSL/USL)
        lsl_int = next((c for c in df.columns if zh_key in c and "min" in c.lower() and "管制" in c), None)
        usl_int = next((c for c in df.columns if zh_key in c and "max" in c.lower() and "管制" in c), None)
        
        # 4. 獲取客戶要求值 (Customer Spec)
        lsl_cust = next((c for c in df.columns if zh_key in c and "min" in c.lower() and "客戶要求" in c), None)
        usl_cust = next((c for c in df.columns if zh_key in c and "max" in c.lower() and "客戶要求" in c), None)

        if data_col:
            plot_data = df_filtered[data_col].dropna().reset_index(drop=True)
            n = len(plot_data)
            
            # 統計計算
            mu, sigma = plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma
            
            # 界限取值 (中位數)
            val_lsl_int = float(df_filtered[lsl_int].median()) if lsl_int else None
            val_usl_int = float(df_filtered[usl_int].median()) if usl_int else None
            val_lsl_cust = float(df_filtered[lsl_cust].median()) if lsl_cust else None
            val_usl_cust = float(df_filtered[usl_cust].median()) if usl_cust else None

            st.title(f"🚀 生產質量監控: {selected_label}")

            # --- 頂部指標卡 ---
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("樣本數 (n)", n)
            c2.metric("平均值 (Mean)", f"{mu:.2f}")
            c3.metric("標準差 (σ)", f"{sigma:.2f}")
            
            # 計算 Cpk (優先使用客戶要求，若無則用內部管制)
            target_lsl = val_lsl_cust if val_lsl_cust is not None else val_lsl_int
            target_usl = val_usl_cust if val_usl_cust is not None else val_usl_int
            if target_lsl is not None and target_usl is not None and sigma > 0:
                cpk = min((target_usl - mu)/(3*sigma), (mu - target_lsl)/(3*sigma))
                c4.metric("Cpk (客戶規格)", f"{cpk:.2f}", delta="合格" if cpk >= 1.33 else "預警", delta_color="normal" if cpk >= 1.33 else "inverse")

            # --- VIEW 1: 分佈與趨勢 ---
            if view_mode == "View 1: 分佈與趨勢圖":
                col_left, col_right = st.columns([1, 1.4])
                
                with col_left:
                    st.subheader("直方圖與常態分佈")
                    # Sturges Rule
                    k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                    bin_width = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                    
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, name='實測分布', marker_color='#1976D2', opacity=0.6))
                    
                    if sigma > 0:
                        x_curve = np.linspace(mu - 4*sigma, mu + 4*sigma, 200)
                        y_curve = norm.pdf(x_curve, mu, sigma) * n * bin_width
                        fig_dist.add_trace(go.Scatter(x=x_curve, y=y_curve, mode='lines', name='常態曲線', line=dict(color='#0D47A1', width=3)))
                    
                    # 在直方圖顯示客戶界限
                    if val_lsl_cust: fig_dist.add_vline(x=val_lsl_cust, line_dash="dash", line_color="red", line_width=2)
                    if val_usl_cust: fig_dist.add_vline(x=val_usl_cust, line_dash="dash", line_color="red", line_width=2)
                    
                    fig_dist.update_layout(template="plotly_white", yaxis_title="鋼捲數量 (Coils)", margin=dict(t=20))
                    st.plotly_chart(fig_dist, use_container_width=True)

                with col_right:
                    st.subheader("趨勢分析 (客戶規格 vs 內部管制)")
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', name='量測值',
                                                  line=dict(color='#1976D2', width=2), marker=dict(size=7, color='white', line=dict(width=2, color='#1976D2'))))
                    
                    # --- 線條配置清單 ---
                    # 格式: (數值, 標籤, 顏色, 線型, 偏移位置)
                    lines_config = [
                        (mu, "平均值", "green", "solid", 1.01),
                        (ucl, "UCL(3σ)", "orange", "dash", 1.01),
                        (lcl, "LCL(3σ)", "orange", "dash", 1.01),
                        (val_usl_int, "內部管制上限", "#5D4037", "dot", 1.10),
                        (val_lsl_int, "內部管制下限", "#5D4037", "dot", 1.10),
                        (val_usl_cust, "客戶要求Max", "red", "dashdot", 1.22),
                        (val_lsl_cust, "客戶要求Min", "red", "dashdot", 1.22),
                    ]
                    
                    for val, lbl, clr, style, pos in lines_config:
                        if val is not None:
                            fig_trend.add_hline(y=val, line_dash=style, line_color=clr, line_width=2)
                            fig_trend.add_annotation(x=pos, y=val, xref="paper", text=f"<b>{lbl}: {val:.1f}</b>",
                                                     showarrow=False, font=dict(color=clr, size=11), xanchor="left")
                    
                    fig_trend.update_layout(template="plotly_white", margin=dict(r=220), xaxis_title="生產順序 (Coil No.)", yaxis_title="數值")
                    st.plotly_chart(fig_trend, use_container_width=True)

            # --- VIEW 2: I-MR CHART ---
            else:
                st.subheader("I-MR 控制圖 (統計過程控制)")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                                        subplot_titles=("單值控制圖 (Individual)", "移動極差圖 (Moving Range)"))
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='I'), row=1, col=1)
                fig_imr.add_hline(y=ucl, line_dash="dash", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=lcl, line_dash="dash", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=mu, line_color="green", row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR', line=dict(color='orange')), row=2, col=1)
                fig_imr.update_layout(height=700, template="plotly_white", showlegend=False)
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"數據讀取失敗: {e}")
else:
    st.info("👈 請在左側上傳生產日報 Excel 文件以開始分析。")
