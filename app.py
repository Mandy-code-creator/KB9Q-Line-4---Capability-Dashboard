import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# ==========================================
# 1. PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(page_title="Line 4 Quality Analytics", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #F8FAFC; }
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-left: 5px solid #1E40AF;
        border-radius: 4px;
        padding: 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    h1, h2, h3 { color: #1E3A8A !important; font-family: 'Segoe UI', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. UTILITY FUNCTIONS
# ==========================================
def find_data_col(df, key):
    for col in df.columns:
        if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求"]):
            return col
    return None

def get_limit(df, keyword, limit_type, category):
    col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
    if col:
        val = pd.to_numeric(df[col], errors='coerce').median()
        return float(val) if pd.notnull(val) and val > 0 else None
    return None

export_config = {
    'displayModeBar': True, 
    'displaylogo': False,
    'toImageButtonOptions': {'format': 'png', 'filename': 'Quality_Report', 'height': 700, 'width': 1200, 'scale': 2}
}

# ==========================================
# 3. SIDEBAR & DATA PROCESSING
# ==========================================
st.sidebar.header("📂 DATA SOURCE")
uploaded_file = st.sidebar.file_uploader("Upload Excel/CSV Report", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df_raw.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df_raw.columns]

        if "用途碼" in df_raw.columns:
            usage_list = sorted(df_raw["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Filter Usage Code:", options=usage_list, default=usage_list)
            df = df_raw[df_raw["用途碼"].isin(selected_usages)]
        else:
            df = df_raw

        metrics_map = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        
        if not available:
            st.error("❌ No matching measurement columns found.")
            st.stop()

        selected_label = st.sidebar.selectbox("Select Parameter:", available)
        view_mode = st.sidebar.radio("View Mode:", ["Process Analytics", "SPC Control Charts"])
        
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df, short_key)
        zh_map = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}
        zh_key = zh_map.get(short_key, short_key)
        
        v_lsl_std = get_limit(df, zh_key, "min", "管制")
        v_usl_std = get_limit(df, zh_key, "max", "管制")
        v_lsl_tgt = get_limit(df, zh_key, "min", "客戶要求")
        v_usl_tgt = get_limit(df, zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            cpk = None
            if sigma > 0 and v_lsl_std and v_usl_std:
                cpk = min((v_usl_std - mu)/(3*sigma), (mu - v_lsl_std)/(3*sigma))

            st.title(f"📊 Quality Analytics: {selected_label}")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Samples (N)", n)
            k2.metric("Mean (μ)", f"{mu:.2f}")
            k3.metric("Std Dev (σ)", f"{sigma:.2f}")
            k4.metric("Cpk (Internal)", f"{cpk:.2f}" if cpk else "N/A")

            # ==========================================
            # CHẾ ĐỘ 1: PROCESS ANALYTICS
            # ==========================================
            if view_mode == "Process Analytics":
                st.subheader("I. Distribution & Capability")
                k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                pts = [v for v in [v_lsl_tgt, v_usl_tgt, v_lsl_std, v_usl_std, plot_data.min(), plot_data.max()] if v is not None]
                x_range = [min(pts)*0.95, max(pts)*1.05]

                fig_dist = go.Figure()
                fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, marker_color='#7FB3D5', opacity=0.8, marker_line_color='white'))
                
                def add_smart_vline(fig, val, name, color, dash, pos):
                    if val is not None:
                        fig.add_vline(x=val, line_dash=dash, line_color=color, line_width=2.5,
                                    annotation_text=f"<b>{name}:<br>{val:.1f}</b>", annotation_position=pos,
                                    annotation_font=dict(size=10, color=color), annotation_bgcolor="rgba(255,255,255,0.85)")

                add_smart_vline(fig_dist, v_lsl_tgt, "Cust LSL", "#2E7D32", "solid", "top left")
                add_smart_vline(fig_dist, v_usl_tgt, "Cust USL", "#2E7D32", "solid", "top right")
                add_smart_vline(fig_dist, v_lsl_std, "Int LSL", "#D32F2F", "dash", "top right")
                add_smart_vline(fig_dist, v_usl_std, "Int USL", "#D32F2F", "dash", "top left")

                # SỬA KHUNG VIỀN: mirror=True tạo hình hộp kín
                fig_dist.update_layout(template="simple_white", height=500, xaxis_range=x_range, margin=dict(t=80, b=40, l=40, r=40))
                fig_dist.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                fig_dist.update_yaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                st.plotly_chart(fig_dist, use_container_width=True)

                st.subheader("II. Trend Analysis")
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(y=plot_data, mode='lines+markers', line=dict(color='#1F77B4', width=2), marker=dict(size=7)))
                
                def add_smart_hline(fig, val, name, color, dash, pos):
                    if val is not None:
                        fig.add_hline(y=val, line_dash=dash, line_color=color, line_width=2.5,
                                    annotation_text=f"<b>{name}: {val:.1f}</b>", annotation_position=pos,
                                    annotation_font=dict(size=10, color=color), annotation_bgcolor="rgba(255,255,255,0.85)")

                add_smart_hline(fig_trend, v_usl_tgt, "Cust USL", "#2E7D32", "solid", "top right")
                add_smart_hline(fig_trend, v_lsl_std, "Int LSL", "#D32F2F", "dash", "top right")
                add_smart_hline(fig_trend, mu, "Mean", "#8E44AD", "dashdot", "top left")

                # SỬA KHUNG VIỀN: mirror=True tạo hình hộp kín
                fig_trend.update_layout(template="simple_white", height=600, margin=dict(t=50, r=20, l=40, b=40))
                fig_trend.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                fig_trend.update_yaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                st.plotly_chart(fig_trend, use_container_width=True)

            # ==========================================
            # CHẾ ĐỘ 2: SPC I-MR
            # ==========================================
            else:
                st.subheader("III. Statistical Process Control (I-MR)")
                mr = plot_data.diff().abs()
                mr_ucl = mr.mean() * 3.267
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.15,
                                      subplot_titles=("Individual Chart (I)", "Moving Range Chart (MR)"))
                
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='I'), row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR'), row=2, col=1)

                def add_imr_line(fig, val, label, color, row):
                    if val is not None:
                        fig.add_hline(y=val, line_dash="dash", line_color=color, line_width=2.5,
                                    annotation_text=f"<b>{label}: {val:.1f}</b>", annotation_position="top right",
                                    annotation_font=dict(color=color), row=row, col=1)

                add_imr_line(fig_imr, ucl, 'UCL', 'red', 1)
                add_imr_line(fig_imr, lcl, 'LCL', 'red', 1)
                add_imr_line(fig_imr, mu, 'Mean', 'green', 1)
                add_imr_line(fig_imr, mr_ucl, 'MR UCL', 'red', 2)

                # SỬA KHUNG VIỀN: Áp dụng mirror cho cả các subplot
                fig_imr.update_layout(height=750, template="simple_white", showlegend=False, margin=dict(r=80, t=60))
                fig_imr.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                fig_imr.update_yaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                
                # Chống tiêu đề đè lên khung
                for ann in fig_imr['layout']['annotations']: ann['y'] += 0.03
                
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Please upload the production data report (Excel/CSV) to begin.")
