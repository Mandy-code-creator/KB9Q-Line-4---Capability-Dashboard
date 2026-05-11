import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. CẤU HÌNH GIAO DIỆN CHUẨN EXECUTIVE DASHBOARD ---
st.set_page_config(page_title="Line 4 Quality Analytics", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
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
        font-family: 'Segoe UI', sans-serif !important; 
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

# --- CẤU HÌNH XUẤT ẢNH CHO WORD (HIGH RESOLUTION) ---
export_config = {
    'displayModeBar': True, # Hiển thị thanh công cụ
    'displaylogo': False,   # Tắt logo Plotly
    'toImageButtonOptions': {
        'format': 'png', 
        'filename': 'Bieu_do_Line4',
        'height': 600,
        'width': 1200,
        'scale': 2 # Nhân đôi độ phân giải để chèn Word cực nét
    }
}

# --- 3. THANH BÊN (SIDEBAR) ---
st.sidebar.header("📂 HỆ THỐNG DỮ LIỆU")
uploaded_file = st.sidebar.file_uploader("Tải file Excel/CSV báo cáo Line 4", type=["xlsx", "csv", "xls"])

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

        metrics_map = {"YS (降伏強度)": "YS", "TS (抗拉強度)": "TS", "EL (伸長率)": "EL", "Hardness (硬度)": "HRB"}
        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        
        if not available:
            st.error("❌ Không tìm thấy các cột dữ liệu phù hợp.")
            st.stop()

        selected_label = st.sidebar.selectbox("Thông số phân tích:", available)
        view_mode = st.sidebar.radio("Chế độ hiển thị:", ["Phân tích Tổng thể (View 1)", "Kiểm soát SPC I-MR (View 2)"])
        
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df, short_key)
        zh_key = "降伏強度" if "YS" in short_key else "抗拉強度" if "TS" in short_key else "伸長率" if "EL" in short_key else "硬度"
        
        v_lsl_int = get_valid_limit(df, zh_key, "min", "管制")
        v_usl_int = get_valid_limit(df, zh_key, "max", "管制")
        v_lsl_cust = get_valid_limit(df, zh_key, "min", "客戶要求")
        v_usl_cust = get_valid_limit(df, zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            st.title(f"LINE 4 ANALYTICS: {selected_label}")
            st.caption("💡 Mẹo: Rê chuột vào góc phải biểu đồ, nhấn biểu tượng 📷 (Camera) để tải ảnh sắc nét chèn vào Word.")

            # KHỐI KPI
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Tổng số mẫu (N)", n)
            k2.metric("Trung bình (μ)", f"{mu:.2f}")
            k3.metric("Độ lệch (σ)", f"{sigma:.2f}")
            
            t_lsl = v_lsl_cust if v_lsl_cust else v_lsl_int
            t_usl = v_usl_cust if v_usl_cust else v_usl_int
            cpk = None
            if sigma > 0:
                if t_lsl and t_usl: cpk = min((t_usl-mu)/(3*sigma), (mu-t_lsl)/(3*sigma))
                elif t_lsl: cpk = (mu - t_lsl)/(3*sigma)
                elif t_usl: cpk = (t_usl - mu)/(3*sigma)
            k4.metric("Năng lực Cpk", f"{cpk:.2f}" if cpk else "N/A", delta="Đạt" if cpk and cpk >= 1.33 else "Cảnh báo" if cpk else None)

            if "View 1" in view_mode:
                
                # --- BIỂU ĐỒ 1: PHÂN BỐ ---
                st.subheader("I. Trạng thái phân bố & Khả năng đáp ứng")
                
                k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                pts = [plot_data.min(), plot_data.max()]
                all_lims = [v for v in [v_lsl_cust, v_usl_cust, v_lsl_int, v_usl_int, lcl, ucl] if v]
                pts.extend(all_lims)
                
                # Tính toán không gian (padding) an toàn 8% để chữ không bị cắt
                min_pt, max_pt = min(pts), max(pts)
                pad = (max_pt - min_pt) * 0.08 if max_pt != min_pt else max_pt * 0.05
                x_range = [min_pt - pad, max_pt + pad]

                fig_dist = go.Figure()
                fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, marker_color='#3498db', opacity=0.7))
                
                if sigma > 0:
                    bin_w = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                    x_c = np.linspace(x_range[0], x_range[1], 400)
                    y_c = norm.pdf(x_c, mu, sigma) * n * bin_w
                    fig_dist.add_trace(go.Scatter(x=x_c, y=y_c, mode='lines', line=dict(color='#113763', width=3)))

                limit_hist = [
                    (v_lsl_cust, "KHÁCH MIN", "#FF0000", "dash"),
                    (v_usl_cust, "KHÁCH MAX", "#FF0000", "dash"),
                    (v_lsl_int, "Nội bộ Min", "#2C3E50", "dot"),
                    (v_usl_int, "Nội bộ Max", "#2C3E50", "dot")
                ]
                for v, lbl, clr, sty in limit_hist:
                    if v:
                        fig_dist.add_vline(x=v, line_dash=sty, line_color=clr, line_width=2.5)
                        fig_dist.add_annotation(
                            x=v, y=0.95, yref="paper", 
                            text=f"<b>{lbl}: {v}</b>", 
                            textangle=-90, 
                            font=dict(color=clr, size=12), 
                            bgcolor="white", bordercolor=clr, borderwidth=1, borderpad=4,
                            showarrow=False
                        )

                # Thêm lề phải r=80 để chứa khung chữ dọc
                fig_dist.update_layout(template="simple_white", height=450, xaxis_range=x_range, showlegend=False, 
                                      margin=dict(l=50, r=80, t=30, b=50),
                                      yaxis_title="Số lượng cuộn thép (Coils)", xaxis_title=f"Giá trị {selected_label}")
                
                # Gọi config để tải ảnh nét
                st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

                # --- BIỂU ĐỒ 2: TRENDING ---
                st.subheader("II. Xu hướng sản xuất & Các tầng giới hạn")
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', 
                                              line=dict(color='#3498db', width=2),
                                              marker=dict(size=7, color='white', line=dict(width=2, color='#3498db'))))

                trend_lines = [
                    (mu, "MEAN", "#27AE60", "solid", 1.02),
                    (ucl, "UCL", "#D35400", "dash", 1.02),
                    (lcl, "LCL", "#D35400", "dash", 1.02),
                    (v_usl_int, "Int Max", "#2C3E50", "dot", 1.12),
                    (v_lsl_int, "Int Min", "#2C3E50", "dot", 1.12),
                    (v_usl_cust, "SPEC MAX", "#FF0000", "dashdot", 1.22),
                    (v_lsl_cust, "SPEC MIN", "#FF0000", "dashdot", 1.22)
                ]

                for v, lbl, clr, sty, pos in trend_lines:
                    if v:
                        fig_trend.add_hline(y=v, line_dash=sty, line_color=clr, line_width=2)
                        fig_trend.add_annotation(
                            x=pos, y=v, xref="paper", 
                            text=f"<b>{lbl}: {v:.1f}</b>",
                            showarrow=False, 
                            font=dict(color=clr, size=12), 
                            bgcolor="white", bordercolor=clr, borderwidth=1, borderpad=4,
                            xanchor="left"
                        )

                # Nới lề phải lên r=280 để chữ không bao giờ bị cắt
                fig_trend.update_layout(template="simple_white", height=500, margin=dict(l=50, r=280, t=30, b=50), showlegend=False,
                                       xaxis_title="Thứ tự cuộn (Sequence)", yaxis_title="Giá trị đo thực tế")
                
                # Gọi config để tải ảnh nét
                st.plotly_chart(fig_trend, use_container_width=True, config=export_config)

            else:
                st.subheader("Biểu đồ kiểm soát SPC I-MR")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=("I-Chart", "MR-Chart"))
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers'), row=1, col=1)
                fig_imr.add_hline(y=ucl, line_dash="dash", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=lcl, line_dash="dash", line_color="red", row=1, col=1)
                fig_imr.add_hline(y=mu, line_color="green", row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', line=dict(color='orange')), row=2, col=1)
                fig_imr.update_layout(height=750, template="simple_white", showlegend=False)
                
                st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"Lỗi hệ thống: {e}")
else:
    st.info("👈 Vui lòng tải file Excel lên thanh Sidebar để bắt đầu báo cáo.")
