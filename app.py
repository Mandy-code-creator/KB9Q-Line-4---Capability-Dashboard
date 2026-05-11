import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. DASHBOARD CONFIGURATION ---
st.set_page_config(page_title="Line 4 Quality Analytics System", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #F0F4F8; }
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 12px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 25px;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-top: 5px solid #113763;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    h1, h2, h3 { 
        color: #113763 !important; 
        font-family: 'Segoe UI', Tahoma, sans-serif !important; 
        font-weight: 800 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA PROCESSING FUNCTIONS ---
def find_data_col(df, key):
    for col in df.columns:
        if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求"]):
            return col
    return None

def get_valid_limit(df, keyword, limit_type, category):
    col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
    if col:
        val = pd.to_numeric(df[col], errors='coerce').median()
        return float(val) if pd.notnull(val) and val > 0 else None
    return None

export_config = {
    'displayModeBar': True, 
    'displaylogo': False,
    'toImageButtonOptions': {
        'format': 'png', 
        'filename': 'Quality_Analytics_Chart',
        'height': 600,
        'width': 1200,
        'scale': 2 
    }
}

# --- 3. SIDEBAR ---
st.sidebar.header("📂 DATA SOURCE")
uploaded_file = st.sidebar.file_uploader("Upload Data Report (Excel/CSV)", type=["xlsx", "csv", "xls"])

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

        metrics_map = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB"}
        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        
        if not available:
            st.error("❌ No matching data columns found.")
            st.stop()

        selected_label = st.sidebar.selectbox("Mechanical Parameter:", available)
        view_mode = st.sidebar.radio("Display Settings:", ["Overall Analysis (View 1)", "SPC Control Charts (View 2)"])
        
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df, short_key)
        zh_key = "降伏強度" if "YS" in short_key else "抗拉強度" if "TS" in short_key else "伸長率" if "EL" in short_key else "硬度"
        
        v_lsl_int = get_valid_limit(df, zh_key, "min", "管制")
        v_usl_int = get_valid_limit(df, zh_key, "max", "管制")
        v_lsl_cust = get_valid_limit(df, zh_key, "min", "客戶要求")
        v_usl_cust = get_valid_limit(df, zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            # Define target and standard limits mapping
            target_lsl = v_lsl_cust if v_lsl_cust else v_lsl_int
            target_usl = v_usl_cust if v_usl_cust else v_usl_int
            std_lsl = v_lsl_int if v_lsl_int else target_lsl
            std_usl = v_usl_int if v_usl_int else target_usl
            
            cp, cpk = None, None
            if sigma > 0:
                if target_lsl and target_usl:
                    cp = (target_usl - target_lsl) / (6 * sigma)
                    cpk = min((target_usl-mu)/(3*sigma), (mu-target_lsl)/(3*sigma))
                elif target_lsl: 
                    cpk = (mu - target_lsl)/(3*sigma)
                elif target_usl: 
                    cpk = (target_usl - mu)/(3*sigma)

            st.title(f"🚀 Quality Analytics: {selected_label}")
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Samples (N)", n)
            k2.metric("Mean (μ)", f"{mu:.2f}")
            k3.metric("Std Deviation (σ)", f"{sigma:.2f}")
            k4.metric("Cpk Capability", f"{cpk:.2f}" if cpk else "N/A", delta="Pass" if cpk and cpk >= 1.33 else "Warning" if cpk else None)

            if "View 1" in view_mode:
                
                # ==========================================
                # 1. DISTRIBUTION CHART (Histogram)
                # ==========================================
                st.subheader("I. Distribution State (Histogram)")
                
                k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                pts = [plot_data.min(), plot_data.max()]
                all_lims = [v for v in [target_lsl, target_usl, std_lsl, std_usl, lcl, ucl] if v]
                pts.extend(all_lims)
                min_pt, max_pt = min(pts), max(pts)
                padding = (max_pt - min_pt) * 0.1 if max_pt != min_pt else max_pt * 0.05
                x_range = [min_pt - padding, max_pt + padding]

                counts, _ = np.histogram(plot_data, bins=k_bins)
                max_count = counts.max() if len(counts) > 0 else 10
                bin_w = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                y_c_max = norm.pdf(mu, mu, sigma) * n * bin_w if sigma > 0 else 0
                max_y_axis = max(max_count, y_c_max) * 1.35 

                fig_dist = go.Figure()
                
                fig_dist.add_trace(go.Histogram(
                    x=plot_data, nbinsx=k_bins, name='LINE Hist',
                    marker_color='#85B4D3', marker_line_color='white', marker_line_width=1, opacity=0.9
                ))
                
                if sigma > 0:
                    x_c = np.linspace(x_range[0], x_range[1], 400)
                    y_c = norm.pdf(x_c, mu, sigma) * n * bin_w
                    fig_dist.add_trace(go.Scatter(
                        x=x_c, y=y_c, mode='lines', name='LINE Fit',
                        line=dict(color='#003F88', width=3)
                    ))

                if target_lsl: fig_dist.add_vline(x=target_lsl, line_dash="dash", line_color="#FF0000", line_width=2)
                if target_usl: fig_dist.add_vline(x=target_usl, line_dash="dash", line_color="#FF0000", line_width=2)
                if std_lsl and std_lsl != target_lsl: fig_dist.add_vline(x=std_lsl, line_dash="dashdot", line_color="#800080", line_width=2)
                if std_usl and std_usl != target_usl: fig_dist.add_vline(x=std_usl, line_dash="dashdot", line_color="#800080", line_width=2)

                fig_dist.add_trace(go.Scatter(x=[None], y=[None], mode='lines', name='Target LSL/USL', line=dict(color='#FF0000', width=2, dash='dash')))
                fig_dist.add_trace(go.Scatter(x=[None], y=[None], mode='lines', name='Std LSL/USL', line=dict(color='#800080', width=2, dash='dashdot')))

                cp_text = f"{cp:.2f}" if cp else "N/A"
                cpk_text = f"{cpk:.2f}" if cpk else "N/A"
                rating = "Good" if cpk and cpk >= 1.33 else "Poor" if cpk else "N/A"
                
                box_text = f"<b>SPC Indices (LINE):</b><br>N = {n}<br>Mean = {mu:.2f}<br>Std = {sigma:.2f}<br>Cp = {cp_text}<br>Cpk = {cpk_text}<br>Rating: {rating}"
                
                fig_dist.add_annotation(
                    xref="paper", yref="paper", x=0.02, y=0.96,
                    text=box_text, showarrow=False, align="left",
                    font=dict(size=12, family="Courier New, monospace", color="black"),
                    bgcolor="rgba(250, 250, 250, 0.9)", bordercolor="#D3D3D3", borderwidth=1, borderpad=8,
                    xanchor="left", yanchor="top"
                )

                fig_dist.update_layout(
                    title=dict(text=f"<b>{selected_label} Distribution</b>", x=0.5, font=dict(size=16)),
                    plot_bgcolor='white', paper_bgcolor='white',
                    height=500, xaxis_range=x_range, yaxis_range=[0, max_y_axis],
                    xaxis_title="Value", yaxis_title="Number of Coils",
                    legend=dict(x=0.98, y=0.98, xanchor="right", yanchor="top", bgcolor="rgba(255, 255, 255, 0.9)", bordercolor="#D3D3D3", borderwidth=1)
                )
                
                fig_dist.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True, showgrid=True, gridcolor='#E5E5E5')
                fig_dist.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True, showgrid=True, gridcolor='#E5E5E5')

                st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

                # ==========================================
                # 2. TREND CHART (Bottom Legend Layout)
                # ==========================================
                st.subheader("II. Trend by Coil Sequence")
                fig_trend = go.Figure()

                # Add Target Zone Shading
                if target_lsl and target_usl:
                    fig_trend.add_hrect(y0=target_lsl, y1=target_usl, fillcolor="#e8f4e9", opacity=0.5, layer="below", line_width=0)
                    # Dummy trace for Target Zone Legend
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(size=15, color='#e8f4e9', symbol='square'), name='Target Zone'))

                # Limit Lines & Legend Entries
                if target_usl:
                    fig_trend.add_hline(y=target_usl, line_dash="dash", line_color="green", line_width=2)
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='green', width=2, dash='dash'), name=f'Target USL={target_usl}'))
                if target_lsl:
                    fig_trend.add_hline(y=target_lsl, line_dash="dash", line_color="green", line_width=2)
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='green', width=2, dash='dash'), name=f'Target LSL={target_lsl}'))
                
                if std_usl and std_usl != target_usl:
                    fig_trend.add_hline(y=std_usl, line_dash="dash", line_color="red", line_width=2)
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='red', width=2, dash='dash'), name=f'Std USL={std_usl}'))
                if std_lsl and std_lsl != target_lsl:
                    fig_trend.add_hline(y=std_lsl, line_dash="dash", line_color="red", line_width=2)
                    fig_trend.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='red', width=2, dash='dash'), name=f'Std LSL={std_lsl}'))

                # Plot Main Data
                fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', 
                                              name='LINE', line=dict(color='#1f77b4', width=2),
                                              marker=dict(symbol='square', size=6, color='#1f77b4')))

                # Detect and Plot 'Out of Control' Points
                ooc_x, ooc_y = [], []
                for i, val in enumerate(plot_data):
                    if (std_usl and val > std_usl) or (std_lsl and val < std_lsl):
                        ooc_x.append(i)
                        ooc_y.append(val)
                if ooc_x:
                    fig_trend.add_trace(go.Scatter(x=ooc_x, y=ooc_y, mode='markers', 
                                                  name='Out of Control', marker=dict(color='red', size=10, symbol='circle')))

                # Layout configuration
                fig_trend.update_layout(
                    title=dict(text=f"<b>{selected_label} Trend by Coil Sequence</b>", x=0.5, font=dict(size=16)),
                    template="simple_white", height=550,
                    xaxis_title="", yaxis_title="",
                    legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.15, yanchor="top")
                )
                
                # Framing the chart
                fig_trend.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
                fig_trend.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
                
                st.plotly_chart(fig_trend, use_container_width=True, config=export_config)

            else:
                st.subheader("SPC I-MR Control Charts")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=("I-Chart", "MR-Chart"))
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', line=dict(color='#1f77b4'), marker=dict(size=4)), row=1, col=1)
                fig_imr.add_hline(y=ucl, line_dash="dash", line_color="#FF0000", row=1, col=1)
                fig_imr.add_hline(y=lcl, line_dash="dash", line_color="#FF0000", row=1, col=1)
                fig_imr.add_hline(y=mu, line_dash="dash", line_color="#008000", row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', line=dict(color='#1f77b4'), marker=dict(size=4)), row=2, col=1)
                fig_imr.update_layout(height=750, template="simple_white", showlegend=False)
                
                fig_imr.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
                fig_imr.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
                
                st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"System Error: {e}")
else:
    st.info("👈 Upload production data report on the sidebar to begin.")
