import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# =========================================
# PAGE CONFIG
# =========================================
st.set_page_config(
    page_title="KB9Q Line 4 Analytics",
    layout="wide"
)

# =========================================
# CSS STYLE
# =========================================
st.markdown("""
<style>

.main {
    background-color: #f4f6f9;
}

/* KPI CARD */
div[data-testid="stMetric"] {
    background: white;
    border-radius: 12px;
    padding: 15px;
    border-left: 6px solid #1565C0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

/* CHART CARD */
div.stPlotlyChart {
    background: white;
    padding: 15px;
    border-radius: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08);
}

/* TITLE */
h1, h2, h3 {
    color: #0D47A1 !important;
    font-weight: 700 !important;
}

</style>
""", unsafe_allow_html=True)

# =========================================
# SIDEBAR
# =========================================
st.sidebar.header("📂 Data Management")

uploaded_file = st.sidebar.file_uploader(
    "Upload Excel / CSV",
    type=["xlsx", "xls", "csv"]
)

# =========================================
# MAIN
# =========================================
if uploaded_file:

    try:

        # =========================================
        # LOAD DATA
        # =========================================
        df = (
            pd.read_csv(uploaded_file)
            if uploaded_file.name.endswith(".csv")
            else pd.read_excel(uploaded_file)
        )

        # Clean column
        df.columns = [
            re.sub(r"\s+", " ", str(c)).strip()
            for c in df.columns
        ]

        # =========================================
        # FILTER
        # =========================================
        if "用途碼" in df.columns:

            usage_list = sorted(
                df["用途碼"]
                .dropna()
                .unique()
                .tolist()
            )

            selected_usage = st.sidebar.multiselect(
                "Filter 用途碼",
                options=usage_list,
                default=usage_list
            )

            df_filtered = df[
                df["用途碼"].isin(selected_usage)
            ]

        else:
            df_filtered = df.copy()

        # =========================================
        # FIND COLUMN
        # =========================================
        def find_col(keyword, exclude=[]):

            for col in df.columns:

                if (
                    keyword in col and
                    not any(ex in col for ex in exclude)
                ):
                    return col

            return None

        # =========================================
        # METRIC MAP
        # =========================================
        metrics = {

            "YS (降伏強度)": {
                "data": find_col(
                    "降伏強度 (YS)"
                ),
                "lsl": find_col(
                    "降伏強度[(min.)管制值]"
                ),
                "usl": find_col(
                    "降伏強度[(max.)管制值]"
                )
            },

            "TS (抗拉強度)": {
                "data": find_col(
                    "抗拉強度 (TS)"
                ),
                "lsl": find_col(
                    "抗拉強度[(min.)管制值]"
                ),
                "usl": find_col(
                    "抗拉強度[(max.)管制值]"
                )
            },

            "EL (伸長率)": {
                "data": find_col(
                    "伸長率 (EL)"
                ),
                "lsl": find_col(
                    "伸長率[(min.)管制值]"
                ),
                "usl": find_col(
                    "伸長率[(max.)管制值]"
                )
            },

            "Hardness (HRB)": {
                "data": find_col(
                    "硬度HRB"
                ),
                "lsl": find_col(
                    "硬度[(min.)管制值]"
                ),
                "usl": find_col(
                    "硬度[(max.)管制值]"
                )
            },

            "YPE": {
                "data": find_col("YPE"),
                "lsl": None,
                "usl": None
            }
        }

        # =========================================
        # SELECT PROPERTY
        # =========================================
        selected_label = st.sidebar.selectbox(
            "Mechanical Property",
            list(metrics.keys())
        )

        view_mode = st.sidebar.radio(
            "View Mode",
            [
                "Distribution & Trending",
                "SPC Control Chart"
            ]
        )

        data_col = metrics[selected_label]["data"]
        lsl_col = metrics[selected_label]["lsl"]
        usl_col = metrics[selected_label]["usl"]

        if data_col is None:

            st.error(
                f"Cannot find column for {selected_label}"
            )

            st.stop()

        # =========================================
        # DATA
        # =========================================
        plot_data = pd.to_numeric(
            df_filtered[data_col],
            errors="coerce"
        ).dropna().reset_index(drop=True)

        n = len(plot_data)

        mu = plot_data.mean()

        sigma = plot_data.std()

        # =========================================
        # SPEC LIMIT
        # =========================================
        lsl = (
            pd.to_numeric(
                df_filtered[lsl_col],
                errors="coerce"
            ).median()
            if lsl_col
            else None
        )

        usl = (
            pd.to_numeric(
                df_filtered[usl_col],
                errors="coerce"
            ).median()
            if usl_col
            else None
        )

        # =========================================
        # CAPABILITY
        # =========================================
        cp = None
        ca = None
        cpk = None

        if (
            sigma > 0 and
            lsl is not None and
            usl is not None
        ):

            cp = (
                (usl - lsl)
                / (6 * sigma)
            )

            spec_center = (
                (usl + lsl)
                / 2
            )

            ca = abs(
                mu - spec_center
            ) / (
                (usl - lsl) / 2
            )

            cpu = (
                (usl - mu)
                / (3 * sigma)
            )

            cpl = (
                (mu - lsl)
                / (3 * sigma)
            )

            cpk = min(cpu, cpl)

        # =========================================
        # CONTROL LIMIT
        # =========================================
        ucl = mu + 3 * sigma
        lcl = mu - 3 * sigma

        # =========================================
        # TITLE
        # =========================================
        st.title(
            f"🚀 KB9Q Line 4 Analytics — {selected_label}"
        )

        # =========================================
        # KPI
        # =========================================
        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Samples",
            f"{n:,}"
        )

        c2.metric(
            "Mean",
            f"{mu:.2f}"
        )

        c3.metric(
            "σ (Std Dev)",
            f"{sigma:.2f}"
        )

        c4.metric(
            "Cpk",
            f"{cpk:.2f}" if cpk else "N/A",
            delta=(
                "Excellent"
                if cpk and cpk >= 1.67
                else "Stable"
                if cpk and cpk >= 1.33
                else "Risk"
            )
        )

        # =========================================
        # CAPABILITY BAR
        # =========================================
        if cpk:

            st.progress(
                min(max(cpk / 2, 0), 1)
            )

            st.caption(
                f"""
                Cp = {cp:.2f}
                | Ca = {ca:.2f}
                | Cpk = {cpk:.2f}
                """
            )

        # =========================================
        # VIEW 1
        # =========================================
        if view_mode == "Distribution & Trending":

            col1, col2 = st.columns([1, 1.4])

            # =====================================
            # DISTRIBUTION
            # =====================================
            with col1:

                st.subheader(
                    "Distribution State"
                )

                k_bins = (
                    math.ceil(
                        1 + 3.322 * math.log10(n)
                    )
                    if n > 0 else 10
                )

                bin_width = (
                    (plot_data.max() - plot_data.min())
                    / k_bins
                    if n > 1 else 1
                )

                fig_dist = go.Figure()

                # Histogram
                fig_dist.add_trace(
                    go.Histogram(
                        x=plot_data,
                        nbinsx=k_bins,
                        name="Distribution",
                        marker=dict(
                            color="rgba(33,150,243,0.65)",
                            line=dict(
                                color="white",
                                width=1
                            )
                        )
                    )
                )

                # Normal curve
                if sigma > 0:

                    x_curve = np.linspace(
                        mu - 4*sigma,
                        mu + 4*sigma,
                        300
                    )

                    y_curve = (
                        norm.pdf(
                            x_curve,
                            mu,
                            sigma
                        )
                        * n
                        * bin_width
                    )

                    fig_dist.add_trace(
                        go.Scatter(
                            x=x_curve,
                            y=y_curve,
                            mode="lines",
                            name="Normal Curve",
                            line=dict(
                                color="#0D47A1",
                                width=4
                            )
                        )
                    )

                # Mean
                fig_dist.add_vline(
                    x=mu,
                    line_color="green",
                    line_width=3,
                    annotation_text="Mean"
                )

                # LSL
                if lsl is not None:

                    fig_dist.add_vline(
                        x=lsl,
                        line_color="red",
                        line_dash="dash",
                        line_width=3,
                        annotation_text="LSL"
                    )

                # USL
                if usl is not None:

                    fig_dist.add_vline(
                        x=usl,
                        line_color="red",
                        line_dash="dash",
                        line_width=3,
                        annotation_text="USL"
                    )

                fig_dist.update_layout(

                    title=dict(
                        text=f"{selected_label} Distribution",
                        x=0.02
                    ),

                    template="plotly_white",

                    height=520,

                    bargap=0.03,

                    legend=dict(
                        orientation="h",
                        y=1.05
                    ),

                    xaxis=dict(
                        title="Mechanical Property"
                    ),

                    yaxis=dict(
                        title="Frequency",
                        gridcolor="rgba(0,0,0,0.05)"
                    )
                )

                st.plotly_chart(
                    fig_dist,
                    use_container_width=True
                )

            # =====================================
            # TREND
            # =====================================
            with col2:

                st.subheader(
                    "Process Trending"
                )

                fig_trend = go.Figure()

                # Actual
                fig_trend.add_trace(
                    go.Scatter(

                        x=plot_data.index,
                        y=plot_data,

                        mode='lines+markers',

                        name='Actual',

                        line=dict(
                            color='#1565C0',
                            width=2.5
                        ),

                        marker=dict(
                            size=6,
                            color='white',
                            line=dict(
                                color='#1565C0',
                                width=2
                            )
                        )
                    )
                )

                # Rolling mean
                rolling = (
                    plot_data
                    .rolling(10)
                    .mean()
                )

                fig_trend.add_trace(
                    go.Scatter(

                        x=plot_data.index,
                        y=rolling,

                        mode='lines',

                        name='Rolling Mean',

                        line=dict(
                            color='#2E7D32',
                            width=4
                        )
                    )
                )

                # Mean
                fig_trend.add_hline(
                    y=mu,
                    line_color="green",
                    line_width=2
                )

                # UCL
                fig_trend.add_hline(
                    y=ucl,
                    line_color="orange",
                    line_dash="dash"
                )

                # LCL
                fig_trend.add_hline(
                    y=lcl,
                    line_color="orange",
                    line_dash="dash"
                )

                # LSL
                if lsl is not None:

                    fig_trend.add_hline(
                        y=lsl,
                        line_color="red",
                        line_dash="dot",
                        line_width=2.5
                    )

                # USL
                if usl is not None:

                    fig_trend.add_hline(
                        y=usl,
                        line_color="red",
                        line_dash="dot",
                        line_width=2.5
                    )

                # Outlier
                outlier = plot_data[
                    (plot_data > ucl) |
                    (plot_data < lcl)
                ]

                fig_trend.add_trace(
                    go.Scatter(

                        x=outlier.index,
                        y=outlier.values,

                        mode="markers",

                        name="Outlier",

                        marker=dict(
                            color="red",
                            size=11
                        )
                    )
                )

                fig_trend.update_layout(

                    title=dict(
                        text=f"{selected_label} Trending",
                        x=0.02
                    ),

                    template="plotly_white",

                    height=520,

                    hovermode="x unified",

                    legend=dict(
                        orientation="h",
                        y=1.08
                    ),

                    xaxis=dict(
                        title="Production Sequence",
                        gridcolor="rgba(0,0,0,0.05)"
                    ),

                    yaxis=dict(
                        title="Value",
                        gridcolor="rgba(0,0,0,0.05)"
                    )
                )

                st.plotly_chart(
                    fig_trend,
                    use_container_width=True
                )

        # =========================================
        # VIEW 2
        # =========================================
        else:

            st.subheader(
                "I-MR Control Chart"
            )

            mr = plot_data.diff().abs()

            fig_imr = make_subplots(

                rows=2,
                cols=1,

                shared_xaxes=True,

                vertical_spacing=0.1,

                subplot_titles=(
                    "Individual Chart",
                    "Moving Range Chart"
                )
            )

            # I chart
            fig_imr.add_trace(
                go.Scatter(
                    y=plot_data,
                    mode='lines+markers',
                    line=dict(
                        color="#1565C0",
                        width=2
                    )
                ),
                row=1,
                col=1
            )

            fig_imr.add_hline(
                y=ucl,
                line_dash="dash",
                line_color="red",
                row=1,
                col=1
            )

            fig_imr.add_hline(
                y=lcl,
                line_dash="dash",
                line_color="red",
                row=1,
                col=1
            )

            fig_imr.add_hline(
                y=mu,
                line_color="green",
                row=1,
                col=1
            )

            # MR chart
            fig_imr.add_trace(
                go.Scatter(
                    y=mr,
                    mode='lines+markers',
                    line=dict(
                        color="orange",
                        width=2
                    )
                ),
                row=2,
                col=1
            )

            fig_imr.update_layout(
                height=700,
                template="plotly_white",
                showlegend=False
            )

            st.plotly_chart(
                fig_imr,
                use_container_width=True
            )

    except Exception as e:

        st.error(f"Error: {e}")

else:

    st.info(
        "👈 Upload production Excel file"
    )
