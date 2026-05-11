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

export_config = {
    'displayModeBar': True, 
    'displaylogo': False,
    'toImageButtonOptions': {'format': 'png', 'filename': 'Quality_Report', 'height': 700, 'width': 1200, 'scale': 2}
}

# ==========================================
# 2. CACHING & UTILITY FUNCTIONS
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

def add_smart_line(fig, axis, val, name, color, dash, pos):
    """Hàm chung để vẽ đường ngang (y) hoặc dọc (x) sắc nét"""
    if val is None: return
    
    line_args = dict(line_dash=dash, line_color=color, line_width=2.5, opacity=1,
                     annotation_text=f"<b>{name}:<br>{val:.1f}</b>" if axis == 'x' else f"<b>{name}: {val:.1f}</b>",
                     annotation_position=pos,
                     annotation_font=dict(size=11, color=color),
                     annotation_bgcolor="rgba(255,255,255,0.85)")
    
    if axis == 'x':
        fig.add_vline(x=val, **line_args)
    else:
        fig.add_hline(y=val, **line_args)

# ==========================================
# 3. SIDEBAR & MAIN LOGIC
# ==========================================
st.sidebar.header("📂 DATA SOURCE")
uploaded_file = st.sidebar.file_uploader("Upload Excel/CSV Report", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df_raw = load_and_clean_data(uploaded_file)

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
            n = len(plot_data)
            
            if n < 2:
                st.warning("⚠️ Cần ít nhất 2 mẫu dữ liệu để thực hiện phân tích thống kê.")
                st.stop()
                
            mu, sigma = plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

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
            status = "Pass" if cpk and cpk >= 1.33 else "Warning"
            k4.metric("Cpk (Internal)", f"{cpk:.2f}" if cpk else "N/A", delta=status if cpk else None)

            tab1, tab2 = st.tabs(["📈 Process Analytics", "📊 SPC Control Charts (I-MR)"])

            with tab1:
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("I. Distribution & Capability")
                    k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                    pts = [v for v in [v_lsl_tgt, v_usl_tgt, v_lsl_std, v_usl_std, plot_data.min(), plot_data.max()] if v is not None]
                    x_range = [min(pts) - abs(min(pts)*0.1), max(pts) + abs(max(pts)*0.1)]

                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, name='Data', marker_color='#7FB3D5', opacity=0.8, marker_line_color='white', marker_line_width=1))
                    
                    if sigma > 0:
                        x_c = np.linspace(x_range[0], x_range[1], 200)
                        y_c = norm.pdf(x_c, mu, sigma) * n * ((plot_data.max() - plot_data.min()) / k_bins)
                        fig_dist.add_trace(go.Scatter(x=x_c, y=y_c, mode='lines', name='Normal', line=dict(color='#1E3A8A', width=2)))

                    add_smart_line(fig_dist, 'x', v_lsl_tgt, "Cust LSL", "#2E7D32", "solid", "top left")
                    add_smart_line(fig_dist, 'x', v_usl_tgt, "Cust USL", "#2E7D32", "solid", "top right")
                    add_smart_line(fig_dist, 'x', v_lsl_std, "Int LSL", "#D32F2F", "dash", "top right")
                    add_smart_line(fig_dist, 'x', v_usl_std, "Int USL", "#D32F2F", "dash", "top left")

                    fig_dist.update_layout(template="simple_white", height=550, xaxis_range=x_range, showlegend=False, margin=dict(t=80))
                    # THÊM KHUNG VIỀN HOÀN CHỈNH
                    fig_trend.update_xaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True, ticks="outside")
                    fig_trend.update_yaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True, ticks="outside")
                    fig_trend.update_layout(margin=dict(t=80, r=20, b=40, l=40))
                    st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

                with col2:
                    st.subheader("II. Trend Analysis")
                    fig_trend = go.Figure()

                    if v_lsl_tgt and v_usl_tgt:
                        fig_trend.add_hrect(y0=v_lsl_tgt, y1=v_usl_tgt, fillcolor="#E8F5E9", opacity=0.4, layer="below", line_width=0)

                    add_smart_line(fig_trend, 'y', v_usl_tgt, "Cust USL", "#2E7D32", "solid", "top right")
                    add_smart_line(fig_trend, 'y', v_usl_std, "Int USL", "#D32F2F", "dash", "bottom right")
                    add_smart_line(fig_trend, 'y', v_lsl_tgt, "Cust LSL", "#2E7D32", "solid", "bottom right")
                    add_smart_line(fig_trend, 'y', v_lsl_std, "Int LSL", "#D32F2F", "dash", "top right")
                    add_smart_line(fig_trend, 'y', ucl, "UCL", "#E67E22", "dot", "top left")
                    add_smart_line(fig_trend, 'y', lcl, "LCL", "#E67E22", "dot", "bottom left")
                    add_smart_line(fig_trend, 'y', mu, "Mean", "#8E44AD", "dashdot", "top left")

                    fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', name='Data',
                                                line=dict(color='#1F77B4', width=2), marker=dict(size=7, symbol='circle', color='#1F77B4')))
                    
                    usl_limit = v_usl_std if v_usl_std is not None else (v_usl_tgt if v_usl_tgt is not None else float('inf'))
                    lsl_limit = v_lsl_std if v_lsl_std is not None else (v_lsl_tgt if v_lsl_tgt is not None else float('-inf'))
                    ooc = plot_data[(plot_data > usl_limit) | (plot_data < lsl_limit)]
                    if not ooc.empty:
                        fig_trend.add_trace(go.Scatter(x=ooc.index, y=ooc, mode='markers', name='Out of Spec', 
                                                    marker=dict(color='#D32F2F', size=9, symbol='circle', line=dict(color='white', width=1))))

                    fig_trend.update_layout(template="simple_white", height=550, margin=dict(t=50, r=20), showlegend=False)
                    # THÊM KHUNG VIỀN HOÀN CHỈNH
                    fig_trend.update_xaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True)
                    fig_trend.update_yaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True)
                    st.plotly_chart(fig_trend, use_container_width=True, config=export_config)

            with tab2:
                st.subheader("III. Statistical Process Control (I-MR)")
                mr = plot_data.diff().abs()
                mr_mean = mr.mean()
                mr_ucl = mr_mean * 3.267

                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.15, 
                                      subplot_titles=("Individual Chart (I)", "Moving Range Chart (MR)"))
                
                fig_imr.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', 
                    name='Data (I)', line=dict(color='#1F77B4', width=2), marker=dict(size=7, symbol='circle')), row=1, col=1)
                
                ooc_i = plot_data[(plot_data > ucl) | (plot_data < lcl)]
                if not ooc_i.empty:
                    fig_imr.add_trace(go.Scatter(x=ooc_i.index, y=ooc_i, mode='markers', name='OOC (I)',
                        marker=dict(color='#D32F2F', size=9, symbol='circle', line=dict(color='white', width=1))), row=1, col=1)

                fig_imr.add_trace(go.Scatter(x=mr.index, y=mr, mode='lines+markers', 
                    name='Data (MR)', line=dict(color='#1F77B4', width=2), marker=dict(size=7, symbol='circle')), row=2, col=1)

                ooc_mr = mr[mr > mr_ucl]
                if not ooc_mr.empty:
                    fig_imr.add_trace(go.Scatter(x=ooc_mr.index, y=ooc_mr, mode='markers', name='OOC (MR)',
                        marker=dict(color='#D32F2F', size=9, symbol='circle', line=dict(color='white', width=1))), row=2, col=1)

                def add_imr_hline(val, label, color, row):
                    if val is not None:
                        fig_imr.add_hline(y=val, line_dash="dash", line_color=color, line_width=2.5, opacity=1,
                                        annotation_text=f"<b>{label}: {val:.1f}</b>", annotation_position="top right",
                                        annotation_font=dict(color=color, size=11),
                                        annotation_bgcolor="rgba(255,255,255,0.85)", row=row, col=1)

                add_imr_hline(ucl, 'UCL', '#D32F2F', 1)
                add_imr_hline(lcl, 'LCL', '#D32F2F', 1)
                add_imr_hline(mu, 'Mean', '#2E7D32', 1)
                add_imr_hline(mr_mean, 'MR Mean', '#2E7D32', 2)
                add_imr_hline(mr_ucl, 'MR UCL', '#D32F2F', 2)

                fig_imr.update_layout(height=700, template="simple_white", showlegend=False, margin=dict(l=40, r=80, t=60, b=40))
                for annotation in fig_imr['layout']['annotations']:
                    annotation['y'] += 0.02 

                # THÊM KHUNG VIỀN HOÀN CHỈNH CHO CẢ 2 SUBPLOTS
                fig_imr.update_xaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True, ticks="outside")
                fig_imr.update_yaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True, ticks="outside")
                
                # Vẽ thủ công cạnh trên cho từng subplot (subplot titles che mất mirror)
                fig_imr.add_shape(type="rect", xref="paper", yref="paper",
                    x0=0, y0=0.55, x1=1, y1=1.0,
                    line=dict(color="black", width=1.5))
                fig_imr.add_shape(type="rect", xref="paper", yref="paper",
                    x0=0, y0=0, x1=1, y1=0.45,
                    line=dict(color="black", width=1.5))
                
                st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
else:
    st.info("👈 Please upload the production data report (Excel/CSV) to begin.")
