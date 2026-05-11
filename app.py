import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. CÀI ĐẶT GIAO DIỆN ---
st.set_page_config(page_title="Phân Tích Cơ Tính KB9Q", layout="wide")
st.title("🛠️ Phân Tích Cơ Tính & SPC (Auto Control Limits)")
st.markdown("Hệ thống tự động lọc theo **Vật liệu (熱軋材質)** và trích xuất **Giới hạn kiểm soát nội bộ (管制值)** từ file dữ liệu.")

# --- 2. TẢI DỮ LIỆU & BỘ LỌC (SIDEBAR) ---
st.sidebar.header("📂 1. Tải Dữ Liệu")
uploaded_file = st.sidebar.file_uploader("Tải file sản xuất (Excel/CSV)", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.sidebar.success("Tải file thành công!")
        
        # --- BỘ LỌC THEO VẬT LIỆU (熱軋材質) ---
        st.sidebar.header("🔍 2. Bộ Lọc Dữ Liệu")
        
        if "熱軋材質" in df.columns:
            material_list = df["熱軋材質"].dropna().unique().tolist()
            selected_materials = st.sidebar.multiselect(
                "Lọc theo Vật liệu (熱軋材質):", 
                options=material_list, 
                default=material_list
            )
            
            if selected_materials:
                df = df[df["熱軋材質"].isin(selected_materials)]
            else:
                st.warning("⚠️ Vui lòng chọn ít nhất một Vật liệu (熱軋材質) bên thanh công cụ.")
                st.stop()
        else:
            st.sidebar.warning("Không tìm thấy cột '熱軋材質' trong dữ liệu.")
            
        # --- 3. BẢNG ĐIỀU KHIỂN & TỰ ĐỘNG NHẬN DIỆN 管制值 ---
        st.markdown("### ⚙️ Cài đặt Phân tích")
        
        # Bao gồm cả Hardness nếu có
        core_metrics = ["降伏強度 (YS)", "抗拉強度 (TS)", "伸長率 (EL)", "硬度HRB"]
        available_metrics = [col for col in core_metrics if col in df.columns]
        
        if not available_metrics:
            st.error("Không tìm thấy các cột cơ tính (YS, TS, EL, HRB) trong file.")
            st.stop()
            
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            target_metric = st.selectbox("Chọn thông số cơ tính:", available_metrics)
            
        # Tự động tìm cột LSL và USL dựa trên chữ "管制" (Giới hạn kiểm soát)
        # Tách lấy chữ Hán đầu tiên (VD: "降伏強度", "抗拉強度", "伸長率", "硬度")
        base_name = target_metric.split(" ")[0] 
        if base_name == "硬度HRB": 
            base_name = "硬度"
        
        lsl_col = next((col for col in df.columns if base_name in col and "min" in col.lower() and "管制" in col), None)
        usl_col = next((col for col in df.columns if base_name in col and "max" in col.lower() and "管制" in col), None)
        
        # Lấy giá trị mặc định cho LSL/USL từ dữ liệu (dùng median để tránh nhiễu do lỗi nhập liệu)
        default_lsl = float(df[lsl_col].median()) if lsl_col and pd.notnull(df[lsl_col].median()) else 0.0
        default_usl = float(df[usl_col].median()) if usl_col and pd.notnull(df[usl_col].median()) else 100.0
        
        with col2:
            lsl = st.number_input("Giới hạn dưới (LSL):", value=default_lsl, help=f"Tự động lấy từ cột: {lsl_col}" if lsl_col else "Nhập tay")
            usl = st.number_input("Giới hạn trên (USL):", value=default_usl, help=f"Tự động lấy từ cột: {usl_col}" if usl_col else "Nhập tay")
            
        # --- 4. TÍNH TOÁN THỐNG KÊ & CPK ---
        if target_metric:
            data = df[target_metric].dropna().reset_index(drop=True)
            total_coils = len(data)
            
            if total_coils < 2:
                st.error("Dữ liệu sau khi lọc quá ít (cần ít nhất 2 cuộn). Vui lòng nới lỏng bộ lọc.")
                st.stop()
            
            mean_val = data.mean()
            std_overall = data.std()
            
            cp = (usl - lsl) / (6 * std_overall) if std_overall > 0 else 0
            cpu = (usl - mean_val) / (3 * std_overall) if std_overall > 0 else 0
            cpl = (mean_val - lsl) / (3 * std_overall) if std_overall > 0 else 0
            cpk = min(cpu, cpl)
            
            # --- 5. TÍNH TOÁN GIỚI HẠN KIỂM SOÁT I-MR ---
            mr = data.diff().abs() 
            mean_mr = mr.mean()
            
            ucl_i = mean_val + 2.66 * mean_mr
            lcl_i = mean_val - 2.66 * mean_mr
            ucl_mr = 3.267 * mean_mr
            
            # --- 6. HIỂN THỊ CHỈ SỐ KPI ---
            st.markdown("---")
            st.markdown("### 📊 Kết Quả Phân Tích")
            k0, k1, k2, k3, k4 = st.columns(5)
            k0.metric("Số lượng mẫu (N)", f"{total_coils}")
            k1.metric("Trung bình (Mean)", f"{mean_val:.2f}")
            k2.metric("Độ lệch chuẩn (σ)", f"{std_overall:.2f}")
            k3.metric("Cp", f"{cp:.2f}")
            
            if cpk >= 1.33:
                k4.metric("Cpk", f"{cpk:.2f}", "Đạt yêu cầu", delta_color="normal")
            else:
                k4.metric("Cpk", f"{cpk:.2f}", "Cần cải thiện", delta_color="inverse")
                
            # --- 7. VẼ BIỂU ĐỒ ---
            tab1, tab2 = st.tabs(["🎯 Biểu đồ Phân bố (Cpk)", "📈 Biểu đồ Kiểm soát (I-MR)"])
            
            with tab1:
                fig_hist = px.histogram(df, x=target_metric, nbins=30, marginal="box", 
                                        title=f"Phân bố {target_metric} theo Vật liệu: {', '.join(selected_materials)[:50]}...")
                
                fig_hist.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text=f"LSL ({lsl})")
                fig_hist.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text=f"USL ({usl})")
                fig_hist.add_vline(x=mean_val, line_dash="solid", line_color="green", annotation_text=f"Mean ({mean_val:.2f})")
                
                st.plotly_chart(fig_hist, use_container_width=True)
                
            with tab2:
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, 
                                        subplot_titles=('Individual Chart (Biểu đồ giá trị cá nhân)', 
                                                        'Moving Range Chart (Biểu đồ dải di chuyển)'))
                
                fig_imr.add_trace(go.Scatter(y=data, mode='lines+markers', name='Thực tế', marker=dict(color='#1f77b4')), row=1, col=1)
                fig_imr.add_hline(y=mean_val, line_color="green", annotation_text="Mean", row=1, col=1)
                fig_imr.add_hline(y=ucl_i, line_dash="dash", line_color="red", annotation_text="UCL", row=1, col=1)
                fig_imr.add_hline(y=lcl_i, line_dash="dash", line_color="red", annotation_text="LCL", row=1, col=1)
                
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR', marker=dict(color='#ff7f0e')), row=2, col=1)
                fig_imr.add_hline(y=mean_mr, line_color="green", annotation_text="Mean MR", row=2, col=1)
                fig_imr.add_hline(y=ucl_mr, line_dash="dash", line_color="red", annotation_text="UCL MR", row=2, col=1)
                
                fig_imr.update_layout(height=700, showlegend=False, template="plotly_white")
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Đã xảy ra lỗi khi xử lý dữ liệu: {e}")
else:
    st.info("👈 Vui lòng tải file dữ liệu ở thanh công cụ bên trái để bắt đầu.")
