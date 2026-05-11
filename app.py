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

            st.title(f"📊 Quality Analytics: {selected_label}")

            # ==========================================
            # VIEW 1: PROCESS ANALYTICS (FULL STATIC)
            # ==========================================
            if view_mode == "Process Analytics":
                tab_trend, tab_dist = st.tabs(["📈 Trend Analysis", "📊 Distribution & SPC"])
                ucl_v1, lcl_v1 = mu + 3*sigma_fixed, mu - 3*sigma_fixed

                with tab_trend:
                    fig_t, ax_t = plt.subplots(figsize=(12, 6))
                    ax_t.plot(np.arange(1, n+1), plot_data, marker="o", markersize=6, color="#1f77b4", label="Actual Value")
                    # Thêm đường Mean vào Trend
                    ax_t.axhline(mu, color="purple", ls="--", lw=2, label=f"Mean: {mu:.1f}")
                    
                    if cust_lsl: ax_t.axhline(cust_lsl, color="green", ls="-", lw=3, label=f"Cust LSL: {cust_lsl:.1f}")
                    if cust_usl: ax_t.axhline(cust_usl, color="green", ls="-", lw=3, label=f"Cust USL: {cust_usl:.1f}")
                    if int_lsl: ax_t.axhline(int_lsl, color="red", ls="--", lw=3, label=f"Int LSL: {int_lsl:.1f}")
                    if int_usl: ax_t.axhline(int_usl, color="red", ls="--", lw=3, label=f"Int USL: {int_usl:.1f}")
                    ax_t.axhline(ucl_v1, color="#ff7f0e", ls=":", lw=3, label="3σ UCL")
                    ax_t.axhline(lcl_v1, color="#ff7f0e", ls=":", lw=3, label="3σ LCL")
                    
                    ax_t.set_title(f"{selected_label} Trend Analysis", pad=20)
                    ax_t.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4, fontsize=9)
                    apply_full_border(ax_t); plt.tight_layout(); st.pyplot(fig_t)

                with tab_dist:
                    fig_d, ax_d = plt.subplots(figsize=(12, 6))
                    ax_d.hist(plot_data, bins=20, density=True, alpha=0.4, color="#7FB3D5", edgecolor="black")
                    xs = np.linspace(plot_data.min()*0.9, plot_data.max()*1.1, 500)
                    ax_d.plot(xs, norm.pdf(xs, mu, sigma_fixed), color="#1E3A8A", lw=3, label="Normal Fit")
                    
                    def add_vline_stepped(ax, val, color, ls, label, level=1):
                        if val is not None:
                            ax.axvline(val, color=color, linestyle=ls, linewidth=3, label=label)
                            y_max = ax.get_ylim()[1]
                            # Phân tầng cao độ để không bị ghi đè nhãn số
                            y_pos = y_max * (1 + (level * 0.07)) 
                            ax.text(val, y_pos, f"{val:.1f}", color=color, ha='center', va='bottom', fontweight='bold')

                    # Level 0 cho Mean (Dời lên cao nhất hoặc riêng biệt)
                    add_vline_stepped(ax_d, mu, "blue", "-", "Mean", 0)
                    add_vline_stepped(ax_d, cust_lsl, "green", "-", "Cust LSL", 1)
                    add_vline_stepped(ax_d, cust_usl, "green", "-", "Cust USL", 1)
                    add_vline_stepped(ax_d, int_lsl, "red", "--", "Int LSL", 2)
                    add_vline_stepped(ax_d, int_usl, "red", "--", "Int USL", 2)
                    add_vline_stepped(ax_d, ucl_v1, "#ff7f0e", ":", "3σ UCL", 3)
                    add_vline_stepped(ax_d, lcl_v1, "#ff7f0e", ":", "3σ LCL", 3)

                    ax_d.set_title(f"{selected_label} Distribution & Capability", pad=80)
                    ax_d.legend(loc="upper left", bbox_to_anchor=(1, 1))
                    apply_full_border(ax_d); plt.tight_layout(); st.pyplot(fig_d)

            # ==========================================
            # VIEW 2: SPC & LIMIT OPTIMIZATION
            # ==========================================
            else:
                st.subheader("II. Control Limit Optimization & I-MR")
                
                st.markdown("##### ⚙️ Parameters")
                c_i1, c_i2 = st.columns(2)
                with c_i1:
                    k_val = st.number_input("Target k-factor:", 1.0, 6.0, 3.0, 0.1)
                with c_i2:
                    m_sigma = st.number_input("Target Sigma (0=auto):", 0.0, 100.0, 0.0, 0.1)
                
                s_std = sigma_fixed
                q1, q3 = plot_data.quantile(0.25), plot_data.quantile(0.75)
                s_iqr = (q3 - q1) / 1.349
                s_used = s_std if m_sigma == 0 else m_sigma

                st.markdown("##### 🎯 Calculation Steps")
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    st.write("**Method: Standard Deviation**")
                    st.table(pd.DataFrame({
                        "Metric": ["Mean", "Sigma (σ)", "LSL", "USL"],
                        "Value": [format_num(mu), format_num(s_std), format_num(mu - k_val*s_std), format_num(mu + k_val*s_std)],
                        "Calculation": ["Avg", "StdDev", f"Mean-({k_val}*σ)", f"Mean+({k_val}*σ)"]
                    }))
                with col_t2:
                    st.write("**Method: IQR (Robust)**")
                    st.table(pd.DataFrame({
                        "Metric": ["Mean", "Sigma_iqr", "LSL", "USL"],
                        "Value": [format_num(mu), format_num(s_iqr), format_num(mu - k_val*s_iqr), format_num(mu + k_val*s_iqr)],
                        "Calculation": ["Avg", "IQR/1.349", f"Mean-({k_val}*σ_i)", f"Mean+({k_val}*σ_i)"]
                    }))

                st.markdown("---")
                fig_imr, ax_i = plt.subplots(figsize=(12, 6))
                ax_i.plot(plot_data, marker="o", color="#1f77b4", label="Actual Data", alpha=0.7)
                # Thêm đường Mean vào Trend của View 2
                ax_i.axhline(mu, color="purple", ls="--", lw=2, label=f"Mean: {mu:.1f}")
                
                if int_lsl: ax_i.axhline(int_lsl, color="red", ls="--", label="Current LSL (File)")
                if int_usl: ax_i.axhline(int_usl, color="red", ls="--", label="Current USL (File)")
                ax_i.axhline(mu + k_val*s_used, color="darkred", ls="-", lw=2, label=f"Proposed USL ({k_val}σ)")
                ax_i.axhline(mu - k_val*s_used, color="darkred", ls="-", lw=2, label=f"Proposed LSL ({k_val}σ)")
                
                ax_i.set_title("I-Chart: Optimization Comparison", weight="bold")
                ax_i.legend(loc="upper left", bbox_to_anchor=(1, 1))
                apply_full_border(ax_i); plt.tight_layout(); st.pyplot(fig_imr)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Please upload data to start.")
