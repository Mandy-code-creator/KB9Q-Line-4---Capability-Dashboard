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

def format_num(val):
    if val is None or pd.isna(val): return "-"
    rounded = round(float(val), 1)
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
            n, mu = len(plot_data), plot_data.mean()
            sigma_fixed = plot_data.std(ddof=1)
            data_max = plot_data.max()
            data_min = plot_data.min()

            st.title(f"📊 Quality Analytics: {selected_label}")

            # ==========================================
            # VIEW 1: PROCESS ANALYTICS
            # ==========================================
            if view_mode == "Process Analytics":
                tab_trend, tab_dist = st.tabs(["📈 Trend Analysis", "📊 Distribution & SPC"])
                ucl_v1, lcl_v1 = mu + 3*sigma_fixed, mu - 3*sigma_fixed

                with tab_trend:
                    fig_t, ax_t = plt.subplots(figsize=(12, 6))
                    ax_t.plot(np.arange(1, n+1), plot_data, marker="o", markersize=6, color="#1f77b4", label="Actual Value")
                    ax_t.axhline(mu, color="blue", ls="-", lw=2, label=f"Mean: {mu:.1f}")
                    if cust_lsl: ax_t.axhline(cust_lsl, color="green", ls="-", lw=3, label=f"Cust LSL: {cust_lsl:.1f}")
                    if cust_usl: ax_t.axhline(cust_usl, color="green", ls="-", lw=3, label=f"Cust USL: {cust_usl:.1f}")
                    if int_lsl: ax_t.axhline(int_lsl, color="red", ls="--", lw=3, label=f"Int LSL: {int_lsl:.1f}")
                    if int_usl: ax_t.axhline(int_usl, color="red", ls="--", lw=3, label=f"Int USL: {int_usl:.1f}")
                    ax_t.axhline(ucl_v1, color="#ff7f0e", ls=":", lw=3, label="3σ UCL")
                    ax_t.axhline(lcl_v1, color="#ff7f0e", ls=":", lw=3, label="3σ LCL")
                    
                    ax_t.set_xlabel("Coil Sequence", weight="bold")
                    ax_t.set_ylabel(f"{selected_label} Value", weight="bold")
                    ax_t.set_title(f"{selected_label} Trend Analysis (N={n})", pad=20)
                    ax_t.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4, fontsize=9)
                    apply_full_border(ax_t); plt.tight_layout(); st.pyplot(fig_t)

                with tab_dist:
                    fig_d, ax_d = plt.subplots(figsize=(12, 6))
                    counts, bins, patches = ax_d.hist(plot_data, bins=20, density=False, alpha=0.4, color="#7FB3D5", edgecolor="black")
                    
                    ax_d.yaxis.set_major_locator(MaxNLocator(integer=True))
                    ax_d.set_xlabel(f"{selected_label} Value", weight="bold")
                    ax_d.set_ylabel("Coil Count", weight="bold")
                    
                    ax_pdf = ax_d.twinx()
                    x_min_fit = min(plot_data.min(), mu - 4 * sigma_fixed)
                    x_max_fit = max(plot_data.max(), mu + 4 * sigma_fixed)
                    pad_x = (x_max_fit - x_min_fit) * 0.05
                    xs = np.linspace(x_min_fit - pad_x, x_max_fit + pad_x, 500)
                    
                    ax_pdf.plot(xs, norm.pdf(xs, mu, sigma_fixed), color="#1E3A8A", lw=3, label="Normal Fit")
                    ax_pdf.set_yticks([])
                    
                    def add_vline_std(ax, val, color, ls, label, level=0):
                        if val is not None:
                            ax.axvline(val, color=color, linestyle=ls, linewidth=3, label=label)
                            trans = ax.get_xaxis_transform()
                            y_pos = 1.02 + (level * 0.05) 
                            ax.text(val, y_pos, f"{val:.1f}", color=color, ha='center', va='bottom', transform=trans, fontweight='bold')

                    add_vline_std(ax_d, mu, "blue", "-", "Mean", level=0)
                    add_vline_std(ax_d, cust_lsl, "green", "-", "Cust LSL", level=0)
                    add_vline_std(ax_d, cust_usl, "green", "-", "Cust USL", level=0)
                    add_vline_std(ax_d, int_lsl, "red", "--", "Int LSL", level=1)
                    add_vline_std(ax_d, int_usl, "red", "--", "Int USL", level=1)
                    add_vline_std(ax_d, ucl_v1, "#ff7f0e", ":", "3σ UCL", level=2)
                    add_vline_std(ax_d, lcl_v1, "#ff7f0e", ":", "3σ LCL", level=2)
                    
                    ax_d.set_title(f"{selected_label} Distribution (N={n})", pad=55)
                    ax_d.legend(loc="upper left", bbox_to_anchor=(1, 1))
                    apply_full_border(ax_d); plt.tight_layout(); st.pyplot(fig_d)

            # ==========================================
            # VIEW 2: SPC & OPTIMIZATION
            # ==========================================
            else:
                st.subheader("II. Control Limit Optimization & I-MR")
                
                st.markdown("##### ⚙️ Parameters")
                c_i1, c_i2 = st.columns(2)
                with c_i1:
                    k_std = st.number_input("Target Multiplier for StdDev (Sigma):", 1.0, 6.0, 3.0, 0.1)
                with c_i2:
                    k_iqr = st.number_input("Target Multiplier for IQR (k-factor):", 1.0, 6.0, 3.0, 0.1)
                
                q1, q3 = plot_data.quantile(0.25), plot_data.quantile(0.75)
                s_iqr = (q3 - q1) / 1.349

                st.markdown("##### 🎯 Comparative Analysis")
                col_res1, col_res2 = st.columns(2)
                
                with col_res1:
                    st.write("**Method: Standard Deviation**")
                    st.table(pd.DataFrame({
                        "Metric": ["N (Sample Size)", "Max", "Min", "Mean", "Sigma (σ)", "LSL", "USL"],
                        "Value": [str(n), format_num(data_max), format_num(data_min), format_num(mu), format_num(sigma_fixed), format_num(mu - k_std*sigma_fixed), format_num(mu + k_std*sigma_fixed)],
                        "Formula": ["Count", "Maximum", "Minimum", "Sum/N", "StdDev", f"Mean-({k_std}*σ)", f"Mean+({k_std}*σ)"]
                    }))
                    
                with col_res2:
                    st.write("**Method: IQR (Robust)**")
                    st.table(pd.DataFrame({
                        "Metric": ["N (Sample Size)", "Max", "Min", "Mean", "Sigma_iqr", "LSL", "USL"],
                        "Value": [str(n), format_num(data_max), format_num(data_min), format_num(mu), format_num(s_iqr), format_num(mu - k_iqr*s_iqr), format_num(mu + k_iqr*s_iqr)],
                        "Formula": ["Count", "Maximum", "Minimum", "Sum/N", "IQR/1.349", f"Mean-({k_iqr}*σ_i)", f"Mean+({k_iqr}*σ_i)"]
                    }))

                st.markdown("---")
                fig_imr, ax_i = plt.subplots(figsize=(12, 6))
                ax_i.plot(plot_data, marker="o", color="#1f77b4", label="Actual Data", alpha=0.7)
                ax_i.axhline(mu, color="blue", ls="-", lw=2, label=f"Mean: {mu:.1f}")
                
                if cust_lsl: ax_i.axhline(cust_lsl, color="green", ls="-", lw=2.5, label=f"Cust LSL: {cust_lsl:.1f}")
                if cust_usl: ax_i.axhline(cust_usl, color="green", ls="-", lw=2.5, label=f"Cust USL: {cust_usl:.1f}")
                
                if int_lsl: ax_i.axhline(int_lsl, color="red", ls="--", label="Current Int LSL")
                if int_usl: ax_i.axhline(int_usl, color="red", ls="--", label="Current Int USL")
                
                ax_i.axhline(mu + k_std*sigma_fixed, color="darkred", ls="-", lw=2, label=f"Proposed USL (StdDev {k_std}σ)")
                ax_i.axhline(mu - k_std*sigma_fixed, color="darkred", ls="-", lw=2, label=f"Proposed LSL (StdDev {k_std}σ)")
                ax_i.axhline(mu + k_iqr*s_iqr, color="darkorange", ls="--", lw=2, label=f"Proposed USL (IQR {k_iqr}σ)")
                ax_i.axhline(mu - k_iqr*s_iqr, color="darkorange", ls="--", lw=2, label=f"Proposed LSL (IQR {k_iqr}σ)")
                
                ax_i.set_xlabel("Coil Sequence", weight="bold")
                ax_i.set_ylabel(f"{selected_label} Value", weight="bold")
                ax_i.set_title(f"I-Chart: Optimization Comparison (N={n})", weight="bold")
                ax_i.legend(loc="upper left", bbox_to_anchor=(1, 1))
                apply_full_border(ax_i); plt.tight_layout(); st.pyplot(fig_imr)

    except Exception as e:
        st.error(f"System Error: {e}")
else:
    st.info("👈 Please upload the production report to start.")
