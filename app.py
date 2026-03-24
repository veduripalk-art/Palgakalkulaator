import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SEADISTUS ---
st.set_page_config(page_title="Vedurijuhi Kalkulaator PRO", layout="wide")

# 1g78dHlfNWL8SXc3Ee3C_tpxWvdXNqt2edwzvUuSdW6w
SHEET_ID = "1g78dHlfNWL8SXc3Ee3C_tpxWvdXNqt2edwzvUuSdW6w"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

KVAL_LISA = {"EMU/DMU": 140, "EMU+DMU": 165, "EMU+DMU+SKODA": 205}

# --- 2. ANDMETE LAADIMINE ---
@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        # Teeme veergude nimed koodile kindlaks (suured tähed ja tühikuteta)
        df.columns = df.columns.str.strip().str.upper()
        df['ALATES'] = pd.to_datetime(df['ALATES'].str.strip())
        df['KUNI'] = pd.to_datetime(df['KUNI'].str.strip())
        return df
    except Exception as e:
        st.error(f"Viga tabeli laadimisel: {e}")
        return None

def get_day_type(date):
    d = date.weekday()
    if d == 0: return "E"
    if 1 <= d <= 3: return "T-N"
    if d == 4: return "R"
    return "LP"

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Seaded")
    baaspalk = st.number_input("Baastasu (€/h)", value=12.42)
    kval = st.selectbox("Kvalifikatsioon", options=list(KVAL_LISA.keys()))
    norm_kuu = st.number_input("Kuu normtunnid", value=168.0)
    
    st.divider()
    valitud_kuu_nimi = st.selectbox("Vali kuu", ["Jaanuar", "Veebruar", "Märts", "Aprill", "Mai", "Juuni"])
    kuu_map = {"Jaanuar": 1, "Veebruar": 2, "Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}
    k_num = kuu_map[valitud_kuu_nimi]

# --- 4. PEALINE LOOGIKA ---
df_tuurid = load_data()

if df_tuurid is not None:
    st.title(f"🚂 {valitud_kuu_nimi} 2026 Graafik")
    
    # Määrame kuu päevade arvu
    päevi = (pd.Timestamp(2026, k_num, 1) + pd.offsets.MonthEnd(0)).day
    graafik_tulemused = []

    cols = st.columns(7)
    for i in range(1, päevi + 1):
        dt = datetime(2026, k_num, i)
        dtype = get_day_type(dt)
        
        with cols[(i-1)%7]:
            st.write(f"**{i:02d}.{k_num:02d} ({dtype})**")
            # Võtame unikaalsed tuuride nimed tabelist valikusse
            tuuri_nimed = sorted(df_tuurid['TUUR'].unique().tolist())
            t_valik = st.selectbox("Tuur", ["Vaba", "P", "KO"] + tuuri_nimed, key=f"t{i}")
            lisa_min = st.number_input("+ min", min_value=0, step=5, key=f"m{i}")
            opilane = st.checkbox("Õp", key=f"s{i}")

            tunnid, tasu, nv = 0, 0, 0
            
            if t_valik == "P":
                nv = 8.0
            elif t_valik == "KO":
                tunnid, tasu = 8.0, 8.0 * baaspalk
            elif t_valik != "Vaba":
                # Otsime tabelist õige tuuri kellaajad
                mask = (
                    (df_tuurid['TUUR'] == t_valik) & 
                    (df_tuurid['ALATES'] <= dt) & 
                    (df_tuurid['KUNI'] >= dt)
                )
                soobivad_read = df_tuurid[mask]
                
                # Filtreerime päeva tüübi järgi
                leitud_rida = None
                for _, rida in soobivad_read.iterrows():
                    p_tyyp = str(rida['PAEV']).strip().upper()
                    if p_tyyp == "DEFAULT": leitud_rida = rida; break
                    if p_tyyp == dtype: leitud_rida = rida; break
                    if p_tyyp == "ER" and dtype != "LP": leitud_rida = rida; break
                    if p_tyyp == "T-R" and dtype in ["T-N", "R"]: leitud_rida = rida; break

                if leitud_rida is not None:
                    try:
                        fmt = "%H:%M"
                        s_dt = datetime.strptime(str(leitud_rida['ALGUS']), fmt)
                        e_dt = datetime.strptime(str(leitud_rida['LOPP']), fmt)
                        if e_dt <= s_dt: e_dt += timedelta(days=1)
                        
                        tunnid = ((e_dt - s_dt).total_seconds() / 3600) + (lisa_min / 60)
                        
                        kordaja = 1.0
                        if str(leitud_rida['SPLIT']).upper() == "TRUE": kordaja += 0.2
                        if opilane: kordaja += 0.2
                        
                        tasu = tunnid * (baaspalk * kordaja)
                    except:
                        st.warning(f"Viga kellaaegadega päeval {i}")

            graafik_tulemused.append({"t": tunnid, "r": tasu, "nv": nv, "work": t_valik not in ["Vaba", "P"]})

    # --- 5. STATISTIKA ---
    res_df = pd.DataFrame(graafik_tulemused)
    kokku_t = res_df["t"].sum()
    tegelik_norm = norm_kuu - res_df["nv"].sum()
    uletunnid = max(0, kokku_t - tegelik_norm)
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Töötatud tunde", f"{kokku_t:.2f} h")
    c2.metric("Ületunnid", f"{uletunnid:.2f} h", delta=f"Norm: {tegelik_norm}h")
    c3.metric("Ületundide lisa (0.5x)", f"{uletunnid * baaspalk * 0.5:.2f} €")
    
    toopaevi = res_df[res_df["work"] == True].shape[0]
    arvutatud_kval = min((toopaevi / 22) * KVAL_LISA[kval], KVAL_LISA[kval])
    
    st.success(f"### Jooksev kuu Bruto: {(res_df['r'].sum() + arvutatud_kval):.2f} €")
else:
    st.info("Palun seadista Google Sheetsi ID koodis.")
