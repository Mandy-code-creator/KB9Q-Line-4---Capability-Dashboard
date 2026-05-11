import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import re
from scipy.stats import norm

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Line 4 Quality Analytics", layout="wide")

plt.rcParams.update({
    'font.size': 12, 'axes.labelweight': 'bold', 'axes.titleweight': 'bold',
    'axes.titlesize': 15, 'legend.fontsize': 10, 'font.weight': 'bold', 'lines.linewidth': 2.5
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
        spine.set_linewidth(2.5); spine.set_color('black'); spine.set_visible(True)

def format_num(val):
    if val is None or pd.isna(val): return "-"
    rounded = round(float(val), 2)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)

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

        view_mode = st.sidebar.radio("View Mode:", ["Process Analytics", "SPC Control Charts (I-MR)", "Executive Summary"])
        
        if view_mode != "Executive Summary":
            selected_label = st.sidebar.selectbox("Select Parameter:", available)
            short_key = metrics_map[selected_label]; data_col = find_data_col(df, short_key)
            zh_map = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}
            zh_key = zh_map.get(short_key, short_key)
            
            int_lsl = get_limit(df, zh_key, "min", "管制")
            int_usl = get_limit(df, zh_key, "max", "管制")
            cust_lsl = get_limit(df, zh_key, "min", "客戶要求")
            cust_usl = get_limit(df, zh_key, "max", "客戶要求")

            if data_col:
                plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
                n, mu, sigma_fixed = len(plot_data), plot_data.mean(), plot_data.std(ddof=1)
                data_max, data_min = plot_data.max(), plot_data.min()

                st.title(f"📊 Quality Analytics: {selected_label}")

                # VIEW 1: PROCESS ANALYTICS (Giữ nguyên logic Mandy đã duyệt)
                if view_mode == "Process Analytics":
                    tab_trend, tab_dist = st.tabs(["📈 Trend Analysis", "📊 Distribution & SPC"])
                    ucl_v1, lcl_v1 = mu + 3*sigma_fixed, mu - 3*sigma_fixed
                    with tab_trend:
                        fig_t, ax_t = plt.subplots(figsize=(12, 6))
                        ax_t.plot(np.arange(1, n+1), plot_data, marker="o", color="#1f77b4", label="Actual Value")
                        ax_t.axhline(mu, color="blue", label=f"Mean: {mu:.1f}")
                        if int_lsl: ax_t.axhline(int_lsl, color="red", ls="--", label="Int LSL")
                        if int_usl: ax_t.axhline(int_usl, color="red", ls="--", label="Int USL")
                        ax_t.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4)
                        apply_full_border(ax_t); plt.tight_layout(); st.pyplot(fig_t)
                    with tab_dist:
                        fig_d, ax_d = plt.subplots(figsize=(12, 6))
                        ax_d.hist(plot_data, bins=20, alpha=0.4, color="#7FB3D5", edgecolor="black")
                        ax_d.yaxis.set_major_locator(MaxNLocator(integer=True))
                        ax_pdf = ax_d.twinx()
                        x_min_f, x_max_f = min(plot_data.min(), mu - 4*sigma_fixed), max(plot_data.max(), mu + 4*sigma_fixed)
                        xs = np.linspace(x_min_f, x_max_f, 500)
                        ax_pdf.plot(xs, norm.pdf(xs, mu, sigma_fixed), color="#1E3A8A", lw=3)
                        ax_pdf.set_yticks([])
                        def add_v(ax, val, color, ls, level=0):
                            if val is not None:
                                ax.axvline(val, color=color, linestyle=ls, lw=3)
                                t = ax.get_xaxis_transform(); y = 1.02 + (level * 0.05)
                                ax.text(val, y, f"{val:.1f}", color=color, ha='center', transform=t, fontweight='bold')
                        add_v(ax_d, mu, "blue", "-", 0)
                        add_v(ax_d, int_lsl, "red", "--", 1); add_v(ax_d, int_usl, "red", "--", 1)
                        ax_d.set_title(f"{selected_label} Distribution (N={n})", pad=55)
                        apply_full_border(ax_d); plt.tight_layout(); st.pyplot(fig_d)

                # VIEW 2: SPC OPTIMIZATION (Giữ nguyên logic Mandy đã duyệt)
                elif view_mode == "SPC Control Charts (I-MR)":
                    st.subheader("II. Control Limit Optimization & I-MR")
                    c1, c2 = st.columns(2)
                    with c1: k_std = st.number_input("Target Multiplier for StdDev (Sigma):", 1.0, 6.0, 3.0, 0.1)
                    with c2: k_iqr = st.number_input("Target Multiplier for IQR (k-factor):", 1.0, 6.0, 3.0, 0.1)
                    q1, q3 = plot_data.quantile(0.25), plot_data.quantile(0.75); s_iqr = (q3 - q1) / 1.349
                    fig_imr, ax_i = plt.subplots(figsize=(12, 6))
                    ax_i.plot(plot_data, marker="o", color="#1f77b4", alpha=0.7)
                    if int_lsl: ax_i.axhline(int_lsl, color="red", ls="--", label="Current Int LSL")
                    if int_usl: ax_i.axhline(int_usl, color="red", ls="--", label="Current Int USL")
                    ax_i.axhline(mu + k_std*sigma_fixed, color="darkred", label="Prop USL (StdDev)")
                    ax_i.axhline(mu + k_iqr*s_iqr, color="darkorange", ls="--", label="Prop USL (IQR)")
                    ax_i.legend(loc="upper left", bbox_to_anchor=(1, 1))
                    apply_full_border(ax_i); plt.tight_layout(); st.pyplot(fig_imr)

        # VIEW 3: EXECUTIVE SUMMARY (CẬP NHẬT ĐIỀU KIỆN MỚI CỦA MANDY)
        elif view_mode == "Executive Summary":
            st.title("📑 Executive Quality Summary")
            summary_data = []
            zh_sum_map = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "Hardness": "硬度", "YPE": "YPE"}
            
            for label in available:
                short_key = metrics_map[label]; data_col = find_data_col(df, short_key)
                zh_key = zh_sum_map.get(short_key, short_key)
                if data_col:
                    p_data = pd.to_numeric(df[data_col], errors='coerce').dropna()
                    if len(p_data) == 0: continue
                    mu_v, sig_v = p_data.mean(), p_data.std(ddof=1)
                    i_lsl = get_limit(df, zh_key, "min", "管制")
                    i_usl = get_limit(df, zh_key, "max", "管制")
                    
                    cp, ca, cpk, formula, status = "-", "-", "-", "-", "N/A"
                    cpk_val = None
                    if sig_v > 0:
                        if i_usl is not None and i_lsl is not None:
                            cp_v = (i_usl - i_lsl) / (6 * sig_v)
                            cnt, half = (i_usl + i_lsl) / 2, (i_usl - i_lsl) / 2
                            ca_v = (mu_v - cnt) / half
                            cpk_val = cp_v * (1 - abs(ca_v))
                            cp, ca, cpk, formula = format_num(cp_v), f"{ca_v*100:.1f}%", format_num(cpk_val), "Cp*(1-|Ca|)"
                        elif i_usl is not None:
                            cpk_val = (i_usl - mu_v) / (3 * sig_v); cpk, formula = format_num(cpk_val), "Cpu"
                        elif i_lsl is not None:
                            cpk_val = (mu_v - i_lsl) / (3 * sig_v); cpk, formula = format_num(cpk_val), "Cpl"
                            
                        if cpk_val is not None:
                            # THÊM ĐIỀU KIỆN CỦA MANDY: Cảnh báo khi chất lượng quá dư thừa
                            if cpk_val < 1.0: status = "🔴 Action Required"
                            elif 1.0 <= cpk_val < 1.33: status = "🟡 Acceptable"
                            elif 1.33 <= cpk_val <= 2.0: status = "🟢 Excellent"
                            else: status = "🔵 Over-engineered (>2.0)"
                    
                    summary_data.append({"Parameter": label, "N": len(p_data), "Mean": format_num(mu_v), "StdDev (σ)": format_num(sig_v),
                                       "Int LSL": format_num(i_lsl), "Int USL": format_num(i_usl), "Cp": cp, "Ca": ca, "Cpk": cpk, 
                                       "Cpk Formula": formula, "Status": status})
            
            st.dataframe(pd.DataFrame(summary_data), hide_index=True, use_container_width=True)
            st.info("💡 **Tip:** Blue status (Over-engineered) suggests potential for cost optimization or process speed increase.")

    except Exception as e:
        st.error(f"System Error: {e}")
else:
    st.info("👈 Please upload the production report to start.")
