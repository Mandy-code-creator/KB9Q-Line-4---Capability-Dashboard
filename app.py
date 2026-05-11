import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
from scipy.stats import norm

# ==========================================
# 1. CẤU HÌNH TRANG
# ==========================================
st.set_page_config(page_title="Line 4 Quality Analytics", layout="wide")

plt.rcParams.update({
    'font.size': 12,
    'axes.labelweight': 'bold',
    'axes.titleweight': 'bold',
    'axes.titlesize': 15,
    'legend.fontsize': 10,
    'font.weight': 'bold',
    'lines.linewidth': 2.5
})

# ==========================================
# 2. CÁC HÀM TIỆN ÍCH
# ==========================================
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]
    return df

def find_data_col(df, key):
    for col in df.columns:
        if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求"]):
            return col
    return None

def get_limit(df, keyword, limit_type, category):
    col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
    if col:
        val = pd.to_numeric(df[col], errors='coerce').median()
        return float(val) if pd.notnull(val) and val > 0 else None
    return None

def apply_full_border(ax):
    for spine in ax.spines.values():
        spine.set_linewidth(2.5)
        spine.set_color('black')
        spine.set_visible(True)

def format_num(val):
    if val is None or pd.isna(val): return "-"
    rounded = round(float(val), 1)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)

