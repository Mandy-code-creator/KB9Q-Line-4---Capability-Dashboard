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
    'toImageButtonOptions': {
        'format': 'png', 'filename': 'Quality_Report',
        'height': 700, 'width': 1200, 'scale': 2
    }
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


def apply_clean_axes(fig):
    """Áp dụng khung viền 4 cạnh hoàn chỉnh cho figure đơn (không phải subplot)."""
    fig.update_xaxes(
        showline=True, linewidth=1.5, linecolor='black',
        mirror=True, ticks="outside", ticklen=5
    )
    fig.update_yaxes(
        showline=True, linewidth=1.5, linecolor='black',
        mirror=True, ticks="outside", ticklen=5
    )
    # Vẽ thêm rectangle bao ngoài để đảm bảo đủ 4 cạnh
    fig.add_shape(
        type="rect", xref="paper", yref="paper",
        x0=0, y0=0, x1=1, y1=1,
        line=dict(color="black", width=1.5),
        fillcolor="rgba(0,0,0,0)"
    )
    return fig


def apply_clean_axes_subplot(fig, n_rows=2):
    """Áp dụng khung viền 4 cạnh hoàn chỉnh cho subplot figure."""
    fig.update_xaxes(
        showline=True, linewidth=1.5, linecolor='black',
        mirror=True, ticks="outside", ticklen=5
    )
    fig.update_yaxes(
        showline=True, linewidth=1.5, linecolor='black',
        mirror=True, ticks="outside", ticklen=5
    )
    # Tọa độ paper của từng subplot row (2 rows)
    # Row 1: y từ ~0.57 → 1.0 | Row 2: y từ 0.0 → 0.43
    row_coords = [
        (0.0, 0.0, 1.0, 0.43),   # row 2 (bottom)
        (0.0, 0.57, 1.0, 1.0),   # row 1 (top)
    ]
    for (x0, y0, x1, y1) in row_coords:
        fig.add_shape(
            type="rect", xref="paper", yref="paper",
            x0=x0, y0=y0, x1=x1, y1=y1,
            line=dict(color="black", width=1.5),
            fillcolor="rgba(0,0,0,0)"
        )
    return fig


# ==========================================
# HELPER: Vẽ đường giới hạn với label KHÔNG che dữ liệu
# Label được đặt ở lề phải ngoài vùng vẽ (xref=paper)
# ==========================================
def add_hline_labeled(fig, y_val, label, color, dash, row=None):
    """Vẽ đường ngang + label ngoài lề phải, không che dữ liệu.
    Dùng add_annotation riêng để tránh lỗi xref trên Plotly >= 5.18.
    """
    if y_val is None:
        return

    # Vẽ đường không kèm annotation (tránh lỗi annotation_xref=paper)
    hline_kwargs = dict(line_dash=dash, line_color=color, line_width=2, opacity=1)
    if row is not None:
        hline_kwargs["row"] = row
        hline_kwargs["col"] = 1
    fig.add_hline(y=y_val, **hline_kwargs)

    # Xác định yref phù hợp với subplot row
    if row is None or row == 1:
        yref = "y"
    else:
        yref = f"y{row}"

    # Annotation riêng biệt đặt ngoài lề phải
    fig.add_annotation(
        x=1.01, y=y_val,
        xref="paper", yref=yref,
        text=f"<b>{label}: {y_val:.1f}</b>",
        showarrow=False,
        xanchor="left", yanchor="middle",
        font=dict(size=10, color=color),
        bgcolor="rgba(255,255,255,0)",
    )


