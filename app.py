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


def add_full_border(fig):
    """
    Vẽ khung viền 4 cạnh hoàn chỉnh cho figure đơn.
    Dùng add_shape với xref/yref='paper' — cách duy nhất đảm bảo đủ 4 cạnh.
    """
    fig.update_xaxes(showline=True, linewidth=1.5, linecolor='black',
                     mirror=True, ticks="outside", ticklen=4)
    fig.update_yaxes(showline=True, linewidth=1.5, linecolor='black',
                     mirror=True, ticks="outside", ticklen=4)
    fig.add_shape(type="rect",
                  xref="paper", yref="paper",
                  x0=0, y0=0, x1=1, y1=1,
                  line=dict(color="black", width=1.5),
                  fillcolor="rgba(0,0,0,0)")
    return fig


def add_full_border_subplot(fig, row_domains):
    """
    Vẽ khung viền 4 cạnh cho từng subplot.
    row_domains: list of (y0, y1) tọa độ paper của từng subplot (từ dưới lên).
    """
    fig.update_xaxes(showline=True, linewidth=1.5, linecolor='black',
                     mirror=True, ticks="outside", ticklen=4)
    fig.update_yaxes(showline=True, linewidth=1.5, linecolor='black',
                     mirror=True, ticks="outside", ticklen=4)
    for (y0, y1) in row_domains:
        fig.add_shape(type="rect",
                      xref="paper", yref="paper",
                      x0=0, y0=y0, x1=1, y1=y1,
                      line=dict(color="black", width=1.5),
                      fillcolor="rgba(0,0,0,0)")
    return fig


def add_hline_with_label(fig, y_val, label, color, dash, row=None):
    """
    Vẽ đường ngang + label ở lề phải NGOÀI vùng vẽ.
    Tách hoàn toàn add_hline và add_annotation để tránh lỗi Plotly >= 5.18.
    """
    if y_val is None:
        return

    # Bước 1: vẽ đường (không annotation)
    hline_kw = dict(line_dash=dash, line_color=color, line_width=2, opacity=1)
    if row is not None:
        hline_kw["row"] = row
        hline_kw["col"] = 1
    fig.add_hline(y=y_val, **hline_kw)

    # Bước 2: annotation riêng — xref=paper, yref theo subplot
    yref = "y" if (row is None or row == 1) else f"y{row}"
    fig.add_annotation(
        x=1.02, y=y_val,
        xref="paper", yref=yref,
        text=f"<b>{label}: {y_val:.1f}</b>",
        showarrow=False,
        xanchor="left", yanchor="middle",
        font=dict(size=10, color=color),
        bgcolor="rgba(255,255,255,0.85)",
        borderpad=2,
    )


def add_vline_with_label(fig, x_val, label, color, dash, ay=-40):
    """
    Vẽ đường dọc + label dạng annotation có mũi tên,
    đặt phía trên đường để không che histogram.
    ay âm = annotation phía trên điểm neo.
    """
    if x_val is None:
        return
    fig.add_vline(x=x_val, line_dash=dash, line_color=color,
                  line_width=2, opacity=1)
    fig.add_annotation(
        x=x_val, y=1, xref="x", yref="paper",
        text=f"<b>{label}<br>{x_val:.1f}</b>",
        showarrow=True, arrowhead=2, arrowsize=0.8,
        arrowcolor=color, ax=0, ay=ay,
        font=dict(size=9, color=color),
        bgcolor="rgba(255,255,255,0.88)",
        bordercolor=color, borderwidth=1, borderpad=3,
        xanchor="center",
    )


