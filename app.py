import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import norm
import re

# --- 1. CẤU HÌNH GIAO DIỆN CHUYÊN NGHIỆP ---
st.set_page_config(page_title="KB9Q Power BI Analytics", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 2px solid #113763;
    }
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #dcdfe6;
    }
    /* Làm đậm font chữ tiêu đề Streamlit */
    h1, h2, h3 {
        color: #113763 !important;
        font-weight: 800 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. THANH BÊN ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Data", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        # Filter 用途碼
        if "用途碼" in df.columns:
            usage_list = sorted(df["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Usage Code:", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        def find_col(key):
            for col in df.columns:
                if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格"]):
                    return col
            return None

        metrics_def = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        available_display = [k for k, v in metrics_def.items() if find_col(v)]
        selected_display = st.sidebar.selectbox("Select Metric:", available_display)
        
        actual_col = find_col(metrics_def[selected_display])
        kw_han = "降伏強度" if "YS" in selected_display else "抗拉強度" if "TS" in selected_display else "伸長率" if "EL" in selected_display else "硬度" if "Hardness" in selected_display else "降伏點"
        lsl_col = next((c for c in df.columns if kw_han in c and "min" in c.lower() and "管制" in c), None)
        usl_col = next((c for c in df.columns if kw_han in c and "max" in c.lower() and "管制" in c), None)

        if actual_col:
            plot_data = df_filtered[actual_col].dropna().reset_index(drop=True)
            lsl = float(df_filtered[lsl_col].median()) if lsl_col else plot_data.min()
            usl = float(df_filtered[usl_col].median()) if usl_col else plot_data.max()
            
            mean_val = plot_data.mean()
            std_val = plot_data.std()
            
            # Tính toán Cpk
            cp = (usl - lsl) / (6 * std_val) if std_val > 0 else 0
            cpu = (usl - mean_val) / (3 * std_val) if std_val > 0 else 0
            cpl = (mean_val - lsl) / (3 * std_val) if std_val > 0 else 0
            cpk = min(cpu, cpl)

            st.title(f"📊 LINE 4 ANALYTICS: {selected_display}")

            col_left, col_right = st.columns([1, 1.3])
            
            with col_left:
                st.subheader("Distribution & Process Capability")
                fig_dist = go.Figure()
                
                # Histogram
                fig_dist.add_trace(go.Histogram(
                    x=plot_data, histnorm='probability density', 
                    name='Actual', marker_color='#0078D4', opacity=0.5
                ))
                
                # Normal Curve kéo dài đuôi (±4 sigma)
                if std_val > 0:
                    x_ext = np.linspace(mean_val - 4*std_val, mean_val + 4*std_val, 200)
                    y_ext = norm.pdf(x_ext, mean_val, std_val)
                    fig_dist.add_trace(go.Scatter(
                        x=x_ext, y=y_ext, mode='lines', 
                        name='Normal Curve', line=dict(color='#113763', width=4)
                    ))

                # Đường giới hạn
                fig_dist.add_vline(x=lsl, line_dash="dash", line_color="red", line_width=3)
                fig_dist.add_vline(x=usl, line_dash="dash", line_color="red", line_width=3)

                # Ghi chú chỉ số ngay trên biểu đồ (Text Box)
                stats_text = (f"<b>Capability Indices</b><br>"
                              f"Mean: {mean_val:.2f}<br>"
                              f"StdDev: {std_val:.2f}<br>"
                              f"Cp: {cp:.2f}<br>"
                              f"Cpk: {cpk:.2f}")
                
                fig_dist.add_annotation(
                    xref="paper", yref="paper", x=0.05, y=0.95,
                    text=stats_text, showarrow=False,
                    align="left", bgcolor="rgba(255, 255, 255, 0.8)",
                    bordercolor="#113763", borderwidth=2, borderpad=10,
                    font=dict(size=14, color="#113763")
                )

                fig_dist.update_layout(
                    template="plotly_white", margin=dict(t=10),
                    xaxis=dict(title=dict(text=f"<b>{selected_display} Value</b>", font=dict(size=16, color="black"))),
                    font=dict(family="Segoe UI", size=14, color="black")
                )
                st.plotly_chart(fig_dist, use_container_width=True)

            with col_right:
                st.subheader("Trending & Control Limits")
                fig_trend = go.Figure()
                
                fig_trend.add_trace(go.Scatter(
                    x=plot_data.index, y=plot_data, mode='lines+markers',
                    line=dict(color='#0078D4', width=2),
                    marker=dict(size=8, color='#ffffff', line=dict(width=2, color='#0078D4'))
                ))
                
                # Các đường giới hạn đậm hơn
                ucl, lcl = mean_val + 3*std_val, mean_val - 3*std_val
                for val, label, color in [(ucl, "UCL", "red"), (mean_val, "MEAN", "green"), (lcl, "LCL", "red")]:
                    fig_trend.add_hline(y=val, line_dash="dash", line_color=color, line_width=2)
                    fig_trend.add_annotation(
                        x=1.01, y=val, xref="paper", text=f"<b>{label}: {val:.1f}</b>",
                        showarrow=False, font=dict(color=color, size=15), xanchor="left"
                    )

                fig_trend.update_layout(
                    template="plotly_white", margin=dict(r=150),
                    xaxis=dict(title=dict(text="<b>Coil Sequence</b>", font=dict(size=16, color="black"))),
                    font=dict(family="Segoe UI", size=14, color="black")
                )
                st.plotly_chart(fig_trend, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Upload Excel file to start.")
