import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import re
from scipy.stats import norm
import io
from docx import Document
from docx.shared import Inches

# ==========================================
# 1. PAGE CONFIGURATION & FONTS
# ==========================================
st.set_page_config(page_title="Line 4 Quality Analytics", layout="wide")

# Thiết lập font hỗ trợ tiếng Trung để không bị lỗi ô vuông (▯▯) ở Legend
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

plt.rcParams.update({
    'font.size': 12,
    'axes.labelweight': 'bold',
    'axes.titleweight': 'bold',
    'axes.titlesize': 15,
    'legend.fontsize': 10,
    'font.weight': 'bold',
    'lines.linewidth': 2.5,
    'figure.dpi': 150  
})

# ==========================================
# 2. UTILITY FUNCTIONS
# ==========================================
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def find_data_col(df, key):
    for col in df.columns:
        if re.search(key, col, re.IGNORECASE) and not any(kw in col for kw in ["管制", "規格", "要求", "原始"]):
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
    rounded = round(float(val), 2)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)

def export_to_word(figures, titles):
    doc = Document()
    doc.add_heading('Quality Analytics Report', 0)

    for fig, title in zip(figures, titles):
        doc.add_heading(title, level=1)
        img_stream = io.BytesIO()
        fig.savefig(img_stream, format='png', dpi=300, bbox_inches='tight')
        img_stream.seek(0)
        doc.add_picture(img_stream, width=Inches(5.5))
        doc.add_paragraph("-" * 50)
    
    out_io = io.BytesIO()
    doc.save(out_io)
    out_io.seek(0)
    return out_io

# ==========================================
# 3. MAIN APP LOGIC
# ==========================================
st.sidebar.header("📂 DATA SOURCE")
uploaded_files = st.sidebar.file_uploader("Upload Excel/CSV Reports", type=["xlsx", "csv", "xls"], accept_multiple_files=True)

