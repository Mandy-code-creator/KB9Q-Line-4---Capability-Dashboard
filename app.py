import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ thống phân tích chất lượng Line 4", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #F0F4F8; }
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 12px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 25px;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-top: 5px solid #113763;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    h1, h2, h3 { 
        color: #113763 !important; 
        font-family: 'Segoe UI', Tahoma, sans-serif !important; 
        font-weight: 800 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. HÀM XỬ LÝ DỮ LIỆU ---
def find_data_col(df, key):
    for col in df.columns:
        if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求"]):
            return col
    return None

def get_valid_limit(df, keyword, limit_type, category):
    col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
    if col:
        val = pd.to_numeric(df[col], errors='coerce').median()
        return float(val) if pd.notnull(val) and val > 0 else None
    return None

export_config = {
    'displayModeBar': True, 
    'displaylogo': False,
    'toImageButtonOptions': {
        'format': 'png', 
        'filename': 'Line4_Quality_Analytics',
        'height': 600,
        'width': 1200,
        'scale': 2 
    }
}

# --- 3. THANH BÊN (SIDEBAR) ---
st.sidebar.header("📂 NGUỒN DỮ LIỆU")
uploaded_file = st.sidebar.file_uploader("Tải file Excel/CSV báo cáo", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df_raw.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df_raw.columns]

        if "用途碼" in df_raw.columns:
            usage_list = sorted(df_raw["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Lọc mã ứng dụng (用途碼):", options=usage_list, default=usage_list)
            df = df_raw[df_raw["用途碼"].isin(selected_usages)]
        else:
            df = df_raw

        metrics_map = {"YS (降伏強度)": "YS", "TS (抗拉強度)": "TS", "EL (伸長率)": "EL", "Hardness (硬 độ)": "HRB"}
        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        
        if not available:
            st.error("❌ Không tìm thấy các cột dữ liệu phù hợp.")
            st.stop()

        selected_label = st.sidebar.selectbox("Thông số cơ tính:", available)
        view_mode = st.sidebar.radio("Cài đặt hiển thị:", ["Phân tích Tổng thể (View 1)", "Biểu đồ Kiểm soát SPC (View 2)"])
        
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df, short_key)
        zh_key = "降伏強度" if "YS" in short_key else "抗拉強度" if "TS" in short_key else "伸長率" if "EL" in short_key else "硬度"
        
        v_lsl_int = get_valid_limit(df, zh_key, "min", "管制")
        v_usl_int = get_valid_limit(df, zh_key, "max", "管制")
        v_lsl_cust = get_valid_limit(df, zh_key, "min", "客戶要求")
        v_usl_cust = get_valid_limit(df, zh_key, "max", "客戶 yêu cầu")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            # Tính Cp và Cpk
            t_lsl = v_lsl_cust if v_lsl_cust else v_lsl_int
            t_usl = v_usl_cust if v_usl_cust else v_usl_int
            
            cp, cpk = None, None
            if sigma > 0:
                if t_lsl and t_usl:
                    cp = (t_usl - t_lsl) / (6 * sigma)
                    cpk = min((t_usl-mu)/(3*sigma), (mu-t_lsl)/(3*sigma))
                elif t_lsl: 
                    cpk = (mu - t_lsl)/(3*sigma)
                elif t_usl: 
                    cpk = (t_usl - mu)/(3*sigma)

            st.title(f"🚀 Phân tích Chất lượng: {selected_label}")
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Tổng số mẫu (N)", n)
            k2.metric("Trung bình (μ)", f"{mu:.2f}")
            k3.metric("Độ lệch (σ)", f"{sigma:.2f}")
            k4.metric("Năng lực Cpk", f"{cpk:.2f}" if cpk else "N/A", delta="Đạt" if cpk and cpk >= 1.33 else "Cảnh báo" if cpk else None)

            if "View 1" in view_mode:
                
                # ==========================================
                # 1. BIỂU ĐỒ PHÂN BỐ (CHUẨN MINITAB STYLE)
                # ==========================================
                st.subheader("I. Trạng thái phân bố (Histogram)")
                
                k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                
                # Tính toán X-range
                pts = [plot_data.min(), plot_data.max()]
                all_lims = [v for v in [v_lsl_cust, v_usl_cust, v_lsl_int, v_usl_int, lcl, ucl] if v]
                pts.extend(all_lims)
                min_pt, max_pt = min(pts), max(pts)
                padding = (max_pt - min_pt) * 0.1 if max_pt != min_pt else max_pt * 0.05
                x_range = [min_pt - padding, max_pt + padding]

                # Tính toán Y-range (Đẩy cao lên 35% để lấy chỗ chứa Hộp thông số)
                counts, _ = np.histogram(plot_data, bins=k_bins)
                max_count = counts.max() if len(counts) > 0 else 10
                bin_w = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                y_c_max = norm.pdf(mu, mu, sigma) * n * bin_w if sigma > 0 else 0
                max_y_axis = max(max_count, y_c_max) * 1.35 # +35% headroom

                fig_dist = go.Figure()
                
                # Histogram (Giống màu Line Hist trong hình)
                fig_dist.add_trace(go.Histogram(
                    x=plot_data, nbinsx=k_bins, name='Thực tế (LINE)',
                    marker_color='#85B4D3', marker_line_color='white', marker_line_width=1, opacity=0.9
                ))
                
                # Đường chuẩn Normal (Xanh đậm nét dày)
                if sigma > 0:
                    x_c = np.linspace(x_range[0], x_range[1], 400)
                    y_c = norm.pdf(x_c, mu, sigma) * n * bin_w
                    fig_dist.add_trace(go.Scatter(
                        x=x_c, y=y_c, mode='lines', name='Đường chuẩn (Fit)',
                        line=dict(color='#003F88', width=3)
                    ))

                # Thêm Vline thực tế
                if v_lsl_cust: fig_dist.add_vline(x=v_lsl_cust, line_dash="dash", line_color="#FF0000", line_width=2)
                if v_usl_cust: fig_dist.add_vline(x=v_usl_cust, line_dash="dash", line_color="#FF0000", line_width=2)
                if v_lsl_int: fig_dist.add_vline(x=v_lsl_int, line_dash="dashdot", line_color="#800080", line_width=2)
                if v_usl_int: fig_dist.add_vline(x=v_usl_int, line_dash="dashdot", line_color="#800080", line_width=2)

                # Các đường giả (Dummy traces) để tạo Legend giống hệt hình mẫu
                fig_dist.add_trace(go.Scatter(x=[None], y=[None], mode='lines', name='Khách hàng (Spec)', line=dict(color='#FF0000', width=2, dash='dash')))
                fig_dist.add_trace(go.Scatter(x=[None], y=[None], mode='lines', name='Nội bộ (Internal)', line=dict(color='#800080', width=2, dash='dashdot')))

                # Hộp SPC Indices (Góc trên bên trái)
                cp_text = f"{cp:.2f}" if cp else "N/A"
                cpk_text = f"{cpk:.2f}" if cpk else "N/A"
                rating = "Tốt" if cpk and cpk >= 1.33 else "Cảnh báo" if cpk else "N/A"
                
                box_text = f"<b>SPC Indices (LINE):</b><br>N = {n}<br>Mean = {mu:.2f}<br>Std = {sigma:.2f}<br>Cp = {cp_text}<br>Cpk = {cpk_text}<br>Rating: {rating}"
                
                fig_dist.add_annotation(
                    xref="paper", yref="paper", x=0.02, y=0.96,
                    text=box_text, showarrow=False, align="left",
                    font=dict(size=12, family="Courier New, monospace", color="black"),
                    bgcolor="rgba(250, 250, 250, 0.9)", bordercolor="#D3D3D3", borderwidth=1, borderpad=8,
                    xanchor="left", yanchor="top"
                )

                # Cấu hình Layout (Viền đen xung quanh, Lưới xám, Legend góc phải)
                fig_dist.update_layout(
                    title=dict(text=f"<b>{selected_label} Distribution - Line 4</b>", x=0.5, font=dict(size=16)),
                    plot_bgcolor='white', paper_bgcolor='white',
                    height=500, xaxis_range=x_range, yaxis_range=[0, max_y_axis],
                    xaxis_title="Giá trị", yaxis_title="Số lượng cuộn (Number of Coils)",
                    showlegend=True,
                    legend=dict(
                        x=0.98, y=0.98, xanchor="right", yanchor="top",
                        bgcolor="rgba(255, 255, 255, 0.9)", bordercolor="#D3D3D3", borderwidth=1
                    )
                )
                
                # Bật khung viền và lưới cho trục X, Y
                fig_dist.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True, showgrid=True, gridcolor='#E5E5E5')
                fig_dist.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True, showgrid=True, gridcolor='#E5E5E5')

                st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

                # ==========================================
                # 2. BIỂU ĐỒ TRENDING
                # ==========================================
                st.subheader("II. Xu hướng sản xuất & Các tầng giới hạn")
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', 
                                              line=dict(color='#1f77b4', width=1.5),
                                              marker=dict(size=5, color='#1f77b4')))

                limit_configs_trend = [
                    (mu, "Mean", "#008000", "dash", 1.01), 
                    (ucl, "UCL (+3σ)", "#FF0000", "dash", 1.01), 
                    (lcl, "LCL (-3σ)", "#FF0000", "dash", 1.01),
                    (v_usl_int, "Nội bộ Max", "#FF9933", "dot", 1.12), 
                    (v_lsl_int, "Nội bộ Min", "#FF9933", "dot", 1.12),
                    (v_usl_cust, "KHÁCH MAX", "#113763", "dashdot", 1.23), 
                    (v_lsl_cust, "KHÁCH MIN", "#113763", "dashdot", 1.23)
                ]

                for v, lbl, clr, sty, pos in limit_configs_trend:
                    if v:
                        fig_trend.add_hline(y=v, line_dash=sty, line_color=clr, line_width=1.2)
                        fig_trend.add_annotation(
                            x=pos, y=v, xref="paper", yref="y",
                            text=f"<b>{lbl}: {v:.1f}</b>",
                            showarrow=False, font=dict(color=clr, size=11), 
                            xanchor="left", yanchor="middle"
                        )

                fig_trend.update_layout(template="simple_white", height=500, margin=dict(l=50, r=260, t=30, b=50), showlegend=False,
                                       xaxis_title="Thứ tự cuộn (Sequence)", yaxis_title="Giá trị đo thực tế",
                                       font=dict(family="Segoe UI", size=12))
                
                st.plotly_chart(fig_trend, use_container_width=True, config=export_config)

            else:
                st.subheader("Biểu đồ kiểm soát SPC I-MR")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=("I-Chart", "MR-Chart"))
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', line=dict(color='#1f77b4'), marker=dict(size=4)), row=1, col=1)
                fig_imr.add_hline(y=ucl, line_dash="dash", line_color="#FF0000", row=1, col=1)
                fig_imr.add_hline(y=lcl, line_dash="dash", line_color="#FF0000", row=1, col=1)
                fig_imr.add_hline(y=mu, line_dash="dash", line_color="#008000", row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', line=dict(color='#1f77b4'), marker=dict(size=4)), row=2, col=1)
                fig_imr.update_layout(height=750, template="simple_white", showlegend=False)
                
                st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"Error system: {e}")
else:
    st.info("👈 Tải file Excel báo cáo sản xuất ở Sidebar bên trái để bắt đầu phân tích đa tầng giới hạn.")
