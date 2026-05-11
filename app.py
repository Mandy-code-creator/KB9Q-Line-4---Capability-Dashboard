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
            sigma = plot_data.std(ddof=1)
            
            # Tính toán thêm chỉ số IQR
            q1 = plot_data.quantile(0.25)
            q3 = plot_data.quantile(0.75)
            iqr = q3 - q1
            sigma_iqr = iqr / 1.349 # Ước lượng sigma từ IQR cho phân phối chuẩn
            
            ucl_3s, lcl_3s = mu + 3*sigma, mu - 3*sigma

            st.title(f"📊 Quality Analytics: {selected_label}")

            # ==========================================
            # VIEW 1: GIỮ NGUYÊN
            # ==========================================
            if view_mode == "Process Analytics":
                tab_trend, tab_dist = st.tabs(["📈 Trend Analysis", "📊 Distribution & SPC"])
                with tab_trend:
                    x_idx = np.arange(1, n + 1)
                    fig_t, ax_t = plt.subplots(figsize=(12, 6))
                    ax_t.plot(x_idx, plot_data, marker="o", markersize=6, label="Actual Value", color="#1f77b4", zorder=1)
                    out_mask = (plot_data > (int_usl if int_usl else 99999)) | (plot_data < (int_lsl if int_lsl else -99999))
                    if out_mask.any():
                        ax_t.scatter(x_idx[out_mask], plot_data[out_mask], color='red', s=120, label="Out of Internal Spec", edgecolor='black', zorder=3)
                    if cust_lsl: ax_t.axhline(cust_lsl, color="green", linestyle="-", linewidth=3, label=f"Cust LSL: {cust_lsl:.1f}")
                    if cust_usl: ax_t.axhline(cust_usl, color="green", linestyle="-", linewidth=3, label=f"Cust USL: {cust_usl:.1f}")
                    if int_lsl: ax_t.axhline(int_lsl, color="red", linestyle="--", linewidth=3, label=f"Int LSL: {int_lsl:.1f}")
                    if int_usl: ax_t.axhline(int_usl, color="red", linestyle="--", linewidth=3, label=f"Int USL: {int_usl:.1f}")
                    ax_t.axhline(ucl_3s, color="#ff7f0e", linestyle=":", linewidth=3, label=f"3σ Limit")
                    ax_t.axhline(lcl_3s, color="#ff7f0e", linestyle=":", linewidth=3)
                    ax_t.set_title(f"{selected_label} Trend Analysis", pad=20)
                    ax_t.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), frameon=True, ncol=3, fontsize=9)
                    apply_full_border(ax_t); plt.tight_layout(); st.pyplot(fig_t)

                with tab_dist:
                    cpk = min((int_usl - mu)/(3*sigma), (mu - int_lsl)/(3*sigma)) if sigma > 0 and int_usl and int_lsl else 0
                    fig_d, ax_d = plt.subplots(figsize=(12, 6))
                    ax_d.hist(plot_data, bins=20, density=True, alpha=0.5, color="#7FB3D5", edgecolor="black")
                    xs = np.linspace(plot_data.min()*0.9, plot_data.max()*1.1, 500); ax_d.plot(xs, norm.pdf(xs, mu, sigma), color="#1E3A8A", linewidth=3)
                    def add_vline_with_value(ax, val, color, ls, label, level=1):
                        if val is not None:
                            ax.axvline(val, color=color, linestyle=ls, linewidth=3, label=label)
                            y_pos = ax.get_ylim()[1] * (1 + (level - 1) * 0.06)
                            ax.text(val, y_pos, f"{val:.1f}", color=color, ha='center', va='bottom', fontsize=11, fontweight='bold')
                    add_vline_with_value(ax_d, cust_lsl, "green", "-", "Cust LSL", 1); add_vline_with_value(ax_d, cust_usl, "green", "-", "Cust USL", 1)
                    add_vline_with_value(ax_d, int_lsl, "red", "--", "Int LSL", 2); add_vline_with_value(ax_d, int_usl, "red", "--", "Int USL", 2)
                    add_vline_with_value(ax_d, ucl_3s, "#ff7f0e", ":", "3σ UCL", 3); add_vline_with_value(ax_d, lcl_3s, "#ff7f0e", ":", "3σ LCL", 3)
                    ax_d.set_title(f"{selected_label} Distribution & Capability", pad=65); ax_d.legend(loc="upper left", bbox_to_anchor=(1, 1))
                    apply_full_border(ax_d); plt.tight_layout(); st.pyplot(fig_d)
                    st.dataframe(pd.DataFrame([{"N": n, "Mean": f"{mu:.3f}", "Std": f"{sigma:.3f}", "Cpk": f"{cpk:.3f}"}]), hide_index=True)

            # ==========================================
            # VIEW 2: SPC & LIMIT OPTIMIZATION (Gộp bảng dữ liệu và I-MR)
            # ==========================================
            else:
                st.subheader("II. Statistics & Control Limit Optimization")
                
                # --- PHẦN 1: BẢNG DỮ LIỆU THỐNG KÊ (NẰM TRÊN) ---
                st.markdown("##### 📏 Descriptive Statistics")
                col_stats_1, col_stats_2 = st.columns(2)
                
                with col_stats_1:
                    stats_basic = pd.DataFrame({
                        "Metric": ["Max", "Min", "Mean", "Count (N)"],
                        "Value": [plot_data.max(), plot_data.min(), round(mu, 3), n]
                    })
                    st.table(stats_basic)

                with col_stats_2:
                    stats_dispersion = pd.DataFrame({
                        "Method": ["Standard Deviation (σ)", "Interquartile Range (IQR)", "Estimated σ (from IQR)"],
                        "Value": [round(sigma, 3), round(iqr, 3), round(sigma_iqr, 3)]
                    })
                    st.table(stats_dispersion)

                st.markdown("##### 🎯 Proposed Internal Control Limits")
                comp_df = pd.DataFrame({
                    "Loại giới hạn": ["Khách hàng (Spec)", "Nội bộ hiện tại (File)", "Đề xuất tối ưu (±3σ Std)", "Đề xuất tối ưu (±3σ IQR)"],
                    "LSL": [cust_lsl, int_lsl, round(mu - 3*sigma, 1), round(mu - 3*sigma_iqr, 1)],
                    "USL": [cust_usl, int_usl, round(mu + 3*sigma, 1), round(mu + 3*sigma_iqr, 1)]
                })
                st.table(comp_df)
                
                st.markdown("---")

                # --- PHẦN 2: BIỂU ĐỒ I-MR (NẰM DƯỚI) ---
                st.markdown("##### 📈 I-MR Charts")
                mr = plot_data.diff().abs()
                mr_ucl = mr.mean() * 3.267
                fig_imr, (ax_i, ax_mr) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
                
                ax_i.plot(plot_data, marker="o", color="#1f77b4", markersize=5)
                ax_i.axhline(ucl_3s, color="red", ls="--", label="UCL (Std)")
                ax_i.axhline(lcl_3s, color="red", ls="--", label="LCL (Std)")
                ax_i.axhline(mu, color="green", ls="-", label="Mean")
                ax_i.set_title("Individual Chart (I)", weight="bold")
                ax_i.legend(loc="upper left", bbox_to_anchor=(1, 1)); apply_full_border(ax_i)
                
                ax_mr.plot(mr, marker="o", color="#ff7f0e", markersize=5)
                ax_mr.axhline(mr_ucl, color="red", ls="--", label="MR UCL")
                ax_mr.axhline(mr.mean(), color="green", ls="-", label="Avg MR")
                ax_mr.set_title("Moving Range Chart (MR)", weight="bold")
                ax_mr.legend(loc="upper left", bbox_to_anchor=(1, 1)); apply_full_border(ax_mr)
                
                plt.tight_layout(); st.pyplot(fig_imr)

    except Exception as e:
        st.error(f"Lỗi: {e}")
else:
    st.info("👈 Mandy hãy tải file lên để bắt đầu phân tích thống kê.")
