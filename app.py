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
    /* Clean industrial background */
    .main { background-color: #F4F6F9; }
    
    /* Card layout for charts */
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #D1D5DB;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }
    
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-top: 4px solid #1D4ED8;
        border-radius: 6px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Professional Typography */
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
    """Find the actual measurement column, excluding spec limit columns"""
    for col in df.columns:
        if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求"]):
            return col
    return None

def get_limit(df, keyword, limit_type, category):
    """Extract standard and target limits safely"""
    col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
    if col:
        val = pd.to_numeric(df[col], errors='coerce').median()
        return float(val) if pd.notnull(val) and val > 0 else None
    return None

# High-resolution export configuration for Word reports
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

        # Parameter mapping
        metrics_map = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB"}
        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        
        if not available:
            st.error("❌ No matching measurement columns found.")
            st.stop()

        selected_label = st.sidebar.selectbox("Select Parameter:", available)
        view_mode = st.sidebar.radio("View Mode:", ["Process Analytics", "SPC Control Charts (I-MR)"])
        
        # Identify columns
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df, short_key)
        zh_key = "降伏強度" if "YS" in short_key else "抗拉強度" if "TS" in short_key else "伸長率" if "EL" in short_key else "硬度"
        
        # Get Limits (Target = Customer, Std = Internal)
        v_lsl_std = get_limit(df, zh_key, "min", "管制")
        v_usl_std = get_limit(df, zh_key, "max", "管制")
        v_lsl_tgt = get_limit(df, zh_key, "min", "客戶要求")
        v_usl_tgt = get_limit(df, zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            # Resolve limits
            target_lsl = v_lsl_tgt if v_lsl_tgt else v_lsl_std
            target_usl = v_usl_tgt if v_usl_tgt else v_usl_std
            std_lsl = v_lsl_std if v_lsl_std else target_lsl
            std_usl = v_usl_std if v_usl_std else target_usl
            
            # Capability Calculations
            cp, cpk = None, None
            if sigma > 0:
                if target_lsl and target_usl:
                    cp = (target_usl - target_lsl) / (6 * sigma)
                    cpk = min((target_usl-mu)/(3*sigma), (mu-target_lsl)/(3*sigma))
                elif target_lsl: 
                    cpk = (mu - target_lsl)/(3*sigma)
                elif target_usl: 
                    cpk = (target_usl - mu)/(3*sigma)

            # --- TOP KPI METRICS ---
            st.title(f"📊 Quality Analytics: {selected_label}")
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Samples (N)", n)
            k2.metric("Mean (μ)", f"{mu:.2f}")
            k3.metric("Std Dev (σ)", f"{sigma:.2f}")
            k4.metric("Cpk Capability", f"{cpk:.2f}" if cpk else "N/A", delta="Pass" if cpk and cpk >= 1.33 else "Warning" if cpk else None)

            # ==========================================
            # VIEW 1: PROCESS ANALYTICS
            # ==========================================
            if view_mode == "Process Analytics":
                
                # --- CHART 1: HISTOGRAM (MINITAB STYLE) ---
                st.subheader(f"I. {selected_label} Distribution")
                
                k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                pts = [plot_data.min(), plot_data.max()]
                pts.extend([v for v in [target_lsl, target_usl, std_lsl, std_usl, lcl, ucl] if v])
                min_pt, max_pt = min(pts), max(pts)
                padding = (max_pt - min_pt) * 0.1 if max_pt != min_pt else max_pt * 0.05
                x_range = [min_pt - padding, max_pt + padding]

                # Dynamic Y-axis to fit SPC box
                counts, _ = np.histogram(plot_data, bins=k_bins)
                max_y = counts.max() * 1.35 if len(counts) > 0 else 10

                fig_dist = go.Figure()
                
                # Histogram
                fig_dist.add_trace(go.Histogram(
                    x=plot_data, nbinsx=k_bins, name='LINE Hist',
                    marker_color='#7FB3D5', marker_line_color='white', marker_line_width=1, opacity=0.8
                ))
                
                # Normal Curve
                if sigma > 0:
                    bin_w = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                    x_c = np.linspace(x_range[0], x_range[1], 400)
                    y_c = norm.pdf(x_c, mu, sigma) * n * bin_w
                    fig_dist.add_trace(go.Scatter(x=x_c, y=y_c, mode='lines', name='LINE Fit', line=dict(color='#004080', width=3)))

                # Add limit lines
                if target_lsl: fig_dist.add_vline(x=target_lsl, line_dash="dash", line_color="#FF0000", line_width=2)
                if target_usl: fig_dist.add_vline(x=target_usl, line_dash="dash", line_color="#FF0000", line_width=2)
                if std_lsl and std_lsl != target_lsl: fig_dist.add_vline(x=std_lsl, line_dash="dashdot", line_color="#800080", line_width=2)
                if std_usl and std_usl != target_usl: fig_dist.add_vline(x=std_usl, line_dash="dashdot", line_color="#800080", line_width=2)

                # Dummy traces for legend
                fig_dist.add_trace(go.Scatter(x=[None], y=[None], mode='lines', name='Target LSL/USL', line=dict(color='#FF0000', width=2, dash='dash')))
                fig_dist.add_trace(go.Scatter(x=[None], y=[None], mode='lines', name='Std LSL/USL', line=dict(color='#800080', width=2, dash='dashdot')))

                # SPC Indices Box
                cp_str = f"{cp:.2f}" if cp else "N/A"
                cpk_str = f"{cpk:.2f}" if cpk else "N/A"
                rating = "Good" if cpk and cpk >= 1.33 else "Poor" if cpk else "N/A"
                box_txt = f"<b>SPC Indices (LINE):</b><br>N = {n}<br>Mean = {mu:.2f}<br>Std = {sigma:.2f}<br>Cp = {cp_str}<br>Cpk = {cpk_str}<br>Rating: {rating}"
                
                fig_dist.add_annotation(
                    xref="paper", yref="paper", x=0.02, y=0.96, text=box_txt, showarrow=False, align="left",
                    font=dict(size=12, family="Courier New, monospace", color="black"),
                    bgcolor="#F9FAFB", bordercolor="#D1D5DB", borderwidth=1, borderpad=8, xanchor="left", yanchor="top"
                )

                fig_dist.update_layout(
                    title=dict(text=f"<b>{selected_label} Distribution</b>", x=0.5, font=dict(size=16)),
                    plot_bgcolor='white', paper_bgcolor='white',
                    height=500, xaxis_range=x_range, yaxis_range=[0, max_y],
                    xaxis_title="Measurement Value", yaxis_title="Number of Coils",
                    legend=dict(x=0.98, y=0.98, xanchor="right", yanchor="top", bgcolor="white", bordercolor="#D1D5DB", borderwidth=1)
                )
                
                fig_dist.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True, showgrid=True, gridcolor='#F3F4F6')
                fig_dist.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True, showgrid=True, gridcolor='#F3F4F6')

                st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

                # --- CHART 2: TREND BY SEQUENCE (BOTTOM LEGEND STYLE) ---
                st.subheader(f"II. {selected_label} Trend by Coil Sequence")
                fig_trend = go.Figure()

                # 1. Target Zone (Green Background)
                if target_lsl and target_usl:
                    fig_trend.add_hrect(y0=target_lsl, y1=target_usl, fillcolor="#E8F5E9", opacity=0.4, layer="below", line_width=0)
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(size=12, color='#E8F5E9', symbol='square', line=dict(color='black', width=1)), name='Target Zone'))

                # 2. Add Horizontal Limits (with Legend Traces)
                if target_usl:
                    fig_trend.add_hline(y=target_usl, line_dash="dash", line_color="#2E7D32", line_width=2)
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='#2E7D32', width=2, dash='dash'), name=f'Target USL={target_usl}'))
                
                if target_lsl:
                    fig_trend.add_hline(y=target_lsl, line_dash="dash", line_color="#2E7D32", line_width=2)
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='#2E7D32', width=2, dash='dash'), name=f'Target LSL={target_lsl}'))
                
                if std_usl and std_usl != target_usl:
                    fig_trend.add_hline(y=std_usl, line_dash="dash", line_color="#D32F2F", line_width=2)
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='#D32F2F', width=2, dash='dash'), name=f'Std USL={std_usl}'))
                
                if std_lsl and std_lsl != target_lsl:
                    fig_trend.add_hline(y=std_lsl, line_dash="dash", line_color="#D32F2F", line_width=2)
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='#D32F2F', width=2, dash='dash'), name=f'Std LSL={std_lsl}'))

                # 3. Main Data (Blue Squares)
                fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', 
                                              name='LINE', line=dict(color='#1F77B4', width=2),
                                              marker=dict(symbol='square', size=6, color='#1F77B4')))

                # 4. Out of Control Markers (Big Red Dots)
                ooc_idx, ooc_vals = [], []
                for i, val in enumerate(plot_data):
                    is_ooc = False
                    if std_usl and val > std_usl: is_ooc = True
                    if std_lsl and val < std_lsl: is_ooc = True
                    if is_ooc:
                        ooc_idx.append(i)
                        ooc_vals.append(val)
                
                if ooc_idx:
                    fig_trend.add_trace(go.Scatter(x=ooc_idx, y=ooc_vals, mode='markers', 
                                                  name='Out of Control', marker=dict(color='#FF0000', size=12, symbol='circle')))

                # 5. Layout Configuration (Bottom Horizontal Legend)
                fig_trend.update_layout(
                    title=dict(text=f"<b>{selected_label} Trend by Coil Sequence</b>", x=0.5, font=dict(size=16)),
                    template="simple_white", height=550,
                    xaxis_title="Sequence", yaxis_title="Measurement Value",
                    legend=dict(
                        orientation="h", x=0.5, xanchor="center", y=-0.2, yanchor="top",
                        bgcolor="rgba(255,255,255,0)", borderwidth=0
                    ),
                    margin=dict(l=50, r=50, t=50, b=100) # Ensure bottom space for legend
                )
                
                fig_trend.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
                fig_trend.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
                
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
                fig_imr.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
                fig_imr.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
                
                st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"Data Processing Error: {e}")
else:
    st.info("👈 Please upload the production data report to begin.")
