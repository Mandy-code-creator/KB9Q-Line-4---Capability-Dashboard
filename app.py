import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
import math
from scipy.stats import norm

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Line 4 Quality Analytics", layout="wide")

# Thiết lập font in đậm và to hơn toàn cục
plt.rcParams.update({
    'font.size': 12,
    'axes.labelweight': 'bold',
    'axes.titleweight': 'bold',
    'axes.titlesize': 15,
    'legend.fontsize': 11,
    'font.weight': 'bold'
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
    """Ép khung viền đen đậm kín 4 cạnh"""
    for spine in ax.spines.values():
        spine.set_linewidth(2.5)
        spine.set_color('black')
        spine.set_visible(True)

# ==========================================
# 3. MAIN APP
# ==========================================
st.sidebar.header("📂 DATA SOURCE")
uploaded_file = st.sidebar.file_uploader("Upload Excel/CSV Report", type=["xlsx", "csv", "xls"])

if uploaded_file:
    try:
        df_raw = load_and_clean_data(uploaded_file)
        df = df_raw.copy()
        
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
        
        # 1. Giới hạn Nội bộ (Control Limits)
        int_lsl = get_limit(df, zh_key, "min", "管制")
        int_usl = get_limit(df, zh_key, "max", "管制")
        
        # 2. Giới hạn Khách hàng (Customer Specs)
        cust_lsl = get_limit(df, zh_key, "min", "客戶要求")
        cust_usl = get_limit(df, zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            mu, sigma = plot_data.mean(), plot_data.std(ddof=1)
            
            # 3. Giới hạn 3-Sigma (Statistical Limits)
            ucl_3s, lcl_3s = mu + 3*sigma, mu - 3*sigma

            st.title(f"📊 Quality Analytics: {selected_label}")

            if view_mode == "Process Analytics":
                tab_trend, tab_dist = st.tabs(["📈 Trend Analysis", "📊 Distribution & SPC"])

                with tab_trend:
                    x_idx = np.arange(1, len(plot_data) + 1)
                    fig, ax = plt.subplots(figsize=(12, 6))
                    
                    # Vẽ đường dữ liệu
                    ax.plot(x_idx, plot_data, marker="o", markersize=8, linewidth=2.5, label="Actual Value", color="#1f77b4")
                    
                    # Giới hạn KHÁCH HÀNG (Xanh lá - Solid)
                    if cust_lsl: ax.axhline(cust_lsl, color="green", linestyle="-", linewidth=3, label=f"Cust LSL: {cust_lsl:.1f}")
                    if cust_usl: ax.axhline(cust_usl, color="green", linestyle="-", linewidth=3, label=f"Cust USL: {cust_usl:.1f}")
                    
                    # Giới hạn NỘI BỘ (Đỏ - Dash)
                    if int_lsl: ax.axhline(int_lsl, color="red", linestyle="--", linewidth=3, label=f"Int LSL: {int_lsl:.1f}")
                    if int_usl: ax.axhline(int_usl, color="red", linestyle="--", linewidth=3, label=f"Int USL: {int_usl:.1f}")
                    
                    # Giới hạn 3-SIGMA (Cam - Dot)
                    ax.axhline(ucl_3s, color="#ff7f0e", linestyle=":", linewidth=3, label=f"3σ UCL: {ucl_3s:.1f}")
                    ax.axhline(lcl_3s, color="#ff7f0e", linestyle=":", linewidth=3, label=f"3σ LCL: {lcl_3s:.1f}")
                    ax.axhline(mu, color="purple", linestyle="-.", linewidth=2, label=f"Mean: {mu:.1f}")

                    ax.set_title(f"{selected_label} Trend Analysis", weight="bold", pad=20)
                    ax.set_xlabel("Sequence")
                    ax.set_ylabel("Value")
                    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), frameon=True, ncol=3, fontsize=10)
                    
                    apply_full_border(ax)
                    plt.tight_layout()
                    st.pyplot(fig)

                with tab_dist:
                    fig_dist, ax_dist = plt.subplots(figsize=(12, 6))
                    # Histogram
                    ax_dist.hist(plot_data, bins=20, density=True, alpha=0.5, color="#7FB3D5", edgecolor="black", linewidth=1.2)
                    
                    # Normal Fit
                    xs = np.linspace(plot_data.min()*0.9, plot_data.max()*1.1, 500)
                    ax_dist.plot(xs, norm.pdf(xs, mu, sigma), color="#1E3A8A", linewidth=3, label="Normal Fit")
                    
                    # Các đường giới hạn (Tương tự Trend)
                    if cust_lsl: ax_dist.axvline(cust_lsl, color="green", linestyle="-", linewidth=3, label=f"Cust LSL")
                    if cust_usl: ax_dist.axvline(cust_usl, color="green", linestyle="-", linewidth=3, label=f"Cust USL")
                    if int_lsl: ax_dist.axvline(int_lsl, color="red", linestyle="--", linewidth=3, label=f"Int LSL")
                    if int_usl: ax_dist.axvline(int_usl, color="red", linestyle="--", linewidth=3, label=f"Int USL")
                    ax_dist.axvline(ucl_3s, color="#ff7f0e", linestyle=":", linewidth=3, label="3σ UCL")
                    ax_dist.axvline(lcl_3s, color="#ff7f0e", linestyle=":", linewidth=3, label="3σ LCL")

                    ax_dist.set_title(f"{selected_label} Distribution & Specs", weight="bold", pad=20)
                    ax_dist.legend(loc="upper right", fontsize=9)
                    apply_full_border(ax_dist)
                    st.pyplot(fig_dist)

                    # Bảng thống kê SPC
                    cpk = min((int_usl - mu)/(3*sigma), (mu - int_lsl)/(3*sigma)) if sigma > 0 and int_usl and int_lsl else 0
                    eval_msg = "Excellent" if cpk >= 1.33 else ("Good" if cpk >= 1.0 else "Poor")
                    st.table(pd.DataFrame([{"Samples": len(plot_data), "Mean": f"{mu:.2f}", "Std Dev": f"{sigma:.2f}", "Cpk": f"{cpk:.2f}", "Rating": eval_msg}]))

            else:
                # SPC I-MR (Giữ thiết kế in đậm)
                st.subheader("III. Statistical Process Control (I-MR)")
                mr = plot_data.diff().abs()
                mr_ucl = mr.mean() * 3.267
                
                fig_imr, (ax_i, ax_mr) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
                
                # I Chart
                ax_i.plot(plot_data, marker="o", color="#1f77b4", linewidth=2)
                ax_i.axhline(ucl_3s, color="red", linestyle="--", linewidth=2.5, label="UCL")
                ax_i.axhline(lcl_3s, color="red", linestyle="--", linewidth=2.5, label="LCL")
                ax_i.axhline(mu, color="green", linestyle="-", linewidth=2.5, label="Mean")
                ax_i.set_title("Individual Chart (I)", weight="bold")
                apply_full_border(ax_i)
                
                # MR Chart
                ax_mr.plot(mr, marker="o", color="#ff7f0e", linewidth=2)
                ax_mr.axhline(mr_ucl, color="red", linestyle="--", linewidth=2.5, label="UCL")
                ax_mr.axhline(mr.mean(), color="green", linestyle="-", linewidth=2.5, label="Avg MR")
                ax_mr.set_title("Moving Range Chart (MR)", weight="bold")
                apply_full_border(ax_mr)
                
                plt.tight_layout()
                st.pyplot(fig_imr)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Please upload data to begin.")
