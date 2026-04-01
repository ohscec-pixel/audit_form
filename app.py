import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe

st.set_page_config(layout="wide") 

# --- 0. 系統急救站 ---
with st.sidebar:
    st.header("🛠️ 系統維護")
    if st.button("🚨 強制重置系統"):
        st.session_state.clear()
        st.cache_resource.clear()
        st.rerun()

st.title("☁️ 稽核檢查自動化表單 (雲端協同作戰版)")

# --- 1. 雲端連線 ---
@st.cache_resource
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    key_dict = json.loads(st.secrets["json_key"])
    creds = Credentials.from_service_account_info(key_dict, scopes=scope)
    client = gspread.authorize(creds)
    # 👇 居米，請在這裡貼上你的_GOOGLE_SHEET_ID
    SHEET_ID = "1FDchd2MQ1KyUzcNkDM44YnDbpJ6_dBBmSIPoNqv1-tI" 
    sh = client.open_by_key(SHEET_ID)
    return sh.worksheet("Records"), sh.worksheet("Settings")

try:
    record_sheet, setting_sheet = init_connection()
except Exception as e:
    st.error(f"❌ 連線失敗！錯誤細節：{e}")
    st.stop()

# --- 2. 載入設定 ---
def load_settings():
    try:
        data = setting_sheet.get_all_records()
        if data:
            df_set = pd.DataFrame(data)
            if "檢查項目" in df_set.columns:
                st.session_state.inspection_items = [str(x) for x in df_set["檢查項目"] if str(x).strip()]
            for cat in ['建築', '土木', '機電']:
                if cat in df_set.columns:
                    st.session_state.sites[cat] = [str(x) for x in df_set[cat] if str(x).strip()]
    except: pass

# --- 3. 初始化 ---
if 'sites' not in st.session_state:
    st.session_state.sites = {'建築': [], '土木': [], '機電': []}
    st.session_state.inspection_items = ['管制標籤', '高度2M以下', '金屬繫材確實延伸', '跨坐勿站立頂板']
    load_settings() 

if 'results' not in st.session_state: st.session_state.results = {}
if 'last_sync_results' not in st.session_state: st.session_state.last_sync_results = {}
if 'last_sync_texts' not in st.session_state: st.session_state.last_sync_texts = {}
if 'reset_key' not in st.session_state: st.session_state.reset_key = 0
if 'sync_success' not in st.session_state: st.session_state.sync_success = False

def reset_form():
    st.session_state.results = {}
    st.session_state.last_sync_results = {}
    st.session_state.last_sync_texts = {}
    st.session_state.reset_key += 1
    st.success("✨ 已清空全部畫面紀錄！")

def clean_ls(lst):
    return list(dict.fromkeys([str(x).strip() for x in lst if pd.notna(x) and str(x).strip()]))

tab1, tab2 = st.tabs(["📝 表單填寫", "⚙️ 後台設定"])

# === 第二頁：後台設定 ===
with tab2:
    st.header("⚙️ 系統設定")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. 檢查項目")
        df_i = pd.DataFrame({"檢查項目": st.session_state.inspection_items})
        ed_i = st.data_editor(df_i, num_rows="dynamic", use_container_width=True, key="ed_items")
        
    with c2:
        st.subheader("2. 工地清單")
        site_tabs = st.tabs(['🏗️ 建築', '🛣️ 土木', '⚡ 機電'])
        editors = {} 
        for idx, cat in enumerate(['建築', '土木', '機電']):
            with site_tabs[idx]:
                df_s = pd.DataFrame({f"{cat}工地": st.session_state.sites[cat]})
                editors[cat] = st.data_editor(df_s, num_rows="dynamic", use_container_width=True, key=f"ed_{cat}")
            
    if st.button("💾 將以上設定儲存至雲端", use_container_width=True):
        with st.spinner('寫入雲端中...'):
            try:
                st.session_state.inspection_items = clean_ls(ed_i["檢查項目"].tolist())
                for cat in ['建築', '土木', '機電']:
                    st.session_state.sites[cat] = clean_ls(editors[cat][f"{cat}工地"].tolist())
                    
                dict_series = {"檢查項目": pd.Series(st.session_state.inspection_items)}
                for c in ['建築', '土木', '機電']: dict_series[c] = pd.Series(st.session_state.sites[c])
                setting_sheet.clear()
                set_with_dataframe(setting_sheet, pd.DataFrame(dict_series), include_column_header=True)
                st.success("✅ 設定已永久儲存！")
            except Exception as e: st.error(f"儲存失敗: {e}")
            
    st.divider()
    st.subheader("🗑️ 雲端資料庫管理 (測試專用)")
    if st.button("🧨 徹底清空雲端填寫紀錄"):
        with st.spinner("正在清除雲端資料庫..."):
            try:
                record_sheet.clear()
                st.success("✅ 雲端資料庫已徹底清空！請切換到『表單填寫』點擊『🔄 清空畫面重新填寫』即可開始全新紀錄！")
            except Exception as e: st.error(f"清除失敗: {e}")

