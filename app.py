import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. CÀI ĐẶT GIAO DIỆN ---
st.set_page_config(page_title="Phân Tích Cơ Tính KB9Q", layout="wide")
st.title("🛠️ Hệ Thống Phân Tích Cơ Tính & SPC")
st.markdown("Tự động phân tích theo **用途碼** và trích xuất **Giới hạn kiểm soát (管制值)**.")

# --- 2. THANH BÊN (SIDEBAR): TẢI FILE & BỘ LỌC ---
st.sidebar.header("📂 1. Dữ Liệu Đầu Vào")
uploaded_file = st.sidebar.file_uploader("Tải file Excel/CSV sản xuất", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        # Đọc dữ liệu
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.sidebar.success("Tải file thành công!")
        
        # --- BỘ LỌC 用途碼 ---
        st.sidebar.header("🔍 2. Bộ Lọc 用途碼")
        if "用途碼" in df.columns:
            usage_list = df["用途碼"].dropna().unique().tolist()
            selected_usages = st.sidebar.multiselect(
                "Chọn Mã Ứng Dụng (用途碼):", 
                options=usage_list, 
                default=usage_list
            )
            
            if selected_usages:
                df = df[df["用途碼"].isin(selected_usages)]
            else:
                st.warning("⚠️ Hãy chọn ít nhất một 用途碼.")
                st.stop()
        else:
            st.sidebar.warning("Không tìm thấy cột '用途碼'.")

        # --- 3. CÀI ĐẶT THÔNG SỐ PHÂN TÍCH ---
        st.markdown("### ⚙️ Cấu hình thông số")
        
        # Ánh xạ tên hiển thị và từ khóa tìm kiếm cột
        metrics_map = {
            "降伏強度 (YS)": "降伏強度",
            "抗拉強度 (TS)": "抗拉強度",
            "伸長率 (EL)": "伸長率",
            "硬度 (Hardness)": "硬度",
            "降伏點延伸 (YPE)": "降伏點延伸"
        }
        
        # Lọc ra các thông số thực sự có trong file dữ liệu
        available_metrics = [m for m, keyword in metrics_map.items() if any(keyword in col for col in df.columns)]
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            selected_display = st.selectbox("Chọn thông số cơ tính:", available_metrics)
            keyword = metrics_map[selected_display]
            
        # Tự động tìm cột 管制值 (Control Limits)
        lsl_col = next((col for col in df.columns if keyword in col and "min" in col.lower() and "管制" in col), None)
        usl_col = next((col for col in df.columns if keyword in col and "max" in col.lower() and "管制" in col), None)
        
        # Lấy giá trị mặc định từ dữ liệu
        default_lsl = float(df[lsl_col].median()) if lsl_col and pd.notnull(df[lsl_col].median()) else 0.0
        default_usl = float(df[usl_col].median()) if usl_col and pd.notnull(df[usl_col].median()) else 100.0
        
        with col2:
            lsl = st.number_input("Giới hạn dưới (LSL/管制 min):", value=default_lsl)
            usl = st.number_input("Giới hạn trên (USL/管制 max):", value=default_usl)

        # --- 4. TÍNH TOÁN CPK & I-MR ---
        # Tìm cột dữ liệu thực tế (thường là cột không chứa chữ '規格' hay '管制')
        data_col = next((col for col in df.columns if keyword in col and "規格" not in col and "管制" not in col), None)
        
        if data_col:
            data = df[data_col].dropna().reset_index(drop=True)
            
            if len(data) >= 2:
                mean_val = data.mean()
                std_overall = data.std()
                
                # Cpk calculation
                cp = (usl - lsl) / (6 * std_overall) if std_overall > 0 else 0
                cpu = (usl - mean_val) / (3 * std_overall) if std_overall > 0 else 0
                cpl = (mean_val - lsl) / (3 * std_overall) if std_overall > 0 else 0
                cpk = min(cpu, cpl)
                
                # I-MR calculation
                mr = data.diff().abs()
                mean_mr = mr.mean()
                ucl_i = mean_val + 2.66 * mean_mr
                lcl_i = mean_val - 2.66 * mean_mr
                ucl_mr = 3.267 * mean_mr

                # --- 5. HIỂN THỊ KẾT QUẢ ---
                st.markdown("---")
                st.markdown(f"### 📊 Kết quả phân tích: {selected_display}")
                k0, k1, k2, k3, k4 = st.columns(5)
                k0.metric("Số mẫu (N)", len(data))
                k1.metric("Trung bình", f"{mean_val:.2f}")
                k2.metric("Độ lệch (σ)", f"{std_overall:.2f}")
                k3.metric("Cp", f"{cp:.2f}")
                k4.metric("Cpk", f"{cpk:.2f}", delta="Đạt" if cpk >= 1.33 else "Yếu", delta_color="normal" if cpk >= 1.33 else "inverse")

                # --- 6. VẼ BIỂU ĐỒ ---
                tab1, tab2 = st.tabs(["🎯 Phân bố & Cpk", "📈 Kiểm soát I-MR"])
                
                with tab1:
                    fig_hist = px.histogram(df, x=data_col, nbins=30, marginal="box", title=f"Histogram {selected_display}")
                    fig_hist.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text="LSL")
                    fig_hist.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text="USL")
                    st.plotly_chart(fig_hist, use_container_width=True)
                    
                with tab2:
                    fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=('Biểu đồ Individual (I)', 'Biểu đồ Moving Range (MR)'))
                    # I-Chart
                    fig_imr.add_trace(go.Scatter(y=data, mode='lines+markers', name='Giá trị'), row=1, col=1)
                    fig_imr.add_hline(y=ucl_i, line_dash="dash", line_color="red", row=1, col=1)
                    fig_imr.add_hline(y=lcl_i, line_dash="dash", line_color="red", row=1, col=1)
                    fig_imr.add_hline(y=mean_val, line_color="green", row=1, col=1)
                    # MR-Chart
                    fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='Khoảng biến thiên', line=dict(color='orange')), row=2, col=1)
                    fig_imr.add_hline(y=ucl_mr, line_dash="dash", line_color="red", row=2, col=1)
                    fig_imr.add_hline(y=mean_mr, line_color="green", row=2, col=1)
                    
                    fig_imr.update_layout(height=600, showlegend=False)
                    st.plotly_chart(fig_imr, use_container_width=True)
            else:
                st.warning("Dữ liệu sau khi lọc không đủ để phân tích.")
        else:
            st.error(f"Không tìm thấy cột dữ liệu thực tế cho {keyword}")

    except Exception as e:
        st.error(f"Lỗi: {e}")
else:
    st.info("👈 Hãy tải file để bắt đầu phân tích.")
