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

# Thiết lập font in đậm và to hơn cho Matplotlib toàn cục
plt.rcParams.update({
    'font.size': 12,
    'axes.labelweight': 'bold',
    'axes.titleweight': 'bold',
    'axes.titlesize': 14,
    'legend.fontsize': 10
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

# ==========================================
# 3. SIDEBAR & DATA PROCESSING
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
        
        # Lấy giới hạn
        lo = get_limit(df, zh_key, "min", "管制")  # Std LSL
        hi = get_limit(df, zh_key, "max", "管制")  # Std USL
        TARGET_MIN = get_limit(df, zh_key, "min", "客戶要求")
        TARGET_MAX = get_limit(df, zh_key, "max", "客戶要求")

        # Đảm bảo có giá trị để vẽ
        lo = lo if lo is not None else 0
        hi = hi if hi is not None else 100
        TARGET_MIN = TARGET_MIN if TARGET_MIN is not None else lo
        TARGET_MAX = TARGET_MAX if TARGET_MAX is not None else hi

        if data_col:
            plot_data = pd.to_numeric(df[data_col], errors='coerce').dropna().reset_index(drop=True)
            
            st.title(f"📊 Quality Analytics: {selected_label}")

            if view_mode == "Process Analytics":
                tab_trend, tab_dist = st.tabs(["📈 Trend Analysis", "📊 Distribution & SPC"])

                with tab_trend:
                    x_idx = np.arange(1, len(plot_data) + 1)
                    fig, ax = plt.subplots(figsize=(12, 6))
                    
                    # Vẽ đường dữ liệu chính
                    ax.plot(x_idx, plot_data, marker="s", linewidth=2.5, label=f"{selected_label} LINE", color="#1f77b4", alpha=0.9)
                    
                    # Vẽ các đường giới hạn
                    ax.axhline(lo, linestyle="--", linewidth=2.5, color="red", label=f"Std LSL={lo:.1f}")
                    ax.axhline(hi, linestyle="--", linewidth=2.5, color="red", label=f"Std USL={hi:.1f}")
                    ax.axhline(TARGET_MIN, linestyle=":", linewidth=2.5, color="green", label=f"Target LSL={TARGET_MIN:.1f}")
                    ax.axhline(TARGET_MAX, linestyle=":", linewidth=2.5, color="green", label=f"Target USL={TARGET_MAX:.1f}")
                    
                    # Tô màu vùng mục tiêu
                    ax.fill_between(x_idx, TARGET_MIN, TARGET_MAX, color="green", alpha=0.1, label="Target Zone")
                    
                    ax.set_title(f"{selected_label} Trend Analysis", weight="bold", pad=20)
                    ax.set_xlabel("Coil Sequence")
                    ax.set_ylabel("Measurement Value")
                    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), frameon=True, ncol=3)
                    
                    # Khung viền đen hoàn chỉnh
                    for spine in ax.spines.values():
                        spine.set_linewidth(2)
                        spine.set_color('black')
                    
                    plt.tight_layout()
                    st.pyplot(fig)

                with tab_dist:
                    if len(plot_data) < 5:
                        st.warning("⚠️ At least 5 coils are required for distribution analysis.")
                    else:
                        mean_val, std_val = plot_data.mean(), plot_data.std(ddof=1)
                        
                        # Tính toán SPC (Cp, Ca, Cpk)
                        cp = (hi - lo) / (6 * std_val) if std_val > 0 else 0
                        ca = ((mean_val - (hi + lo) / 2) / ((hi - lo) / 2)) * 100 if hi != lo else 0
                        cpu, cpl = (hi - mean_val) / (3 * std_val), (mean_val - lo) / (3 * std_val)
                        cpk = min(cpu, cpl)
                        
                        # Chuẩn bị vùng vẽ
                        all_vals = [plot_data.min(), plot_data.max(), lo, hi, TARGET_MIN, TARGET_MAX]
                        x_min, x_max = min(all_vals) - abs(min(all_vals)*0.05), max(all_vals) + abs(max(all_vals)*0.05)
                        
                        fig_dist, ax_dist = plt.subplots(figsize=(12, 6))
                        
                        # Vẽ Histogram
                        ax_dist.hist(plot_data, bins=20, density=True, alpha=0.6, color="#ff7f0e", edgecolor="white", label="Actual Hist")
                        
                        # Vẽ đường cong Normal Fit
                        if std_val > 0:
                            xs = np.linspace(x_min, x_max, 400)
                            ax_dist.plot(xs, norm.pdf(xs, mean_val, std_val), linewidth=3, color="#b25e00", label="Normal Fit")
                        
                        # V-Lines
                        ax_dist.axvline(lo, linestyle="--", linewidth=2.5, color="red", label=f"Std LSL ({lo:.1f})")
                        ax_dist.axvline(hi, linestyle="--", linewidth=2.5, color="red", label=f"Std USL ({hi:.1f})")
                        ax_dist.axvline(TARGET_MIN, linestyle=":", linewidth=2.5, color="green", label=f"Target LSL ({TARGET_MIN:.1f})")
                        ax_dist.axvline(TARGET_MAX, linestyle=":", linewidth=2.5, color="green", label=f"Target USL ({TARGET_MAX:.1f})")
                        ax_dist.axvspan(TARGET_MIN, TARGET_MAX, color="green", alpha=0.1)

                        ax_dist.set_xlim(x_min, x_max)
                        ax_dist.set_title(f"{selected_label} Distribution & Capability", weight="bold", pad=20)
                        ax_dist.legend(loc="upper right")
                        ax_dist.grid(axis='y', alpha=0.3)
                        
                        # Khung viền đen hoàn chỉnh
                        for spine in ax_dist.spines.values():
                            spine.set_linewidth(2)
                            spine.set_color('black')
                            
                        st.pyplot(fig_dist)

                        # Bảng thống kê SPC
                        eval_msg = "Excellent" if cpk >= 1.33 else ("Good" if cpk >= 1.0 else "Poor")
                        color_code = "green" if cpk >= 1.33 else ("orange" if cpk >= 1.0 else "red")
                        
                        df_spc = pd.DataFrame([{
                            "N": len(plot_data), 
                            "Mean": mean_val, 
                            "Std": std_val, 
                            "Cp": cp, 
                            "Ca (%)": ca, 
                            "Cpk": cpk, 
                            "Rating": eval_msg
                        }])
                        
                        st.dataframe(
                            df_spc.style.format("{:.2f}", subset=["Mean", "Std", "Cp", "Ca (%)", "Cpk"])
                            .map(lambda v: f'color: {color_code}; font-weight: bold', subset=['Rating']), 
                            hide_index=True, use_container_width=True
                        )

            # --- CHẾ ĐỘ 2: SPC CONTROL CHARTS (I-MR) ---
            else:
                # Giữ nguyên thiết kế Plotly cho I-MR vì nó yêu cầu tính tương tác cao, 
                # nhưng tôi đã thêm mirror='all' và linewidth cho khung viền đen.
                st.subheader("III. Statistical Process Control (I-MR)")
                mr = plot_data.diff().abs()
                mu = plot_data.mean()
                sigma = plot_data.std()
                ucl, lcl = mu + 3*sigma, mu - 3*sigma
                mr_ucl = mr.mean() * 3.267
                
                fig_imr = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.15, subplot_titles=("Individual Chart (I)", "Moving Range Chart (MR)"))
                fig_imr.add_trace(go.Scatter(y=plot_data, mode='lines+markers', name='Data'), row=1, col=1)
                fig_imr.add_trace(go.Scatter(y=mr, mode='lines+markers', name='MR'), row=2, col=1)

                # Cấu hình khung viền và in đậm cho I-MR
                fig_imr.update_layout(height=750, template="simple_white", showlegend=False, margin=dict(r=80, t=60))
                fig_imr.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror='all', title_font=dict(size=14, family='Arial', color='black'))
                fig_imr.update_yaxes(showline=True, linewidth=2, linecolor='black', mirror='all', title_font=dict(size=14, family='Arial', color='black'))
                
                st.plotly_chart(fig_imr, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Please upload data to begin.")
