import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. CẤU HÌNH GIAO DIỆN CHUẨN POWER BI ---
st.set_page_config(page_title="KB9Q Line 4 Analytics", layout="wide")

# CSS tạo khung bao quanh và làm đậm chữ
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    /* Tạo khung cho từng khối biểu đồ */
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border: 2px solid #dcdfe6;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    /* Làm đậm các tiêu đề */
    h1, h2, h3 {
        color: #113763 !important;
        font-weight: 800 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    /* Thẻ Metric chuẩn Power BI */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 2px solid #113763;
        border-radius: 10px;
        padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. XỬ LÝ DỮ LIỆU & THANH BÊN ---
st.sidebar.header("📂 Data Management")
uploaded_file = st.sidebar.file_uploader("Tải file Excel/CSV sản xuất", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        # Đọc dữ liệu
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        # Chuẩn hóa tên cột
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        # Bộ lọc 用途碼 (Mã ứng dụng)
        if "用途碼" in df.columns:
            usage_list = sorted(df["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Lọc theo 用途碼:", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        # Thuật toán tìm cột thông minh
        def find_col(key):
            for col in df.columns:
                if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格"]):
                    return col
            return None

        metrics_def = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        available_display = [k for k, v in metrics_def.items() if find_col(v)]
        
        if not available_display:
            st.error("Không tìm thấy dữ liệu cơ tính phù hợp.")
            st.stop()

        selected_display = st.sidebar.selectbox("Thông số phân tích:", available_display)
        view_mode = st.sidebar.radio("Chế độ xem:", ["View 1: Distribution & Trending", "View 2: SPC Control Limits"])
        
        # Xác định cột dữ liệu thực tế và quy cách (管制值)
        actual_col = find_col(metrics_def[selected_display])
        kw_han = "降伏強度" if "YS" in selected_display else "抗拉強度" if "TS" in selected_display else "伸長率" if "EL" in selected_display else "硬度" if "Hardness" in selected_display else "降伏點"
        
        lsl_col = next((c for c in df.columns if kw_han in c and "min" in c.lower() and "管制" in c), None)
        usl_col = next((c for c in df.columns if kw_han in c and "max" in c.lower() and "管制" in c), None)

        if actual_col:
            plot_data = df_filtered[actual_col].dropna().reset_index(drop=True)
            n = len(plot_data)
            
            # Tính toán thống kê
            mean_val = plot_data.mean()
            std_val = plot_data.std()
            lsl = float(df_filtered[lsl_col].median()) if lsl_col else plot_data.min()
            usl = float(df_filtered[usl_col].median()) if usl_col else plot_data.max()
            
            # Tính Cpk
            cpk = min((usl - mean_val)/(3*std_val), (mean_val - lsl)/(3*std_val)) if std_val > 0 else 0
            ucl_actual = mean_val + 3*std_val
            lcl_actual = mean_val - 3*std_val

            # --- GIAO DIỆN CHÍNH ---
            st.title(f"📈 LINE 4 ANALYTICS: {selected_display}")

            # Hàng Metric trên cùng
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Samples", n)
            m2.metric("Process Mean", f"{mean_val:.2f}")
            m3.metric("Std Deviation", f"{std_val:.2f}")
            m4.metric("Cpk (Internal)", f"{cpk:.2f}")
            m5.metric("Yield Rate", f"{(len(plot_data[(plot_data >= lsl) & (plot_data <= usl)])/n*100):.1f}%")

            # --- CHẾ ĐỘ XEM 1: DISTRIBUTION & TRENDING ---
            if view_mode == "View 1: Distribution & Trending":
                col_left, col_right = st.columns([1, 1.2])

                with col_left:
                    st.subheader("Distribution Analysis")
                    # Quy tắc Sturges cho số cột
                    k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                    bin_width = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                    
                    fig_dist = go.Figure()
                    # Histogram thể hiện số lượng (Count)
                    fig_dist.add_trace(go.Histogram(
                        x=plot_data, nbinsx=k_bins, name='Coil Count',
                        marker_color='#0078D4', opacity=0.6
                    ))
                    
                    # Normal Curve scale theo Count
                    if std_val > 0:
                        x_range = np.linspace(mean_val - 4*std_val, mean_val + 4*std_val, 200)
                        y_normal = norm.pdf(x_range, mean_val, std_val) * n * bin_width
                        fig_dist.add_trace(go.Scatter(
                            x=x_range, y=y_normal, mode='lines', 
                            name='Normal Curve', line=dict(color='#113763', width=3)
                        ))

                    # Đường giới hạn quy cách (管制值)
                    fig_dist.add_vline(x=lsl, line_dash="dash", line_color="red", line_width=2, annotation_text="LSL")
                    fig_dist.add_vline(x=usl, line_dash="dash", line_color="red", line_width=2, annotation_text="USL")
                    
                    fig_dist.update_layout(template="plotly_white", margin=dict(t=30), yaxis_title="Number of Coils")
                    st.plotly_chart(fig_dist, use_container_width=True)

                with col_right:
                    st.subheader("Trending & Control Limits")
                    fig_trend = go.Figure()
                    
                    # Đường Trending chính
                    fig_trend.add_trace(go.Scatter(
                        x=plot_data.index, y=plot_data, mode='lines+markers',
                        line=dict(color='#0078D4', width=2),
                        marker=dict(size=8, color='#ffffff', line=dict(width=2, color='#0078D4'))
                    ))
                    
                    # 1. Control Limits (Đường máy - Red Dash)
                    for val, lbl in [(ucl_actual, "UCL"), (lcl_actual, "LCL")]:
                        fig_trend.add_hline(y=val, line_dash="dash", line_color="red", line_width=1.5)
                        fig_trend.add_annotation(x=1.01, y=val, xref="paper", text=f"<b>{lbl}: {val:.1f}</b>", 
                                                 showarrow=False, font=dict(color="red", size=12), xanchor="left")
                    
                    # 2. Spec Limits (Đường tiêu chuẩn - Brown Dot)
                    for val, lbl in [(usl, "USL(管制)"), (lsl, "LSL(管制)")]:
                        fig_trend.add_hline(y=val, line_dash="dot", line_color="#5D4037", line_width=2)
                        fig_trend.add_annotation(x=1.12, y=val, xref="paper", text=f"<b>{lbl}: {val:.1f}</b>", 
                                                 showarrow=False, font=dict(color="#5D4037", size=12), xanchor="left")
                    
                    # Đường Mean (Green)
                    fig_trend.add_hline(y=mean_val, line_color="green", line_width=2)
                    fig_trend.add_annotation(x=1.01, y=mean_val, xref="paper", text=f"<b>Mean: {mean_val:.1f}</b>", 
                                             showarrow=False, font=dict(color="green", size=12), xanchor="left")

                    fig_trend.update_layout(template="plotly_white", margin=dict(r=150), xaxis_title="Coil Sequence")
                    st.plotly_chart(fig_trend, use_container_width=True)

            # --- CHẾ ĐỘ XEM 2: SPC CONTROL LIMITS (I-MR) ---
            else:
                st.subheader("I-MR Control Charts")
                mr = plot_data.diff().abs()
                ucl_mr = 3.267 * mr.mean()
                
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                                        subplot_titles=("Individual Chart (I)", "Moving Range Chart (MR)"))
                
                # I-Chart
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='I'), row=1, col=1)
                fig_imr.add_hline(y=ucl_actual, line_dash="dash", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=lcl_actual, line_dash="dash", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=mean_val, line_color="green", row=1, col=1)
                
                # MR-Chart
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR', line=dict(color='orange')), row=2, col=1)
                fig_imr.add_hline(y=ucl_mr, line_dash="dash", line_color="red", row=2, col=1)
                fig_imr.add_hline(y=mr.mean(), line_color="green", row=2, col=1)
                
                fig_imr.update_layout(height=700, template="plotly_white", showlegend=False)
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi xử lý dữ liệu: {e}")
else:
    st.info("👈 Vui lòng tải file dữ liệu ở thanh bên trái để bắt đầu.")
