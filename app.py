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
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
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
        
        # Mapping Vietnamese/Chinese keywords for limits
        zh_map = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}
        zh_key = zh_map.get(short_key, short_key)
        
        # Extract Limits
        v_lsl_std = get_limit(df, zh_key, "min", "管制")
        v_usl_std = get_limit(df, zh_key, "max", "管制")
        v_lsl_tgt = get_limit(df, zh_key, "min", "客戶要求")
        v_usl_tgt = get_limit(df, zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            # Capability Calculations
            cp, cpk = None, None
            if sigma > 0:
                if v_lsl_std and v_usl_std:
                    cp = (v_usl_std - v_lsl_std) / (6 * sigma)
                    cpk = min((v_usl_std - mu)/(3*sigma), (mu - v_lsl_std)/(3*sigma))
                elif v_lsl_std: cpk = (mu - v_lsl_std)/(3*sigma)
                elif v_usl_std: cpk = (v_usl_std - mu)/(3*sigma)

            st.title(f"📊 Quality Analytics: {selected_label}")
            
            # --- TOP KPI METRICS ---
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Samples (N)", n)
            k2.metric("Mean (μ)", f"{mu:.2f}")
            k3.metric("Std Dev (σ)", f"{sigma:.2f}")
            status = "Pass" if cpk and cpk >= 1.33 else "Warning"
            k4.metric("Cpk (Internal)", f"{cpk:.2f}" if cpk else "N/A", delta=status if cpk else None)

            # ==========================================
            # VIEW 1: PROCESS ANALYTICS
            # ==========================================
            if view_mode == "Process Analytics":
                
                # --- CHART 1: DISTRIBUTION ---
                st.subheader("I. Distribution & Capability")
                
                k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                pts = [v for v in [v_lsl_tgt, v_usl_tgt, v_lsl_std, v_usl_std, plot_data.min(), plot_data.max()] if v is not None]
                x_range = [min(pts) - abs(min(pts)*0.1), max(pts) + abs(max(pts)*0.1)]

                fig_dist = go.Figure()
                fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, name='Data', marker_color='#7FB3D5', opacity=0.7))
                
                if sigma > 0:
                    x_c = np.linspace(x_range[0], x_range[1], 200)
                    bin_w = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                    y_c = norm.pdf(x_c, mu, sigma) * n * bin_w
                    fig_dist.add_trace(go.Scatter(x=x_c, y=y_c, mode='lines', name='Normal', line=dict(color='#1E3A8A', width=2)))

                # Function to add labeled vlines
                def add_dist_limit(val, label, color, dash, y_pos):
                    if val is not None:
                        fig_dist.add_vline(x=val, line_dash=dash, line_color=color, line_width=2)
                        fig_dist.add_annotation(x=val, y=y_pos, yref="paper", text=f"{label}:{val:.1f}", 
                                              showarrow=False, font=dict(color=color, size=10), bgcolor="white", yshift=10)

                add_dist_limit(v_lsl_tgt, "Cust LSL", "#2E7D32", "solid", 0.95)
                add_dist_limit(v_usl_tgt, "Cust USL", "#2E7D32", "solid", 0.95)
                add_dist_limit(v_lsl_std, "Int LSL", "#D32F2F", "dash", 0.82)
                add_dist_limit(v_usl_std, "Int USL", "#D32F2F", "dash", 0.82)

                fig_dist.update_layout(template="simple_white", height=500, xaxis_range=x_range, showlegend=False, margin=dict(t=80))
                st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

                # --- CHART 2: TREND BY SEQUENCE ---
                st.subheader("II. Trend Analysis")
                fig_trend = go.Figure()

                # Highlight customer zone
                if v_lsl_tgt and v_usl_tgt:
                    fig_trend.add_hrect(y0=v_lsl_tgt, y1=v_usl_tgt, fillcolor="#E8F5E9", opacity=0.3, layer="below", line_width=0)

                limits = [
                    (v_usl_tgt, "Cust USL", "#2E7D32", "solid"), (v_lsl_tgt, "Cust LSL", "#2E7D32", "solid"),
                    (v_usl_std, "Int USL", "#D32F2F", "dash"), (v_lsl_std, "Int LSL", "#D32F2F", "dash"),
                    (ucl, "UCL", "#E67E22", "dot"), (lcl, "LCL", "#E67E22", "dot"), (mu, "Mean", "#8E44AD", "dashdot")
                ]

                for val, name, color, dash in limits:
                    if val is not None:
                        fig_trend.add_hline(y=val, line_dash=dash, line_color=color)
                        fig_trend.add_annotation(x=1.01, y=val, xref="paper", text=f"<b>{name}:{val:.1f}</b>", 
                                               showarrow=False, font=dict(color=color, size=10), xanchor="left")

                fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', 
                                            line=dict(color='#1F77B4', width=2), marker=dict(size=6, symbol='square')))
                
                # Out of spec points
                ooc = plot_data[(plot_data > (v_usl_std or 9999)) | (plot_data < (v_lsl_std or -9999))]
                if not ooc.empty:
                    fig_trend.add_trace(go.Scatter(x=ooc.index, y=ooc, mode='markers', name='Alert', 
                                                marker=dict(color='red', size=10, symbol='circle-open', line_width=2)))

                fig_trend.update_layout(template="simple_white", height=600, margin=dict(r=120, t=50), showlegend=False)
                st.plotly_chart(fig_trend, use_container_width=True, config=export_config)

            # ==========================================
            # VIEW 2: SPC I-MR
            # ==========================================
            else:
                st.subheader("III. SPC Control Charts (I-MR)")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, 
                                      subplot_titles=("Individual Chart (I)", "Moving Range Chart (MR)"))
                
                # I-Chart
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', line=dict(color='#1F77B4')), row=1, col=1)
                for val, name, color in [(ucl, 'UCL', 'red'), (lcl, 'LCL', 'red'), (mu, 'Mean', 'green')]:
                    fig_imr.add_hline(y=val, line_dash="dash", line_color=color, row=1, col=1)
                
                # MR-Chart
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', line=dict(color='#1F77B4')), row=2, col=1)
                mr_mean = mr.mean()
                fig_imr.add_hline(y=mr_mean, line_dash="dash", line_color="green", row=2, col=1)
                fig_imr.add_hline(y=mr_mean * 3.267, line_dash="dash", line_color="red", row=2, col=1) # UCL for MR

                fig_imr.update_layout(height=700, template="simple_white", showlegend=False)
                st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Please upload the production data report (Excel/CSV) to begin.")
