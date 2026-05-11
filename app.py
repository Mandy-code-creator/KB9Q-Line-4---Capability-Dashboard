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
    .main { background-color: #F4F6F9; }
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #D1D5DB;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-top: 4px solid #1D4ED8;
        border-radius: 6px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    h1, h2, h3 { 
        color: #1E3A8A !important; 
        font-family: 'Arial', sans-serif !important; 
        font-weight: 700 !important;
    }
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
    'toImageButtonOptions': {'format': 'png', 'filename': 'Quality_Chart', 'height': 600, 'width': 1200, 'scale': 2}
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
        view_mode = st.sidebar.radio("View Mode:", ["Process Analytics", "SPC Control Charts (I-MR)"])
        
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df, short_key)
        
        if "YS" in short_key: zh_key = "降伏強度"
        elif "TS" in short_key: zh_key = "抗拉強度"
        elif "EL" in short_key: zh_key = "伸長率"
        elif "HRB" in short_key: zh_key = "硬度"
        else: zh_key = "YPE"
        
        v_lsl_std = get_limit(df, zh_key, "min", "管制")
        v_usl_std = get_limit(df, zh_key, "max", "管制")
        v_lsl_tgt = get_limit(df, zh_key, "min", "客戶要求")
        v_usl_tgt = get_limit(df, zh_key, "max", "客戶 yêu cầu")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            target_lsl = v_lsl_tgt if v_lsl_tgt else v_lsl_std
            target_usl = v_usl_tgt if v_usl_tgt else v_usl_std
            std_lsl = v_lsl_std if v_lsl_std else target_lsl
            std_usl = v_usl_std if v_usl_std else target_usl
            
            cp, cpk = None, None
            if sigma > 0:
                if v_lsl_std and v_usl_std:
                    cp = (v_usl_std - v_lsl_std) / (6 * sigma)
                    cpk = min((v_usl_std - mu)/(3*sigma), (mu - v_lsl_std)/(3*sigma))
                elif v_lsl_std: cpk = (mu - v_lsl_std)/(3*sigma)
                elif v_usl_std: cpk = (v_usl_std - mu)/(3*sigma)

            st.title(f"📊 Quality Analytics: {selected_label}")
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Samples (N)", n)
            k2.metric("Mean (μ)", f"{mu:.2f}")
            k3.metric("Std Dev (σ)", f"{sigma:.2f}")
            k4.metric("Cpk (Internal)", f"{cpk:.2f}" if cpk else "N/A", delta="Pass" if cpk and cpk >= 1.33 else "Warning" if cpk else None)

            # ==========================================
            # VIEW 1: PROCESS ANALYTICS
            # ==========================================
            if view_mode == "Process Analytics":
                st.subheader(f"I. {selected_label} Distribution")
                
                k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                pts = [plot_data.min(), plot_data.max()]
                pts.extend([v for v in [target_lsl, target_usl, std_lsl, std_usl, lcl, ucl] if v])
                min_pt, max_pt = min(pts), max(pts)
                padding = (max_pt - min_pt) * 0.1 if max_pt != min_pt else max_pt * 0.05
                x_range = [min_pt - padding, max_pt + padding]

                counts, _ = np.histogram(plot_data, bins=k_bins)
                max_y = counts.max() * 1.35 if len(counts) > 0 else 10

                fig_dist = go.Figure()
                fig_dist.add_trace(go.Histogram(
                    x=plot_data, nbinsx=k_bins, name='Actual Data',
                    marker_color='#7FB3D5', marker_line_color='white', marker_line_width=1, opacity=0.8
                ))
                
                if sigma > 0:
                    bin_w = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                    x_c = np.linspace(x_range[0], x_range[1], 400)
                    y_c = norm.pdf(x_c, mu, sigma) * n * bin_w
                    fig_dist.add_trace(go.Scatter(x=x_c, y=y_c, mode='lines', name='Normal Fit', line=dict(color='#004080', width=3)))

                # Thêm đường giới hạn
                if v_lsl_tgt: fig_dist.add_vline(x=v_lsl_tgt, line_dash="solid", line_color="#2E7D32", line_width=2)
                if v_usl_tgt: fig_dist.add_vline(x=v_usl_tgt, line_dash="solid", line_color="#2E7D32", line_width=2)
                if v_lsl_std: fig_dist.add_vline(x=v_lsl_std, line_dash="dash", line_color="#D32F2F", line_width=2)
                if v_usl_std: fig_dist.add_vline(x=v_usl_std, line_dash="dash", line_color="#D32F2F", line_width=2)

                # Annotations logic giữ nguyên của bạn
                cp_str, cpk_str = (f"{cp:.2f}" if cp else "N/A"), (f"{cpk:.2f}" if cpk else "N/A")
                rating = "Good" if cpk and cpk >= 1.33 else "Poor" if cpk else "N/A"
                box_txt = f"<b>SPC Indices (Internal):</b><br>N = {n}<br>Mean = {mu:.2f}<br>Std = {sigma:.2f}<br>Cp = {cp_str}<br>Cpk = {cpk_str}<br>Rating: {rating}"
                
                fig_dist.add_annotation(
                    xref="paper", yref="paper", x=0.02, y=0.96, text=box_txt, showarrow=False, align="left",
                    font=dict(size=12, family="Courier New, monospace", color="black"),
                    bgcolor="#F9FAFB", bordercolor="#D1D5DB", borderwidth=1, borderpad=8, xanchor="left", yanchor="top"
                )

                fig_dist.update_layout(
                    title=dict(text=f"<b>{selected_label} Distribution</b>", x=0.5, font=dict(size=16)),
                    plot_bgcolor='white', paper_bgcolor='white',
                    height=500, xaxis_range=x_range, yaxis_range=[0, max_y],
                    xaxis_title="Measurement Value", yaxis_title="Number of Coils"
                )
                
                # SỬA KHUNG VIỀN: mirror=True để kín 4 cạnh
                fig_dist.update_xaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True, showgrid=True, gridcolor='#F3F4F6')
                fig_dist.update_yaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True, showgrid=True, gridcolor='#F3F4F6')

                st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

                st.subheader(f"II. {selected_label} Trend by Coil Sequence")
                fig_trend = go.Figure()
                
                # Logic Trend vẽ vùng và các đường của bạn
                if v_lsl_tgt and v_usl_tgt:
                    fig_trend.add_hrect(y0=v_lsl_tgt, y1=v_usl_tgt, fillcolor="#E8F5E9", opacity=0.4, layer="below", line_width=0)
                
                # Các đường giới hạn trên Trend
                lines = [(v_usl_tgt, "solid", "#2E7D32"), (v_lsl_tgt, "solid", "#2E7D32"), 
                         (v_usl_std, "dash", "#D32F2F"), (v_lsl_std, "dash", "#D32F2F"),
                         (ucl, "dot", "#E67E22"), (lcl, "dot", "#E67E22"), (mu, "dashdot", "#8E44AD")]
                
                for val, dash, color in lines:
                    if val: fig_trend.add_hline(y=val, line_dash=dash, line_color=color, line_width=2)

                fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', 
                                              line=dict(color='#1F77B4', width=2), marker=dict(symbol='square', size=6)))

                fig_trend.update_layout(
                    title=dict(text=f"<b>{selected_label} Trend by Coil Sequence</b>", x=0.5, font=dict(size=16)),
                    template="simple_white", height=600, xaxis_title="Sequence", yaxis_title="Measurement Value",
                    margin=dict(l=50, r=50, t=50, b=120) 
                )
                
                # SỬA KHUNG VIỀN: mirror=True để kín 4 cạnh
                fig_trend.update_xaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True)
                fig_trend.update_yaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True)
                
                st.plotly_chart(fig_trend, use_container_width=True, config=export_config)

            # ==========================================
            # VIEW 2: SPC I-MR CHARTS
            # ==========================================
            else:
                st.subheader("III. Statistical Process Control (I-MR)")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=("Individual Chart (I)", "Moving Range Chart (MR)"))
                
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', line=dict(color='#1F77B4'), marker=dict(size=5)), row=1, col=1)
                fig_imr.add_hline(y=ucl, line_dash="dash", line_color="#D32F2F", row=1, col=1)
                fig_imr.add_hline(y=lcl, line_dash="dash", line_color="#D32F2F", row=1, col=1)
                fig_imr.add_hline(y=mu, line_dash="dash", line_color="#2E7D32", row=1, col=1)
                
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', line=dict(color='#1F77B4'), marker=dict(size=5)), row=2, col=1)
                
                fig_imr.update_layout(height=700, template="simple_white", showlegend=False)
                
                # SỬA KHUNG VIỀN: mirror=True cho cả subplots
                fig_imr.update_xaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True)
                fig_imr.update_yaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True)
                
                st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"Data Processing Error: {e}")
else:
    st.info("👈 Please upload the production data report to begin.")
