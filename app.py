import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
from scipy.stats import norm

# ==========================================
# 1. PAGE CONFIGURATION
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
# 2. UTILITY FUNCTIONS
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

# ==========================================
# 3. MAIN APP LOGIC
# ==========================================
st.sidebar.header("📂 DATA SOURCE")
uploaded_file = st.sidebar.file_uploader("Upload Excel/CSV Report", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df_raw = load_and_clean_data(uploaded_file)
        df = df_raw.copy()
        
        # --- SIDEBAR SETTINGS ---
        st.sidebar.header("⚙️ SPC PARAMETERS")
        k_factor = st.sidebar.number_input("Hệ số Sigma (k):", min_value=1.0, max_value=6.0, value=3.0, step=0.1)
        
        if "用途碼" in df_raw.columns:
            usage_list = sorted(df_raw["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Filter Usage Code:", options=usage_list, default=usage_list)
            df = df_raw[df_raw["用途碼"].isin(selected_usages)]

        metrics_map = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        if not available: st.stop()

        selected_label = st.sidebar.selectbox("Select Parameter:", available)
        view_mode = st.sidebar.radio("View Mode:", ["Process Analytics", "SPC Control Charts (I-MR)"])
        
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
            n = len(plot_data)
            mu = plot_data.mean()
            
            # Tính toán Sigma Standard
            sigma_std = plot_data.std(ddof=1)
            # Tính toán Sigma IQR
            q1, q3 = plot_data.quantile(0.25), plot_data.quantile(0.75)
            iqr_val = q3 - q1
            sigma_iqr = iqr_val / 1.349
            
            # Cho phép người dùng nhập Sigma thủ công nếu muốn
            user_sigma = st.sidebar.number_input("Nhập Sigma tùy chỉnh (để trống để dùng Std Dev):", value=0.0, step=0.01)
            final_sigma = user_sigma if user_sigma > 0 else sigma_std

            st.title(f"📊 Quality Analytics: {selected_label}")

            # ==========================================
            # VIEW 1: GIỮ NGUYÊN
            # ==========================================
            if view_mode == "Process Analytics":
                # ... (Phần code View 1 giữ nguyên như các phiên bản trước của bạn) ...
                st.info("Chế độ Process Analytics đang hiển thị dựa trên Standard Deviation.")
                pass 

            # ==========================================
            # VIEW 2: SPC & LIMIT OPTIMIZATION (Cập nhật mới)
            # ==========================================
            else:
                st.subheader("II. Statistics & Control Limit Optimization")
                
                # --- PHẦN 1: THỐNG KÊ MÔ TẢ ---
                st.markdown("##### 📏 Descriptive Statistics")
                stats_df = pd.DataFrame({
                    "Thông số": ["Số lượng (N)", "Giá trị Max", "Giá trị Min", "Trung bình (Mean)"],
                    "Giá trị": [n, plot_data.max(), plot_data.min(), round(mu, 3)]
                })
                st.table(stats_df)

                # --- PHẦN 2: KẾT QUẢ RIÊNG BIỆT CHO 2 PHƯƠNG PHÁP ---
                st.markdown(f"##### 🎯 Internal Control Limit Optimization (k = {k_factor})")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Phương pháp 1: Standard Deviation**")
                    df_std = pd.DataFrame({
                        "Chỉ số": ["Sigma (σ)", "Giới hạn dưới (LSL)", "Giới hạn trên (USL)", "Công thức tính"],
                        "Giá trị": [
                            round(sigma_std, 3), 
                            round(mu - k_factor * sigma_std, 1), 
                            round(mu + k_factor * sigma_std, 1),
                            f"Mean ± ({k_factor} * StdDev)"
                        ]
                    })
                    st.table(df_std)

                with col2:
                    st.write("**Phương pháp 2: Interquartile Range (IQR)**")
                    df_iqr = pd.DataFrame({
                        "Chỉ số": ["Sigma (σ_iqr)", "Giới hạn dưới (LSL)", "Giới hạn trên (USL)", "Công thức tính"],
                        "Giá trị": [
                            round(sigma_iqr, 3), 
                            round(mu - k_factor * sigma_iqr, 1), 
                            round(mu + k_factor * sigma_iqr, 1),
                            f"Mean ± ({k_factor} * (IQR/1.349))"
                        ]
                    })
                    st.table(df_iqr)

                st.markdown("---")
                
                # --- PHẦN 3: BIỂU ĐỒ I-MR ---
                st.markdown(f"##### 📈 I-MR Charts (Sử dụng σ được chọn: {final_sigma:.3f})")
                mr = plot_data.diff().abs()
                mr_ucl = mr.mean() * 3.267
                
                fig_imr, (ax_i, ax_mr) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
                
                # I Chart
                ax_i.plot(plot_data, marker="o", color="#1f77b4", markersize=5)
                ax_i.axhline(mu + k_factor * final_sigma, color="red", ls="--", label=f"UCL ({k_factor}σ)")
                ax_i.axhline(mu - k_factor * final_sigma, color="red", ls="--", label=f"LCL ({k_factor}σ)")
                ax_i.axhline(mu, color="green", ls="-", label="Mean")
                ax_i.set_title("Individual Chart (I)", weight="bold")
                ax_i.legend(loc="upper left", bbox_to_anchor=(1, 1))
                apply_full_border(ax_i)
                
                # MR Chart
                ax_mr.plot(mr, marker="o", color="#ff7f0e", markersize=5)
                ax_mr.axhline(mr_ucl, color="red", ls="--", label="MR UCL")
                ax_mr.axhline(mr.mean(), color="green", ls="-", label="Avg MR")
                ax_mr.set_title("Moving Range Chart (MR)", weight="bold")
                ax_mr.legend(loc="upper left", bbox_to_anchor=(1, 1))
                apply_full_border(ax_mr)
                
                plt.tight_layout(); st.pyplot(fig_imr)

    except Exception as e:
        st.error(f"Lỗi: {e}")
else:
    st.info("👈 Mandy hãy tải file lên để bắt đầu.")
