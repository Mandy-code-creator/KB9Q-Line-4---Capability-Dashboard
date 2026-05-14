import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import re
from scipy.stats import norm, ttest_ind, sem, t
import io
from docx import Document
from docx.shared import Inches
import matplotlib.lines as mlines

# ==========================================
# 1. PAGE CONFIGURATION & FONTS
# ==========================================
st.set_page_config(page_title="Line 4 Quality Analytics", layout="wide")

plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'sans-serif']
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

def get_limit_series(df, keyword, limit_type, category, length):
    col = next((c for c in df.columns if keyword in c and limit_type in c.lower() and category in c), None)
    if col:
        s = pd.to_numeric(df[col], errors='coerce')
        s = s.mask(s <= 0, np.nan).ffill().bfill()
        return s
    return pd.Series([np.nan] * length)

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
    metrics_map = {"YS": "YS", "TS": "TS", "EL": "EL", "Hardness": "HRB", "YPE": "YPE"}
    zh_map_global = {"YS": "降伏強度", "TS": "抗拉強度", "EL": "伸長率", "HRB": "硬度", "YPE": "YPE"}

    file_names = [f.name for f in uploaded_files]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏭 ASSIGN LINE DATA")
    ma_filename = st.sidebar.selectbox("Select Galvanizing File:", file_names, key="ma_sel")
    son_filename = st.sidebar.selectbox("Select Coating File:", file_names, index=1 if len(file_names) > 1 else 0, key="son_sel")
    
    st.sidebar.markdown("---")
    view_mode = st.sidebar.radio("🔍 VIEW MODE:", [
        "Process Analytics", 
        "SPC Control Charts (I-MR)", 
        "Executive Summary", 
        "Cross-Line Comparison 🔀"
    ])

    # =========================================================================
    # MODE 1: CROSS-LINE COMPARISON
    # =========================================================================
    if view_mode == "Cross-Line Comparison 🔀":
        st.title("🔀 Statistical Process Shift & Limits Recommendation")
        
        if ma_filename == son_filename:
            st.warning("⚠️ You selected the same file for both lines. Please assign different files in the sidebar to compare.")
        else:
            file_ma = next(f for f in uploaded_files if f.name == ma_filename)
            df_ma = load_and_clean_data(file_ma)
            
            file_son = next(f for f in uploaded_files if f.name == son_filename)
            df_son = load_and_clean_data(file_son)

            common_labels = [k for k, v in metrics_map.items() if find_data_col(df_ma, v) and find_data_col(df_son, v)]

            if not common_labels:
                st.error("❌ No common mechanical property columns found between the two files.")
            else:
                st.success(f"✅ Found {len(common_labels)} common properties to analyze: {', '.join(common_labels)}")
                
                for selected_label in common_labels:
                    st.markdown(f"<hr><h2 style='color: #2E86C1; text-align: center;'>🔹 Analysis for Parameter: {selected_label} 🔹</h2>", unsafe_allow_html=True)
                    
                    short_key = metrics_map[selected_label]
                    zh_key = zh_map_global.get(short_key, short_key)

                    col_ma = find_data_col(df_ma, short_key)
                    col_son = find_data_col(df_son, short_key)

                    temp_ma = df_ma.copy()
                    temp_ma['val'] = pd.to_numeric(temp_ma[col_ma], errors='coerce')
                    temp_ma = temp_ma.dropna(subset=['val']).reset_index(drop=True)

                    temp_son = df_son.copy()
                    temp_son['val'] = pd.to_numeric(temp_son[col_son], errors='coerce')
                    temp_son = temp_son.dropna(subset=['val']).reset_index(drop=True)

                    thick_col_ma = next((c for c in temp_ma.columns if "厚度" in str(c) or "thickness" in str(c).lower()), None)
                    thick_col_son = next((c for c in temp_son.columns if "厚度" in str(c) or "thickness" in str(c).lower()), None)

                    groups_to_compare = []

                    if thick_col_ma and thick_col_son:
                        temp_ma['Thick_Num'] = pd.to_numeric(temp_ma[thick_col_ma], errors='coerce')
                        temp_son['Thick_Num'] = pd.to_numeric(temp_son[thick_col_son], errors='coerce')
                        
                        ma_g1 = temp_ma[temp_ma['Thick_Num'] <= 0.60].copy()
                        son_g1 = temp_son[temp_son['Thick_Num'] <= 0.60].copy()
                        if not ma_g1.empty and not son_g1.empty:
                            groups_to_compare.append(("Độ dày (Thickness) <= 0.60", ma_g1, son_g1))
                            
                        ma_g2 = temp_ma[temp_ma['Thick_Num'] > 0.60].copy()
                        son_g2 = temp_son[temp_son['Thick_Num'] > 0.60].copy()
                        if not ma_g2.empty and not son_g2.empty:
                            groups_to_compare.append(("Độ dày (Thickness) > 0.60", ma_g2, son_g2))
                    
                    if not groups_to_compare:
                        st.info(f"ℹ️ Không tìm thấy dữ liệu phân chia độ dày cho {selected_label}. Chuyển sang chế độ phân tích tổng thể.")
                        groups_to_compare.append(("Toàn bộ dữ liệu (Global)", temp_ma, temp_son))

                    for group_info in groups_to_compare:
                        group_name = group_info[0]
                        group_ma = group_info[1]
                        group_son = group_info[2]

                        st.markdown(f"<h3 style='color: #D35400;'>📌 Phân tích: {group_name}</h3>", unsafe_allow_html=True)

                        vals_ma_full = group_ma['val']
                        vals_son_full = group_son['val']

                        def get_theoretical_mean_group(df_group):
                            df_calc = df_group.copy()
                            g_col = next((c for c in df_group.columns if any(kw in str(c).lower() for kw in ['grade', '等级', '等級', 'cấp', 'quality', 'loại'])), None)
                            if g_col:
                                f_df = df_calc[df_calc[g_col].astype(str).str.upper().str.contains(r'A|B', regex=True, na=False)]
                                if not f_df.empty: df_calc = f_df
                            return df_calc['val'].mean()

                        mean_ma = get_theoretical_mean_group(group_ma)
                        mean_son = get_theoretical_mean_group(group_son)
                        
                        delta = mean_son - mean_ma if pd.notnull(mean_son) and pd.notnull(mean_ma) else 0

                        son_lsl_series = get_limit_series(group_son, zh_key, "min", "管制", len(group_son))
                        son_usl_series = get_limit_series(group_son, zh_key, "max", "管制", len(group_son))
                        
                        lsl_vals = son_lsl_series[son_lsl_series > 0]
                        usl_vals = son_usl_series[son_usl_series > 0]
                        
                        lsl_son = lsl_vals.mode()[0] if not lsl_vals.empty else None
                        usl_son = usl_vals.mode()[0] if not usl_vals.empty else None

                        if short_key == "YPE":
                            lsl_son = 4.0

                        s_lsl = (lsl_son - delta) if lsl_son is not None else "N/A"
                        s_usl = (usl_son - delta) if usl_son is not None else "N/A"

                        st.markdown(f"**🔄 Optimal Limits Recommendation**")
                        delta_data = [{
                            "Phân loại": group_name,
                            "Galv. Theo. Value": format_num(mean_ma),
                            "Coating Theo. Value": format_num(mean_son),
                            "Shift (Δ)": format_num(delta),
                            "Current Coating LSL (Mode)": format_num(lsl_son) if lsl_son is not None else "N/A",
                            "Current Coating USL (Mode)": format_num(usl_son) if usl_son is not None else "N/A",
                            "Recommended Galv. LSL": format_num(s_lsl) if isinstance(s_lsl, (int, float)) else s_lsl,
                            "Recommended Galv. USL": format_num(s_usl) if isinstance(s_usl, (int, float)) else s_usl
                        }]
                        st.dataframe(pd.DataFrame(delta_data), hide_index=True, use_container_width=True)

                        if len(vals_son_full) > 1 and len(vals_ma_full) > 1:
                            t_stat, p_val = ttest_ind(vals_son_full, vals_ma_full, equal_var=False)
                            is_significant = "YES" if p_val < 0.05 else "NO"
                        else:
                            t_stat, p_val, is_significant = np.nan, np.nan, "N/A"
                        
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            st.markdown("**🔬 2-Sample T-Test**")
                            t_test_data = pd.DataFrame([{
                                "Metric": "T-Statistic", "Value": format_num(t_stat)
                            }, {
                                "Metric": "P-Value", "Value": f"{p_val:.4f}" if pd.notnull(p_val) else "N/A"
                            }, {
                                "Metric": "Significant Shift?", "Value": is_significant
                            }])
                            st.table(t_test_data)

                        with c2:
                            fig_comp, ax_comp = plt.subplots(figsize=(8, 4))
                            
                            for label_name, vals, color in [
                                (f"Galvanizing (n={len(vals_ma_full)})", vals_ma_full, '#1f77b4'),
                                (f"Coating (n={len(vals_son_full)})", vals_son_full, '#ff7f0e')
                            ]:
                                if len(vals) > 1 and vals.std() > 0:
                                    mu_val = vals.mean()
                                    sigma_val = vals.std(ddof=1)
                                    
                                    x_range = np.linspace(mu_val - 4*sigma_val, mu_val + 4*sigma_val, 500)
                                    bin_width = (vals.max() - vals.min()) / 20 if vals.max() > vals.min() else 1
                                    y_vals = norm.pdf(x_range, mu_val, sigma_val) * len(vals) * bin_width
                                    
                                    ax_comp.plot(x_range, y_vals, color=color, lw=2.5, label=label_name)
                                    ax_comp.fill_between(x_range, y_vals, alpha=0.3, color=color)
                                    ax_comp.axvline(mu_val, color=color, linestyle='--', alpha=0.8) 
                            
                            ax_comp.set_ylabel("Coil Count")
                            ax_comp.set_xlabel(f"{selected_label} Value")
                            
                            ax_comp.set_title(f"Shift Dist. (Δ = {format_num(delta)})", pad=10)
                            
                            ax_comp.legend(loc="upper right", fontsize=9)
                            apply_full_border(ax_comp)
                            plt.tight_layout()
                            st.pyplot(fig_comp)
                        
                        st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # MODE 2: TABBED ANALYSIS FOR INDIVIDUAL LINES
    # =========================================================================
    else:
        st.title(f"📊 {view_mode}")
        
        if view_mode == "SPC Control Charts (I-MR)":
            st.info("⚙️ Configure global target multipliers below. The system will apply them to all available properties across both lines.")
            c_i1, c_i2 = st.columns(2)
            with c_i1: k_std = st.number_input("Target Multiplier for StdDev (Sigma):", 1.0, 6.0, 3.0, 0.1)
            with c_i2: k_iqr = st.number_input("Target Multiplier for IQR (k-factor):", 1.0, 6.0, 1.5, 0.1)
        else:
            k_std, k_iqr = 3.0, 1.5

        tab_ma, tab_son = st.tabs(["🏭 Galvanizing Line Data", "🎨 Coating Line Data"])
        
        line_configs = [
            (tab_ma, ma_filename, "Galvanizing Line"),
            (tab_son, son_filename, "Coating Line")
        ]

        for tab_obj, fname, line_label in line_configs:
            with tab_obj:
                file_obj = next((f for f in uploaded_files if f.name == fname), None)
                if not file_obj:
                    st.warning(f"File '{fname}' not found.")
                    continue
                
                df_raw = load_and_clean_data(file_obj)
                df = df_raw.copy()
                
                is_coating_line = any("原始" in str(c) for c in df.columns)
                actual_line_type = "Coating Line" if is_coating_line else "Galvanizing Line"
                
                st.info(f"📂 Analyzing File: **{fname}** | Auto-detected: **{actual_line_type}**")
                
                if "用途碼" in df.columns:
                    usage_list = sorted(df["用途碼"].dropna().unique().tolist())
                    selected_usages = st.multiselect(f"Filter Usage Code ({line_label}):", options=usage_list, default=usage_list, key=f"usage_{fname}_{view_mode}")
                    df = df[df["用途碼"].isin(selected_usages)]

                available = [k for k, v in metrics_map.items() if find_data_col(df, v)]
                if not available:
                    st.warning(f"⚠️ Mechanical property data column not found in this file.")
                    continue

                if view_mode == "Executive Summary":
                    summary_data = []
                    for selected_label in available:
                        short_key = metrics_map[selected_label]
                        data_col = find_data_col(df, short_key)
                        zh_key = zh_map_global.get(short_key, short_key)
                        
                        if data_col:
                            p_data = pd.to_numeric(df[data_col], errors='coerce').dropna()
                            if len(p_data) == 0: continue
                            mu_v = p_data.mean()
                            sig_v = p_data.std(ddof=1)
                            i_lsl = get_limit(df, zh_key, "min", "管制")
                            i_usl = get_limit(df, zh_key, "max", "管制")
                            
                            if is_coating_line and short_key == "YPE":
                                i_lsl = 4.0
                            
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
                            
                            summary_data.append({"Parameter": selected_label, "N": len(p_data), "Mean": format_num(mu_v), "StdDev (σ)": format_num(sig_v),
                                               "Int LSL": format_num(i_lsl), "Int USL": format_num(i_usl), "Cp": cp, "Ca": ca, "Cpk": cpk, 
                                               "Cpk Formula": formula, "Status": status})
                    
                    st.dataframe(pd.DataFrame(summary_data), hide_index=True, use_container_width=True)

                else:
                    for selected_label in available:
                        st.markdown(f"<hr><h3 style='color: #2E86C1;'>🔹 Parameter: {selected_label}</h3>", unsafe_allow_html=True)
                        short_key = metrics_map[selected_label]
                        data_col = find_data_col(df, short_key) 
                        zh_key = zh_map_global.get(short_key, short_key)
                        
                        if data_col:
                            temp_df = df.copy()
                            temp_df[data_col] = pd.to_numeric(temp_df[data_col], errors='coerce')
                            
                            plot_df = temp_df.dropna(subset=[data_col]).reset_index(drop=True)
                            plot_data = plot_df[data_col]
                            n = len(plot_data)

                            if view_mode == "Process Analytics":
                                int_lsl_series = get_limit_series(plot_df, zh_key, "min", "管制", n)
                                int_usl_series = get_limit_series(plot_df, zh_key, "max", "管制", n)
                                cust_lsl_series = get_limit_series(plot_df, zh_key, "min", "客戶要求", n)
                                cust_usl_series = get_limit_series(plot_df, zh_key, "max", "客戶要求", n)

                                if is_coating_line and short_key == "YPE":
                                    int_lsl_series = pd.Series([4.0] * n)
                                
                                temp_plot_df = plot_df.copy()
                                temp_plot_df['LSL_temp'] = int_lsl_series.fillna(-1).values
                                temp_plot_df['USL_temp'] = int_usl_series.fillna(-1).values
                                
                                groups = temp_plot_df.groupby(['LSL_temp', 'USL_temp'])
                                trend_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
                                
                                df_calc = plot_df.copy()
                                grade_col = next((c for c in df.columns if any(kw in str(c).lower() for kw in ['grade', '等级', '等級', 'cấp', 'quality', 'loại'])), None)
                                if grade_col:
                                    f_df = df_calc[df_calc[grade_col].astype(str).str.upper().str.contains(r'A|B', regex=True, na=False)]
                                    if not f_df.empty: df_calc = f_df
                                
                                calc_data = df_calc[data_col].dropna()
                                mu = calc_data.mean()
                                sigma_fixed = calc_data.std(ddof=1)

                                tab_trend, tab_dist = st.tabs([f"📈 {selected_label} Trend", f"📊 {selected_label} Distribution"])
                                ucl_v1, lcl_v1 = mu + 3*sigma_fixed, mu - 3*sigma_fixed

                                with tab_trend:
                                    fig_t, ax_t = plt.subplots(figsize=(13, 6.5)) 
                                    x_coords = np.arange(1, n+1)

                                    # Lưu bounds để check Out of Limit
                                    if not int_lsl_series.isna().all() and not int_usl_series.isna().all():
                                        lower_bound = int_lsl_series.ffill().bfill()
                                        upper_bound = int_usl_series.ffill().bfill()
                                    else:
                                        lower_bound = pd.Series([-np.inf] * n)
                                        upper_bound = pd.Series([np.inf] * n)

                                    # Hàm thu thập Label để gom bên lề phải
                                    label_dict = {}
                                    def add_to_label(val, name, color):
                                        if pd.isna(val) or val <= 0: return
                                        val = round(val, 1) 
                                        if val not in label_dict: label_dict[val] = []
                                        if not any(item['name'] == name for item in label_dict[val]):
                                            label_dict[val].append({'name': name, 'color': color})

                                    # 1. ĐƯỜNG GIỚI HẠN KHÁCH HÀNG (Kéo dài hết đồ thị)
                                    if not cust_lsl_series.isna().all():
                                        for c_val in cust_lsl_series.dropna().unique():
                                            if c_val > 0: 
                                                ax_t.axhline(c_val, color="#7F8C8D", linestyle=":", linewidth=1.5, alpha=0.7)
                                                add_to_label(c_val, "Cust LSL", "#7F8C8D")
                                    if not cust_usl_series.isna().all():
                                        for c_val in cust_usl_series.dropna().unique():
                                            if c_val > 0: 
                                                ax_t.axhline(c_val, color="#7F8C8D", linestyle=":", linewidth=1.5, alpha=0.7)
                                                add_to_label(c_val, "Cust USL", "#7F8C8D")

                                    # 2. VẼ ĐIỂM DỮ LIỆU, MEAN, & GIỚI HẠN NỘI BỘ (Kéo dài hết đồ thị theo màu)
                                    color_idx = 0
                                    for (lsl, usl), group in groups:
                                        c = trend_colors[color_idx % len(trend_colors)]
                                        mask = temp_plot_df.index.isin(group.index)
                                        l_str = "N/A" if lsl == -1 else format_num(lsl)
                                        u_str = "N/A" if usl == -1 else format_num(usl)
                                        
                                        # Mean đứt đoạn tại đúng khu vực dữ liệu của nhóm
                                        group_mean = group[data_col].mean()
                                        ax_t.plot(x_coords, np.where(mask, group_mean, np.nan), color=c, linestyle="-", linewidth=1.5, alpha=0.5, label="Group Mean")
                                        add_to_label(group_mean, "Theo. Value", c)
                                        
                                        # Đường Int Limit kéo liền ngang qua đồ thị (Dễ nhìn, phân biệt bằng màu)
                                        if lsl != -1: 
                                            ax_t.axhline(lsl, color=c, linestyle="--", linewidth=1.5, alpha=0.8)
                                            add_to_label(lsl, "Int LSL", c)
                                        if usl != -1: 
                                            ax_t.axhline(usl, color=c, linestyle="--", linewidth=1.5, alpha=0.8)
                                            add_to_label(usl, "Int USL", c)
                                            
                                        # Data points
                                        ax_t.scatter(x_coords[mask], plot_data[mask], color=c, s=40, edgecolor="black", linewidth=0.8, zorder=4, label=f"Data ({l_str}-{u_str})")
                                        color_idx += 1

                                    # 3. HIGHLIGHT CÁC ĐIỂM OUT OF LIMIT
                                    mask_out = (plot_data < lower_bound) | (plot_data > upper_bound)
                                    if mask_out.any():
                                        ax_t.scatter(x_coords[mask_out], plot_data[mask_out], color="#E74C3C", s=60, edgecolor="darkred", linewidth=1.5, zorder=6, label="Out of Limit")

                                    # 4. AUTO-ZOOM TRỤC Y VÀ CĂN LỀ TEXT LỀ PHẢI
                                    valid_y = plot_data.dropna()
                                    ymin, ymax = valid_y.min(), valid_y.max()
                                    for val in label_dict.keys():
                                        ymin = min(ymin, val)
                                        ymax = max(ymax, val)
                                            
                                    y_range = ymax - ymin if ymax > ymin else 10
                                    ax_t.set_ylim(ymin - y_range*0.12, ymax + y_range*0.12)
                                    ax_t.set_xlim(0, n * 1.18)

                                    sorted_vals = sorted(label_dict.keys())
                                    min_y_dist = y_range * 0.05  
                                    last_y = -np.inf
                                    
                                    for val in sorted_vals:
                                        items = label_dict[val]
                                        names_str = " / ".join([item['name'] for item in items])
                                        main_color = items[0]['color']
                                        
                                        y_draw = val
                                        if y_draw - last_y < min_y_dist:
                                            y_draw = last_y + min_y_dist
                                            
                                        ax_t.plot([n, n + (n*0.02)], [val, y_draw], color="black", linestyle="-", lw=0.8, alpha=0.3)
                                        bbox = dict(boxstyle="round,pad=0.3", fc="#FDFEFE", ec=main_color, alpha=0.9, lw=1.2)
                                        ax_t.text(n + (n*0.025), y_draw, f"{names_str}: {val:.1f}", color=main_color, va='center', ha='left', fontsize=9, bbox=bbox, fontweight='bold')
                                        last_y = y_draw

                                    ax_t.set_xlabel("Coil Sequence")
                                    ax_t.set_ylabel(f"{selected_label} Value")
                                    ax_t.set_title(f"{selected_label} Trend Analysis (N={n})", pad=20)
                                    
                                    handles, labels = ax_t.get_legend_handles_labels()
                                    by_label = dict(zip(labels, handles))
                                    clean_dict = {k: v for k, v in by_label.items() if not k.startswith('_')}
                                    ax_t.legend(clean_dict.values(), clean_dict.keys(), loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4, fontsize=9)
                                    
                                    apply_full_border(ax_t); plt.tight_layout(); st.pyplot(fig_t)
                                    
                                    buf_t = export_to_word([fig_t], [f"Trend Analysis - {selected_label}"])
                                    st.download_button(label=f"📥 Download Trend Chart ({selected_label})", data=buf_t, file_name=f"Trend_Report_{selected_label}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_trend_{fname}_{selected_label}")

                                with tab_dist:
                                    fig_d, ax_d = plt.subplots(figsize=(12, 6))
                                    
                                    hist_data, hist_labels = [], []
                                    color_idx = 0
                                    for (lsl, usl), group in groups:
                                        hist_data.append(group[data_col].values)
                                        l_str = "N/A" if lsl == -1 else format_num(lsl)
                                        u_str = "N/A" if usl == -1 else format_num(usl)
                                        hist_labels.append(f"Data (Spec: {l_str} - {u_str})")
                                        color_idx += 1
                                        
                                    if len(hist_data) > 1:
                                        ax_d.hist(hist_data, bins=20, stacked=True, density=False, alpha=0.7, edgecolor="black", label=hist_labels, color=trend_colors[:len(hist_data)])
                                    else:
                                        ax_d.hist(plot_data, bins=20, density=False, alpha=0.5, color="#7FB3D5", edgecolor="black", label="Data")

                                    ax_d.yaxis.set_major_locator(MaxNLocator(integer=True))
                                    ax_d.set_xlabel(f"{selected_label} Value")
                                    ax_d.set_ylabel("Coil Count")
                                    
                                    ax_pdf = ax_d.twinx()
                                    x_min_fit, x_max_fit = min(plot_data.min(), mu - 4*sigma_fixed), max(plot_data.max(), mu + 4*sigma_fixed)
                                    xs = np.linspace(x_min_fit, x_max_fit, 500)
                                    
                                    bin_w = (plot_data.max() - plot_data.min()) / 20 if plot_data.max() > plot_data.min() else 1
                                    y_vals = norm.pdf(xs, mu, sigma_fixed) * n * bin_w
                                    ax_pdf.plot(xs, y_vals, color="#1E3A8A", lw=3, label="Normal Fit")
                                    ax_pdf.set_yticks([])
                                    
                                    lines_to_draw = []
                                    def register_vline(val, color, ls, label):
                                        if val is not None and val > 0:
                                            lines_to_draw.append({'val': val, 'color': color, 'ls': ls, 'label': label})

                                    def register_multiple(limit_series, color, ls, base_label):
                                        if limit_series is not None and not limit_series.isna().all():
                                            unique_vals = limit_series.dropna().unique()
                                            unique_vals = [v for v in unique_vals if v > 0]
                                            for i, val in enumerate(unique_vals):
                                                label = base_label if i == 0 else None
                                                register_vline(val, color, ls, label)

                                    # Lấy mean_series.dropna().unique() thay vì truyền thẳng mảng
                                    mean_unique_vals = mean_series.dropna().unique()
                                    for v in mean_unique_vals:
                                        register_vline(v, "blue", "-", "Theo. Value")
                                        
                                    register_multiple(cust_lsl_series, "green", "-", "Cust LSL")
                                    register_multiple(cust_usl_series, "green", "-", "Cust USL")
                                    register_multiple(int_lsl_series, "red", "--", "Int LSL")
                                    register_multiple(int_usl_series, "red", "--", "Int USL")

                                    lines_to_draw.sort(key=lambda x: x['val'])
                                    x_range = x_max_fit - x_min_fit
                                    min_dist = x_range * 0.09  
                                    levels_last_x = [-np.inf] * 6  
                                    trans = ax_d.get_xaxis_transform()
                                    
                                    for item in lines_to_draw:
                                        val = item['val']
                                        c = item['color']
                                        ax_d.axvline(val, color=c, linestyle=item['ls'], linewidth=2.5, label=item['label'])
                                        
                                        assigned_level = 0
                                        for i in range(len(levels_last_x)):
                                            if (val - levels_last_x[i]) > min_dist:
                                                assigned_level = i
                                                levels_last_x[i] = val
                                                break
                                        else:
                                            assigned_level = 5
                                            levels_last_x[5] = val
                                        
                                        y_pos = 1.02 + (assigned_level * 0.08)
                                        bbox_props = dict(boxstyle="round,pad=0.2", fc="white", ec=c, alpha=0.9, lw=1.5)
                                        
                                        ax_d.text(val, y_pos, f"{val:.1f}", color=c, ha='center', va='bottom', 
                                                  transform=trans, fontweight='bold', fontsize=10, bbox=bbox_props)
                                    
                                    ax_d.set_title(f"{selected_label} Distribution (N={n})", pad=110) 
                                    
                                    handles, labels = ax_d.get_legend_handles_labels()
                                    handles_pdf, labels_pdf = ax_pdf.get_legend_handles_labels()
                                    by_label = dict(zip(labels + labels_pdf, handles + handles_pdf))
                                    clean_dict = {k: v for k, v in by_label.items() if k is not None and k != ''}
                                    
                                    ax_d.legend(clean_dict.values(), clean_dict.keys(), loc="upper left", bbox_to_anchor=(1, 1))
                                    apply_full_border(ax_d)
                                    plt.tight_layout(rect=[0, 0, 1, 0.9]) 
                                    st.pyplot(fig_d)
                                    
                                    buf_d = export_to_word([fig_d], [f"Distribution Analysis - {selected_label}"])
                                    st.download_button(label=f"📥 Download Dist Chart ({selected_label})", data=buf_d, file_name=f"Dist_Report_{selected_label}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_dist_{fname}_{selected_label}")

                            elif view_mode == "SPC Control Charts (I-MR)":
                                thick_col = next((c for c in df.columns if "厚度" in str(c) or "thickness" in str(c).lower()), None)
                                
                                spc_groups = []
                                temp_spc_df = plot_df.copy()
                                
                                if thick_col:
                                    temp_spc_df['Thick_Num'] = pd.to_numeric(temp_spc_df[thick_col], errors='coerce')
                                    
                                    g1 = temp_spc_df[temp_spc_df['Thick_Num'] <= 0.60]
                                    g2 = temp_spc_df[temp_spc_df['Thick_Num'] > 0.60]
                                    g_nan = temp_spc_df[temp_spc_df['Thick_Num'].isna()]
                                    
                                    if not g1.empty: spc_groups.append(("Thickness <= 0.60", g1))
                                    if not g2.empty: spc_groups.append(("Thickness > 0.60", g2))
                                    if not g_nan.empty: spc_groups.append(("Unknown Thickness", g_nan))
                                    
                                    st.markdown(f"#### 📐 Bảng thông số Kiểm soát (Phân loại theo Độ dày)")
                                else:
                                    spc_groups.append(("Toàn bộ dữ liệu", temp_spc_df))
                                    st.warning("⚠️ Không tìm thấy cột '訂單厚度' (Độ dày). Hệ thống đang tính chung cho toàn bộ dữ liệu.")
                                    st.markdown(f"#### 📐 Bảng thông số Kiểm soát")

                                spc_stats = []
                                for g_name, group in spc_groups:
                                    g_data = group[data_col].dropna()
                                    if len(g_data) > 1:
                                        g_n = len(g_data)
                                        g_mu = g_data.mean()
                                        g_sig = g_data.std(ddof=1)
                                        g_q1, g_q3 = g_data.quantile(0.25), g_data.quantile(0.75)
                                        g_iqr = g_q3 - g_q1
                                        
                                        spc_stats.append({
                                            "Nhóm (Group)": g_name,
                                            "N": g_n,
                                            "Mean": format_num(g_mu),
                                            "Sigma": format_num(g_sig),
                                            "UCL (3σ)": format_num(g_mu + k_std*g_sig),
                                            "LCL (3σ)": format_num(g_mu - k_std*g_sig),
                                            "IQR": format_num(g_iqr),
                                            "UCL (IQR)": format_num(g_q3 + k_iqr*g_iqr),
                                            "LCL (IQR)": format_num(g_q1 - k_iqr*g_iqr)
                                        })
                                
                                if spc_stats:
                                    st.dataframe(pd.DataFrame(spc_stats), hide_index=True, use_container_width=True)

                                fig_imr, ax_i = plt.subplots(figsize=(13, 6.5)) 
                                x_coords_spc = np.arange(1, n+1)
                                
                                ax_i.plot(x_coords_spc, plot_data, color="#CFD8DC", linestyle="-", linewidth=1.5, zorder=1)
                                
                                color_idx = 0
                                trend_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
                                
                                for g_name, group in spc_groups:
                                    c = trend_colors[color_idx % len(trend_colors)]
                                    mask = temp_spc_df.index.isin(group.index)
                                    g_data = group[data_col].dropna()
                                    
                                    if len(g_data) > 1:
                                        g_mu = g_data.mean()
                                        g_sig = g_data.std(ddof=1)
                                        g_q1, g_q3 = g_data.quantile(0.25), g_data.quantile(0.75)
                                        g_iqr = g_q3 - g_q1
                                        
                                        ax_i.scatter(x_coords_spc[mask], plot_data[mask], color=c, s=50, edgecolor="black", zorder=3, label=f"Data ({g_name})")
                                        
                                        ax_i.plot(x_coords_spc, np.where(mask, g_mu, np.nan), color=c, linestyle="-", linewidth=2, alpha=0.7)
                                        
                                        ax_i.plot(x_coords_spc, np.where(mask, g_mu + k_std*g_sig, np.nan), color=c, linestyle="--", linewidth=1.5)
                                        ax_i.plot(x_coords_spc, np.where(mask, g_mu - k_std*g_sig, np.nan), color=c, linestyle="--", linewidth=1.5)
                                        
                                        ax_i.plot(x_coords_spc, np.where(mask, g_q3 + k_iqr*g_iqr, np.nan), color=c, linestyle=":", linewidth=2, alpha=0.6)
                                        ax_i.plot(x_coords_spc, np.where(mask, g_q1 - k_iqr*g_iqr, np.nan), color=c, linestyle=":", linewidth=2, alpha=0.6)

                                    color_idx += 1
                                
                                ax_i.set_xlabel("Coil Sequence")
                                ax_i.set_ylabel(f"{selected_label} Value")
                                ax_i.set_title(f"I-Chart: Dynamic Control Limits ({selected_label})", pad=20)
                                
                                custom_lines = [
                                    mlines.Line2D([], [], color='black', linestyle='-', lw=2, alpha=0.7, label='Group Mean'),
                                    mlines.Line2D([], [], color='black', linestyle='--', lw=1.5, label=f'UCL/LCL ({k_std}σ)'),
                                    mlines.Line2D([], [], color='black', linestyle=':', lw=2, alpha=0.6, label=f'UCL/LCL (IQR)')
                                ]
                                
                                handles, labels = ax_i.get_legend_handles_labels()
                                by_label = dict(zip(labels, handles))
                                ax_i.legend(list(by_label.values()) + custom_lines, list(by_label.keys()) + [l.get_label() for l in custom_lines], loc="upper left", bbox_to_anchor=(1, 1))
                                
                                valid_y = plot_data.dropna()
                                ymin, ymax = valid_y.min(), valid_y.max()
                                y_range = ymax - ymin if ymax > ymin else 10
                                ax_i.set_ylim(ymin - y_range*0.1, ymax + y_range*0.1)
                                
                                apply_full_border(ax_i); plt.tight_layout(rect=[0, 0, 0.85, 1]); st.pyplot(fig_imr)
                                
                                buf_i = export_to_word([fig_imr], [f"SPC I-Chart Analysis - {selected_label}"])
                                st.download_button(label=f"📥 Download SPC Chart ({selected_label})", data=buf_i, file_name=f"SPC_Report_{selected_label}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_spc_{fname}_{selected_label}")
else:
    st.info("👈 Please upload the production report to start.")
