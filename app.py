import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. CONFIG GIAO DIỆN PREMIUM (POWER BI STYLE) ---
st.set_page_config(page_title="Executive Quality Dashboard | Line 4", layout="wide")

# CSS Advanced để tạo giao diện Card, Shadow, và Font chuẩn Corporate
st.markdown("""
    <style>
    /* Nền xám nhạt chuẩn BI */
    .main {
        background-color: #f0f2f6;
    }
    /* Style cho các thẻ KPI Metric */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        border: 1px solid #e1e4e8;
        border-left: 5px solid #113763; /* Điểm nhấn màu Navy */
    }
    /* Làm đậm chữ trong Metric */
    div[data-testid="stMetric"] label {
        font-weight: 700 !important;
        color: #113763 !important;
    }
    /* Style cho khung bao quanh biểu đồ (Card) */
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 6px 15px rgba(0,0,0,0.1);
        margin-bottom: 25px;
    }
    /* Style tiêu đề chuyên nghiệp */
    h1, h2, h3 {
        color: #113763 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
        font-weight: 800 !important;
    }
    .stSubheader {
        border-bottom: 2px solid #e1e4e8;
        padding-bottom: 10px;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. XỬ LÝ DỮ LIỆU & SIDEBAR ---
st.sidebar.header("📂 Data Configuration")
uploaded_file = st.sidebar.file_uploader("Upload Line 4 Excel Data", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        # Đọc dữ liệu
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        # Chuẩn hóa tên cột
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        # Bộ lọc 用途碼 (Usage Code)
        st.sidebar.subheader("🔍 Data Filters")
        if "用途碼" in df.columns:
            usage_list = sorted(df["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Select Usage Code:", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        # Thuật toán tìm cột thông minh
        def find_col(key):
            for col in df.columns:
                if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求"]):
                    return col
            return None

        # Danh mục thông số cơ tính
        metrics_def = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        available_display = [k for k, v in metrics_def.items() if find_col(v)]
        
        if not available_display:
            st.error("Cannot find key metrics (YS, TS, EL...) in data.")
            st.stop()

        selected_display = st.sidebar.selectbox("Analyze Metric:", available_display)
        view_mode = st.sidebar.radio("Navigation:", ["View 1: Distribution & Trending", "View 2: SPC Control (I-MR)"])
        
        # Xác định cột dữ liệu thực tế và quy cách (Internal Control)
        actual_col = find_col(metrics_def[selected_display])
        kw_han = "降伏強度" if "YS" in selected_display else "抗拉強度" if "TS" in selected_display else "伸長率" if "EL" in selected_display else "硬度" if "Hardness" in selected_display else "降伏點"
        
        # Hàm lấy giới hạn hợp lệ
        def get_limit(keyword, limit_type, category):
            col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
            if col:
                val = pd.to_numeric(df_filtered[col], errors='coerce').median()
                return float(val) if pd.notnull(val) and val > 0 else None
            return None

        v_lsl_int = get_limit(kw_han, "min", "管制")
        v_usl_int = get_limit(kw_han, "max", "管制")
        v_lsl_cust = get_limit(kw_han, "min", "客戶要求")
        v_usl_cust = get_limit(kw_han, "max", "客戶要求")

        if actual_col:
            plot_data = pd.to_numeric(df_filtered[actual_col], errors='coerce').dropna().reset_index(drop=True)
            n = len(plot_data)
            
            # Tính toán thống kê nền tảng
            mean_val = plot_data.mean()
            std_val = plot_data.std()
            ucl_actual = mean_val + 3*std_val
            lcl_actual = mean_val - 3*std_val
            
            # Cpk calculation (Ưu tiên Customer Spec)
            t_lsl = v_lsl_cust if v_lsl_cust is not None else v_lsl_int
            t_usl = v_usl_cust if v_usl_cust is not None else v_usl_int
            cpk = None
            if std_val > 0:
                if t_lsl is not None and t_usl is not None:
                    cpk = min((t_usl - mean_val)/(3*std_val), (mean_val - t_lsl)/(3*std_val))
                elif t_lsl is not None: cpk = (mean_val - t_lsl)/(3*std_val)
                elif t_usl is not None: cpk = (t_usl - mean_val)/(3*std_val)

            # --- GIAO DIỆN CHÍNH ---
            st.title(f"📊 Quality Dashboard: Line 4 - {selected_display}")

            # Hàng 1: Thẻ KPI Metrics (Làm nổi bật thông số chính)
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1: st.metric("Total Samples (N)", n)
            with m2: st.metric("Process Mean (μ)", f"{mean_val:.2f}")
            with m3: st.metric("Std Deviation (σ)", f"{std_val:.2f}")
            with m4:
                if cpk is not None:
                    status = "OK" if cpk >= 1.33 else "Warning"
                    color = "normal" if cpk >= 1.33 else "inverse"
                    st.metric("Cpk (Spec)", f"{cpk:.2f}", help=f"LSL: {t_lsl}, USL: {t_usl}", delta=status, delta_color=color)
                else:
                    st.metric("Cpk (Spec)", "N/A")
            with m5:
                # Tính tỷ lệ đạt (Yield)
                if t_lsl is not None or t_usl is not None:
                    within_spec = plot_data
                    if t_lsl is not None: within_spec = within_spec[within_spec >= t_lsl]
                    if t_usl is not None: within_spec = within_spec[within_spec <= t_usl]
                    yield_rate = len(within_spec) / n * 100
                    st.metric("Yield Rate", f"{yield_rate:.1f}%")
                else:
                    st.metric("Yield Rate", "N/A")

            # ---VIEW 1: DISTRIBUTION & TRENDING (stacked) ---
            if view_mode == "View 1: Distribution & Trending":
                
                # 2. BIỂU ĐỒ PHÂN BỐ (FULL WIDTH)
                st.subheader("Process Capability & Distribution")
                
                k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                # Cân chỉnh trục X để Normal Curve không bị cụt
                pts = [plot_data.min(), plot_data.max()]
                lims = [v for v in [v_lsl_cust, v_usl_cust, lcl_actual, ucl_actual] if v is not None]
                pts.extend(lims)
                x_range = [min(pts) * 0.98, max(pts) * 1.02]

                fig_dist = go.Figure()
                # Histogram (Count) - Xanh Sky nhẹ nhàng
                fig_dist.add_trace(go.Histogram(
                    x=plot_data, nbinsx=k_bins, name='Actual',
                    marker_color='#3498db', opacity=0.7
                ))
                
                # Normal Curve (Đậm hơn Histogram)
                if std_val > 0:
                    bin_w = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                    x_c = np.linspace(x_range[0], x_range[1], 200)
                    y_c = norm.pdf(x_c, mean_val, std_val) * n * bin_w
                    fig_dist.add_trace(go.Scatter(
                        x=x_c, y=y_c, mode='lines', 
                        name='Normal', line=dict(color='#113763', width=3)
                    ))

                # Đường giới hạn trên Histogram
                if v_lsl_cust is not None: fig_dist.add_vline(x=v_lsl_cust, line_dash="dash", line_color="#C41E3A", line_width=2.5, annotation_text="Spec Min")
                if v_usl_cust is not None: fig_dist.add_vline(x=v_usl_cust, line_dash="dash", line_color="#C41E3A", line_width=2.5, annotation_text="Spec Max")
                
                fig_dist.update_layout(
                    template="plotly_white", margin=dict(t=10, b=20), height=450,
                    yaxis_title="Coil Count", xaxis_title=f"Measured {selected_display}",
                    xaxis_range=x_range, font=dict(family="Segoe UI, Tahoma", size=13),
                    showlegend=False
                )
                st.plotly_chart(fig_dist, use_container_width=True)

                # 3. BIỂU ĐỒ TRENDING (FULL WIDTH - DƯỚI)
                st.subheader("Production Trending & Control Limits")
                fig_trend = go.Figure()
                
                # Đường Trending (Lines + Markers rỗng ở giữa cho chuyên nghiệp)
                fig_trend.add_trace(go.Scatter(
                    x=plot_data.index, y=plot_data, mode='lines+markers', name='Value',
                    line=dict(color='#0078D4', width=1.5),
                    marker=dict(size=6, color='#ffffff', line=dict(width=1.5, color='#0078D4'))
                ))
                
                # Cấu hình hệ thống đường Control & Spec
                # (Giá trị, Nhãn, Màu, Kiểu, Vị trí nhãn)
                limits = [
                    (mu, "Mean", "green", "solid", 1.01),
                    (ucl_actual, "UCL(3σ)", "#FB8C00", "dash", 1.01),
                    (lcl_actual, "LCL(3σ)", "#FB8C00", "dash", 1.01),
                    (v_usl_int, "Int Max", "#5D4037", "dot", 1.10),
                    (v_lsl_int, "Int Min", "#5D4037", "dot", 1.10),
                    (v_usl_cust, "SPEC MAX", "#C41E3A", "dashdot", 1.22),
                    (v_lsl_cust, "SPEC MIN", "#C41E3A", "dashdot", 1.22)
                ]
                
                for val, lbl, clr, style, pos in limits:
                    if val is not None:
                        fig_trend.add_hline(y=val, line_dash=style, line_color=clr, line_width=2)
                        fig_trend.add_annotation(
                            x=pos, y=val, xref="paper", text=f"<b>{lbl}: {val:.1f}</b>",
                            showarrow=False, font=dict(color=clr, size=11), xanchor="left"
                        )
                
                # Đường Trending Lowess (Xu hướng chung - Màu vàng nhạt)
                fig_trend.add_traces(px.scatter(df_filtered, y=actual_col, trendline="lowess", trendline_color_override="#D4AF37").data)
                
                fig_trend.update_layout(
                    template="plotly_white", margin=dict(r=220, t=10, b=20), height=500,
                    xaxis_title="Coil Sequence", yaxis_title="Measured Value",
                    font=dict(family="Segoe UI, Tahoma", size=13), showlegend=False
                )
                st.plotly_chart(fig_trend, use_container_width=True)

            # --- VIEW 2 (Tương tự style Card nhưng xếp dọc I và MR) ---
            else:
                st.subheader("Statistical Process Control Charts (I-MR)")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                                        subplot_titles=("Individual Chart", "Moving Range Chart"))
                
                # I-Chart (Xanh navy)
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='I', line=dict(color='#113763')), row=1, col=1)
                fig_imr.add_hline(y=ucl_actual, line_dash="dash", line_color="#C41E3A", row=1, col=1)
                fig_imr.add_hline(y=lcl_actual, line_dash="dash", line_color="#C41E3A", row=1, col=1)
                fig_imr.add_hline(y=mean_val, line_color="green", row=1, col=1)
                
                # MR-Chart (Màu cam)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR', line=dict(color='#FB8C00')), row=2, col=1)
                fig_imr.add_hline(y=3.267 * mr.mean(), line_dash="dash", line_color="#C41E3A", row=2, col=1)
                fig_imr.add_hline(y=mr.mean(), line_color="green", row=2, col=1)
                
                fig_imr.update_layout(height=750, template="plotly_white", showlegend=False, 
                                     font=dict(family="Segoe UI, Tahoma", size=13))
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Error processing data: {e}")
else:
    st.info("👈 Please upload the production Excel file in the sidebar to begin analysis.")
