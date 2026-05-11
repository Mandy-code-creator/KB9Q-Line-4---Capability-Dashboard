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
# 2. UTILITY & CACHING
# ==========================================
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]
    return df

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

def add_smart_line(fig, axis, val, name, color, dash, pos, row=None, col=None):
    """Vẽ đường giới hạn kèm nhãn in đậm, sắc nét"""
    if val is None: return
    line_args = dict(line_dash=dash, line_color=color, line_width=2.5, opacity=1,
                     annotation_text=f"<b>{name}:<br>{val:.1f}</b>" if axis == 'x' else f"<b>{name}: {val:.1f}</b>",
                     annotation_position=pos,
                     annotation_font=dict(size=10, color=color),
                     annotation_bgcolor="rgba(255,255,255,0.85)")
    if row: # Dùng cho Subplots (I-MR)
        if axis == 'x': fig.add_vline(x=val, row=row, col=col, **line_args)
        else: fig.add_hline(y=val, row=row, col=col, **line_args)
    else: # Dùng cho biểu đồ đơn
        if axis == 'x': fig.add_vline(x=val, **line_args)
        else: fig.add_hline(y=val, **line_args)

# ==========================================
# 3. MAIN APP
# ==========================================
uploaded_file = st.sidebar.file_uploader("Upload Excel/CSV Report", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df_raw = load_and_clean_data(uploaded_file)
        
        # Filter usage
        df = df_raw.copy()
        if "用途碼" in df_raw.columns:
            usage_list = sorted(df_raw["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Filter Usage Code:", options=usage_list, default=usage_list)
            df = df_raw[df_raw["用途碼"].isin(selected_usages)]

        metrics_map = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        if not available: st.stop()
        
        selected_label = st.sidebar.selectbox("Select Parameter:", available)
        data_col = find_data_col(df, metrics_map[selected_label])
        zh_map = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}
        zh_key = zh_map.get(metrics_map[selected_label], metrics_map[selected_label])
        
        # Limits
        v_lsl_std, v_usl_std = get_limit(df, zh_key, "min", "管制"), get_limit(df, zh_key, "max", "管制")
        v_lsl_tgt, v_usl_tgt = get_limit(df, zh_key, "min", "客戶要求"), get_limit(df, zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            mu, sigma = plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma
            cpk = min((v_usl_std - mu)/(3*sigma), (mu - v_lsl_std)/(3*sigma)) if sigma > 0 and v_usl_std and v_lsl_std else None

            # --- TOP KPI ---
            st.title(f"📊 Quality Analytics: {selected_label}")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Samples (N)", len(plot_data))
            k2.metric("Mean (μ)", f"{mu:.2f}")
            k3.metric("Std Dev (σ)", f"{sigma:.2f}")
            k4.metric("Cpk (Internal)", f"{cpk:.2f}" if cpk else "N/A")

            tab1, tab2 = st.tabs(["📈 Process Analytics", "📊 SPC Control Charts (I-MR)"])

            with tab1:
                c1, c2 = st.columns(2)
                # --- DISTRIBUTION ---
                with c1:
                    st.subheader("I. Distribution")
                    pts = [v for v in [v_lsl_tgt, v_usl_tgt, v_lsl_std, v_usl_std, plot_data.min(), plot_data.max()] if v is not None]
                    x_range = [min(pts)*0.9, max(pts)*1.1]
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(x=plot_data, marker_color='#7FB3D5', opacity=0.8, marker_line_color='white'))
                    
                    add_smart_line(fig_dist, 'x', v_lsl_tgt, "Cust LSL", "#2E7D32", "solid", "top left")
                    add_smart_line(fig_dist, 'x', v_usl_tgt, "Cust USL", "#2E7D32", "solid", "top right")
                    add_smart_line(fig_dist, 'x', v_lsl_std, "Int LSL", "#D32F2F", "dash", "top right")
                    add_smart_line(fig_dist, 'x', v_usl_std, "Int USL", "#D32F2F", "dash", "top left")

                    # FIX: Bo khung hoan chinh
                    fig_dist.update_layout(template="simple_white", height=500, margin=dict(t=80, r=20, l=20, b=20))
                    fig_dist.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                    fig_dist.update_yaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                    st.plotly_chart(fig_dist, use_container_width=True)

                # --- TREND ---
                with c2:
                    st.subheader("II. Trend")
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Scatter(y=plot_data, mode='lines+markers', line=dict(color='#1F77B4', width=2)))
                    
                    add_smart_line(fig_trend, 'y', v_usl_tgt, "Cust USL", "#2E7D32", "solid", "top right")
                    add_smart_line(fig_trend, 'y', v_lsl_std, "Int LSL", "#D32F2F", "dash", "top right")
                    add_smart_line(fig_trend, 'y', mu, "Mean", "#8E44AD", "dashdot", "top left")

                    # FIX: Bo khung hoan chinh
                    fig_trend.update_layout(template="simple_white", height=500, margin=dict(t=50, r=20, l=20, b=20))
                    fig_trend.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                    fig_trend.update_yaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                    st.plotly_chart(fig_trend, use_container_width=True)

            with tab2:
                # --- I-MR ---
                st.subheader("III. SPC I-MR Chart")
                mr = plot_data.diff().abs()
                mr_ucl = mr.mean() * 3.267
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.15,
                                      subplot_titles=("<b>Individual Chart (I)</b>", "<b>Moving Range Chart (MR)</b>"))
                
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='I'), row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR'), row=2, col=1)

                add_smart_line(fig_imr, 'y', ucl, "UCL", "red", "dash", "top right", row=1, col=1)
                add_smart_line(fig_imr, 'y', lcl, "LCL", "red", "dash", "bottom right", row=1, col=1)
                add_smart_line(fig_imr, 'y', mu, "Mean", "green", "dash", "top right", row=1, col=1)
                add_smart_line(fig_imr, 'y', mr_ucl, "MR UCL", "red", "dash", "top right", row=2, col=1)

                # FIX: Bo khung hoan chinh cho ca 2 subplot
                fig_imr.update_layout(height=700, template="simple_white", margin=dict(t=60, r=80, l=40, b=40), showlegend=False)
                fig_imr.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                fig_imr.update_yaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                
                # Day tieu de len cao de khong bi khung de len
                for ann in fig_imr['layout']['annotations']: ann['y'] += 0.03
                
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Please upload data to begin.")
