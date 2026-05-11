import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm

# =====================================
# PAGE CONFIG
# =====================================
st.set_page_config(page_title="KB9Q Capability Dashboard", layout="wide")

st.title("📊 KB9Q Line 4 Mechanical Dashboard")

# =====================================
# FILE UPLOAD
# =====================================
uploaded = st.sidebar.file_uploader(
    "Upload Excel/CSV",
    type=["csv", "xlsx", "xls"]
)

if uploaded:

    # =====================================
    # LOAD DATA
    # =====================================
    df = (
        pd.read_csv(uploaded)
        if uploaded.name.endswith(".csv")
        else pd.read_excel(uploaded)
    )

    # =====================================
    # FILTER
    # =====================================
    if "用途碼" in df.columns:
        usage = st.sidebar.multiselect(
            "用途碼",
            df["用途碼"].dropna().unique(),
            default=df["用途碼"].dropna().unique()
        )
        df = df[df["用途碼"].isin(usage)]

    # =====================================
    # METRIC MAP
    # =====================================
    metrics = {
        "YS": "降伏強度",
        "TS": "抗拉強度",
        "EL": "伸長率",
        "YPE": "YPE",
        "HRB": "硬度"
    }

    selected = st.sidebar.selectbox(
        "Mechanical Property",
        list(metrics.keys())
    )

    keyword = metrics[selected]

    # =====================================
    # COLUMN DETECTION
    # =====================================
    data_col = next(
        (
            c for c in df.columns
            if keyword in c
            and "min" not in c.lower()
            and "max" not in c.lower()
        ),
        None
    )

    lsl_col = next(
        (
            c for c in df.columns
            if keyword in c and "min" in c.lower()
        ),
        None
    )

    usl_col = next(
        (
            c for c in df.columns
            if keyword in c and "max" in c.lower()
        ),
        None
    )

    if data_col:

        # =====================================
        # DATA PREP
        # =====================================
        data = pd.to_numeric(
            df[data_col],
            errors="coerce"
        ).dropna()

        mean = data.mean()
        std = data.std()

        lsl = (
            pd.to_numeric(df[lsl_col], errors="coerce").median()
            if lsl_col else data.min()
        )

        usl = (
            pd.to_numeric(df[usl_col], errors="coerce").median()
            if usl_col else data.max()
        )

        spec_center = (lsl + usl) / 2

        # =====================================
        # CAPABILITY
        # =====================================
        cp = (usl - lsl) / (6 * std) if std > 0 else 0

        ca = abs(mean - spec_center) / (
            (usl - lsl) / 2
        )

        cpu = (usl - mean) / (3 * std)
        cpl = (mean - lsl) / (3 * std)

        cpk = min(cpu, cpl)

        # =====================================
        # CONTROL LIMIT
        # =====================================
        ucl = mean + 3 * std
        lcl = mean - 3 * std

        # =====================================
        # KPI
        # =====================================
        k1, k2, k3, k4 = st.columns(4)

        k1.metric("Mean", f"{mean:.2f}")
        k2.metric("Cp", f"{cp:.2f}")
        k3.metric("Ca", f"{ca:.2f}")
        k4.metric(
            "Cpk",
            f"{cpk:.2f}",
            delta="Stable" if cpk >= 1.33 else "Risk"
        )

        # =====================================
        # CHART LAYOUT
        # =====================================
        col1, col2 = st.columns(2)

        # =====================================
        # DISTRIBUTION
        # =====================================
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

            # LSL / USL
            fig_dist.add_vline(
                x=lsl,
                line_dash="dash",
                line_color="red",
                annotation_text="LSL"
            )

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

        # =====================================
        # TREND
        # =====================================
        with col2:

            trend = data.reset_index(drop=True)

            rolling = trend.rolling(10).mean()

            outlier = trend[
                (trend > ucl) | (trend < lcl)
            ]

            fig_trend = go.Figure()

            # Actual
            fig_trend.add_trace(
                go.Scatter(
                    y=trend,
                    mode="lines+markers",
                    name="Actual"
                )
            )

            # Rolling mean
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
                    marker=dict(size=10),
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

        # =====================================
        # SPC TABLE
        # =====================================
        st.subheader("📋 SPC Summary")

        summary = pd.DataFrame({
            "Metric": ["Mean", "STD", "LSL", "USL", "Cp", "Ca", "Cpk"],
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

        st.dataframe(summary, use_container_width=True)

else:
    st.info("👈 Upload production data")