if uploaded_files:
    selected_filename = st.sidebar.selectbox("📝 Select File to Analyze:", [f.name for f in uploaded_files])
    uploaded_file = next(f for f in uploaded_files if f.name == selected_filename)

    try:
        df_raw = load_and_clean_data(uploaded_file)
        df = df_raw.copy()
        
        # TỰ ĐỘNG NHẬN DIỆN DÂY CHUYỀN THÔNG QUA TÊN CỘT
        is_coating_line = any("原始" in str(c) for c in df.columns)
        line_choice = "Dây chuyền sơn phủ (Coating)" if is_coating_line else "Dây chuyền mạ (Galvanizing)"
        
        st.sidebar.markdown("---")
        st.sidebar.info(f"🏭 Tự động nhận diện:\n**{line_choice}**")
        st.sidebar.markdown("---")
        
        if "用途碼" in df_raw.columns:
            usage_list = sorted(df_raw["用途碼"].dropna().unique().tolist())
            selected_usages = st.sidebar.multiselect("Filter Usage Code:", options=usage_list, default=usage_list)
            df = df_raw[df_raw["用途碼"].isin(selected_usages)]

        metrics_map = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
        zh_map_global = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}

        available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
        
        if not available: 
            st.warning(f"⚠️ Không tìm thấy cột dữ liệu cơ tính trong file '{selected_filename}'. Vui lòng kiểm tra lại.")
            st.stop()

        view_mode = st.sidebar.radio("View Mode:", ["Process Analytics", "SPC Control Charts (I-MR)", "Executive Summary"])
        
        if view_mode != "Executive Summary":
            selected_label = st.sidebar.selectbox("Select Parameter:", available)
            short_key = metrics_map[selected_label]
            data_col = find_data_col(df, short_key) 
            
            zh_key = zh_map_global.get(short_key, short_key)
            
            int_lsl = get_limit(df, zh_key, "min", "管制")
            int_usl = get_limit(df, zh_key, "max", "管制")
            cust_lsl = get_limit(df, zh_key, "min", "客戶要求")
            cust_usl = get_limit(df, zh_key, "max", "客戶要求")

            if data_col:
                # =================================================================
                # THUẬT TOÁN QUÉT TỪ KHÓA BẤT BIẾN (TÌM CỘT 原始)
                # =================================================================
                orig_col = None
                if line_choice == "Dây chuyền sơn phủ (Coating)":
                    search_keywords = {
                        "YS": ["降伏", "原始"],
                        "TS": ["抗拉", "原始"],
                        "EL": ["伸長", "原始"],
                        "HRB": ["硬度", "原始"]
                    }
                    target_kws = search_keywords.get(short_key, [])
                    for c in df.columns:
                        # Chỉ cần tên cột CHỨA đủ các từ khóa là lụm luôn
                        if target_kws and all(kw in str(c) for kw in target_kws):
                            orig_col = c
                            break
                
                temp_df = df.copy()
                
                if orig_col:
                    temp_df[orig_col] = pd.to_numeric(temp_df[orig_col], errors='coerce')
                temp_df[data_col] = pd.to_numeric(temp_df[data_col], errors='coerce')
                
                plot_df = temp_df.dropna(subset=[data_col]).reset_index(drop=True)
                plot_data = plot_df[data_col]
                plot_data_orig = plot_df[orig_col] if orig_col else None
                n = len(plot_data)
                data_max, data_min = plot_data.max(), plot_data.min()

                df_calc = plot_df.copy()
                grade_col = next((c for c in df.columns if any(kw in str(c).lower() for kw in ['grade', '等级', '等級', 'cấp', 'quality', 'loại'])), None)
                if grade_col:
                    df_calc = df_calc[df_calc[grade_col].astype(str).str.upper().str.contains(r'A|B', regex=True, na=False)]
                
                if grade_col is None or df_calc.empty:
                    df_calc = plot_df.copy()
                
                calc_data = df_calc[data_col].dropna()
                mu = calc_data.mean()
                sigma_fixed = calc_data.std(ddof=1)

                st.title(f"📊 Quality Analytics: {selected_label} - {line_choice}")

                if view_mode == "Process Analytics":
                    if line_choice == "Dây chuyền sơn phủ (Coating)":
                        tab_trend, tab_dist, tab_compare = st.tabs(["📈 Trend Analysis", "📊 Distribution & SPC", "🔄 Before vs After"])
                    else:
                        tab_trend, tab_dist = st.tabs(["📈 Trend Analysis", "📊 Distribution & SPC"])
                        
                    ucl_v1, lcl_v1 = mu + 3*sigma_fixed, mu - 3*sigma_fixed

                    with tab_trend:
                        fig_t, ax_t = plt.subplots(figsize=(12, 6))
                        x_coords = np.arange(1, n+1)
                        ax_t.plot(x_coords, plot_data, marker="o", markersize=6, color="#1f77b4", label="Actual Value", zorder=1)
                        
                        mask_out = pd.Series([False] * len(plot_data))
                        if int_usl is not None: mask_out = mask_out | (plot_data > int_usl)
                        if int_lsl is not None: mask_out = mask_out | (plot_data < int_lsl)
                        if mask_out.any():
                            ax_t.scatter(x_coords[mask_out], plot_data[mask_out], color="red", s=80, edgecolor="black", zorder=2, label="Out of Int. Limit")

                        ax_t.axhline(mu, color="blue", ls="-", lw=2, label=f"Theoretical Value: {mu:.1f}")
                        if cust_lsl: ax_t.axhline(cust_lsl, color="green", ls="-", lw=3, label="Cust LSL")
                        if cust_usl: ax_t.axhline(cust_usl, color="green", ls="-", lw=3, label="Cust USL")
                        if int_lsl: ax_t.axhline(int_lsl, color="red", ls="--", lw=3, label="Int LSL")
                        if int_usl: ax_t.axhline(int_usl, color="red", ls="--", lw=3, label="Int USL")
                        ax_t.axhline(ucl_v1, color="#6A0DAD", ls=":", lw=3, label="3σ UCL")
                        ax_t.axhline(lcl_v1, color="#6A0DAD", ls=":", lw=3, label="3σ LCL")
                        
                        ax_t.set_xlabel("Coil Sequence")
                        ax_t.set_ylabel(f"{selected_label} Value")
                        ax_t.set_title(f"{selected_label} Trend Analysis (N={n})", pad=20)
                        ax_t.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4, fontsize=9)
                        apply_full_border(ax_t); plt.tight_layout(); st.pyplot(fig_t)
                        
                        buf_t = export_to_word([fig_t], [f"Trend Analysis - {selected_label}"])
                        st.download_button(label="📥 Download Trend Chart", data=buf_t, file_name=f"Trend_Report_{selected_label}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

                    with tab_dist:
                        fig_d, ax_d = plt.subplots(figsize=(12, 6))
                        ax_d.hist(plot_data, bins=20, density=False, alpha=0.4, color="#7FB3D5", edgecolor="black")
                        ax_d.yaxis.set_major_locator(MaxNLocator(integer=True))
                        ax_d.set_xlabel(f"{selected_label} Value")
                        ax_d.set_ylabel("Coil Count")
                        
                        ax_pdf = ax_d.twinx()
                        x_min_fit, x_max_fit = min(plot_data.min(), mu - 4*sigma_fixed), max(plot_data.max(), mu + 4*sigma_fixed)
                        xs = np.linspace(x_min_fit, x_max_fit, 500)
                        ax_pdf.plot(xs, norm.pdf(xs, mu, sigma_fixed), color="#1E3A8A", lw=3, label="Normal Fit")
                        ax_pdf.set_yticks([])
                        
                        def add_vline_std(ax, val, color, ls, label, level=0):
                            if val is not None:
                                ax.axvline(val, color=color, linestyle=ls, linewidth=3, label=label)
                                trans = ax.get_xaxis_transform()
                                y_pos = 1.02 + (level * 0.05) 
                                ax.text(val, y_pos, f"{val:.1f}", color=color, ha='center', va='bottom', transform=trans, fontweight='bold')

                        add_vline_std(ax_d, mu, "blue", "-", "Theoretical Value", 0)
                        add_vline_std(ax_d, cust_lsl, "green", "-", "Cust LSL", 0)
                        add_vline_std(ax_d, cust_usl, "green", "-", "Cust USL", 0)
                        add_vline_std(ax_d, int_lsl, "red", "--", "Int LSL", 1)
                        add_vline_std(ax_d, int_usl, "red", "--", "Int USL", 1)
                        add_vline_std(ax_d, ucl_v1, "#6A0DAD", ":", "3σ UCL", 2) 
                        add_vline_std(ax_d, lcl_v1, "#6A0DAD", ":", "3σ LCL", 2) 
                        
                        ax_d.set_title(f"{selected_label} Distribution (N={n})", pad=55)
                        ax_d.legend(loc="upper left", bbox_to_anchor=(1, 1))
                        apply_full_border(ax_d); plt.tight_layout(); st.pyplot(fig_d)

                    if line_choice == "Dây chuyền sơn phủ (Coating)":
                        with tab_compare:
                            if orig_col is None:
                                st.error(f"❌ Không tìm thấy cột chứa dữ liệu (原始) cho {selected_label}.")
                                st.info(f"👉 Danh sách cột hiện có: {', '.join(df.columns.tolist()[:20])}...")
                            elif plot_data_orig is not None and plot_data_orig.isna().all():
                                st.warning(f"⚠️ Đã tìm thấy cột '{orig_col}' nhưng toàn bộ dữ liệu bên trong bị rỗng.")
                            else:
                                fig_c, ax_c = plt.subplots(figsize=(12, 6))
                                x_coords = np.arange(1, n+1)
                                
                                ax_c.plot(x_coords, plot_data_orig, marker="s", markersize=5, color="#808080", ls="--", label="Before Coating (原始)", alpha=0.7)
                                ax_c.plot(x_coords, plot_data, marker="o", markersize=6, color="#1f77b4", label="After Coating", zorder=3)
                                
                                if int_lsl: ax_c.axhline(int_lsl, color="red", ls="--", lw=2, label="Int LSL")
                                if int_usl: ax_c.axhline(int_usl, color="red", ls="--", lw=2, label="Int USL")

                                ax_c.set_xlabel("Coil Sequence")
                                ax_c.set_ylabel(f"{selected_label} Value")
                                ax_c.set_title(f"Effect of Coating Process: Before vs After ({selected_label})", pad=20)
                                ax_c.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4, fontsize=9)
                                apply_full_border(ax_c); plt.tight_layout(); st.pyplot(fig_c)
                                
                                buf_c = export_to_word([fig_c], [f"Comparison Analysis - {selected_label}"])
                                st.download_button(label="📥 Download Comparison Chart", data=buf_c, file_name=f"Compare_Report_{selected_label}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

                elif view_mode == "SPC Control Charts (I-MR)":
                    st.subheader("II. Control Limit Optimization & I-MR")
                    c_i1, c_i2 = st.columns(2)
                    with c_i1: k_std = st.number_input("Target Multiplier for StdDev (Sigma):", 1.0, 6.0, 3.0, 0.1)
                    with c_i2: k_iqr = st.number_input("Target Multiplier for IQR (k-factor):", 1.0, 6.0, 1.5, 0.1)
                    
                    q1, q3 = calc_data.quantile(0.25), calc_data.quantile(0.75)
                    iqr_val = q3 - q1
                    iqr_lsl = q1 - (k_iqr * iqr_val)
                    iqr_usl = q3 + (k_iqr * iqr_val)

                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        st.write("**Method: Standard Deviation**")
                        st.table(pd.DataFrame({
                            "Metric": ["N", "Max", "Min", "Theoretical Value", "Sigma", "LSL", "USL"],
                            "Value": [str(n), format_num(data_max), format_num(data_min), format_num(mu), format_num(sigma_fixed), format_num(mu - k_std*sigma_fixed), format_num(mu + k_std*sigma_fixed)]
                        }))
                    with col_r2:
                        st.write("**Method: IQR (Strict Standard)**")
                        st.table(pd.DataFrame({
                            "Metric": ["N", "Q1 (25th)", "Q3 (75th)", "IQR", "k-factor", "LSL (Q1 - k*IQR)", "USL (Q3 + k*IQR)"],
                            "Value": [str(n), format_num(q1), format_num(q3), format_num(iqr_val), str(k_iqr), format_num(iqr_lsl), format_num(iqr_usl)]
                        }))

                    fig_imr, ax_i = plt.subplots(figsize=(12, 6))
                    ax_i.plot(plot_data, marker="o", color="#1f77b4", label="Actual Data", alpha=0.7)
                    ax_i.axhline(mu, color="blue", ls="-", lw=2, label="Theoretical Value")
                    
                    if int_lsl: ax_i.axhline(int_lsl, color="red", ls="--", lw=2, label="Current Int LSL")
                    if int_usl: ax_i.axhline(int_usl, color="red", ls="--", lw=2, label="Current Int USL")
                    
                    if cust_lsl: ax_i.axhline(cust_lsl, color="green", ls="-", lw=2.5, label="Cust LSL")
                    if cust_usl: ax_i.axhline(cust_usl, color="green", ls="-", lw=2.5, label="Cust USL")
                    
                    ax_i.axhline(mu + k_std*sigma_fixed, color="darkred", ls="-", label=f"Prop USL ({k_std}σ)")
                    ax_i.axhline(mu - k_std*sigma_fixed, color="darkred", ls="-", label=f"Prop LSL ({k_std}σ)")
                    ax_i.axhline(iqr_usl, color="brown", ls="--", label=f"Prop USL (IQR)")
                    ax_i.axhline(iqr_lsl, color="brown", ls="--", label=f"Prop LSL (IQR)") 
                    
                    ax_i.set_xlabel("Coil Sequence")
                    ax_i.set_ylabel(f"{selected_label} Value")
                    ax_i.set_title(f"I-Chart: Optimization Comparison (N={n})", pad=20)
                    ax_i.legend(loc="upper left", bbox_to_anchor=(1, 1))
                    apply_full_border(ax_i); plt.tight_layout(); st.pyplot(fig_imr)

        elif view_mode == "Executive Summary":
            st.title("📑 Executive Quality Summary")
            summary_data = []
            
            for label in available:
                short_key = metrics_map[label]
                data_col = find_data_col(df, short_key)
                zh_key = zh_map_global.get(short_key, short_key)
                
                if data_col:
                    p_data = pd.to_numeric(df[data_col], errors='coerce').dropna()
                    if len(p_data) == 0: continue
                    mu_v = p_data.mean()
                    sig_v = p_data.std(ddof=1)
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
                            if cpk_val < 1.0: status = "🔴 Action Required"
                            elif 1.0 <= cpk_val < 1.33: status = "🟡 Acceptable"
                            elif 1.33 <= cpk_val <= 2.0: status = "🟢 Excellent"
                            else: status = "🔵 Over-engineered (>2.0)"
                    
                    summary_data.append({"Parameter": label, "N": len(p_data), "Mean": format_num(mu_v), "StdDev (σ)": format_num(sig_v),
                                       "Int LSL": format_num(i_lsl), "Int USL": format_num(i_usl), "Cp": cp, "Ca": ca, "Cpk": cpk, 
                                       "Cpk Formula": formula, "Status": status})
            
            st.dataframe(pd.DataFrame(summary_data), hide_index=True, use_container_width=True)

    except Exception as e:
        st.error(f"System Error: {e}")
else:
    st.info("👈 Please upload the production report to start.")
