import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. CẤU HÌNH GIAO DIỆN CHUYÊN NGHIỆP ---
st.set_page_config(page_title="KB9Q Line 4 Analytics", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        border: 2px solid #cfd8dc;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    h1, h2, h3 { color: #0d47a1 !important; font-weight: 800 !important; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-left: 5px solid #0d47a1;
        border-radius: 5px;
        padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. XỬ LÝ DỮ LIỆU ---
st.sidebar.header("📂 Quản lý dữ liệu")
uploaded_file = st.sidebar.file_uploader("Tải file sản xuất (Excel/CSV)", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        if "用途碼" in df.columns:
            usage_list = sorted(df["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Lọc 用途碼:", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        def find_col(key_word, exclude_list=[]):
            for col in df.columns:
                if re.search(key_word, col, re.IGNORECASE) and not any(ex in col for ex in exclude_list):
                    return col
            return None

        metrics_map = {"YS (降伏強度)": "YS", "TS (抗拉強度)": "TS", "EL (伸長率)": "EL", "Hardness (硬度)": "HRB", "YPE": "YPE"}
        available_metrics = [k for k, v in metrics_map.items() if find_col(v, ["要求", "管制", "規格"])]
        selected_label = st.sidebar.selectbox("Chọn thông số phân tích:", available_metrics)
        view_mode = st.sidebar.radio("Chế độ xem:", ["View 1: Phân bố & Trending", "View 2: SPC Control Chart"])
        
        short_key = metrics_map[selected_label]
        data_col = find_col(short_key, ["要求", "管制", "規格"])
        zh_key = "降伏強度" if "YS" in short_key else "抗拉強度" if "TS" in short_key else "伸長率" if "EL" in short_key else "硬度" if "HRB" in short_key else "降伏點"
        
        # LOGIC: Chỉ lấy giới hạn nếu giá trị > 0 và hợp lệ
        def get_valid_limit(keyword, limit_type, category):
            col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
            if col:
                val = pd.to_numeric(df_filtered[col], errors='coerce').median()
                return float(val) if pd.notnull(val) and val > 0 else None
            return None

        v_lsl_int = get_valid_limit(zh_key, "min", "管制")
        v_usl_int = get_valid_limit(zh_key, "max", "管制")
        v_lsl_cust = get_valid_limit(zh_key, "min", "客戶要求")
        v_usl_cust = get_valid_limit(zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df_filtered[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            st.title(f"📊 Line 4 Analytics: {selected_label}")

            # KPI Cards
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Samples (n)", n)
            c2.metric("Mean", f"{mu:.2f}")
            c3.metric("StdDev (σ)", f"{sigma:.2f}")
            
            # Tính Cpk thông minh (Single-sided hoặc Double-sided)
            target_lsl = v_lsl_cust if v_lsl_cust is not None else v_lsl_int
            target_usl = v_usl_cust if v_usl_cust is not None else v_usl_int
            
            cpk = None
            if sigma > 0:
                if target_lsl is not None and target_usl is not None:
                    cpk = min((target_usl - mu)/(3*sigma), (mu - target_lsl)/(3*sigma))
                elif target_lsl is not None: cpk = (mu - target_lsl)/(3*sigma)
                elif target_usl is not None: cpk = (target_usl - mu)/(3*sigma)
            c4.metric("Cpk (Spec)", f"{cpk:.2f}" if cpk is not None else "N/A")

            # --- VIEW 1 ---
            if view_mode == "View 1: Phân bố & Trending":
                col_left, col_right = st.columns([1, 1.4])
                
                with col_left:
                    st.subheader("Distribution State")
                    k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                    
                    # Xác định trục X dựa trên dữ liệu thực và các giới hạn hữu hình (>0)
                    relevant_pts = [plot_data.min(), plot_data.max()]
                    all_limits = [v for v in [v_lsl_int, v_usl_int, v_lsl_cust, v_usl_cust, lcl, ucl] if v is not None]
                    relevant_pts.extend(all_limits)
                    
                    x_min, x_max = min(relevant_pts) * 0.98, max(relevant_pts) * 1.02
                    bin_width = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                    
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, name='Actual', marker_color='#1976D2', opacity=0.6))
                    
                    if sigma > 0:
                        x_curve = np.linspace(x_min, x_max, 300)
                        y_curve = norm.pdf(x_curve, mu, sigma) * n * bin_width
                        fig_dist.add_trace(go.Scatter(x=x_curve, y=y_curve, mode='lines', name='Normal', line=dict(color='#0D47A1', width=3)))
                    
                    # Chỉ vẽ vạch giới hạn khách hàng nếu có giá trị
                    if v_lsl_cust: fig_dist.add_vline(x=v_lsl_cust, line_dash="dash", line_color="red", line_width=2, annotation_text="Cust Min")
                    if v_usl_cust: fig_dist.add_vline(x=v_usl_cust, line_dash="dash", line_color="red", line_width=2, annotation_text="Cust Max")
                    
                    fig_dist.update_layout(template="plotly_white", yaxis_title="Coils", xaxis_range=[x_min, x_max], margin=dict(t=20), showlegend=False)
                    st.plotly_chart(fig_dist, use_container_width=True)

                with col_right:
                    st.subheader("Trending & Control Limits")
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', name='Value',
                                                  line=dict(color='#1976D2', width=2), marker=dict(size=7, color='white', line=dict(width=2, color='#1976D2'))))
                    
                    # Danh sách các đường giới hạn
                    lines_cfg = [
                        (mu, "Mean", "green", "solid", 1.01),
                        (ucl, "UCL(3σ)", "orange", "dash", 1.01),
                        (lcl, "LCL(3σ)", "orange", "dash", 1.01),
                        (v_usl_int, "管制 Max", "#5D4037", "dot", 1.10),
                        (v_lsl_int, "管制 Min", "#5D4037", "dot", 1.10),
                        (v_usl_cust, "Cust Max", "red", "dashdot", 1.22),
                        (v_lsl_cust, "Cust Min", "red", "dashdot", 1.22),
                    ]
                    
                    for val, lbl, clr, style, pos in lines_cfg:
                        if val is not None:
                            fig_trend.add_hline(y=val, line_dash=style, line_color=clr, line_width=2)
                            fig_trend.add_annotation(x=pos, y=val, xref="paper", text=f"<b>{lbl}: {val:.1f}</b>",
                                                     showarrow=False, font=dict(color=clr, size=11), xanchor="left")
                    
                    fig_trend.update_layout(template="plotly_white", margin=dict(r=220), xaxis_title="Sequence", yaxis_title="Measured Value")
                    st.plotly_chart(fig_trend, use_container_width=True)

            # --- VIEW 2 ---
            else:
                st.subheader("SPC I-MR Charts")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=("Individual Chart", "Moving Range Chart"))
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers'), row=1, col=1)
                fig_imr.add_hline(y=ucl, line_dash="dash", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=lcl, line_dash="dash", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=mu, line_color="green", row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', line=dict(color='orange')), row=2, col=1)
                fig_imr.update_layout(height=700, template="plotly_white", showlegend=False)
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi: {e}")
else:
    st.info("👈 Hãy tải file Excel KB9Q để bắt đầu phân tích.")
