import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="KB9Q Line 4 Dashboard", layout="wide")

# --- 2. THANH BÊN (SIDEBAR) ---
st.sidebar.header("📂 Nguồn Dữ Liệu")
uploaded_file = st.sidebar.file_uploader("Tải file Excel/CSV sản xuất", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        # Đọc dữ liệu
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        
        # Bộ lọc 用途碼 (Mã ứng dụng)
        st.sidebar.header("🔍 Bộ Lọc")
        if "用途碼" in df.columns:
            usage_list = df["用途碼"].dropna().unique().tolist()
            selected_usages = st.sidebar.multiselect("Chọn Mã Ứng Dụng (用途碼):", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        # --- ÁNH XẠ CƠ TÍNH & GIỚI HẠN KIỂM SOÁT ---
        metrics_map = {
            "YS": {
                "actual": "降伏強度  (YS)",
                "lsl": "降伏強度[(min.)管制值]",
                "usl": "降伏強度[(max.)管制值]"
            },
            "TS": {
                "actual": "抗拉強度 (TS)",
                "lsl": "抗拉強度[(min.)管制值]",
                "usl": "抗拉強度[(max.)管制值]"
            },
            "EL": {
                "actual": "伸長率 (EL)",
                "lsl": "伸長率[(min.)管制值]",
                "usl": "伸長率[(max.)管制值]"
            },
            "HRB": {
                "actual": "硬度HRB",
                "lsl": "硬度[(min.)管制值]",
                "usl": "硬度[(max.)管制值]"
            },
            "YPE": {
                "actual": "YPE",
                "lsl": None,
                "usl": None
            }
        }

        available_display = list(metrics_map.keys())

        st.sidebar.header("📊 Cấu Hình View")
        view_mode = st.sidebar.radio("Chọn Chế Độ Xem:", ["View 1: Trạng Thái Phân Bố & Trending", "View 2: Giới Hạn Kiểm Soát (SPC)"])
        selected_display = st.sidebar.selectbox("Thông số cơ tính:", available_display)

        actual_data_col = metrics_map[selected_display]["actual"]
        lsl_col = metrics_map[selected_display]["lsl"]
        usl_col = metrics_map[selected_display]["usl"]

        if actual_data_col in df_filtered.columns:
            plot_data = df_filtered[actual_data_col].dropna().reset_index(drop=True)
            lsl = float(df_filtered[lsl_col].median()) if lsl_col and lsl_col in df_filtered.columns else plot_data.min()
            usl = float(df_filtered[usl_col].median()) if usl_col and usl_col in df_filtered.columns else plot_data.max()

            # --- RENDER VIEW 1 ---
            if view_mode == "View 1: Trạng Thái Phân Bố & Trending":
                st.header(f"📈 Phân Tích Trạng Thái & Xu Hướng: {selected_display}")
                
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.subheader("Biểu đồ Trạng Thái Phân Bố (Normal Distribution)")
                    
                    # Tạo Histogram
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(
                        x=plot_data, 
                        histnorm='probability density', 
                        name='Thực tế',
                        marker_color='#636EFA',
                        opacity=0.7
                    ))
                    
                    # Tính toán đường Normal Curve (Lý thuyết)
                    mu, std = plot_data.mean(), plot_data.std()
                    x_range = np.linspace(plot_data.min() - std, plot_data.max() + std, 100)
                    p = norm.pdf(x_range, mu, std)
                    
                    fig_dist.add_trace(go.Scatter(
                        x=x_range, y=p, 
                        mode='lines', 
                        name='Normal Curve',
                        line=dict(color='black', width=3)
                    ))
                    
                    # Thêm vạch giới hạn 管制值
                    if lsl_col:
                        fig_dist.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text="LSL")
                    if usl_col:
                        fig_dist.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text="USL")
                    
                    fig_dist.update_layout(template="plotly_white", xaxis_title=actual_data_col, yaxis_title="Mật độ")
                    st.plotly_chart(fig_dist, use_container_width=True)
                
                with col_right:
                    st.subheader("Đường Xu Hướng Dây Chuyền (Trending Line)")
                    # Biểu đồ Trending với markers thể hiện từng điểm dữ liệu
                    fig_trend = px.line(
                        df_filtered, 
                        y=actual_data_col, 
                        markers=True, 
                        template="plotly_white",
                        color_discrete_sequence=['#19D3F3']
                    )
                    # Thêm đường xu hướng trung bình động (Lowess)
                    fig_trend.add_traces(px.scatter(df_filtered, y=actual_data_col, trendline="lowess", trendline_color_override="orange").data)
                    
                    fig_trend.update_layout(xaxis_title="Thứ tự sản xuất (Cuộn)", yaxis_title=actual_data_col)
                    st.plotly_chart(fig_trend, use_container_width=True)

            # --- RENDER VIEW 2 ---
            else:
                st.header(f"🛡️ Giới Hạn Kiểm Soát Thực Tế: {selected_display}")
                mean_val = plot_data.mean()
                std_val = plot_data.std()
                mr = plot_data.diff().abs()
                mean_mr = mr.mean()
                ucl_i = mean_val + 2.66 * mean_mr
                lcl_i = mean_val - 2.66 * mean_mr
                cpk = min((usl - mean_val)/(3*std_val), (mean_val - lsl)/(3*std_val)) if std_val > 0 else 0

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Mean", f"{mean_val:.2f}")
                m2.metric("UCL", f"{ucl_i:.2f}")
                m3.metric("LCL", f"{lcl_i:.2f}")
                m4.metric("Cpk (管制)", f"{cpk:.2f}")

                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True)
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='Data'), row=1, col=1)
                fig_imr.add_hline(y=ucl_i, line_dash="dot", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=lcl_i, line_dash="dot", line_color="red", row=1, col=1)
                fig_imr.update_layout(height=600, template="plotly_white")
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi: {e}")
else:
    st.info("👈 Hãy tải file dữ liệu vào thanh Sidebar bên trái.")
