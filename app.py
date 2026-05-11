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
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
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
    'toImageButtonOptions': {
        'format': 'png', 'filename': 'Quality_Report',
        'height': 700, 'width': 1400, 'scale': 2
    }
}

# ==========================================
# 2. UTILITY FUNCTIONS
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

def add_full_border_box(fig):
    """Vẽ khung viền 4 cạnh khép kín tuyệt đối"""
    fig.add_shape(type="rect", xref="paper", yref="paper",
                  x0=0, y0=0, x1=1, y1=1,
                  line=dict(color="black", width=2),
                  fillcolor="rgba(0,0,0,0)", layer="above")
    fig.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
    fig.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True)
    return fig

def add_hline_with_safe_label(fig, y_val, label, color, dash, row=None):
    """Vẽ đường ngang và nhãn ở lề phải, tuyệt đối không đè cạnh"""
    if y_val is None: return
    
    # Vẽ đường
    line_kw = dict(line_dash=dash, line_color=color, line_width=2)
    if row: fig.add_hline(y=y_val, row=row, col=1, **line_kw)
    else: fig.add_hline(y=y_val, **line_kw)
    
    # Vẽ nhãn ở lề phải (ngoài khung viền)
    yref = f"y{row}" if (row and row > 1) else "y"
    fig.add_annotation(
        x=1.01, y=y_val, xref="paper", yref=yref,
        text=f"<b>{label}: {y_val:.1f}</b>",
        showarrow=False, xanchor="left", yanchor="middle",
        font=dict(size=10, color=color),
        bgcolor="rgba(255,255,255,0.8)", borderpad=2
    )

def add_vline_with_top_label(fig, x_val, label, color, dash, offset_y=-50):
    """Nhãn giới hạn đứng cho Histogram, đặt trên cao để không che dữ liệu"""
    if x_val is None: return
    fig.add_vline(x=x_val, line_dash=dash, line_color=color, line_width=2)
    fig.add_annotation(
        x=x_val, y=1, xref="x", yref="paper",
        text=f"<b>{label}<br>{x_val:.1f}</b>",
        showarrow=True, arrowhead=2, arrowcolor=color,
        ax=0, ay=offset_y, font=dict(size=10, color=color),
        bgcolor="white", bordercolor=color, borderwidth=1
    )

