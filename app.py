import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm

# =========================================
# PAGE CONFIG
# =========================================
st.set_page_config(
    page_title="KB9Q Capability Dashboard",
    layout="wide"
)

st.title("📊 KB9Q Line 4 Mechanical Capability Dashboard")

# =========================================
# FILE UPLOAD
# =========================================
uploaded = st.sidebar.file_uploader(
    "Upload Excel / CSV",
    type=["xlsx", "xls", "csv"]
)

if uploaded:

    # =========================================
    # LOAD DATA
    # =========================================
    df = (
        pd.read_csv(uploaded)
        if uploaded.name.endswith(".csv")
        else pd.read_excel(uploaded)
    )

    # =========================================
    # FILTER
    # =========================================
    if "用途碼" in df.columns:

        usage = st.sidebar.multiselect(
            "用途碼",
            df["用途碼"].dropna().unique(),
            default=df["用途碼"].dropna().unique()
        )

        df = df[df["用途碼"].isin(usage)]

    # =========================================
    # PROPERTY MAP
    # =========================================
    metrics = {

        "YS": {
            "data": "降伏強度 (YS)",
            "lsl": "降伏強度[(min.)管制值]",
            "usl": "降伏強度[(max.)管制值]"
        },

        "TS": {
            "data": "抗拉強度 (TS)",
            "lsl": "抗拉強度[(min.)管制值]",
            "usl": "抗拉強度[(max.)管制值]"
        },

        "EL": {
            "data": "伸長率 (EL)",
            "lsl": "伸長率[(min.)管制值]",
            "usl": "伸長率[(max.)管制值]"
        },

        "HRB": {
            "data": "硬度HRB",
            "lsl": "硬度[(min.)管制值]",
            "usl": "硬度[(max.)管制值]"
        },

        "YPE": {
            "data": "YPE",
            "lsl": None,
            "usl": None
        }
    }

    # =========================================
    # SELECT PROPERTY
    # =========================================
    selected = st.sidebar.selectbox(
        "Mechanical Property",
        list(metrics.keys())
    )

    data_col = metrics[selected]["data"]
    lsl_col = metrics[selected]["lsl"]
    usl_col = metrics[selected]["usl"]

    # =========================================
    # DATA CLEANING
    # =========================================
    data = pd.to_numeric(
        df[data_col],
        errors="coerce"
    ).dropna().reset_index(drop=True)

    # =========================================
    # SPEC LIMIT
    # =========================================
    lsl = (
        pd.to_numeric(df[lsl_col], errors="coerce").median()
        if lsl_col and lsl_col in df.columns
        else data.min()
    )

    usl = (
        pd.to_numeric(df[usl_col], errors="coerce").median()
        if usl_col and usl_col in df.columns
        else data.max()
    )

    # =========================================
    # BASIC STATISTICS
    # =========================================
    mean = data.mean()
    std = data.std()

    spec_center = (lsl + usl) / 2

    # =========================================
    # PROCESS CAPABILITY
    # =========================================
    cp = (usl - lsl) / (6 * std) if std > 0 else 0

    ca = abs(mean - spec_center) / (
        (usl - lsl) / 2
    )

    cpu = (usl - mean) / (3 * std)
    cpl = (mean - lsl) / (3 * std)

    cpk = min(cpu, cpl)

    # =========================================
    # CONTROL LIMIT
    # =========================================
    ucl = mean + 3 * std
    lcl = mean - 3 * std

    # =========================================
    # KPI
    # =========================================
    k1, k2, k3, k4 = st.columns(4)

    k1.metric("Mean", f"{mean:.2f}")
    k2.metric("Cp", f"{cp:.2f}")
    k3.metric("Ca", f"{ca:.2f}")
    k4.metric(
        "Cpk",
        f"{cpk:.2f}",
        delta="Stable" if cpk >= 1.33 else "Risk"
    )

    # =========================================
    # CHART LAYOUT
    # =========================================
    col1, col2 = st.columns(2)

    # =========================================
    # DISTRIBUTION CHART
    # =========================================
    with col1:

        fig_dist = go.Figure()

        # Histogram
        fig_dist.add_trace(
            go.Histogram(
                x=data,
                histnorm="probability density",
                nbinsx=30,
                name="Distribution"
            )
        )

        # Normal Curve
        x = np.linspace(data.min(), data.max(), 200)

        y = norm.pdf(x, mean, std)

        fig_dist.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name="Normal Curve"
            )
        )

        # Mean
        fig_dist.add_vline(
            x=mean,
            line_color="blue",
            annotation_text="Mean"
        )

        # Spec Center
        fig_dist.add_vline(
            x=spec_center,
            line_dash="dot",
            line_color="green",
            annotation_text="Spec Center"
        )

        # LSL
        fig_dist.add_vline(
            x=lsl,
            line_dash="dash",
            line_color="red",
            annotation_text="LSL"
        )

        # USL
        fig_dist.add_vline(
            x=usl,
            line_dash="dash",
            line_color="red",
            annotation_text="USL"
        )

        fig_dist.update_layout(
            title=f"{selected} Distribution",
            template="plotly_white",
            height=500
        )

        st.plotly_chart(
            fig_dist,
            use_container_width=True
        )

    # =========================================
    # TREND CHART
    # =========================================
    with col2:

        rolling = data.rolling(10).mean()

        outlier = data[
            (data > ucl) | (data < lcl)
        ]

        fig_trend = go.Figure()

        # Actual
        fig_trend.add_trace(
            go.Scatter(
                y=data,
                mode="lines+markers",
                name="Actual"
            )
        )

        # Rolling Mean
        fig_trend.add_trace(
            go.Scatter(
                y=rolling,
                mode="lines",
                name="Rolling Mean"
            )
        )

        # Outlier
        fig_trend.add_trace(
            go.Scatter(
                x=outlier.index,
                y=outlier.values,
                mode="markers",
                marker=dict(size=10, color="red"),
                name="Outlier"
            )
        )

        # Mean
        fig_trend.add_hline(
            y=mean,
            line_color="blue"
        )

        # UCL
        fig_trend.add_hline(
            y=ucl,
            line_dash="dash",
            line_color="red"
        )

        # LCL
        fig_trend.add_hline(
            y=lcl,
            line_dash="dash",
            line_color="red"
        )

        fig_trend.update_layout(
            title=f"{selected} Trend",
            template="plotly_white",
            height=500
        )

        st.plotly_chart(
            fig_trend,
            use_container_width=True
        )

    # =========================================
    # SUMMARY TABLE
    # =========================================
    st.subheader("📋 SPC Summary")

    summary = pd.DataFrame({

        "Metric": [
            "Mean",
            "STD",
            "LSL",
            "USL",
            "Cp",
            "Ca",
            "Cpk"
        ],

        "Value": [
            round(mean, 2),
            round(std, 2),
            round(lsl, 2),
            round(usl, 2),
            round(cp, 2),
            round(ca, 2),
            round(cpk, 2)
        ]
    })

    st.dataframe(
        summary,
        use_container_width=True
    )

else:
    st.info("👈 Upload production data")
