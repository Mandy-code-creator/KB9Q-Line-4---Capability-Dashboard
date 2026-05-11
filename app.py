import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import re
import math

# --- 1. CONFIG GIAO DIỆN EXECUTIVE DASHBOARD CHUẨN ---
st.set_page_config(page_title="Hệ thống phân tích chất lượng Line 4", layout="wide")

# Tích hợp CSS advanced để tạo các thẻ "Card" trắng, bo tròn đổ bóng, tông xanh navy chuyên nghiệp
st.markdown("""
    <style>
    /* Nền Slate nhạt tạo chiều sâu cho báo cáo */
    .main { background-color: #F0F4F8; }
    
    /* Thiết kế thẻ Card trắng bo tròn đổ bóng nhẹ cho biểu đồ */
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 12px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 25px;
    }
    
    /* KPI Metric Cards bo tròn đổ bóng nhẹ, tông xanh navy nổi bật */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-top: 5px solid #113763;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Font chữ chuyên nghiệp, bôi đậm tiêu đề */
    h1, h2, h3 { 
        color: #113763 !important; 
        font-family: 'Segoe UI', Tahoma, sans-serif !important; 
        font-weight: 800 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. HÀM XỬ LÝ DỮ LIỆU THÔNG MINH ---
def find_data_col(df, key):
    """Tìm cột dữ liệu thực tế bằng regex, loại trừ các từ khóa giới hạn"""
    for col in df.columns:
        if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求"]):
            return col
    return None

def get_valid_limit(df, keyword, limit_type, category):
    """Trích xuất trung vị giới hạn, xử lý bỏ qua ô trống hoặc <= 0"""
    col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
    if col:
        # errors='coerce' để biến các giá trị không hợp lệ thành NaN, pd.notnull bỏ qua NaN
        val = pd.to_numeric(df[col], errors='coerce').median()
        return float(val) if pd.notnull(val) and val > 0 else None
    return None

# --- CẤU HÌNH XUẤT ẢNH PNG ĐỘ PHÂN GIẢI CAO (Chèn Word nét) ---
export_config = {
    'displayModeBar': True, # Hiển thị modebar với modebar.add_annotation: ' Download plot as a png'
    'displaylogo': False,   # Tắt logo Plotly
    'toImageButtonOptions': {
        'format': 'png', 
        'filename': 'Line4_Quality_Analytics',
        'height': 600,
        'width': 1200,
        'scale': 2 # Nhân đôi độ phân giải để chèn Word cực nét, không bị bể nét
    }
}

# --- 3. THANH BÊN (SIDEBAR) ---
st.sidebar.header("📂 NGUỒN DỮ LIỆU")
uploaded_file = st.sidebar.file_uploader("Tải file Excel/CSV báo cáo Line 4", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        # Đọc dữ liệu và dọn sạch tên cột
        df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df_raw.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df_raw.columns]

        # Bộ lọc 用途碼 (Usage Code)
        if "用途碼" in df_raw.columns:
            usage_list = sorted(df_raw["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Lọc mã ứng dụng (用途碼):", options=usage_list, default=usage_list)
            df = df_raw[df_raw["用途碼"].isin(selected_usages)]
        else:
            df = df_raw

        # Danh mục thông số cơ tính
        metrics_map = {"YS (降伏強度)": "YS", "TS (抗拉強度)": "TS", "EL (伸長率)": "EL", "Hardness (硬 độ)": "HRB"}
        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        
        if not available:
            st.error("❌ Không tìm thấy các cột dữ liệu YS, TS, EL... phù hợp.")
            st.stop()

        selected_label = st.sidebar.selectbox("Thông số cơ tính:", available)
        view_mode = st.sidebar.radio("Cài đặt hiển thị:", ["Phân tích Tổng thể (View 1)", "Biểu đồ Kiểm soát SPC I-MR (View 2)"])
        
        # Lấy thông số cụ thể
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df, short_key)
        zh_key = "降伏強度" if "YS" in short_key else "抗拉強度" if "TS" in short_key else "伸長率" if "EL" in short_key else "硬度"
        
        # Trích xuất đầy đủ đa tầng giới hạn
        v_lsl_int = get_valid_limit(df, zh_key, "min", "管制")
        v_usl_int = get_valid_limit(df, zh_key, "max", "管制")
        v_lsl_cust = get_valid_limit(df, zh_key, "min", "客戶要求")
        v_usl_cust = get_valid_limit(df, zh_key, "max", "客戶 yêu cầu")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(plot_data), plot_data.mean(), plot_data.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            # --- GIAO DIỆN CHÍNH ---
            st.title(f"🚀 Phân tích Chất lượng: {selected_label}")
            st.caption("💡 Mẹo: Rê chuột vào góc phải biểu đồ, nhấn biểu tượng 📷 (Download plot as a png) để tải ảnh sắc nét chèn vào file Word.")

            # Khối KPI Metric Card (Đưa các Capability Indices che khuất ra ngoài)
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Tổng số mẫu (N)", n)
            k2.metric("Trung bình (μ)", f"{mu:.2f}")
            k3.metric("Độ lệch (σ)", f"{sigma:.2f}")
            
            # Tính Cpk thông minh (Dựa trên Spec Limits: LSL và USL)
            # Ưu tiên giới hạn khách hàng, nếu không có dùng giới hạn nội bộ
            t_lsl = v_lsl_cust if v_lsl_cust else v_lsl_int
            t_usl = v_usl_cust if v_usl_cust else v_usl_int
            cpk = None
            if sigma > 0:
                if t_lsl and t_usl: cpk = min((t_usl-mu)/(3*sigma), (mu-t_lsl)/(3*sigma))
                elif t_lsl: cpk = (mu - t_lsl)/(3*sigma)
                elif t_usl: cpk = (t_usl - mu)/(3*sigma)
            k4.metric("Năng lực Cpk", f"{cpk:.2f}" if cpk else "N/A", delta="Đạt" if cpk and cpk >= 1.33 else "Cảnh báo" if cpk else None)

            # --- VIEW 1: DISTRIBUTION & TRENDING (STACKED LAYOUT CHỐNG CHE KHUẤT) ---
            if "View 1" in view_mode:
                
                # 1. BIỂU ĐỒ PHÂN BỐ (Bố cục dọc 100% chiều ngang)
                st.subheader("I. Trạng thái phân bố & Năng lực")
                
                # Sturges để tính số binsx cho Histogram
                k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
                
                # Cân chỉnh trục X an toàn để đường chuẩn Normal không bị cụt (Vấn đề mất dữ liệu)
                pts = [plot_data.min(), plot_data.max()]
                all_lims = [v for v in [v_lsl_cust, v_usl_cust, v_lsl_int, v_usl_int, lcl, ucl] if v]
                pts.extend(all_lims)
                
                # Thêm padding an toàn 8% để Normal Curve không bị cụt ở các giới hạn xa
                min_pt, max_pt = min(pts), max(pts)
                padding = (max_pt - min_pt) * 0.08 if max_pt != min_pt else max_pt * 0.05
                x_range = [min_pt - padding, max_pt + padding]

                fig_dist = go.Figure()
                # Histogram (Count) - markers+lines, marker_color='#3498db', opacity=0.7, showlegend=False
                fig_dist.add_trace(go.Histogram(x=plot_data, nbinsx=k_bins, marker_color='#3498db', opacity=0.7, name="Dữ liệu"))
                
                # Normal Curve scale theo Count
                if sigma > 0:
                    bin_w = (plot_data.max() - plot_data.min()) / k_bins if n > 1 else 1
                    x_c = np.linspace(x_range[0], x_range[1], 400)
                    y_c = norm.pdf(x_c, mu, sigma) * n * bin_w
                    fig_dist.add_trace(go.Scatter(x=x_c, y=y_c, mode='lines', line=dict(color='#113763', width=3), name="Đường chuẩn"))

                # Vẽ các giới hạn quy cách lên Histogram (Nhãn dọc -90, x-anchor=center để không che dữ liệu)
                limit_configs_dist = [
                    (v_lsl_cust, "KHÁCH MIN", "#FF0000", "dash"), # Đỏ tươi độ tương phản cao
                    (v_usl_cust, "KHÁCH MAX", "#FF0000", "dash"),
                    (v_lsl_int, "Nội bộ Min", "#2C3E50", "dot"), # Than chì sắc nét
                    (v_usl_int, "Nội bộ Max", "#2C3E50", "dot")
                ]
                for v, lbl, clr, sty in limit_configs_dist:
                    if v:
                        fig_dist.add_vline(x=v, line_dash=sty, line_color=clr, line_width=2.5)
                        fig_dist.add_annotation(x=v, y=1, yref="paper", text=f"<b>{lbl}: {v}</b>", 
                                              textangle=-90, font=dict(color=clr, size=12), bgcolor="white", bordercolor=clr, borderwidth=1, borderpad=4,
                                              showarrow=False)

                fig_dist.update_layout(template="simple_white", height=450, xaxis_range=x_range, showlegend=False, 
                                      yaxis_title="Số lượng cuộn thép (Coils)", xaxis_title=f"Giá trị {selected_label}",
                                      font=dict(family="Segoe UI, Tahoma", size=13))
                st.plotly_chart(fig_dist, use_container_width=True, config=export_config)

                # 2. BIỂU ĐỒ TRENDING (Bố cục dọc 100% chiều ngang)
                st.subheader("II. Xu hướng sản xuất & Các tầng giới hạn")
                fig_trend = go.Figure()
                # Markers trắng viền xanh Blue chuyên nghiệp. markers+lines, marker_line_color='#0078D4', marker_line_width=1.5, marker_color='white', markers_size=6
                fig_trend.add_trace(go.Scatter(x=plot_data.index, y=plot_data, mode='lines+markers', 
                                              line=dict(color='#3498db', width=2),
                                              marker=dict(size=7, color='white', line=dict(width=1.5, color='#3498db'))))

                # Danh sách giới hạn trên Trending (Offset nhãn đè sang lề phải l=280 để không che dữ liệu)
                # Phân tầng: Thống kê (pos 1.02), Nội bộ (pos 1.12), Khách hàng (pos 1.22)
                limit_configs_trend = [
                    (mu, "MEAN", "#27AE60", "solid", 1.02), # Xanh lá đậm tương phản cao
                    (ucl, "UCL", "#D35400", "dash", 1.02), # Cam đậm tương phản cao
                    (lcl, "LCL", "#D35400", "dash", 1.02),
                    (v_usl_int, "Nội bộ Max", "#2C3E50", "dot", 1.12), # Than chì sắc nét
                    (v_lsl_int, "Nội bộ Min", "#2C3E50", "dot", 1.12),
                    (v_usl_cust, "KHÁCH MAX", "#FF0000", "dashdot", 1.22), # Đỏ tươi độ tương phản cao
                    (v_lsl_cust, "KHÁCH MIN", "#FF0000", "dashdot", 1.22)
                ]

                for v, lbl, clr, sty, pos in limit_configs_trend:
                    if v:
                        fig_trend.add_hline(y=v, line_dash=sty, line_color=clr, line_width=2)
                        # Đóng khung nhãn chữ bôi đậm `<b>`
                        fig_trend.add_annotation(x=pos, y=v, xref="paper", text=f"<b>{lbl}: {v:.1f}</b>",
                                               showarrow=False, font=dict(color=clr, size=12), bgcolor="white", bordercolor=clr, borderwidth=1, borderpad=4,
                                               xanchor="left")

                # Nới lề phải lên r=280 để chứa khung nhãn đứng của Exec Dashboard, font="Segoe UI", size=13
                fig_trend.update_layout(template="simple_white", height=500, margin=dict(l=50, r=280, t=30, b=50), showlegend=False,
                                       xaxis_title="Thứ tự cuộn (Sequence)", yaxis_title="Giá trị đo thực tế",
                                       font=dict(family="Segoe UI, Tahoma", size=13))
                
                # Gọi config để tải ảnh PNG chất lượng cao để chèn Word
                st.plotly_chart(fig_trend, use_container_width=True, config=export_config)

            # --- VIEW 2: SPC I-MR CHARTS (Giữ nguyên bố cục của người dùng) ---
            else:
                st.subheader("Biểu đồ kiểm soát SPC I-MR")
                mr = plot_data.diff().abs()
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, 
                                        subplot_titles=("I-Chart (Cá nhân)", "MR-Chart (Moving Range)"),
                                        # template="simple_white", showlegend=False, font="Segoe UI, Tahoma", size=13
                                        )
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers'), row=1, col=1)
                fig_imr.add_hline(y=ucl, line_dash="dash", line_color="#FF0000", row=1, col=1)
                fig_imr.add_hline(y=lcl, line_dash="dash", line_color="#FF0000", row=1, col=1)
                fig_imr.add_hline(y=mu, line_color="#27AE60", row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', line=dict(color='#D35400')), row=2, col=1)
                fig_imr.update_layout(height=750, template="simple_white", showlegend=False,
                                     font=dict(family="Segoe UI, Tahoma", size=13))
                
                # Tích hợp tải ảnh high-res
                st.plotly_chart(fig_imr, use_container_width=True, config=export_config)

    except Exception as e:
        st.error(f"Error system: {e}")
else:
    st.info("👈 Tải file Excel báo cáo sản xuất ở Sidebar bên trái để bắt đầu phân tích đa tầng giới hạn.")