# === 第一頁：表單填寫 (📱 行動版旗艦介面) ===
with tab1:
    if st.session_state.sync_success:
        st.success("✅ 同步成功！資料已安全送達。您可以直接從下方選單切換至下一個工地繼續填寫！")
        st.session_state.sync_success = False

    col_t, col_b = st.columns([4, 1])
    col_t.header("📝 稽核檢查填寫")
    col_b.button("🔄 清空全部畫面", on_click=reset_form, use_container_width=True)

    st.info("💡 請先選擇工程類別與工地，下方會自動展開該工地的檢查表。")

    # 📱 核心升級 1：改用下拉式選單，畫面瞬間清爽！
    sel_cat = st.selectbox("🏗️ 1. 請選擇工程類別", list(st.session_state.sites.keys()))
    
    if st.session_state.sites[sel_cat]:
        sel_site = st.selectbox("📍 2. 請選擇工地名稱", st.session_state.sites[sel_cat])
        
        st.divider()
        st.markdown(f"### 📋 目前填寫：【{sel_cat}】{sel_site}")
        
        if st.session_state.inspection_items:
            # 📱 核心升級 2：取消雙欄位，改用單欄位直式排列，讓手指更好點擊！
            for item in st.session_state.inspection_items:
                key = f"{sel_cat}_{sel_site}_{item}"
                if key not in st.session_state.results: st.session_state.results[key] = None
                cur = st.session_state.results[key]
                idx = ['○', 'X', 'NA'].index(cur) if cur in ['○', 'X', 'NA'] else None
                
                st.session_state.results[key] = st.radio(
                    f"📌 {item}", 
                    ['○', 'X', 'NA'], 
                    key=f"r_{key}_{st.session_state.reset_key}", 
                    index=idx, 
                    horizontal=True
                )
        else:
            st.warning("請先至『後台設定』新增檢查項目！")
    else:
        st.warning(f"目前 {sel_cat} 類別下沒有工地，請先至『後台設定』新增！")

    st.divider()
    st.header("📊 您目前的填寫進度 (準備同步的資料)")
    
    # 📱 核心升級 3：智慧過濾總表，只顯示「你有動過」的工地！
    rep = []
    for cat, s_list in st.session_state.sites.items():
        for s in s_list:
            # 檢查這個工地有沒有填任何資料，沒填就直接跳過，不印在報表上！
            has_data = any(st.session_state.results.get(f"{cat}_{s}_{it}") for it in st.session_state.inspection_items)
            if not has_data: continue 
            
            x_items, row_base = [], {"工程類別": cat, "工地名稱": s}
            for it in st.session_state.inspection_items:
                v = st.session_state.results.get(f"{cat}_{s}_{it}")
                row_base[it] = v if v else ""
                if v == 'X': x_items.append(it)
            if not x_items:
                r = row_base.copy()
                r.update({"缺失工地":"", "缺失項目":"", "缺失描述":"", "改善情形":""})
                rep.append(r)
            else:
                for xi in x_items:
                    r = row_base.copy()
                    txt = st.session_state.last_sync_texts.get(f"{cat}_{s}_{xi}", {})
                    r.update({"缺失工地": s, "缺失項目": xi, "缺失描述": txt.get("缺失描述", ""), "改善情形": txt.get("改善情形", "")})
                    rep.append(r)
                    
    if rep:
        ed_final = st.data_editor(pd.DataFrame(rep), use_container_width=True, hide_index=True, disabled=list(pd.DataFrame(rep).columns[:-2]))
        
        col_dl, col_sync = st.columns(2)
        with col_dl:
            st.download_button("📥 1. 下載目前畫面", ed_final.to_csv(index=False).encode('utf-8-sig'), "稽核報表.csv", "text/csv", use_container_width=True)
            
        with col_sync:
            if st.button("☁️ 2. 智能合併同步至 Google 雲端", use_container_width=True):
                with st.spinner('資料合併上傳中...'):
                    try:
                        try:
                            cloud_data = record_sheet.get_all_records()
                            cloud_df = pd.DataFrame(cloud_data) if cloud_data else pd.DataFrame()
                        except: 
                            cloud_df = pd.DataFrame()
                        
                        merged_results, text_fields = {}, {}
                        
                        if not cloud_df.empty and "工地名稱" in cloud_df.columns:
                            for _, row in cloud_df.iterrows():
                                s, cat = str(row.get("工地名稱", "")).strip(), str(row.get("工程類別", "")).strip()
                                if not s or str(s).lower() == "nan": continue
                                for it in st.session_state.inspection_items:
                                    if it in row and pd.notna(row[it]) and str(row[it]).strip():
                                        merged_results[f"{cat}_{s}_{it}"] = str(row[it]).strip()
                                xi = str(row.get("缺失項目", "")).strip()
                                if xi and str(xi).lower() != "nan":
                                    desc, impr = str(row.get("缺失描述", "")).strip(), str(row.get("改善情形", "")).strip()
                                    text_fields[f"{cat}_{s}_{xi}"] = {"缺失描述": desc if desc.lower() != "nan" else "", "改善情形": impr if impr.lower() != "nan" else ""}
                                            
                        for k, v in st.session_state.results.items():
                            if v is not None and str(v).strip():
                                if str(v) != str(st.session_state.last_sync_results.get(k, "")):
                                    merged_results[k] = v
                                    
                        if not ed_final.empty and "工地名稱" in ed_final.columns:
                            for _, row in ed_final.iterrows():
                                s, cat, xi = str(row.get("工地名稱", "")).strip(), str(row.get("工程類別", "")).strip(), str(row.get("缺失項目", "")).strip()
                                if s and str(s).lower() != "nan" and xi and str(xi).lower() != "nan":
                                    desc, impr = str(row.get("缺失描述", "")).strip(), str(row.get("改善情形", "")).strip()
                                    desc = "" if desc.lower() == "nan" else desc
                                    impr = "" if impr.lower() == "nan" else impr
                                    
                                    cloud_txt = text_fields.get(f"{cat}_{s}_{xi}", {})
                                    last_txt = st.session_state.last_sync_texts.get(f"{cat}_{s}_{xi}", {})
                                    
                                    f_desc = desc if str(desc) != str(last_txt.get("缺失描述", "")) else cloud_txt.get("缺失描述", "")
                                    f_impr = impr if str(impr) != str(last_txt.get("改善情形", "")) else cloud_txt.get("改善情形", "")
                                    text_fields[f"{cat}_{s}_{xi}"] = {"缺失描述": f_desc, "改善情形": f_impr}
                                    
                        rep_merged = []
                        for c_name, s_list in st.session_state.sites.items():
                            for s_name in s_list:
                                x_items, row_base = [], {"工程類別": c_name, "工地名稱": s_name}
                                for it in st.session_state.inspection_items:
                                    v = merged_results.get(f"{c_name}_{s_name}_{it}", "")
                                    row_base[it] = v
                                    if v == 'X': x_items.append(it)
                                if not x_items:
                                    r = row_base.copy()
                                    r.update({"缺失工地":"", "缺失項目":"", "缺失描述":"", "改善情形":""})
                                    rep_merged.append(r)
                                else:
                                    for xi in x_items:
                                        r = row_base.copy()
                                        txt = text_fields.get(f"{c_name}_{s_name}_{xi}", {})
                                        r.update({"缺失工地": s_name, "缺失項目": xi, "缺失描述": txt.get("缺失描述", ""), "改善情形": txt.get("改善情形", "")})
                                        rep_merged.append(r)
                                        
                        merged_df = pd.DataFrame(rep_merged) if rep_merged else pd.DataFrame()
                        if not merged_df.empty:
                            record_sheet.clear() 
                            set_with_dataframe(record_sheet, merged_df, include_column_header=True) 
                            
                            st.session_state.last_sync_results = st.session_state.results.copy()
                            
                            local_texts = {}
                            if not ed_final.empty and "工地名稱" in ed_final.columns:
                                for _, row in ed_final.iterrows():
                                    s, cat, xi = str(row.get("工地名稱", "")).strip(), str(row.get("工程類別", "")).strip(), str(row.get("缺失項目", "")).strip()
                                    if s and str(s).lower() != "nan" and xi and str(xi).lower() != "nan":
                                        desc, impr = str(row.get("缺失描述", "")).strip(), str(row.get("改善情形", "")).strip()
                                        desc = "" if desc.lower() == "nan" else desc
                                        impr = "" if impr.lower() == "nan" else impr
                                        local_texts[f"{cat}_{s}_{xi}"] = {"缺失描述": desc, "改善情形": impr}
                            st.session_state.last_sync_texts = local_texts
                            
                            st.session_state.sync_success = True
                            st.rerun() 
                        else: st.warning("⚠️ 沒有資料可以同步喔！")
                    except Exception as e: st.error(f"同步失敗: {e}")
    else:
        st.info("👆 請先在上方選擇工地並填寫紀錄，資料便會顯示在這裡喔！")
