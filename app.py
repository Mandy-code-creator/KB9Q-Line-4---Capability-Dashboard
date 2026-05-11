import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
import re
import math

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="KB9Q Line 4 Dashboard", layout="wide")

st.markdown("""
    <style>
    h1, h2, h3 { color: #113763 !important; font-weight: 800 !important; }
    div[data-testid="stMetric"] { border: 2px solid #113763; border-radius: 10px; padding: 15px; background-color: #ffffff; }
    .main { background-color: #f0f2f6; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. XỬ LÝ DỮ LIỆU ---
st.sidebar.header("📂 Nguồn Dữ Liệu")
uploaded_file = st.sidebar.file_uploader("Tải file Excel/CSV sản xuất", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

        # Bộ lọc 用途碼
        if "用途碼" in df.columns:
            usage_list = sorted(df["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Chọn Mã Ứng Dụng (用途碼):", options=usage_list, default=usage_list)
            df_filtered = df[df["用途碼"].isin(selected_usages)]
        else:
            df_filtered = df

        # Tìm cột dữ liệu
        metrics_def = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        def find_col(key):
            for col in df.columns:
                if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格"]):
                    return col
            return None

        available_display = [k for k, v in metrics_def.items() if find_col(v)]
        selected_display = st.sidebar.selectbox("Thông số cơ tính:", available_display)
        
        actual_col = find_col(metrics_def[selected_display])
        kw_han = "降伏強度" if "YS" in selected_display else "抗拉強度" if "TS" in selected_display else "伸長率" if "EL" in selected_display else "硬 độ" if "Hardness" in selected_display else "降伏點"
        lsl_col = next((c for c in df.columns if kw_han in c and "min" in c.lower() and "管制" in c), None)
        usl_col = next((c for c in df.columns if kw_han in c and "max" in c.lower() and "管制" in c), None)

        if actual_col:
            plot_data = df_filtered[actual_col].dropna().reset_index(drop=True)
            n = len(plot_data)
            
            # 1. Tính số cột theo Sturges
            k_sturges = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
            
            # 2. Tính toán thống kê
            mean_val, std_val = plot_data.mean(), plot_data.std()
            lsl = float(df_filtered[lsl_col].median()) if lsl_col else plot_data.min()
            usl = float(df_filtered[usl_col].median()) if usl_col else plot_data.max()
            cpk = min((usl - mean_val)/(3*std_val), (mean_val - lsl)/(3*std_val)) if std_val > 0 else 0

            st.title(f"📊 LINE 4 ANALYTICS: {selected_display}")

            col_left, col_right = st.columns([1, 1.2])
            
            with col_left:
                st.subheader("Trạng thái phân bố (Số cuộn thép)")
                
                # Tính độ rộng của mỗi bin (bin width) để scale đường Normal Curve
                bin_width = (plot_data.max() - plot_data.min()) / k_sturges
                
                fig_dist = go.Figure()
                
                # Histogram hiển thị SỐ LƯỢNG (Count)
                fig_dist.add_trace(go.Histogram(
                    x=plot_data, 
                    nbinsx=k_sturges,
                    name='Số cuộn thực tế', 
                    marker_color='#0078D4', 
                    opacity=0.6,
                    hovertemplate='Khoảng giá trị: %{x}<br>Số cuộn: %{y}<extra></extra>'
                ))
                
                # Normal Curve đã được scale theo Số cuộn: y = f(x) * n * bin_width
                if std_val > 0:
                    x_ext = np.linspace(mean_val - 4*std_val, mean_val + 4*std_val, 200)
                    y_normal = norm.pdf(x_ext, mean_val, std_val) * n * bin_width
                    fig_dist.add_trace(go.Scatter(
                        x=x_ext, y=y_normal, 
                        mode='lines', name='Đường chuẩn', 
                        line=dict(color='#113763', width=3)
                    ))

                # Đường giới hạn 管制值
                fig_dist.add_vline(x=lsl, line_dash="dash", line_color="red", line_width=2)
                fig_dist.add_vline(x=usl, line_dash="dash", line_color="red", line_width=2)

                # Bảng thông số đặt phía trên đỉnh
                max_count = (norm.pdf(mean_val, mean_val, std_val) * n * bin_width) * 1.1
                stats_text = (f"<b>THỐNG KÊ SẢN XUẤT</b><br>"
                              f"Tổng số cuộn (n): {n}<br>"
                              f"Số nhóm (k): {k_sturges}<br>"
                              f"Trung bình: {mean_val:.2f}<br>"
                              f"Độ lệch chuẩn: {std_val:.2f}<br>"
                              f"Chỉ số Cpk: {cpk:.2f}")
                
                fig_dist.add_annotation(
                    xref="paper", yref="y", x=0.5, y=max_count,
                    text=stats_text, showarrow=False,
                    bgcolor="rgba(255, 255, 255, 0.9)", bordercolor="#113763",
                    borderwidth=2, borderpad=10, font=dict(size=14, color="#113763")
                )

                fig_dist.update_layout(
                    template="plotly_white", 
                    yaxis_title="Số lượng cuộn thép (Coils)",
                    xaxis_title=f"Giá trị {selected_display}",
                    margin=dict(t=80),
                    showlegend=False
                )
                st.plotly_chart(fig_dist, use_container_width=True)

            with col_right:
                st.subheader("Trending Line & Control Limits")
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=plot_data.index, y=plot_data, mode='lines+markers',
                    line=dict(color='#0078D4', width=2),
                    marker=dict(size=8, color='#ffffff', line=dict(width=2, color='#0078D4'))
                ))
                
                ucl, lcl = mean_val + 3*std_val, mean_val - 3*std_val
                for val, label, color in [(ucl, "UCL", "red"), (mean_val, "MEAN", "green"), (lcl, "LCL", "red")]:
                    fig_trend.add_hline(y=val, line_dash="dash", line_color=color, line_width=2)
                    fig_trend.add_annotation(
                        x=1.01, y=val, xref="paper", text=f"<b>{label}: {val:.1f}</b>",
                        showarrow=False, font=dict(color=color, size=14), xanchor="left"
                    )

                fig_trend.update_layout(template="plotly_white", margin=dict(r=150), yaxis_title="Giá trị đo")
                st.plotly_chart(fig_trend, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi: {e}")
else:
    st.info("👈 Vui lòng tải file để bắt đầu phân tích.")
