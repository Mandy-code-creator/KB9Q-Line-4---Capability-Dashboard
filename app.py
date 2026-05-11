import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
import re
import math

# --- 1. CẤU HÌNH GIAO DIỆN EXECUTIVE DASHBOARD ---
st.set_page_config(page_title="Line 4 Quality Dashboard", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #F8F9FB; }
    
    /* Thiết kế thẻ Card cho biểu đồ - Sạch sẽ & Sang trọng */
    div.stPlotlyChart {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 25px;
    }
    
    /* Thẻ KPI chuẩn BI */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-top: 4px solid #1A365D;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    h1, h2, h3 { 
        color: #1A365D !important; 
        font-family: 'Inter', sans-serif !important; 
        font-weight: 700 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIC TÌM KIẾM DỮ LIỆU ---
def find_actual_col(df, key):
    for col in df.columns:
        if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求"]):
            return col
    return None

def fetch_limit(df, keyword, limit_type, category):
    col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
    if col:
        val = pd.to_numeric(df[col], errors='coerce').median()
        return float(val) if pd.notnull(val) and val > 0 else None
    return None

# --- 3. SIDEBAR ---
st.sidebar.header("📂 Nguồn dữ liệu")
file = st.sidebar.file_uploader("Tải file Excel/CSV báo cáo Line 4", type=["xlsx", "csv", "xls"])

if file:
    try:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        df_raw.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df_raw.columns]

        if "用途碼" in df_raw.columns:
            usage_list = sorted(df_raw["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Lọc 用途碼:", options=usage_list, default=usage_list)
            df = df_raw[df_raw["用途碼"].isin(selected_usages)]
        else:
            df = df_raw

        metrics_map = {"YS (降伏強度)": "YS", "TS (抗拉強度)": "TS", "EL (伸長率)": "EL", "Hardness (硬度)": "HRB"}
        available = [k for k, v in metrics_map.items() if find_actual_col(df, v)]
        
        if not available:
            st.error("Không tìm thấy dữ liệu phù hợp.")
            st.stop()

        metric_label = st.sidebar.selectbox("Thông số hiển thị:", available)
        
        # Xử lý thông số
        short_k = metrics_map[metric_label]
        data_c = find_actual_col(df, short_k)
        zh_k = "降伏強度" if "YS" in short_k else "抗拉強度" if "TS" in short_k else "伸長率" if "EL" in short_k else "硬度"
        
        # Giới hạn
        v_lsl_int = fetch_limit(df, zh_k, "min", "管制")
        v_usl_int = fetch_limit(df, zh_k, "max", "管制")
        v_lsl_cust = fetch_limit(df, zh_k, "min", "客戶要求")
        v_usl_cust = fetch_limit(df, zh_k, "max", "客戶要求")

        if data_c:
            raw_vals = pd.to_numeric(df[data_c], errors='coerce').dropna().reset_index(drop=True)
            n, mu, sigma = len(raw_vals), raw_vals.mean(), raw_vals.std()
            ucl, lcl = mu + 3*sigma, mu - 3*sigma

            st.title(f"🚀 LINE 4 QUALITY: {metric_label}")

            # --- KHỐI KPI - ĐƯA THÔNG SỐ RA NGOÀI BIỂU ĐỒ ---
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Số mẫu (N)", n)
            k2.metric("Trung bình (μ)", f"{mu:.2f}")
            k3.metric("Độ lệch (σ)", f"{sigma:.2f}")
            
            t_lsl = v_lsl_cust if v_lsl_cust else v_lsl_int
            t_usl = v_usl_cust if v_usl_cust else v_usl_int
            cpk = None
            if sigma > 0:
                if t_lsl and t_usl: cpk = min((t_usl-mu)/(3*sigma), (mu-t_lsl)/(3*sigma))
                elif t_lsl: cpk = (mu - t_lsl)/(3*sigma)
                elif t_usl: cpk = (t_usl - mu)/(3*sigma)
            k4.metric("Chỉ số Cpk", f"{cpk:.2f}" if cpk else "N/A")

            # --- PHẦN 1: PHÂN BỐ (HISTOGRAM) ---
            st.subheader("I. Trạng thái phân bố & Đường chuẩn")
            
            k_bins = math.ceil(1 + 3.322 * math.log10(n)) if n > 0 else 10
            pts = [raw_vals.min(), raw_vals.max()]
            all_l = [v for v in [v_lsl_cust, v_usl_cust, v_lsl_int, v_usl_int, lcl, ucl] if v]
            pts.extend(all_l)
            x_rng = [min(pts) * 0.98, max(pts) * 1.02]

            fig_dist = go.Figure()
            # Histogram
            fig_dist.add_trace(go.Histogram(x=raw_vals, nbinsx=k_bins, marker_color='#3182CE', opacity=0.7))
            
            # Normal Curve
            if sigma > 0:
                bin_width = (raw_vals.max() - raw_vals.min()) / k_bins if n > 1 else 1
                xc = np.linspace(x_rng[0], x_rng[1], 400)
                yc = norm.pdf(xc, mu, sigma) * n * bin_width
                fig_dist.add_trace(go.Scatter(x=xc, y=yc, mode='lines', line=dict(color='#2C5282', width=3)))

            # Giới hạn trên Histogram - Nhãn đặt ở trên để tránh che dữ liệu
            h_limits = [(v_lsl_cust, "KHÁCH MIN", "#E53E3E"), (v_usl_cust, "KHÁCH MAX", "#E53E3E"),
                        (v_lsl_int, "Nội bộ Min", "#744210"), (v_usl_int, "Nội bộ Max", "#744210")]
            
            for v, lbl, clr in h_limits:
                if v:
                    fig_dist.add_vline(x=v, line_dash="dash", line_color=clr, line_width=2)
                    fig_dist.add_annotation(x=v, y=1, yref="paper", text=f"<b>{lbl}: {v}</b>", 
                                          textangle=-90, font=dict(color=clr), bgcolor="white", showarrow=False)

            fig_dist.update_layout(template="simple_white", height=450, xaxis_range=x_rng, showlegend=False, 
                                  yaxis_title="Số lượng cuộn", xaxis_title=f"Giá trị thực tế")
            st.plotly_chart(fig_dist, use_container_width=True)

            # --- PHẦN 2: TRENDING (BIỂU ĐỒ XU HƯỚNG) ---
            st.subheader("II. Xu hướng sản xuất & Giới hạn đa tầng")
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=raw_vals.index, y=raw_vals, mode='lines+markers', 
                                          line=dict(color='#3182CE', width=1.5),
                                          marker=dict(size=6, color='white', line=dict(width=1.5, color='#3182CE'))))

            # Nhãn Trending đẩy hẳn sang lề phải (r=250) để không che điểm dữ liệu
            t_limits = [
                (mu, "MEAN", "green", "solid", 1.01),
                (ucl, "UCL", "#DD6B20", "dash", 1.01),
                (lcl, "LCL", "#DD6B20", "dash", 1.01),
                (v_usl_int, "Int Max", "#744210", "dot", 1.10),
                (v_lsl_int, "Int Min", "#744210", "dot", 1.10),
                (v_usl_cust, "SPEC MAX", "#E53E3E", "dashdot", 1.20),
                (v_lsl_cust, "SPEC MIN", "#E53E3E", "dashdot", 1.20)
            ]

            for v, lbl, clr, sty, pos in t_limits:
                if v:
                    fig_trend.add_hline(y=v, line_dash=sty, line_color=clr, line_width=2)
                    fig_trend.add_annotation(x=pos, y=v, xref="paper", text=f"<b>{lbl}: {v:.1f}</b>",
                                           showarrow=False, font=dict(color=clr, size=10), xanchor="left")

            fig_trend.update_layout(template="simple_white", height=500, margin=dict(r=250), showlegend=False,
                                   xaxis_title="Thứ tự cuộn sản xuất", yaxis_title="Giá trị đo")
            st.plotly_chart(fig_trend, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi: {e}")
else:
    st.info("👈 Hãy tải file báo cáo Excel ở Sidebar để bắt đầu.")
