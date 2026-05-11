import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="KB9Q Line 4 Quality Dashboard", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border: 2px solid #cfd8dc;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.08);
    }
    h1, h2, h3 { color: #0d47a1 !important; font-weight: 800 !important; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-left: 5px solid #0d47a1;
        border-radius: 5px;
        padding: 10px;
        box-shadow: 1px 1px 3px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. XỬ LÝ DỮ LIỆU ---
st.sidebar.header("📂 Data Management")
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
        view_mode = st.sidebar.radio("Chế độ xem:", ["Phân bố & Trending", "Kiểm soát SPC (I-MR)"])
        
        short_key = metrics_map[selected_label]
        data_col = find_col(short_key, ["要求", "管制", "規格"])
        zh_key = "降伏強度" if "YS" in short_key else "抗拉強度" if "TS" in short_key else "伸長率" if "EL" in short_key else "硬度" if "HRB" in short_key else "降伏點"
        
        # Hàm lấy giới hạn hợp lệ (>0)
        def get_valid_limit(keyword, limit_type, category):
            col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
            if col:
                val = pd.to_numeric(df_filtered[col], errors='coerce').median()
                return float(val) if pd.notnull(val) and val > 0 else None
            return None

        # Lấy đầy đủ 2 tầng giới hạn
        v_lsl_int = get_valid_limit(zh_key, "min", "管制")
        v_usl_int = get_valid_limit(zh_key, "max", "管制")
        v_lsl_cust = get_valid_limit(zh_key, "min", "客戶要求")
        v_usl_cust = get_valid_limit(zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df_filtered[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            st.title(f"🚀 Phân tích Chất lượng: {selected_label}")

            # KPI Cards
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tổng số cuộn (n)", n)
            c2.metric("Trung bình (Mean)", f"{mu:.2f}")
            c3.metric("Độ lệch (σ)", f"{sigma:.2f}")
            
            # Ưu tiên tính Cpk theo giới hạn khách hàng
            t_lsl = v_lsl_cust if v_lsl_cust is not None else v_lsl_int
            t_usl = v_usl_cust if v_usl_cust is not None else v_usl_int
            cpk = None
            if sigma > 0:
                if t_lsl is not None and t_usl is not None: cpk = min((t_usl-mu)/(3*sigma), (mu-t_lsl)/(3*sigma))
                elif t_lsl is not None: cpk = (mu - t_lsl)/(3*sigma)
                elif t_usl is not None: cpk = (t_usl - mu)/(3*sigma)
            c4.metric("Chỉ số Cpk", f"{cpk:.2f}" if cpk is not None else "N/A")

            # --- VIEW 1 ---
            if view_mode == "Phân bố & Trending":
                col_left, col_right = st.columns([1, 1.4])
                
                # Xác định dải trục X để không bị cắt biểu đồ
                relevant_pts = [plot_data.min(), plot_data.max()]
                all_limits = [v for v in [v_lsl_int, v_usl_int, v_lsl_cust, v_usl_cust, lcl, ucl] if v is not None]
                relevant_pts.extend(all_limits)
                x_min, x_max = min(relevant_pts) * 0.97, max(relevant_pts) * 1.03

                with col_left:
                    st.subheader("Biểu đồ Phân bố (Histogram)")
                    k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, marker_color='#1E88E5', opacity=0.6))
                    
                    if sigma > 0:
                        x_c = np.linspace(x_min, x_max, 300)
                        y_c = norm.pdf(x_c, mu, sigma) * n * ((plot_data.max()-plot_data.min())/k_bins)
                        fig_dist.add_trace(go.Scatter(x=x_c, y=y_c, mode='lines', line=dict(color='#0D47A1', width=3)))
                    
                    # Vẽ giới hạn khách hàng trên Histogram (Đường đỏ đậm)
                    if v_lsl_cust: fig_dist.add_vline(x=v_lsl_cust, line_dash="dash", line_color="#D32F2F", line_width=2.5)
                    if v_usl_cust: fig_dist.add_vline(x=v_usl_cust, line_dash="dash", line_color="#D32F2F", line_width=2.5)
                    
                    fig_dist.update_layout(template="plotly_white", xaxis_range=[x_min, x_max], yaxis_title="Số lượng cuộn", showlegend=False)
                    st.plotly_chart(fig_dist, use_container_width=True)

                with col_right:
                    st.subheader("Biểu đồ Trending & Đa tầng giới hạn")
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', marker=dict(size=6, color='white', line=dict(width=2, color='#1E88E5'))))
                    
                    # Cấu hình các đường kẻ (Sắp xếp nhãn để không chồng nhau)
                    # (Giá trị, Nhãn, Màu, Kiểu dây, Vị trí nhãn)
                    lines = [
                        (mu, "Trung bình", "green", "solid", 1.01),
                        (ucl, "UCL(3σ)", "#FB8C00", "dash", 1.01),
                        (lcl, "LCL(3σ)", "#FB8C00", "dash", 1.01),
                        (v_usl_int, "Nội bộ Max", "#5D4037", "dot", 1.12),
                        (v_lsl_int, "Nội bộ Min", "#5D4037", "dot", 1.12),
                        (v_usl_cust, "KHÁCH HÀNG MAX", "#D32F2F", "dashdot", 1.25),
                        (v_lsl_cust, "KHÁCH HÀNG MIN", "#D32F2F", "dashdot", 1.25),
                    ]
                    
                    for val, lbl, clr, style, pos in lines:
                        if val is not None:
                            fig_trend.add_hline(y=val, line_dash=style, line_color=clr, line_width=2)
                            fig_trend.add_annotation(x=pos, y=val, xref="paper", text=f"<b>{lbl}: {val:.1f}</b>",
                                                     showarrow=False, font=dict(color=clr, size=10), xanchor="left")
                    
                    fig_trend.update_layout(template="plotly_white", margin=dict(r=250), xaxis_title="Số thứ tự sản xuất", yaxis_title="Giá trị đo")
                    st.plotly_chart(fig_trend, use_container_width=True)

            else:
                st.subheader("SPC I-MR Charts")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, subplot_titles=("I-Chart (Cá nhân)", "MR-Chart (Biến động)"))
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
    st.info("👈 Hãy tải file Excel sản xuất để bắt đầu phân tích đa tầng giới hạn.")