def add_vline_labeled(fig, x_val, label, color, dash, position="top"):
    """Vẽ đường dọc + label phía trên/dưới trong vùng vẽ, không che histogram."""
    if x_val is None:
        return
    ann_pos = "top left" if position == "left" else "top right"
    fig.add_vline(
        x=x_val,
        line_dash=dash,
        line_color=color,
        line_width=2,
        opacity=1,
        annotation_text=f"<b>{label}<br>{x_val:.1f}</b>",
        annotation_position=ann_pos,
        annotation_font=dict(size=10, color=color),
        annotation_bgcolor="rgba(255,255,255,0.75)",
        annotation_borderpad=2,
    )


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
        data_col  = find_data_col(df, short_key)
        zh_map    = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}
        zh_key    = zh_map.get(short_key, short_key)

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
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Samples (N)", n)
            k2.metric("Mean (μ)",    f"{mu:.2f}")
            k3.metric("Std Dev (σ)", f"{sigma:.2f}")
            status = "Pass" if cpk and cpk >= 1.33 else "Warning"
            k4.metric("Cpk (Internal)", f"{cpk:.2f}" if cpk else "N/A",
                      delta=status if cpk else None)

            tab1, tab2 = st.tabs(["📈 Process Analytics", "📊 SPC Control Charts (I-MR)"])

            # ==================================================
            # TAB 1
            # ==================================================
            with tab1:
                col1, col2 = st.columns([1, 1])

                # ── I. Distribution & Capability ──────────────────────────────
                with col1:
                    st.subheader("I. Distribution & Capability")

                    k_bins  = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                    pts     = [v for v in [v_lsl_tgt, v_usl_tgt, v_lsl_std, v_usl_std,
                                           plot_data.min(), plot_data.max()] if v is not None]
                    padding = abs(max(pts) - min(pts)) * 0.12
                    x_range = [min(pts) - padding, max(pts) + padding]

                    fig_dist = go.Figure()

                    # Histogram
                    fig_dist.add_trace(go.Histogram(
                        x=plot_data, nbinsx=k_bins, name='Data',
                        marker_color='#7FB3D5', opacity=0.8,
                        marker_line_color='white', marker_line_width=1
                    ))

                    # Normal curve
                    if sigma > 0:
                        x_c = np.linspace(x_range[0], x_range[1], 300)
                        y_c = norm.pdf(x_c, mu, sigma) * n * ((plot_data.max() - plot_data.min()) / k_bins)
                        fig_dist.add_trace(go.Scatter(
                            x=x_c, y=y_c, mode='lines', name='Normal',
                            line=dict(color='#1E3A8A', width=2.5)
                        ))

                    # Vertical spec lines — labels xen kẽ trên/dưới để không chồng nhau
                    add_vline_labeled(fig_dist, v_lsl_tgt, "Cust LSL", "#2E7D32", "solid",  position="left")
                    add_vline_labeled(fig_dist, v_usl_tgt, "Cust USL", "#2E7D32", "solid",  position="right")
                    add_vline_labeled(fig_dist, v_lsl_std, "Int LSL",  "#D32F2F", "dash",   position="right")
                    add_vline_labeled(fig_dist, v_usl_std, "Int USL",  "#D32F2F", "dash",   position="left")

                    fig_dist.update_layout(
                        template="simple_white",
                        height=550,
                        xaxis_range=x_range,
                        showlegend=False,
                        # Lề phải rộng để label không bị cắt
                        margin=dict(t=60, r=20, b=50, l=60),
                        xaxis_title=selected_label,
                        yaxis_title="Count",
                    )
                    fig_dist = apply_clean_axes(fig_dist)
                    st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

                # ── II. Trend Analysis ────────────────────────────────────────
                with col2:
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
                        mode='lines+markers', name='Data',
                        line=dict(color='#1F77B4', width=2),
                        marker=dict(size=6, color='#1F77B4')
                    ))

                    # Out-of-spec points
                    usl_limit = v_usl_std if v_usl_std is not None else (v_usl_tgt if v_usl_tgt is not None else float('inf'))
                    lsl_limit = v_lsl_std if v_lsl_std is not None else (v_lsl_tgt if v_lsl_tgt is not None else float('-inf'))
                    ooc = plot_data[(plot_data > usl_limit) | (plot_data < lsl_limit)]
                    if not ooc.empty:
                        fig_trend.add_trace(go.Scatter(
                            x=ooc.index, y=ooc,
                            mode='markers', name='Out of Spec',
                            marker=dict(color='#D32F2F', size=9, symbol='circle',
                                        line=dict(color='white', width=1.5))
                        ))

                    # Horizontal limit lines — tất cả label ra lề phải
                    add_hline_labeled(fig_trend, v_usl_tgt, "Cust USL", "#2E7D32", "solid")
                    add_hline_labeled(fig_trend, v_lsl_tgt, "Cust LSL", "#2E7D32", "solid")
                    add_hline_labeled(fig_trend, v_usl_std, "Int USL",  "#D32F2F", "dash")
                    add_hline_labeled(fig_trend, v_lsl_std, "Int LSL",  "#D32F2F", "dash")
                    add_hline_labeled(fig_trend, ucl,       "UCL",      "#E67E22", "dot")
                    add_hline_labeled(fig_trend, lcl,       "LCL",      "#E67E22", "dot")
                    add_hline_labeled(fig_trend, mu,        "Mean",     "#8E44AD", "dashdot")

                    fig_trend.update_layout(
                        template="simple_white",
                        height=550,
                        showlegend=False,
                        # Lề phải đủ rộng cho tất cả label
                        margin=dict(t=60, r=110, b=50, l=60),
                        xaxis_title="Sample Index",
                        yaxis_title=selected_label,
                    )
                    fig_trend = apply_clean_axes(fig_trend)
                    st.plotly_chart(fig_trend, use_container_width=True, config=export_config)

            # ==================================================
            # TAB 2: I-MR
            # ==================================================
            with tab2:
                st.subheader("III. Statistical Process Control (I-MR)")

                mr      = plot_data.diff().abs()
                mr_mean = mr.mean()
                mr_ucl  = mr_mean * 3.267

                fig_imr = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.14,
                    subplot_titles=("Individual Chart (I)", "Moving Range Chart (MR)")
                )

                # ── I-Chart ────────────────────────────────────────────────────
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
                        marker=dict(color='#D32F2F', size=10, symbol='circle',
                                    line=dict(color='white', width=1.5))
                    ), row=1, col=1)

                # ── MR-Chart ───────────────────────────────────────────────────
                fig_imr.add_trace(go.Scatter(
                    x=mr.index, y=mr,
                    mode='lines+markers', name='MR',
                    line=dict(color='#1F77B4', width=2),
                    marker=dict(size=6, color='#1F77B4')
                ), row=2, col=1)

                ooc_mr = mr[mr > mr_ucl]
                if not ooc_mr.empty:
                    fig_imr.add_trace(go.Scatter(
                        x=ooc_mr.index, y=ooc_mr,
                        mode='markers', name='OOC (MR)',
                        marker=dict(color='#D32F2F', size=10, symbol='circle',
                                    line=dict(color='white', width=1.5))
                    ), row=2, col=1)

                # ── Limit lines I-chart ────────────────────────────────────────
                add_hline_labeled(fig_imr, ucl,  "UCL",  '#D32F2F', "dash", row=1)
                add_hline_labeled(fig_imr, lcl,  "LCL",  '#D32F2F', "dash", row=1)
                add_hline_labeled(fig_imr, mu,   "Mean", '#2E7D32', "dashdot", row=1)

                # ── Limit lines MR-chart ───────────────────────────────────────
                add_hline_labeled(fig_imr, mr_mean, "MR̄",    '#2E7D32', "dashdot", row=2)
                add_hline_labeled(fig_imr, mr_ucl,  "MR UCL",'#D32F2F', "dash",    row=2)

                # ── Spec lines on I-chart (optional) ──────────────────────────
                add_hline_labeled(fig_imr, v_usl_std, "Int USL", "#D32F2F", "dot", row=1)
                add_hline_labeled(fig_imr, v_lsl_std, "Int LSL", "#D32F2F", "dot", row=1)
                add_hline_labeled(fig_imr, v_usl_tgt, "Cust USL","#2E7D32", "dot", row=1)
                add_hline_labeled(fig_imr, v_lsl_tgt, "Cust LSL","#2E7D32", "dot", row=1)

                fig_imr.update_layout(
                    height=700,
                    template="simple_white",
                    showlegend=False,
                    # Lề phải rộng cho tất cả label
                    margin=dict(l=60, r=120, t=80, b=50),
                )
                fig_imr.update_yaxes(title_text=selected_label, row=1, col=1)
                fig_imr.update_yaxes(title_text="Moving Range",  row=2, col=1)
                fig_imr.update_xaxes(title_text="Sample Index",  row=2, col=1)

                fig_imr = apply_clean_axes_subplot(fig_imr, n_rows=2)
                st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
        import traceback
        st.code(traceback.format_exc())

else:
    st.info("👈 Please upload the production data report (Excel/CSV) to begin.")