# ==========================================
# 3. SIDEBAR
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
        data_col  = find_data_col(df, short_key)

        zh_map = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}
        zh_key = zh_map.get(short_key, short_key)

        v_lsl_std = get_limit(df, zh_key, "min", "管制")
        v_usl_std = get_limit(df, zh_key, "max", "管制")
        v_lsl_tgt = get_limit(df, zh_key, "min", "客戶要求")
        v_usl_tgt = get_limit(df, zh_key, "max", "客戶要求")

        if not data_col:
            st.error(f"❌ Cannot find data column for {selected_label}.")
            st.stop()

        plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
        n = len(plot_data)

        if n < 2:
            st.warning("⚠️ Need at least 2 data points.")
            st.stop()

        mu    = plot_data.mean()
        sigma = plot_data.std()
        ucl   = mu + 3 * sigma
        lcl   = mu - 3 * sigma

        cp, cpk = None, None
        if sigma > 0:
            if v_lsl_std and v_usl_std:
                cp  = (v_usl_std - v_lsl_std) / (6 * sigma)
                cpk = min((v_usl_std - mu) / (3 * sigma), (mu - v_lsl_std) / (3 * sigma))
            elif v_lsl_std:
                cpk = (mu - v_lsl_std) / (3 * sigma)
            elif v_usl_std:
                cpk = (v_usl_std - mu) / (3 * sigma)

        # ── KPI Cards ──────────────────────────────────────────────────────
        st.title(f"📊 Quality Analytics: {selected_label}")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Samples (N)", f"{n:,}")
        k2.metric("Mean (μ)",    f"{mu:.2f}")
        k3.metric("Std Dev (σ)", f"{sigma:.2f}")
        k4.metric("Cp",          f"{cp:.3f}"  if cp  else "N/A")
        cpk_delta = "✅ Pass" if cpk and cpk >= 1.33 else "⚠️ Warning"
        k5.metric("Cpk", f"{cpk:.3f}" if cpk else "N/A",
                  delta=cpk_delta if cpk else None,
                  delta_color="normal" if (cpk and cpk >= 1.33) else "inverse")

        tab1, tab2 = st.tabs(["📈 Process Analytics", "📊 SPC Control Charts (I-MR)"])

        # ======================================================
        # TAB 1 — Distribution (trên) + Trend (dưới), layout DỌC
        # ======================================================
        with tab1:

            # ── I. Distribution & Capability ─────────────────────────────
            st.subheader("I. Distribution & Capability")

            k_bins  = max(5, math.ceil(1 + 3.322 * math.log10(n)))
            pts     = [v for v in [v_lsl_tgt, v_usl_tgt, v_lsl_std, v_usl_std,
                                   plot_data.min(), plot_data.max()] if v is not None]
            padding = abs(max(pts) - min(pts)) * 0.15
            x_range = [min(pts) - padding, max(pts) + padding]

            fig_dist = go.Figure()

            fig_dist.add_trace(go.Histogram(
                x=plot_data, nbinsx=k_bins, name='Data',
                marker_color='#7FB3D5', opacity=0.85,
                marker_line_color='white', marker_line_width=1
            ))

            if sigma > 0:
                x_c = np.linspace(x_range[0], x_range[1], 300)
                bin_w = (plot_data.max() - plot_data.min()) / k_bins
                y_c   = norm.pdf(x_c, mu, sigma) * n * bin_w
                fig_dist.add_trace(go.Scatter(
                    x=x_c, y=y_c, mode='lines', name='Normal Fit',
                    line=dict(color='#1E3A8A', width=2.5)
                ))

            # Vertical spec lines — xen kẽ ay để label không chồng nhau
            add_vline_with_label(fig_dist, v_lsl_tgt, "Cust LSL", "#2E7D32", "solid", ay=-55)
            add_vline_with_label(fig_dist, v_usl_tgt, "Cust USL", "#2E7D32", "solid", ay=-40)
            add_vline_with_label(fig_dist, v_lsl_std, "Int LSL",  "#D32F2F", "dash",  ay=-70)
            add_vline_with_label(fig_dist, v_usl_std, "Int USL",  "#D32F2F", "dash",  ay=-55)

            fig_dist.update_layout(
                template="simple_white",
                height=420,
                xaxis_range=x_range,
                showlegend=True,
                legend=dict(orientation="h", y=1.05, x=0),
                margin=dict(t=80, r=30, b=60, l=70),
                xaxis_title=selected_label,
                yaxis_title="Count",
            )
            fig_dist = add_full_border(fig_dist)
            st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

            st.markdown("---")

            # ── II. Trend Analysis ────────────────────────────────────────
            st.subheader("II. Trend Analysis")

            fig_trend = go.Figure()

            # Shading vùng spec khách hàng
            if v_lsl_tgt is not None and v_usl_tgt is not None:
                fig_trend.add_hrect(
                    y0=v_lsl_tgt, y1=v_usl_tgt,
                    fillcolor="#E8F5E9", opacity=0.35,
                    layer="below", line_width=0
                )

            # Data line
            fig_trend.add_trace(go.Scatter(
                x=plot_data.index, y=plot_data,
                mode='lines+markers', name='Measurement',
                line=dict(color='#1F77B4', width=2),
                marker=dict(size=6, color='#1F77B4')
            ))

            # Out-of-spec markers
            usl_lim = v_usl_std if v_usl_std is not None else (v_usl_tgt if v_usl_tgt is not None else float('inf'))
            lsl_lim = v_lsl_std if v_lsl_std is not None else (v_lsl_tgt if v_lsl_tgt is not None else float('-inf'))
            ooc = plot_data[(plot_data > usl_lim) | (plot_data < lsl_lim)]
            if not ooc.empty:
                fig_trend.add_trace(go.Scatter(
                    x=ooc.index, y=ooc,
                    mode='markers', name='Out of Spec',
                    marker=dict(color='#D32F2F', size=10, symbol='x',
                                line=dict(color='#D32F2F', width=2))
                ))

            # Horizontal lines — label ngoài lề phải, KHÔNG che đường hay data
            add_hline_with_label(fig_trend, v_usl_tgt, "Cust USL", "#2E7D32", "solid")
            add_hline_with_label(fig_trend, v_lsl_tgt, "Cust LSL", "#2E7D32", "solid")
            add_hline_with_label(fig_trend, v_usl_std, "Int USL",  "#D32F2F", "dash")
            add_hline_with_label(fig_trend, v_lsl_std, "Int LSL",  "#D32F2F", "dash")
            add_hline_with_label(fig_trend, ucl,       "UCL",      "#E67E22", "dot")
            add_hline_with_label(fig_trend, lcl,       "LCL",      "#E67E22", "dot")
            add_hline_with_label(fig_trend, mu,        "Mean",     "#8E44AD", "dashdot")

            fig_trend.update_layout(
                template="simple_white",
                height=420,
                showlegend=True,
                legend=dict(orientation="h", y=1.05, x=0),
                # Lề phải đủ rộng (150px) để tất cả label hiển thị đầy đủ
                margin=dict(t=80, r=150, b=60, l=70),
                xaxis_title="Sample Index",
                yaxis_title=selected_label,
            )
            fig_trend = add_full_border(fig_trend)
            st.plotly_chart(fig_trend, use_container_width=True, config=export_config)

        # ======================================================
        # TAB 2 — I-MR Charts (layout dọc, 2 subplot rows)
        # ======================================================
        with tab2:
            st.subheader("III. Statistical Process Control (I-MR)")

            mr      = plot_data.diff().abs()
            mr_mean = mr.mean()
            mr_ucl  = mr_mean * 3.267

            # vertical_spacing=0.12 → row1 domain ≈ [0.56, 1.0], row2 ≈ [0.0, 0.44]
            fig_imr = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.12,
                subplot_titles=("Individual Chart (I)", "Moving Range Chart (MR)")
            )

            # I-Chart data
            fig_imr.add_trace(go.Scatter(
                x=plot_data.index, y=plot_data,
                mode='lines+markers', name='Individual',
                line=dict(color='#1F77B4', width=2),
                marker=dict(size=6, color='#1F77B4')
            ), row=1, col=1)

            ooc_i = plot_data[(plot_data > ucl) | (plot_data < lcl)]
            if not ooc_i.empty:
                fig_imr.add_trace(go.Scatter(
                    x=ooc_i.index, y=ooc_i,
                    mode='markers', name='OOC (I)',
                    marker=dict(color='#D32F2F', size=10, symbol='x',
                                line=dict(color='#D32F2F', width=2))
                ), row=1, col=1)

            # MR-Chart data
            fig_imr.add_trace(go.Scatter(
                x=mr.index, y=mr,
                mode='lines+markers', name='Moving Range',
                line=dict(color='#F39C12', width=2),
                marker=dict(size=6, color='#F39C12')
            ), row=2, col=1)

            ooc_mr = mr[mr > mr_ucl]
            if not ooc_mr.empty:
                fig_imr.add_trace(go.Scatter(
                    x=ooc_mr.index, y=ooc_mr,
                    mode='markers', name='OOC (MR)',
                    marker=dict(color='#D32F2F', size=10, symbol='x',
                                line=dict(color='#D32F2F', width=2))
                ), row=2, col=1)

            # Limit lines I-chart
            add_hline_with_label(fig_imr, ucl,      "UCL",     '#D32F2F', "dash",    row=1)
            add_hline_with_label(fig_imr, lcl,      "LCL",     '#D32F2F', "dash",    row=1)
            add_hline_with_label(fig_imr, mu,       "Mean",    '#2E7D32', "dashdot", row=1)
            add_hline_with_label(fig_imr, v_usl_std,"Int USL", '#D32F2F', "dot",     row=1)
            add_hline_with_label(fig_imr, v_lsl_std,"Int LSL", '#D32F2F', "dot",     row=1)
            add_hline_with_label(fig_imr, v_usl_tgt,"Cust USL",'#2E7D32', "dot",     row=1)
            add_hline_with_label(fig_imr, v_lsl_tgt,"Cust LSL",'#2E7D32', "dot",     row=1)

            # Limit lines MR-chart
            add_hline_with_label(fig_imr, mr_mean, "MR̄",    '#2E7D32', "dashdot", row=2)
            add_hline_with_label(fig_imr, mr_ucl,  "MR UCL",'#D32F2F', "dash",    row=2)

            fig_imr.update_layout(
                height=750,
                template="simple_white",
                showlegend=False,
                # Lề phải 160px cho label
                margin=dict(l=70, r=160, t=80, b=60),
            )
            fig_imr.update_yaxes(title_text=selected_label,  row=1, col=1)
            fig_imr.update_yaxes(title_text="Moving Range",  row=2, col=1)
            fig_imr.update_xaxes(title_text="Sample Index",  row=2, col=1)

            # Khung viền 4 cạnh cho từng subplot
            # vertical_spacing=0.12 → gap=0.12, row1 top=1.0, bottom≈0.56, row2 top≈0.44, bottom=0
            fig_imr = add_full_border_subplot(fig_imr, row_domains=[
                (0.0,  0.44),   # row 2 (MR)
                (0.56, 1.0),    # row 1 (I)
            ])
            st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
        import traceback
        st.code(traceback.format_exc())

else:
    st.info("👈 Please upload the production data report (Excel/CSV) to begin.")
