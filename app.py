import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. CÀI ĐẶT GIAO DIỆN ---
st.set_page_config(page_title="Phân Tích Cơ Tính KB9Q", layout="wide")
st.title("🛠️ Phân Tích Cơ Tính & SPC (Mô hình 1 File)")
st.markdown("Tải file dữ liệu lên để tự động tính **Cpk** và vẽ biểu đồ kiểm soát **I-MR**.")

# --- 2. TẢI DỮ LIỆU ---
uploaded_file = st.file_uploader("Tải file dữ liệu sản xuất (Excel hoặc CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success("Tải dữ liệu thành công!")
        
        # Lấy danh sách các cột dạng số để phân tích
        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        
        # --- 3. BẢNG ĐIỀU KHIỂN (CONTROLS) ---
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            target_metric = st.selectbox("Chọn thông số (YS, TS, EL):", numeric_cols)
        
        with col2:
            lsl = st.number_input("Giới hạn dưới (LSL):", value=0.0)
            usl = st.number_input("Giới hạn trên (USL):", value=100.0)
            
        if target_metric:
            # Loại bỏ các ô trống trong cột dữ liệu được chọn
            data = df[target_metric].dropna().reset_index(drop=True)
            
            # --- 4. TÍNH TOÁN THỐNG KÊ & CPK ---
            mean_val = data.mean()
            std_overall = data.std()
            
            cp = (usl - lsl) / (6 * std_overall) if std_overall > 0 else 0
            cpu = (usl - mean_val) / (3 * std_overall) if std_overall > 0 else 0
            cpl = (mean_val - lsl) / (3 * std_overall) if std_overall > 0 else 0
            cpk = min(cpu, cpl)
            
            # --- 5. TÍNH TOÁN GIỚI HẠN KIỂM SOÁT I-MR ---
            mr = data.diff().abs()  # Tính Moving Range (khoảng cách giữa 2 điểm liên tiếp)
            mean_mr = mr.mean()
            
            # Hằng số chuẩn cho I-MR (n=2)
            ucl_i = mean_val + 2.66 * mean_mr
            lcl_i = mean_val - 2.66 * mean_mr
            ucl_mr = 3.267 * mean_mr
            
            # --- 6. HIỂN THỊ CHỈ SỐ KPI ---
            st.markdown("---")
            st.markdown("### 📊 Kết Quả Phân Tích")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Giá trị Trung bình (Mean)", f"{mean_val:.2f}")
            k2.metric("Độ lệch chuẩn (Std)", f"{std_overall:.2f}")
            k3.metric("Cp", f"{cp:.2f}")
            
            if cpk >= 1.33:
                k4.metric("Cpk", f"{cpk:.2f}", "Đạt yêu cầu", delta_color="normal")
            else:
                k4.metric("Cpk", f"{cpk:.2f}", "Cần cải thiện", delta_color="inverse")
                
            # --- 7. VẼ BIỂU ĐỒ TRỰC QUAN ---
            # Chia làm 2 tab để giao diện gọn gàng
            tab1, tab2 = st.tabs(["🎯 Biểu đồ Phân bố (Cpk)", "📈 Biểu đồ Kiểm soát (I-MR)"])
            
            with tab1:
                st.markdown("**Đánh giá khả năng đáp ứng quy cách của khách hàng.**")
                fig_hist = px.histogram(df, x=target_metric, nbins=30)
                
                # Vẽ thêm các đường LSL, USL, Mean
                fig_hist.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text="LSL")
                fig_hist.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text="USL")
                fig_hist.add_vline(x=mean_val, line_dash="solid", line_color="green", annotation_text="Mean")
                
                st.plotly_chart(fig_hist, use_container_width=True)
                
            with tab2:
                st.markdown("**Theo dõi độ ổn định nội tại của dây chuyền theo từng cuộn.**")
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, 
                                        subplot_titles=('Individual Chart (Kiểm soát giá trị từng cuộn)', 
                                                        'Moving Range Chart (Kiểm soát độ biến thiên liên tiếp)'))
                
                # Vẽ I-Chart (Biểu đồ trên)
                fig_imr.add_trace(go.Scatter(y=data, mode='lines+markers', name='Giá trị thực tế'), row=1, col=1)
                fig_imr.add_hline(y=mean_val, line_color="green", annotation_text="Mean", row=1, col=1)
                fig_imr.add_hline(y=ucl_i, line_dash="dash", line_color="red", annotation_text="UCL", row=1, col=1)
                fig_imr.add_hline(y=lcl_i, line_dash="dash", line_color="red", annotation_text="LCL", row=1, col=1)
                
                # Vẽ MR-Chart (Biểu đồ dưới)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR', line=dict(color='orange')), row=2, col=1)
                fig_imr.add_hline(y=mean_mr, line_color="green", annotation_text="Mean MR", row=2, col=1)
                fig_imr.add_hline(y=ucl_mr, line_dash="dash", line_color="red", annotation_text="UCL MR", row=2, col=1)
                
                fig_imr.update_layout(height=700, showlegend=False)
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Đã xảy ra lỗi khi xử lý dữ liệu: {e}")
else:
    st.info("Vui lòng tải file Excel hoặc CSV ở phía trên để bắt đầu phân tích.")