# ==========================================
# 3. MAIN LOGIC
# ==========================================
uploaded_file = st.sidebar.file_uploader("Upload Data", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df_raw = load_and_clean_data(uploaded_file)
        
        # Mapping & Limit Extraction
        metrics_map = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        selected_label = st.sidebar.selectbox("Select Parameter:", list(metrics_map.keys()))
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df_raw, short_key)
        
        zh_map = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}
        zh_key = zh_map.get(short_key, short_key)
        
        v_lsl_std = get_limit(df_raw, zh_key, "min", "管制")
        v_usl_std = get_limit(df_raw, zh_key, "max", "管制")
        v_lsl_tgt = get_limit(df_raw, zh_key, "min", "客戶要求")
        v_usl_tgt = get_limit(df_raw, zh_key, "max", "客戶要求")

        plot_data = pd.to_numeric(df_raw[data_col], errors='coerce').dropna().reset_index(drop=True)
        mu, sigma = plot_data.mean(), plot_data.std()
        ucl, lcl = mu + 3*sigma, mu - 3*sigma
        
        st.title(f"📊 Quality Analytics: {selected_label}")
        tab1, tab2 = st.tabs(["📈 Process Analytics", "📊 SPC Charts"])

        with tab1:
            # 1. Distribution Chart
            st.subheader("I. Distribution & Capability")
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(x=plot_data, name='Data', marker_color='#7FB3D5', opacity=0.8))
            
            # Normal curve
            x_range = np.linspace(plot_data.min()*0.9, plot_data.max()*1.1, 200)
            fig_dist.add_trace(go.Scatter(x=x_range, y=norm.pdf(x_range, mu, sigma)*len(plot_data)*(plot_data.max()-plot_data.min())/10,
                                         mode='lines', name='Normal Fit', line=dict(color='#1E3A8A', width=3)))
            
            # V-Lines với nhãn so le cao thấp
            add_vline_with_top_label(fig_dist, v_lsl_tgt, "Cust LSL", "#2E7D32", "solid", -60)
            add_vline_with_top_label(fig_dist, v_usl_tgt, "Cust USL", "#2E7D32", "solid", -40)
            add_vline_with_top_label(fig_dist, v_lsl_std, "Int LSL", "#D32F2F", "dash", -80)
            add_vline_with_top_label(fig_dist, v_usl_std, "Int USL", "#D32F2F", "dash", -60)

            fig_dist.update_layout(template="simple_white", height=450, margin=dict(t=100, r=40, b=50, l=60), showlegend=True, legend=dict(orientation="h", y=1.1, x=0))
            fig_dist = add_full_border_box(fig_dist)
            st.plotly_chart(fig_dist, use_container_width=True)

            # 2. Trend Chart
            st.subheader("II. Trend Analysis")
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='Measurement', line=dict(color='#1F77B4')))
            
            # H-Lines với nhãn nằm hoàn toàn ở lề phải (r=160)
            add_hline_with_safe_label(fig_trend, v_usl_tgt, "Cust USL", "#2E7D32", "solid")
            add_hline_with_safe_label(fig_trend, v_lsl_tgt, "Cust LSL", "#2E7D32", "solid")
            add_hline_with_safe_label(fig_trend, v_usl_std, "Int USL", "#D32F2F", "dash")
            add_hline_with_safe_label(fig_trend, v_lsl_std, "Int LSL", "#D32F2F", "dash")
            add_hline_with_safe_label(fig_trend, ucl, "UCL", "#E67E22", "dot")
            add_hline_with_safe_label(fig_trend, lcl, "LCL", "#E67E22", "dot")
            add_hline_with_safe_label(fig_trend, mu, "Mean", "#8E44AD", "dashdot")

            # Out of spec markers
            usl_lim = v_usl_std if v_usl_std else v_usl_tgt
            lsl_lim = v_lsl_std if v_lsl_std else v_lsl_tgt
            ooc = plot_data[(plot_data > usl_lim) | (plot_data < lsl_lim)]
            if not ooc.empty:
                fig_trend.add_trace(go.Scatter(x=ooc.index, y=ooc, mode='markers', name='Out of Spec', marker=dict(color='red', size=10, symbol='x')))

            # Nới lề phải lên 160 để chứa labels
            fig_trend.update_layout(template="simple_white", height=450, margin=dict(t=50, r=160, b=50, l=60), showlegend=True, legend=dict(orientation="h", y=1.1, x=0))
            fig_trend = add_full_border_box(fig_trend)
            st.plotly_chart(fig_trend, use_container_width=True)

        with tab2:
            # I-MR Chart logic (tương tự với add_full_border_box)
            st.subheader("III. Statistical Process Control (I-MR)")
            fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1)
            fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='Individual'), row=1, col=1)
            add_hline_with_safe_label(fig_imr, ucl, "UCL", "red", "dash", row=1)
            add_hline_with_safe_label(fig_imr, lcl, "LCL", "red", "dash", row=1)
            
            fig_imr.update_layout(height=700, template="simple_white", margin=dict(t=50, r=160, b=50, l=60), showlegend=False)
            # Khung viền cho từng subplot paper
            fig_imr.add_shape(type="rect", xref="paper", yref="paper", x0=0, y0=0.55, x1=1, y1=1, line=dict(color="black", width=2))
            fig_imr.add_shape(type="rect", xref="paper", yref="paper", x0=0, y0=0, x1=1, y1=0.45, line=dict(color="black", width=2))
            
            st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Please upload data to begin.")
