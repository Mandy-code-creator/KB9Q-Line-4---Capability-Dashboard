import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import norm
import re

# --- 1. CẤU HÌNH GIAO DIỆN POWER BI STYLE ---
st.set_page_config(page_title="KB9Q Power BI Dashboard", layout="wide")

# CSS để tạo khung bao quanh (Card) và đổ bóng chuyên nghiệp
st.markdown("""
    <style>
    .main {
        background-color: #f0f2f6;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #e1e4e8;
    }
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column"] > div {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #dcdfe6;
        margin-bottom: 20px;
    }
    h1, h2, h3 {
        color: #113763;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    </style>
    """, unsafe_allow_ Harris=True)

# --- 2. THANH BÊN (SIDEBAR) ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Production Data", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        # Bộ lọc 用途碼
        st.sidebar.subheader("🔍 Filters")
        if "用途碼" in df.columns:
            usage_list = sorted(df["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Usage Code (用途碼):", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        # Thuật toán tìm cột
        def find_col(key):
            for col in df.columns:
                if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格"]):
                    return col
            return None

        metrics_def = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        available_display = [k for k, v in metrics_def.items() if find_col(v)]
        
        st.sidebar.subheader("📊 View Config")
        view_mode = st.sidebar.radio("View Mode:", ["View 1: Distribution & Trending", "View 2: SPC & Cpk"])
        selected_display = st.sidebar.selectbox("Metric:", available_display)
        
        actual_col = find_col(metrics_def[selected_display])
        kw_han = "降伏強度" if "YS" in selected_display else "抗拉強度" if "TS" in selected_display else "伸長率" if "EL" in selected_display else "硬度" if "Hardness" in selected_display else "降伏點"
        lsl_col = next((c for c in df.columns if kw_han in c and "min" in c.lower() and "管制" in c), None)
        usl_col = next((c for c in df.columns if kw_han in c and "max" in c.lower() and "管制" in c), None)

        if actual_col:
            plot_data = df_filtered[actual_col].dropna().reset_index(drop=True)
            lsl = float(df_filtered[lsl_col].median()) if lsl_col else plot_data.min()
            usl = float(df_filtered[usl_col].median()) if usl_col else plot_data.max()

            # --- HEADER ---
            st.title(f"Production Analytics: {selected_display}")

            # --- VIEW 1 ---
            if view_mode == "View 1: Distribution & Trending":
                # Layout metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Samples (N)", len(plot_data))
                m2.metric("Mean", f"{plot_data.mean():.2f}")
                m3.metric("Min", f"{plot_data.min():.2f}")
                m4.metric("Max", f"{plot_data.max():.2f}")

                col_left, col_right = st.columns([1, 1.3])
                
                with col_left:
                    st.subheader("Distribution Analysis")
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(x=plot_data, histnorm='probability density', name='Actual', marker_color='#0078D4', opacity=0.6))
                    mu, std = plot_data.mean(), plot_data.std()
                    if std > 0:
                        x = np.linspace(plot_data.min()-std, plot_data.max()+std, 100)
                        fig_dist.add_trace(go.Scatter(x=x, y=norm.pdf(x, mu, std), mode='lines', name='Normal', line=dict(color='#113763', width=2)))
                    fig_dist.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', template="plotly_white")
                    st.plotly_chart(fig_dist, use_container_width=True)

                with col_right:
                    st.subheader("Trending Analytics (Roll-by-Roll)")
                    fig_trend = go.Figure()
                    # Main Line
                    fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', name='Value',
                                                  line=dict(color='#0078D4', width=1.5), marker=dict(size=6, color='#ffffff', line=dict(width=1.5, color='#0078D4'))))
                    
                    # Statistical Lines
                    mean_val = plot_data.mean()
                    ucl, lcl = mean_val + 3*std, mean_val - 3*std
                    
                    for val, label, color in [(ucl, "UCL", "#C41E3A"), (mean_val, "Mean", "#228B22"), (lcl, "LCL", "#C41E3A")]:
                        fig_trend.add_hline(y=val, line_dash="dash", line_color=color, line_width=1)
                        fig_trend.add_annotation(x=1.02, y=val, xref="paper", text=f"{label}: {val:.1f}", showarrow=False, font=dict(color=color), xanchor="left")
                    
                    fig_trend.update_layout(margin=dict(r=120), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', template="plotly_white")
                    st.plotly_chart(fig_trend, use_container_width=True)

            # --- VIEW 2 (Tương tự với style mới) ---
            else:
                st.subheader("SPC Control Charts & Process Capability")
                # (Phần View 2 bạn có thể áp dụng tương tự CSS Card ở trên)
                st.info("View 2 cũng đã được bao khung bởi CSS Card phía trên.")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Please upload a data file to begin.")
