import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="KB9Q Line 4 Dashboard", layout="wide")

# --- 2. THANH BÊN (SIDEBAR) ---
st.sidebar.header("📂 Nguồn Dữ Liệu")
uploaded_file = st.sidebar.file_uploader("Tải file Excel/CSV sản xuất", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        # Đọc dữ liệu
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        
        # Làm sạch tên cột: Xóa khoảng trắng thừa và chuẩn hóa
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        # Bộ lọc 用途碼
        st.sidebar.header("🔍 Bộ Lọc")
        if "用途碼" in df.columns:
            usage_list = sorted(df["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Chọn Mã Ứng Dụng (用途碼):", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        # --- THUẬT TOÁN TÌM CỘT THÔNG MINH (REGEX) ---
        def find_actual_data_col(key):
            for col in df.columns:
                # Tìm cột chứa keyword (YS, TS, EL...) nhưng KHÔNG chứa chữ '管制' hoặc '規格'
                if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格"]):
                    return col
            return None

        # Định nghĩa các cặp: Tên hiển thị - Từ khóa nhận diện
        metrics_definition = {
            "Yield Strength (YS)": "YS",
            "Tensile Strength (TS)": "TS",
            "Elongation (EL)": "EL",
            "Hardness (HRB)": "HRB",
            "Yield Point Elongation (YPE)": "YPE"
        }

        available_display = []
        actual_col_map = {}

        for disp, key in metrics_definition.items():
            found = find_actual_data_col(key)
            if found:
                available_display.append(disp)
                actual_col_map[disp] = found

        st.sidebar.header("📊 Cấu Hình View")
        view_mode = st.sidebar.radio("Chọn Chế Độ Xem:", ["View 1: Distribution & Trending", "View 2: Control Limits (SPC)"])
        
        if not available_display:
            st.error("❌ Không tìm thấy cột dữ liệu YS, TS, EL... Hãy kiểm tra lại tiêu đề file.")
            st.write("Các cột hiện có trong file của bạn:", list(df.columns))
            st.stop()
            
        selected_display = st.sidebar.selectbox("Chọn thông số phân tích:", available_display)
        actual_data_col = actual_col_map[selected_display]
        
        # Lấy từ khóa chữ Hán tương ứng để tìm cột 管制值
        keyword_han = "降伏強度" if "YS" in selected_display else \
                      "抗拉強度" if "TS" in selected_display else \
                      "伸長率" if "EL" in selected_display else \
                      "硬度" if "HRB" in selected_display else "降伏點"

        lsl_col = next((col for col in df.columns if keyword_han in col and "min" in col.lower() and "管制" in col), None)
        usl_col = next((col for col in df.columns if keyword_han in col and "max" in col.lower() and "管制" in col), None)

        if actual_data_col:
            plot_data = df_filtered[actual_data_col].dropna().reset_index(drop=True)
            lsl = float(df_filtered[lsl_col].median()) if lsl_col else plot_data.min()
            usl = float(df_filtered[usl_col].median()) if usl_col else plot_data.max()

            # --- RENDER VIEW 1 ---
            if view_mode == "View 1: Distribution & Trending":
                st.header(f"📈 {selected_display}: Phân Bố & Xu Hướng")
                c1, c2 = st.columns(2)
                
                with c1:
                    st.subheader("Trạng thái phân bố (Normal Curve)")
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(x=plot_data, histnorm='probability density', name='Thực tế', marker_color='#636EFA', opacity=0.7))
                    
                    # Vẽ Normal Curve
                    mu, std = plot_data.mean(), plot_data.std()
                    if std > 0:
                        x_range = np.linspace(plot_data.min() - std, plot_data.max() + std, 100)
                        fig_dist.add_trace(go.Scatter(x=x_range, y=norm.pdf(x_range, mu, std), mode='lines', name='Lý thuyết', line=dict(color='black', width=3)))
                    
                    fig_dist.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text="LSL 管制")
                    fig_dist.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text="USL 管制")
                    fig_dist.update_layout(template="plotly_white", xaxis_title="Giá trị đo", yaxis_title="Mật độ")
                    st.plotly_chart(fig_dist, use_container_width=True)
                    
                with c2:
                    st.subheader("Trending Line (Dây chuyền)")
                    fig_trend = px.line(df_filtered, y=actual_data_col, markers=True, template="plotly_white")
                    fig_trend.add_traces(px.scatter(df_filtered, y=actual_data_col, trendline="lowess", trendline_color_override="orange").data)
                    st.plotly_chart(fig_trend, use_container_width=True)

            # --- RENDER VIEW 2 ---
            else:
                st.header(f"🛡️ {selected_display}: SPC & Cpk")
                mean_val, std_val = plot_data.mean(), plot_data.std()
                mr = plot_data.diff().abs()
                ucl_i = mean_val + 2.66 * mr.mean()
                lcl_i = mean_val - 2.66 * mr.mean()
                cpk = min((usl-mean_val)/(3*std_val), (mean_val-lsl)/(3*std_val)) if std_val > 0 else 0
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Trung bình", f"{mean_val:.2f}")
                m2.metric("UCL (Năng lực máy)", f"{ucl_i:.2f}")
                m3.metric("LCL (Năng lực máy)", f"{lcl_i:.2f}")
                m4.metric("Cpk (Theo 管制值)", f"{cpk:.2f}", delta="Đạt" if cpk >= 1.33 else "Kém")

                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1)
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='Individual'), row=1, col=1)
                fig_imr.add_hline(y=ucl_i, line_dash="dot", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=lcl_i, line_dash="dot", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=mean_val, line_color="green", row=1, col=1)
                
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='Moving Range', line=dict(color='orange')), row=2, col=1)
                fig_imr.update_layout(height=600, template="plotly_white", showlegend=False)
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi hệ thống: {e}")
else:
    st.info("👈 Hãy tải file dữ liệu vào thanh Sidebar bên trái để bắt đầu.")
