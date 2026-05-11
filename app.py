import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.figure_factory as ff # Thêm thư viện này để vẽ đường cong phân phối

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="KB9Q Line 4 Dashboard", layout="wide")

# --- 2. XỬ LÝ DỮ LIỆU & BỘ LỌC (SIDEBAR) ---
st.sidebar.header("📂 Nguồn Dữ Liệu")
uploaded_file = st.sidebar.file_uploader("Tải file Excel/CSV sản xuất", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        
        # Bộ lọc 用途碼
        st.sidebar.header("🔍 Bộ Lọc")
        if "用途碼" in df.columns:
            usage_list = df["用途碼"].dropna().unique().tolist()
            selected_usages = st.sidebar.multiselect("Chọn Mã Ứng Dụng (用途碼):", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        metrics_map = {
            "降伏強度 (YS)": "降伏強度", "抗拉強度 (TS)": "抗拉強度", 
            "伸長率 (EL)": "伸長率", "硬度 (Hardness)": "硬度", "降伏點延伸 (YPE)": "降伏點延伸"
        }
        available_metrics = [m for m, kw in metrics_map.items() if any(kw in col for col in df.columns)]
        
        st.sidebar.header("📊 Cấu Hình View")
        view_mode = st.sidebar.radio("Chọn Chế Độ Xem:", ["View 1: Distribution & Trend", "View 2: Control Limits (SPC)"])
        selected_display = st.sidebar.selectbox("Thông số cơ tính:", available_metrics)
        keyword = metrics_map[selected_display]

        # Xử lý cột dữ liệu
        data_col = next((col for col in df_filtered.columns if keyword in col and "規格" not in col and "管制" not in col), None)
        lsl_col = next((col for col in df_filtered.columns if keyword in col and "min" in col.lower() and "管制" in col), None)
        usl_col = next((col for col in df_filtered.columns if keyword in col and "max" in col.lower() and "管制" in col), None)

        if data_col:
            plot_data = df_filtered[data_col].dropna().reset_index(drop=True)
            lsl = float(df_filtered[lsl_col].median()) if lsl_col else plot_data.min()
            usl = float(df_filtered[usl_col].median()) if usl_col else plot_data.max()

            # --- RENDER VIEW 1 ---
            if view_mode == "View 1: Distribution & Trend":
                st.header(f"📈 Phân Bố & Xu Hướng: {selected_display}")
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.subheader("Trạng Thái Phân Bố (Distribution)")
                    # Sử dụng Distplot để có đường cong KDE mượt mà
                    hist_data = [plot_data]
                    group_labels = [selected_display]
                    
                    fig_dist = ff.create_distplot(hist_data, group_labels, show_hist=True, show_rug=False)
                    fig_dist.update_layout(template="plotly_white", showlegend=False)
                    # Thêm đường giới hạn 管制值
                    fig_dist.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text="LSL")
                    fig_dist.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text="USL")
                    st.plotly_chart(fig_dist, use_container_width=True)
                
                with col_right:
                    st.subheader("Đường Xu Hướng (Trending)")
                    fig_trend = px.line(df_filtered, y=data_col, markers=True, template="plotly_white")
                    fig_trend.add_traces(px.scatter(df_filtered, y=data_col, trendline="lowess", trendline_color_override="orange").data)
                    st.plotly_chart(fig_trend, use_container_width=True)

            # --- RENDER VIEW 2 ---
            else:
                st.header(f"🛡️ Giới Hạn Kiểm Soát SPC: {selected_display}")
                mean_val = plot_data.mean()
                std_val = plot_data.std()
                mr = plot_data.diff().abs()
                mean_mr = mr.mean()
                ucl_i = mean_val + 2.66 * mean_mr
                lcl_i = mean_val - 2.66 * mean_mr
                cpk = min((usl - mean_val)/(3*std_val), (mean_val - lsl)/(3*std_val)) if std_val > 0 else 0

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Mean", f"{mean_val:.2f}")
                k2.metric("UCL", f"{ucl_i:.2f}")
                k3.metric("LCL", f"{lcl_i:.2f}")
                k4.metric("Cpk (管制)", f"{cpk:.2f}", delta="OK" if cpk >= 1.33 else "NG")

                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True)
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='I'), row=1, col=1)
                fig_imr.add_hline(y=ucl_i, line_dash="dot", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=lcl_i, line_dash="dot", line_color="red", row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR'), row=2, col=1)
                fig_imr.update_layout(height=600, template="plotly_white")
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi: {e}")
else:
    st.info("👈 Hãy tải file dữ liệu vào thanh Sidebar.")
