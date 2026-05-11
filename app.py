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

# Thiết lập font in đậm và to toàn cục cho biểu đồ
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
    """Ép khung viền đen đậm kín 4 cạnh"""
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
        if not available:
            st.error("❌ Không tìm thấy cột dữ liệu phù hợp.")
            st.stop()

        selected_label = st.sidebar.selectbox("Select Parameter:", available)
        view_mode = st.sidebar.radio("View Mode:", ["Process Analytics", "SPC Control Charts (I-MR)"])
        
        short_key = metrics_map[selected_label]
        data_col = find_data_col(df, short_key)
        zh_map = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}
        zh_key = zh_map.get(short_key, short_key)
        
        # Lấy các tầng giới hạn
        int_lsl = get_limit(df, zh_key, "min", "管制")
        int_usl = get_limit(df, zh_key, "max", "管制")
        cust_lsl = get_limit(df, zh_key, "min", "客戶要求")
        cust_usl = get_limit(df, zh_key, "max", "客戶要求")

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            n = len(plot_data)
            mu, sigma = plot_data.mean(), plot_data.std(ddof=1)
            ucl_3s, lcl_3s = mu + 3*sigma, mu - 3*sigma

            st.title(f"📊 Quality Analytics: {selected_label}")

            if view_mode == "Process Analytics":
                tab_trend, tab_dist = st.tabs(["📈 Trend Analysis", "📊 Distribution & SPC"])

                with tab_trend:
                    x_idx = np.arange(1, n + 1)
                    fig_t, ax_t = plt.subplots(figsize=(12, 6))
                    ax_t.plot(x_idx, plot_data, marker="o", markersize=6, label="Actual Value", color="#1f77b4", zorder=1)
                    
                    # Highlight điểm vượt giới hạn NỘI BỘ
                    out_mask = pd.Series([False] * n)
                    if int_usl: out_mask |= (plot_data > int_usl)
                    if int_lsl: out_mask |= (plot_data < int_lsl)
                    if out_mask.any():
                        ax_t.scatter(x_idx[out_mask], plot_data[out_mask], color='red', s=120, 
                                    label="Out of Internal Spec", edgecolor='black', linewidth=1.5, zorder=3)

                    # Vẽ đường giới hạn Trend
                    if cust_lsl: ax_t.axhline(cust_lsl, color="green", linestyle="-", linewidth=3, label=f"Cust LSL: {cust_lsl:.1f}")
                    if cust_usl: ax_t.axhline(cust_usl, color="green", linestyle="-", linewidth=3, label=f"Cust USL: {cust_usl:.1f}")
                    if int_lsl: ax_t.axhline(int_lsl, color="red", linestyle="--", linewidth=3, label=f"Int LSL: {int_lsl:.1f}")
                    if int_usl: ax_t.axhline(int_usl, color="red", linestyle="--", linewidth=3, label=f"Int USL: {int_usl:.1f}")
                    ax_t.axhline(ucl_3s, color="#ff7f0e", linestyle=":", linewidth=3, label=f"3σ UCL: {ucl_3s:.1f}")
                    ax_t.axhline(lcl_3s, color="#ff7f0e", linestyle=":", linewidth=3, label=f"3σ LCL: {lcl_3s:.1f}")
                    ax_t.axhline(mu, color="purple", linestyle="-.", linewidth=2, label=f"Mean: {mu:.1f}")

                    ax_t.set_title(f"{selected_label} Trend Analysis", pad=20)
                    ax_t.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), frameon=True, ncol=3, fontsize=9)
                    apply_full_border(ax_t)
                    plt.tight_layout()
                    st.pyplot(fig_t)

                with tab_dist:
                    # Tính SPC dựa trên Giới hạn NỘI BỘ
                    cp, ca, cpk = 0.0, 0.0, 0.0
                    if sigma > 0 and int_usl and int_lsl:
                        cp = (int_usl - int_lsl) / (6 * sigma)
                        ca = ((mu - (int_usl + int_lsl) / 2) / ((int_usl - int_lsl) / 2)) * 100
                        cpu = (int_usl - mu) / (3 * sigma)
                        cpl = (mu - int_lsl) / (3 * sigma)
                        cpk = min(cpu, cpl)

                    fig_d, ax_d = plt.subplots(figsize=(12, 6))
                    ax_d.hist(plot_data, bins=20, density=True, alpha=0.5, color="#7FB3D5", edgecolor="black")
                    xs = np.linspace(plot_data.min()*0.9, plot_data.max()*1.1, 500)
                    ax_d.plot(xs, norm.pdf(xs, mu, sigma), color="#1E3A8A", linewidth=3, label="Normal Fit")
                    
                    # Hàm hiển thị vline kèm giá trị số
                    def add_vline_with_value(ax, val, color, ls, label):
                        if val:
                            ax.axvline(val, color=color, linestyle=ls, linewidth=3, label=label)
                            ax.text(val, ax.get_ylim()[1] * 1.01, f"{val:.1f}", 
                                    color=color, ha='center', va='bottom', fontsize=11, fontweight='bold')

                    add_vline_with_value(ax_d, cust_lsl, "green", "-", "Cust LSL")
                    add_vline_with_value(ax_d, cust_usl, "green", "-", "Cust USL")
                    add_vline_with_value(ax_d, int_lsl, "red", "--", "Int LSL")
                    add_vline_with_value(ax_d, int_usl, "red", "--", "Int USL")
                    add_vline_with_value(ax_d, ucl_3s, "#ff7f0e", ":", "3σ UCL")
                    add_vline_with_value(ax_d, lcl_3s, "#ff7f0e", ":", "3σ LCL")

                    ax_d.set_title(f"{selected_label} Distribution & Capability", pad=35)
                    ax_d.legend(loc="upper left", bbox_to_anchor=(1, 1))
                    apply_full_border(ax_d)
                    plt.tight_layout()
                    st.pyplot(fig_d)

                    # Bảng SPC Rating
                    rating = "Excellent" if cpk >= 1.33 else ("Good" if cpk >= 1.0 else "Poor")
                    color_code = "green" if cpk >= 1.33 else ("orange" if cpk >= 1.0 else "red")
                    df_spc = pd.DataFrame([{"N": n, "Mean": mu, "Std": sigma, "Cp": cp, "Ca (%)": ca, "Cpk": cpk, "Rating": rating}])
                    st.dataframe(df_spc.style.format("{:.3f}", subset=["Mean", "Std", "Cp", "Ca (%)", "Cpk"])
                                 .map(lambda v: f'color: {color_code}; font-weight: bold', subset=['Rating']), 
                                 hide_index=True, use_container_width=True)

            else:
                st.subheader("III. Statistical Process Control (I-MR)")
                mr = plot_data.diff().abs()
                mr_ucl = mr.mean() * 3.267
                fig_imr, (ax_i, ax_mr) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
                ax_i.plot(plot_data, marker="o", color="#1f77b4")
                ax_i.axhline(ucl_3s, color="red", linestyle="--", label="UCL")
                ax_i.axhline(lcl_3s, color="red", linestyle="--", label="LCL")
                ax_i.axhline(mu, color="green", linestyle="-", label="Mean")
                ax_i.set_title("Individual Chart (I)")
                ax_i.legend(loc="right")
                apply_full_border(ax_i)
                ax_mr.plot(mr, marker="o", color="#ff7f0e")
                ax_mr.axhline(mr_ucl, color="red", linestyle="--", label="MR UCL")
                ax_mr.axhline(mr.mean(), color="green", linestyle="-", label="Avg MR")
                ax_mr.set_title("Moving Range Chart (MR)")
                ax_mr.legend(loc="right")
                apply_full_border(ax_mr)
                plt.tight_layout()
                st.pyplot(fig_imr)

    except Exception as e:
        st.error(f"Lỗi: {e}")
else:
    st.info("👈 Vui lòng upload file để bắt đầu.")