# ==========================================
# 3. LOGIC CHÍNH CỦA ỨNG DỤNG
# ==========================================
st.sidebar.header("📂 NGUỒN DỮ LIỆU")
uploaded_file = st.sidebar.file_uploader("Tải file báo cáo Excel/CSV", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df_raw = load_and_clean_data(uploaded_file)
        df = df_raw.copy()
        
        if "用途碼" in df_raw.columns:
            usage_list = sorted(df_raw["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Lọc mã sử dụng:", options=usage_list, default=usage_list)
            df = df_raw[df_raw["用途碼"].isin(selected_usages)]

        metrics_map = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        if not available: st.stop()

        selected_label = st.sidebar.selectbox("Chọn thông số:", available)
        view_mode = st.sidebar.radio("Chế độ xem:", ["Phân tích quy trình (View 1)", "Tối ưu hóa giới hạn (View 2)"])
        
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df, short_key)
        zh_map = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}
        zh_key = zh_map.get(short_key, short_key)
        
        int_lsl = get_limit(df, zh_key, "min", "管制")
        int_usl = get_limit(df, zh_key, "max", "管制")
        cust_lsl = get_limit(df, zh_key, "min", "客戶要求")
        cust_usl = get_limit(df, zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n, mu = len(plot_data), plot_data.mean()
            sigma_std = plot_data.std(ddof=1)

            st.title(f"📊 Phân tích chất lượng: {selected_label}")

            # ==========================================
            # VIEW 1: GIỮ NGUYÊN KHÔNG THAY ĐỔI
            # ==========================================
            if view_mode == "Phân tích quy trình (View 1)":
                tab_trend, tab_dist = st.tabs(["📈 Biểu đồ xu hướng", "📊 Phân phối & Năng lực"])
                ucl_3s, lcl_3s = mu + 3*sigma_std, mu - 3*sigma_std

                with tab_trend:
                    fig_t, ax_t = plt.subplots(figsize=(12, 6))
                    ax_t.plot(np.arange(1, n+1), plot_data, marker="o", markersize=6, color="#1f77b4")
                    if cust_lsl: ax_t.axhline(cust_lsl, color="green", ls="-", lw=3)
                    if cust_usl: ax_t.axhline(cust_usl, color="green", ls="-", lw=3)
                    if int_lsl: ax_t.axhline(int_lsl, color="red", ls="--", lw=3)
                    if int_usl: ax_t.axhline(int_usl, color="red", ls="--", lw=3)
                    ax_t.axhline(ucl_3s, color="#ff7f0e", ls=":", lw=3)
                    ax_t.axhline(lcl_3s, color="#ff7f0e", ls=":", lw=3)
                    ax_t.set_title(f"Xu hướng {selected_label}", pad=20)
                    apply_full_border(ax_t); plt.tight_layout(); st.pyplot(fig_t)

                with tab_dist:
                    fig_d, ax_d = plt.subplots(figsize=(12, 6))
                    ax_d.hist(plot_data, bins=20, density=True, alpha=0.5, color="#7FB3D5", edgecolor="black")
                    xs = np.linspace(plot_data.min()*0.9, plot_data.max()*1.1, 500)
                    ax_d.plot(xs, norm.pdf(xs, mu, sigma_std), color="#1E3A8A", lw=3)
                    ax_d.set_title(f"Phân phối {selected_label}", pad=20)
                    apply_full_border(ax_d); plt.tight_layout(); st.pyplot(fig_d)

            # ==========================================
            # VIEW 2: TỐI ƯU HÓA & GHI CHÚ BƯỚC TÍNH
            # ==========================================
            else:
                st.subheader("II. Tối ưu hóa giới hạn kiểm soát")
                
                # Khu vực nhập liệu trong View 2
                st.markdown("##### ⚙️ Thiết lập thông số")
                c_i1, c_i2 = st.columns(2)
                with c_i1:
                    k_val = st.number_input("Nhập hệ số k (ví dụ: 3):", 1.0, 6.0, 3.0, 0.1)
                with c_i2:
                    m_sigma = st.number_input("Nhập Sigma (σ) mục tiêu (0 = tự động):", 0.0, 100.0, 0.0, 0.1)
                
                # Tính toán các loại Sigma
                s_std = sigma_std
                q1, q3 = plot_data.quantile(0.25), plot_data.quantile(0.75)
                s_iqr = (q3 - q1) / 1.349
                s_used = s_std if m_sigma == 0 else m_sigma

                st.markdown("##### 🎯 Bảng so sánh phương pháp và bước tính")
                col_t1, col_t2 = st.columns(2)
                
                with col_t1:
                    st.write("**Phương pháp 1: Độ lệch chuẩn (Std Dev)**")
                    data_std = {
                        "Thông số": ["Trung bình (Mean)", "Sigma (σ)", "Giới hạn dưới (LSL)", "Giới hạn trên (USL)"],
                        "Giá trị": [format_num(mu), format_num(s_std), format_num(mu - k_val*s_std), format_num(mu + k_val*s_std)],
                        "Cách tính": ["Tống / N", "Công thức StdDev", f"Mean - ({k_val} * σ)", f"Mean + ({k_val} * σ)"]
                    }
                    st.table(pd.DataFrame(data_std))

                with col_t2:
                    st.write("**Phương pháp 2: Khoảng tứ phân vị (IQR)**")
                    data_iqr = {
                        "Thông số": ["Trung bình (Mean)", "Sigma IQR (σ_iqr)", "Giới hạn dưới (LSL)", "Giới hạn trên (USL)"],
                        "Giá trị": [format_num(mu), format_num(s_iqr), format_num(mu - k_val*s_iqr), format_num(mu + k_val*s_iqr)],
                        "Cách tính": ["Tống / N", "IQR / 1.349", f"Mean - ({k_val} * σ_iqr)", f"Mean + ({k_val} * σ_iqr)"]
                    }
                    st.table(pd.DataFrame(data_iqr))

                st.markdown("---")
                st.markdown(f"##### 📈 So sánh giới hạn thực tế và đề xuất (k={k_val})")
                
                fig_imr, ax_i = plt.subplots(figsize=(12, 6))
                ax_i.plot(plot_data, marker="o", color="#1f77b4", label="Dữ liệu thực tế", alpha=0.7)
                
                # Giới hạn nội bộ hiện tại (từ file)
                if int_lsl: ax_i.axhline(int_lsl, color="red", ls="--", label="LSL hiện tại (File)")
                if int_usl: ax_i.axhline(int_usl, color="red", ls="--", label="USL hiện tại (File)")
                
                # Giới hạn đề xuất mới
                ax_i.axhline(mu + k_val*s_used, color="darkred", ls="-", lw=2, label=f"USL đề xuất ({k_val}σ)")
                ax_i.axhline(mu - k_val*s_used, color="darkred", ls="-", lw=2, label=f"LSL đề xuất ({k_val}σ)")
                ax_i.axhline(mu, color="green", ls="-", label="Trung bình")
                
                ax_i.set_title("Biểu đồ I-Chart: So sánh giới hạn cũ vs mới", weight="bold")
                ax_i.legend(loc="upper left", bbox_to_anchor=(1, 1))
                apply_full_border(ax_i)
                plt.tight_layout(); st.pyplot(fig_imr)

    except Exception as e:
        st.error(f"Lỗi hệ thống: {e}")
else:
    st.info("👈 Mandy hãy tải file báo cáo để bắt đầu phân tích.")
