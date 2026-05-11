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
st.set_page_config(
    page_title="Line 4 Quality Analytics",
    layout="wide"
)

st.markdown("""
<style>

.main {
    background-color: #F8FAFC;
}

div.stPlotlyChart {
    background-color: #ffffff;
    padding: 12px;
    border-radius: 10px;
    border: 1px solid #CBD5E1;
    box-shadow: 0 3px 6px rgba(0,0,0,0.08);
}

div[data-testid="stMetric"] {
    background-color: #ffffff;
    border-left: 6px solid #1E40AF;
    border-radius: 6px;
    padding: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08);
}

h1, h2, h3 {
    color: #1E3A8A !important;
    font-family: 'Segoe UI', sans-serif;
    font-weight: 700;
}

</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CACHING & UTILITY FUNCTIONS
# ==========================================
@st.cache_data
def load_and_clean_data(file):

    df = (
        pd.read_csv(file)
        if file.name.endswith('.csv')
        else pd.read_excel(file)
    )

    df.columns = [
        re.sub(r'\s+', ' ', str(c)).strip()
        for c in df.columns
    ]

    return df


def find_data_col(df, key):

    for col in df.columns:

        if (
            re.search(key, col, re.IGNORECASE)
            and not any(
                kw in col
                for kw in ["管制", "規格", "要求"]
            )
        ):
            return col

    return None


def get_limit(df, keyword, limit_type, category):

    col = next(
        (
            c for c in df.columns
            if keyword in c
            and limit_type in c.lower()
            and category in c
        ),
        None
    )

    if col:

        val = pd.to_numeric(
            df[col],
            errors='coerce'
        ).median()

        return (
            float(val)
            if pd.notnull(val) and val > 0
            else None
        )

    return None


# ==========================================
# EXPORT CONFIG
# ==========================================
export_config = {
    'displayModeBar': True,
    'displaylogo': False,
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'Quality_Report_HD',
        'height': 1200,
        'width': 2200,
        'scale': 4
    }
}

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.header("📂 DATA SOURCE")

uploaded_file = st.sidebar.file_uploader(
    "Upload Excel/CSV Report",
    type=["xlsx", "csv", "xls"]
)

# ==========================================
# MAIN
# ==========================================
if uploaded_file:

    try:

        df_raw = load_and_clean_data(uploaded_file)

        df = df_raw.copy()

        # ======================================
        # FILTER USAGE CODE
        # ======================================
        if "用途碼" in df_raw.columns:

            usage_list = sorted(
                df_raw["用途碼"]
                .dropna()
                .unique()
                .tolist()
            )

            selected_usages = st.sidebar.multiselect(
                "Filter Usage Code:",
                options=usage_list,
                default=usage_list
            )

            df = df_raw[
                df_raw["用途碼"].isin(selected_usages)
            ]

        # ======================================
        # METRIC MAP
        # ======================================
        metrics_map = {
            "YS": "YS",
            "TS": "TS",
            "EL": "EL",
            "Hardness": "HRB",
            "YPE": "YPE"
        }

        available = [
            k for k, v in metrics_map.items()
            if find_data_col(df, v)
        ]

        if not available:
            st.stop()

        selected_label = st.sidebar.selectbox(
            "Select Parameter:",
            available
        )

        view_mode = st.sidebar.radio(
            "View Mode:",
            [
                "Process Analytics",
                "SPC Control Charts (I-MR)"
            ]
        )

        short_key = metrics_map[selected_label]

        data_col = find_data_col(df, short_key)

        zh_map = {
            "YS": "降伏強度",
            "TS": "抗拉強度",
            "EL": "伸長率",
            "HRB": "硬度",
            "YPE": "YPE"
        }

        zh_key = zh_map.get(short_key, short_key)

        # ======================================
        # LIMITS
        # ======================================
        v_lsl_std = get_limit(
            df,
            zh_key,
            "min",
            "管制"
        )

        v_usl_std = get_limit(
            df,
            zh_key,
            "max",
            "管制"
        )

        v_lsl_tgt = get_limit(
            df,
            zh_key,
            "min",
            "客戶要求"
        )

        v_usl_tgt = get_limit(
            df,
            zh_key,
            "max",
            "客戶要求"
        )

        # ======================================
        # DATA
        # ======================================
        if data_col:

            plot_data = pd.to_numeric(
                df[data_col],
                errors='coerce'
            ).dropna().reset_index(drop=True)

            n = len(plot_data)

            mu = plot_data.mean()

            sigma = plot_data.std()

            ucl = mu + 3 * sigma

            lcl = mu - 3 * sigma

            cpk = (
                min(
                    (v_usl_std - mu) / (3 * sigma),
                    (mu - v_lsl_std) / (3 * sigma)
                )
                if sigma > 0
                and v_usl_std
                and v_lsl_std
                else None
            )

            # ==================================
            # HEADER
            # ==================================
            st.title(
                f"📊 Quality Analytics: {selected_label}"
            )

            k1, k2, k3, k4 = st.columns(4)

            k1.metric("Samples (N)", n)

            k2.metric("Mean (μ)", f"{mu:.2f}")

            k3.metric("Std Dev (σ)", f"{sigma:.2f}")

            k4.metric(
                "Cpk (Internal)",
                f"{cpk:.2f}" if cpk else "N/A"
            )

            # ==================================
            # PROCESS ANALYTICS
            # ==================================
            if view_mode == "Process Analytics":

                st.subheader(
                    "I. Distribution & Capability"
                )

                k_bins = (
                    math.ceil(
                        1 + 3.322 * math.log10(n)
                    )
                    if n > 0
                    else 10
                )

                pts = [
                    v for v in [
                        v_lsl_tgt,
                        v_usl_tgt,
                        v_lsl_std,
                        v_usl_std,
                        plot_data.min(),
                        plot_data.max()
                    ]
                    if v is not None
                ]

                x_range = [
                    min(pts) - abs(min(pts) * 0.1),
                    max(pts) + abs(max(pts) * 0.1)
                ]

                # ==================================
                # DISTRIBUTION CHART
                # ==================================
                fig_dist = go.Figure()

                # HISTOGRAM
                fig_dist.add_trace(
                    go.Histogram(
                        x=plot_data,
                        nbinsx=k_bins,
                        marker_color='#7FB3D5',
                        opacity=0.85,
                        marker_line_color='white',
                        marker_line_width=1.2
                    )
                )

                # NORMAL CURVE
                if sigma > 0:

                    x_c = np.linspace(
                        x_range[0],
                        x_range[1],
                        200
                    )

                    y_c = norm.pdf(
                        x_c,
                        mu,
                        sigma
                    ) * n * (
                        (plot_data.max() - plot_data.min())
                        / k_bins
                    )

                    fig_dist.add_trace(
                        go.Scatter(
                            x=x_c,
                            y=y_c,
                            mode='lines',
                            line=dict(
                                color='#1E3A8A',
                                width=5
                            )
                        )
                    )

                # ==================================
                # LIMIT LINES
                # ==================================
                def add_dist_vline(
                    val,
                    name,
                    color,
                    dash,
                    text_side="left"
                ):

                    if val is not None:

                        # LINE
                        fig_dist.add_vline(
                            x=val,
                            line_dash=dash,
                            line_color=color,
                            line_width=5,
                            opacity=1
                        )

                        # TEXT POSITION
                        x_shift = -12 if text_side == "left" else 12

                        align = (
                            "right"
                            if text_side == "left"
                            else "left"
                        )

                        # TEXT
                        fig_dist.add_annotation(
                            x=val,
                            y=10,

                            text=f"<b>{name}<br>{val:.1f}</b>",

                            showarrow=False,

                            xshift=x_shift,

                            font=dict(
                                size=20,
                                color=color,
                                family="Arial Black"
                            ),

                            align=align,

                            bgcolor="rgba(0,0,0,0)"
                        )

                add_dist_vline(
                    v_lsl_tgt,
                    "Cust LSL",
                    "#2E7D32",
                    "solid",
                    "left"
                )

                add_dist_vline(
                    v_usl_tgt,
                    "Cust USL",
                    "#2E7D32",
                    "solid",
                    "right"
                )

                add_dist_vline(
                    v_lsl_std,
                    "Int LSL",
                    "#D32F2F",
                    "dash",
                    "left"
                )

                add_dist_vline(
                    v_usl_std,
                    "Int USL",
                    "#D32F2F",
                    "dash",
                    "right"
                )

                # ==================================
                # LAYOUT
                # ==================================
                fig_dist.update_layout(
                    template="simple_white",

                    height=650,

                    xaxis_range=x_range,

                    showlegend=False,

                    font=dict(
                        size=18,
                        family="Arial",
                        color="black"
                    ),

                    margin=dict(
                        t=80,
                        r=80,
                        l=80,
                        b=80
                    )
                )

                fig_dist.update_xaxes(
                    showline=True,
                    linewidth=3,
                    linecolor='black',
                    mirror='all',
                    tickfont=dict(size=18)
                )

                fig_dist.update_yaxes(
                    showline=True,
                    linewidth=3,
                    linecolor='black',
                    mirror='all',
                    tickfont=dict(size=18)
                )

                st.plotly_chart(
                    fig_dist,
                    use_container_width=True,
                    config=export_config
                )

                # ==================================
                # TREND ANALYSIS
                # ==================================
                st.subheader("II. Trend Analysis")

                fig_trend = go.Figure()

                if v_lsl_tgt and v_usl_tgt:

                    fig_trend.add_hrect(
                        y0=v_lsl_tgt,
                        y1=v_usl_tgt,
                        fillcolor="#E8F5E9",
                        opacity=0.4,
                        layer="below",
                        line_width=0
                    )

                # ==================================
                # TREND LIMITS
                # ==================================
                def add_trend_hline(
                    val,
                    name,
                    color,
                    dash,
                    pos
                ):

                    if val is not None:

                        fig_trend.add_hline(
                            y=val,
                            line_dash=dash,
                            line_color=color,
                            line_width=5,

                            annotation_text=f"<b>{name}: {val:.1f}</b>",

                            annotation_position=pos,

                            annotation_font=dict(
                                size=18,
                                color=color,
                                family="Arial Black"
                            ),

                            annotation_bgcolor="rgba(255,255,255,0)"
                        )

                add_trend_hline(v_usl_tgt, "Cust USL", "#2E7D32", "solid", "top right")
                add_trend_hline(v_usl_std, "Int USL", "#D32F2F", "dash", "bottom right")
                add_trend_hline(v_lsl_tgt, "Cust LSL", "#2E7D32", "solid", "bottom right")
                add_trend_hline(v_lsl_std, "Int LSL", "#D32F2F", "dash", "top right")
                add_trend_hline(ucl, "UCL", "#E67E22", "dot", "top left")
                add_trend_hline(lcl, "LCL", "#E67E22", "dot", "bottom left")
                add_trend_hline(mu, "Mean", "#8E44AD", "dashdot", "top left")

                # TREND LINE
                fig_trend.add_trace(
                    go.Scatter(
                        x=plot_data.index,
                        y=plot_data,
                        mode='lines+markers',

                        line=dict(
                            color='#1F77B4',
                            width=4
                        ),

                        marker=dict(
                            size=10,
                            color='#1F77B4',
                            line=dict(
                                color='white',
                                width=1
                            )
                        )
                    )
                )

                # OOC
                usl_limit = (
                    v_usl_std
                    if v_usl_std is not None
                    else (
                        v_usl_tgt
                        if v_usl_tgt is not None
                        else float('inf')
                    )
                )

                lsl_limit = (
                    v_lsl_std
                    if v_lsl_std is not None
                    else (
                        v_lsl_tgt
                        if v_lsl_tgt is not None
                        else float('-inf')
                    )
                )

                ooc = plot_data[
                    (plot_data > usl_limit) |
                    (plot_data < lsl_limit)
                ]

                if not ooc.empty:

                    fig_trend.add_trace(
                        go.Scatter(
                            x=ooc.index,
                            y=ooc,
                            mode='markers',

                            marker=dict(
                                color='#D32F2F',
                                size=14,
                                symbol='circle',
                                line=dict(
                                    color='white',
                                    width=2
                                )
                            )
                        )
                    )

                fig_trend.update_layout(
                    template="simple_white",

                    height=750,

                    showlegend=False,

                    font=dict(
                        size=18,
                        family="Arial",
                        color="black"
                    ),

                    margin=dict(
                        t=80,
                        r=80,
                        l=80,
                        b=80
                    )
                )

                fig_trend.update_xaxes(
                    showline=True,
                    linewidth=3,
                    linecolor='black',
                    mirror='all',
                    tickfont=dict(size=18)
                )

                fig_trend.update_yaxes(
                    showline=True,
                    linewidth=3,
                    linecolor='black',
                    mirror='all',
                    tickfont=dict(size=18)
                )

                st.plotly_chart(
                    fig_trend,
                    use_container_width=True,
                    config=export_config
                )

            # ==================================
            # SPC CONTROL CHARTS
            # ==================================
            else:

                st.subheader(
                    "III. Statistical Process Control (I-MR)"
                )

                mr = plot_data.diff().abs()

                mr_mean = mr.mean()

                mr_ucl = mr.mean() * 3.267

                fig_imr = make_subplots(
                    rows=2,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.15,
                    subplot_titles=(
                        "Individual Chart (I)",
                        "Moving Range Chart (MR)"
                    )
                )

                fig_imr.add_trace(
                    go.Scatter(
                        y=plot_data,
                        mode='lines+markers',

                        line=dict(
                            color='#1F77B4',
                            width=4
                        ),

                        marker=dict(size=9)
                    ),
                    row=1,
                    col=1
                )

                fig_imr.add_trace(
                    go.Scatter(
                        y=mr,
                        mode='lines+markers',

                        line=dict(
                            color='#1F77B4',
                            width=4
                        ),

                        marker=dict(size=9)
                    ),
                    row=2,
                    col=1
                )

                # ==================================
                # IMR LIMITS
                # ==================================
                def add_imr_hline(
                    val,
                    label,
                    color,
                    row
                ):

                    if val is not None:

                        fig_imr.add_hline(
                            y=val,
                            line_dash="dash",
                            line_color=color,
                            line_width=5,

                            annotation_text=f"<b>{label}: {val:.1f}</b>",

                            annotation_position="top right",

                            annotation_font=dict(
                                color=color,
                                size=18,
                                family="Arial Black"
                            ),

                            annotation_bgcolor="rgba(255,255,255,0)",

                            row=row,
                            col=1
                        )

                add_imr_hline(ucl, 'UCL', '#D32F2F', 1)
                add_imr_hline(lcl, 'LCL', '#D32F2F', 1)
                add_imr_hline(mu, 'Mean', '#2E7D32', 1)

                add_imr_hline(mr_mean, 'MR Mean', '#2E7D32', 2)
                add_imr_hline(mr_ucl, 'MR UCL', '#D32F2F', 2)

                fig_imr.update_layout(
                    height=900,

                    template="simple_white",

                    showlegend=False,

                    font=dict(
                        size=18,
                        family="Arial",
                        color="black"
                    ),

                    margin=dict(
                        l=80,
                        r=80,
                        t=80,
                        b=80
                    )
                )

                fig_imr.update_xaxes(
                    showline=True,
                    linewidth=3,
                    linecolor='black',
                    mirror='all',
                    tickfont=dict(size=18)
                )

                fig_imr.update_yaxes(
                    showline=True,
                    linewidth=3,
                    linecolor='black',
                    mirror='all',
                    tickfont=dict(size=18)
                )

                st.plotly_chart(
                    fig_imr,
                    use_container_width=True,
                    config=export_config
                )

    except Exception as e:

        st.error(f"Error: {e}")

else:

    st.info("👈 Please upload data to begin.")
