import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
import re
import math

# --- 1. CONFIG GIAO DIỆN TINH GỌN ---
st.set_page_config(page_title="KB9Q Analytics - Line 4", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    /* Khung card tối giản */
    div.stPlotlyChart {
        padding: 10px;
        border-radius: 4px;
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
    }
    /* Thẻ Metric tinh gọn */
    div[data-testid="stMetric"] {
        border-bottom: 3px solid #1a237e;
        background-color: #f8f9fa;
        padding: 10px;
    }
    h1, h2, h3 { color: #1a237e !important; font-family: 'Segoe UI', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. XỬ LÝ DỮ LIỆU ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Excel", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        # Filter
        if "用途碼" in df.columns:
            usage_list = sorted(df["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Usage Code:", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        def find_col(key):
            for col in df.columns:
                if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求"]):
                    return col
            return None

        metrics_def = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        available_display = [k for k, v in metrics_def.items() if find_col(v)]
        selected_display = st.sidebar.selectbox("Select Metric:", available_display)
        
        actual_col = find_col(metrics_def[selected_display])
        kw_han = "降伏強度" if "YS" in selected_display else "抗拉強度" if "TS" in selected_display else "伸長率" if "EL" in selected_display else "硬度" if "Hardness" in selected_display else "降伏點"
        
        def get_valid_limit(keyword, limit_type, category):
            col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
            if col:
                val = pd.to_numeric(df_filtered[col], errors='coerce').median()
                return float(val) if pd.notnull(val) and val > 0 else None
            return None

        v_lsl_int, v_usl_int = get_valid_limit(kw_han, "min", "管制"), get_valid_limit(kw_han, "max", "管制")
        v_lsl_cust, v_usl_cust = get_valid_limit(kw_han, "min", "客戶要求"), get_valid_limit(kw_han, "max", "客戶要求")

        if actual_col:
            plot_data = pd.to_numeric(df_filtered[actual_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            st.title(f"LINE 4 ANALYTICS: {selected_display}")

            # Top Metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Samples (N)", n)
            c2.metric("Mean (μ)", f"{mu:.2f}")
            c3.metric("StdDev (σ)", f"{sigma:.2f}")
            
            t_lsl = v_lsl_cust if v_lsl_cust is not None else v_lsl_int
            t_usl = v_usl_cust if v_usl_cust is not None else v_usl_int
            cpk = None
            if sigma > 0:
                if t_lsl is not None and t_usl is not None: cpk = min((t_usl-mu)/(3*sigma), (mu-t_lsl)/(3*sigma))
                elif t_lsl is not None: cpk = (mu - t_lsl)/(3*sigma)
                elif t_usl is not None: cpk = (t_usl - mu)/(3*sigma)
            c4.metric("Cpk", f"{cpk:.2f}" if cpk is not None else "N/A")

            # --- CHART 1: DISTRIBUTION ---
            st.subheader("1. Distribution State")
            k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
            pts = [plot_data.min(), plot_data.max()]
            lims = [v for v in [v_lsl_cust, v_usl_cust, lcl, ucl] if v is not None]
            pts.extend(lims)
            x_range = [min(pts) * 0.98, max(pts) * 1.02]

            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, marker_color='#42a5f5', opacity=0.7))
            
            if sigma > 0:
                bin_w = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                x_c = np.linspace(x_range[0], x_range[1], 200)
                y_c = norm.pdf(x_c, mu, sigma) * n * bin_w
                fig_dist.add_trace(go.Scatter(x=x_c, y=y_c, mode='lines', line=dict(color='#1a237e', width=2)))

            # Giới hạn khách hàng (Đỏ đậm, nét đứt)
            for v, lbl in [(v_lsl_cust, "Cust Min"), (v_usl_cust, "Cust Max")]:
                if v:
                    fig_dist.add_vline(x=v, line_dash="dash", line_color="#d32f2f", line_width=2)
                    fig_dist.add_annotation(x=v, y=1.02, yref="paper", text=f"<b>{lbl}</b>", showarrow=False, font=dict(color="#d32f2f"))

            fig_dist.update_layout(template="simple_white", height=400, margin=dict(t=50, b=20), xaxis_range=x_range, showlegend=False, yaxis_title="Coils")
            st.plotly_chart(fig_dist, use_container_width=True)

            # --- CHART 2: TRENDING ---
            st.subheader("2. Production Trending")
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', line=dict(color='#42a5f5', width=1), marker=dict(size=6, color='white', line=dict(width=1, color='#42a5f5'))))
            
            # Cấu hình nhãn Trending
            t_lines = [
                (mu, "MEAN", "green", "solid", 1.01),
                (ucl, "UCL", "#fb8c00", "dash", 1.01),
                (lcl, "LCL", "#fb8c00", "dash", 1.01),
                (v_usl_int, "Int Max", "#757575", "dot", 1.08),
                (v_lsl_int, "Int Min", "#757575", "dot", 1.08),
                (v_usl_cust, "SPEC MAX", "#d32f2f", "dashdot", 1.16),
                (v_lsl_cust, "SPEC MIN", "#d32f2f", "dashdot", 1.16)
            ]
            
            for val, lbl, clr, style, pos in t_lines:
                if val:
                    fig_trend.add_hline(y=val, line_dash=style, line_color=clr, line_width=1.5)
                    fig_trend.add_annotation(x=pos, y=val, xref="paper", text=f"<b>{lbl}: {val:.1f}</b>", showarrow=False, font=dict(color=clr, size=10), xanchor="left")

            fig_trend.update_layout(template="simple_white", height=450, margin=dict(r=200, t=20), showlegend=False, xaxis_title="Coil Sequence", yaxis_title="Value")
            st.plotly_chart(fig_trend, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Upload Excel to start.")
