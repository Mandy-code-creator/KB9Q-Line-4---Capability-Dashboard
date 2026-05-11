import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. CÀI ĐẶT GIAO DIỆN ---
st.set_page_config(page_title="Phân Tích Cơ Tính KB9Q", layout="wide")
st.title("🛠️ Phân Tích Cơ Tính & SPC (KB9Q - Line 4)")
st.markdown("Hệ thống tự động lọc dữ liệu, tính **Cpk** và vẽ biểu đồ kiểm soát **I-MR**.")

# --- 2. THANH BÊN (SIDEBAR): TẢI DỮ LIỆU & BỘ LỌC ---
st.sidebar.header("📂 1. Tải Dữ Liệu")
uploaded_file = st.sidebar.file_uploader("Tải file sản xuất (Excel/CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # Đọc dữ liệu
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.sidebar.success("Tải file thành công!")
        
        # --- BỘ LỌC DỮ LIỆU (FILTERS) ---
        st.sidebar.header("🔍 2. Bộ Lọc Dữ Liệu")
        
        # Bộ lọc 用途碼 (Usage Code)
        if "用途碼" in df.columns:
            usage_list = df["用途碼"].dropna().unique().tolist()
            # Sử dụng multiselect để có thể chọn 1 hoặc nhiều mã cùng lúc
            selected_usages = st.sidebar.multiselect(
                "Lọc theo Mã Ứng Dụng (用途碼):", 
                options=usage_list, 
                default=usage_list # Mặc định hiển thị tất cả
            )
            
            # Áp dụng data filter
            if selected_usages:
                df = df[df["用途碼"].isin(selected_usages)]
            else:
                st.warning("⚠️ Vui lòng chọn ít nhất một mã 用途碼 bên thanh công cụ để xem dữ liệu.")
                st.stop() # Dừng chạy code bên dưới nếu không chọn gì
        else:
            st.sidebar.warning("Không tìm thấy cột '用途碼' trong dữ liệu.")
            
        # Lấy danh sách các cột dạng số để làm thông số phân tích
        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        
        # --- 3. BẢNG ĐIỀU KHIỂN (CONTROLS) TRÊN MÀN HÌNH CHÍNH ---
        st.markdown("### ⚙️ Cài đặt Phân tích")
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            target_metric = st.selectbox("Chọn thông số cơ tính (YS, TS, EL):", numeric_cols)
        
        with col2:
            lsl = st.number_input("Giới hạn dưới (LSL):", value=0.0)
            usl = st.number_input("Giới hạn trên (USL):", value=100.0)
            
        if target_metric:
            # Lấy dữ liệu và loại bỏ các dòng bị trống (NaN) ở cột mục tiêu
            data = df[target_metric].dropna().reset_index(drop=True)
            total_coils = len(data)
            
            if total_coils < 2:
                st.error("Dữ liệu sau khi lọc quá ít (cần ít nhất 2 cuộn) để tính toán SPC. Vui lòng chọn thêm 用途碼.")
                st.stop()
            
            # --- 4. TÍNH TOÁN THỐNG KÊ & CPK ---
            mean_val = data.mean()
            std_overall = data.std()
            
            cp = (usl - lsl) / (6 * std_overall) if std_overall > 0 else 0
            cpu = (usl - mean_val) / (3 * std_overall) if std_overall > 0 else 0
            cpl = (mean_val - lsl) / (3 * std_overall) if std_overall > 0 else 0
            cpk = min(cpu, cpl)
            
            # --- 5. TÍNH TOÁN GIỚI HẠN KIỂM SOÁT I-MR ---
            mr = data.diff().abs()  # Tính Moving Range
            mean_mr = mr.mean()
            
            ucl_i = mean_val + 2.66 * mean_mr
            lcl_i = mean_val - 2.66 * mean_mr
            ucl_mr = 3.267 * mean_mr
            
            # --- 6. HIỂN THỊ CHỈ SỐ KPI ---
            st.markdown("---")
            st.markdown("### 📊 Kết Quả Phân Tích")
            k0, k1, k2, k3, k4 = st.columns(5)
            k0.metric("Số cuộn (N)", f"{total_coils}")
            k1.metric("Giá trị Trung bình", f"{mean_val:.2f}")
            k2.metric("Độ lệch chuẩn", f"{std_overall:.2f}")
            k3.metric("Cp", f"{cp:.2f}")
            
            if cpk >= 1.33:
                k4.metric("Cpk", f"{cpk:.2f}", "Đạt yêu cầu", delta_color="normal")
            else:
                k4.metric("Cpk", f"{cpk:.2f}", "Cần cải thiện", delta_color="inverse")
                
            # --- 7. VẼ BIỂU ĐỒ TRỰC QUAN ---
            tab1, tab2 = st.tabs(["🎯 Biểu đồ Phân bố (Cpk)", "📈 Biểu đồ Kiểm soát (I-MR)"])
            
            with tab1:
                st.markdown("**Đánh giá khả năng đáp ứng quy cách của khách hàng.**")
                fig_hist = px.histogram(df, x=target_metric, nbins=30, marginal="box", 
                                        title=f"Phân bố {target_metric} theo Mã: {', '.join(selected_usages)[:50]}...")
                
                fig_hist.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text="LSL")
                fig_hist.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text="USL")
                fig_hist.add_vline(x=mean_val, line_dash="solid", line_color="green", annotation_text="Mean")
                
                st.plotly_chart(fig_hist, use_container_width=True)
                
            with tab2:
                st.markdown("**Theo dõi độ ổn định nội tại của dây chuyền theo từng cuộn.**")
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, 
                                        subplot_titles=('Individual Chart (Kiểm soát giá trị từng cuộn)', 
                                                        'Moving Range Chart (Kiểm soát độ biến thiên liên tiếp)'))
                
                fig_imr.add_trace(go.Scatter(y=data, mode='lines+markers', name='Thực tế'), row=1, col=1)
                fig_imr.add_hline(y=mean_val, line_color="green", annotation_text="Mean", row=1, col=1)
                fig_imr.add_hline(y=ucl_i, line_dash="dash", line_color="red", annotation_text="UCL", row=1, col=1)
                fig_imr.add_hline(y=lcl_i, line_dash="dash", line_color="red", annotation_text="LCL", row=1, col=1)
                
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR', line=dict(color='orange')), row=2, col=1)
                fig_imr.add_hline(y=mean_mr, line_color="green", annotation_text="Mean MR", row=2, col=1)
                fig_imr.add_hline(y=ucl_mr, line_dash="dash", line_color="red", annotation_text="UCL MR", row=2, col=1)
                
                fig_imr.update_layout(height=700, showlegend=False)
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Đã xảy ra lỗi: {e}")
else:
    st.info("👈 Vui lòng tải file dữ liệu ở thanh công cụ bên trái để bắt đầu.")
