import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="KB9Q Quality Analysis", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    h1, h2, h3 { color: #1a237e !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. XỬ LÝ DỮ LIỆU ---
st.sidebar.header("📂 Cài đặt dữ liệu")
uploaded_file = st.sidebar.file_uploader("Tải file Excel sản xuất", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        # Lọc 用途碼
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

        metrics_map = {"YS (降伏強度)": "YS", "TS (抗拉強度)": "TS", "EL (伸長率)": "EL", "Hardness (硬 độ)": "HRB", "YPE": "YPE"}
        available_metrics = [k for k, v in metrics_map.items() if find_col(v, ["要求", "管制", "規格"])]
        selected_label = st.sidebar.selectbox("Thông số phân tích:", available_metrics)
        
        short_key = metrics_map[selected_label]
        data_col = find_col(short_key, ["要求", "管制", "規格"])
        zh_key = "降伏強度" if "YS" in short_key else "抗拉強度" if "TS" in short_key else "伸長率" if "EL" in short_key else "硬度" if "HRB" in short_key else "降伏點"
        
        def get_valid_limit(keyword, limit_type, category):
            col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
            if col:
                val = pd.to_numeric(df_filtered[col], errors='coerce').median()
                return float(val) if pd.notnull(val) and val > 0 else None
            return None

        # Lấy giới hạn
        v_lsl_int = get_valid_limit(zh_key, "min", "管制")
        v_usl_int = get_valid_limit(zh_key, "max", "管制")
        v_lsl_cust = get_valid_limit(zh_key, "min", "客戶要求")
        v_usl_cust = get_valid_limit(zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df_filtered[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            st.title(f"🚀 Báo cáo Chất lượng: {selected_label}")

            # --- KHÔNG GIAN BIỂU ĐỒ DỌC ---
            
            # 1. BIỂU ĐỒ PHÂN BỐ (FULL WIDTH)
            st.subheader("1. Trạng thái phân bố & Năng lực quy trình")
            relevant_pts = [plot_data.min(), plot_data.max()]
            all_limits = [v for v in [v_lsl_int, v_usl_int, v_lsl_cust, v_usl_cust, lcl, ucl] if v is not None]
            relevant_pts.extend(all_limits)
            x_range = [min(relevant_pts) * 0.98, max(relevant_pts) * 1.02]

            k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
            bin_width = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1

            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, marker_color='#3498db', opacity=0.7, name="Dữ liệu"))
            
            if sigma > 0:
                x_curve = np.linspace(x_range[0], x_range[1], 400)
                y_curve = norm.pdf(x_curve, mu, sigma) * n * bin_width
                fig_dist.add_trace(go.Scatter(x=x_curve, y=y_curve, mode='lines', line=dict(color='#1a237e', width=3), name="Đường chuẩn"))

            # Vẽ vạch giới hạn với chú thích rõ ràng
            limit_configs = [
                (v_lsl_cust, "KHÁCH MIN", "#e74c3c", "dash"),
                (v_usl_cust, "KHÁCH MAX", "#e74c3c", "dash"),
                (v_lsl_int, "Nội bộ Min", "#795548", "dot"),
                (v_usl_int, "Nội bộ Max", "#795548", "dot")
            ]

            for val, lbl, clr, style in limit_configs:
                if val:
                    fig_dist.add_vline(x=val, line_dash=style, line_color=clr, line_width=2)
                    fig_dist.add_annotation(x=val, y=1, yref="paper", text=f"<b>{lbl}: {val}</b>", 
                                          textangle=-90, showarrow=False, font=dict(color=clr), bgcolor="white")

            fig_dist.update_layout(height=450, margin=dict(t=50, b=50), template="plotly_white", 
                                  xaxis_title=selected_label, yaxis_title="Số lượng cuộn thép", 
                                  xaxis_range=x_range, showlegend=False)
            st.plotly_chart(fig_dist, use_container_width=True)

            # 2. BIỂU ĐỒ TRENDING (FULL WIDTH - DƯỚI)
            st.subheader("2. Biểu đồ xu hướng sản xuất (Trending Line)")
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', 
                                          line=dict(color='#3498db', width=1.5),
                                          marker=dict(size=5, color='white', line=dict(width=1.5, color='#3498db'))))

            trend_lines = [
                (mu, "Mean", "green", "solid"),
                (ucl, "UCL", "#f39c12", "dash"),
                (lcl, "LCL", "#f39c12", "dash"),
                (v_usl_int, "Nội bộ Max", "#795548", "dot"),
                (v_lsl_int, "Nội bộ Min", "#795548", "dot"),
                (v_usl_cust, "KHÁCH MAX", "#e74c3c", "dashdot"),
                (v_lsl_cust, "KHÁCH MIN", "#e74c3c", "dashdot")
            ]

            for val, lbl, clr, style in trend_lines:
                if val:
                    fig_trend.add_hline(y=val, line_dash=style, line_color=clr, line_width=2)
                    fig_trend.add_annotation(x=1.005, y=val, xref="paper", text=f"<b>{lbl}: {val:.1f}</b>",
                                           showarrow=False, font=dict(color=clr, size=11), xanchor="left")

            fig_trend.update_layout(height=500, margin=dict(r=150, t=20, b=50), template="plotly_white",
                                   xaxis_title="Số thứ tự cuộn (Sequence)", yaxis_title="Giá trị đo", showlegend=False)
            st.plotly_chart(fig_trend, use_container_width=True)

    except Exception as e:
        st.error(f"Đã xảy ra lỗi: {e}")
else:
    st.info("👈 Vui lòng tải file Excel lên để bắt đầu phân tích.")
