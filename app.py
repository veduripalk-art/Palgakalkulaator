import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SEADISTUS ---
st.set_page_config(page_title="Vedurijuhi Kalkulaator PRO", layout="wide")

SHEET_ID = "123_0JLW-SPtFugfMLTCIvTaL80Puexw875lWOmwXvjc"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

KVAL_LISA = {"EMU/DMU": 140, "EMU+DMU": 165, "EMU+DMU+SKODA": 205}
OPILASE_TUNNITASU = 2.83 

# Erisused (ainult minutite jaoks)
if 'minutid' not in st.session_state:
    st.session_state.minutid = {}

# --- 2. ANDMETE LAADIMINE ---
@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for col in ['TUUR', 'PAEV', 'ALGUS', 'LOPP', 'SPLIT']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        df['ALATES'] = pd.to_datetime(df['ALATES'], errors='coerce')
        df['KUNI'] = pd.to_datetime(df['KUNI'], errors='coerce')
        return df.dropna(subset=['TUUR', 'ALATES', 'KUNI'])
    except Exception as e:
        st.error(f"Viga tabeli laadimisel: {e}")
        return None

def get_matching_rows(df, tuur_nimi, valitud_kuupaev):
    mask = (df['TUUR'] == tuur_nimi) & (df['ALATES'] <= valitud_kuupaev) & (df['KUNI'] >= valitud_kuupaev)
    potentsiaalsed = df[mask]
    if potentsiaalsed.empty: return None
    wd = valitud_kuupaev.weekday()
    kp_str = valitud_kuupaev.strftime("%d.%m")
    sobivad = ["DEFAULT"]
    if wd <= 4: sobivad.append("ER")
    if wd >= 5: sobivad.append("LP")
    if wd == 0: sobivad.append("E")
    if 1 <= wd <= 4: sobivad.append("T-R")
    if wd <= 3: sobivad.append("E-N")
    if wd == 4: sobivad.append("R")
    match = potentsiaalsed[potentsiaalsed['PAEV'].str.contains(kp_str, na=False)]
    if not match.empty: return match.iloc[0]
    for tahis in reversed(sobivad):
        match = potentsiaalsed[potentsiaalsed['PAEV'].str.upper() == tahis]
        if not match.empty: return match.iloc[0]
    return None

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Üldseaded")
    baaspalk = st.number_input("Baastasu (€/h)", value=12.42)
    kval = st.selectbox("Kvalifikatsioon", options=list(KVAL_LISA.keys()))
    norm_kuu = st.number_input("Kuu normtunnid", value=168.0)
    
    st.divider()
    st.header("⏳ Lisaminutid")
    valitud_kuu = st.selectbox("Vali kuu", ["Märts", "Aprill", "Mai", "Juuni"])
    kuu_map = {"Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}
    k_num = kuu_map[valitud_kuu]
    
    paevi_valikus = range(1, (pd.Timestamp(2026, k_num, 1) + pd.offsets.MonthEnd(0)).day + 1)
    e_paev = st.selectbox("Vali kuupäev", paevi_valikus)
    e_min = st.number_input("Lisa minutid (+)", min_value=0, step=5)
    
    if st.button("Salvesta minutid"):
        st.session_state.minutid[f"{e_paev}.{k_num}"] = e_min
        st.toast(f"Päevale {e_paev} lisatud {e_min} min")

    if st.session_state.minutid:
        if st.button("Puhasta lisaminutid"):
            st.session_state.minutid = {}
            st.rerun()

# --- 4. PEALINE TÖÖLAUD ---
df_tuurid = load_data()

if df_tuurid is not None:
    st.title(f"🚂 {valitud_kuu} 2026")
    paevi_kuus = (pd.Timestamp(2026, k_num, 1) + pd.offsets.MonthEnd(0)).day
    graafik_tulemused = []
    
    cols = st.columns(7) 
    for i in range(1, paevi_kuus + 1):
        dt = datetime(2026, k_num, i)
        lisa_min = st.session_state.minutid.get(f"{i}.{k_num}", 0)
        
        with cols[(i-1)%7]:
            # Kui on lisaminutid, näitame märki
            p_text = f"**{i:02d}.{k_num:02d}**"
            if lisa_min > 0: p_text += f" (+{lisa_min}m)"
            st.write(p_text)
            
            tuuri_nimed = sorted(df_tuurid['TUUR'].unique().tolist())
            t_valik = st.selectbox("T", ["Vaba", "P", "KO"] + tuuri_nimed, key=f"t{i}", label_visibility="collapsed")
            # ÕPILASE MÄRGE TAGASI KALENDRISSE
            opilane = st.checkbox("Õ", key=f"s{i}", help="Õpilase tasu 2.83€/h")

            tunnid, tasu, nv_tunnid = 0.0, 0.0, 0.0
            is_work = False

            if t_valik == "P":
                nv_tunnid = 8.0
            elif t_valik == "KO":
                tunnid = 8.0
                tasu = 8.0 * baaspalk
                is_work = True
            elif t_valik != "Vaba":
                rida = get_matching_rows(df_tuurid, t_valik, dt)
                if rida is not None:
                    try:
                        s_str = str(rida['ALGUS']).replace('.', ':')
                        e_str = str(rida['LOPP']).replace('.', ':')
                        s_dt = datetime.strptime(s_str, "%H:%M")
                        e_dt = datetime.strptime(e_str, "%H:%M")
                        if e_dt <= s_dt: e_dt += timedelta(days=1)
                        
                        tunnid = ((e_dt - s_dt).total_seconds() / 3600) + (lisa_min / 60)
                        kordaja = 1.2 if str(rida['SPLIT']).upper() == "TRUE" else 1.0
                        tasu = (tunnid * baaspalk * kordaja) + (tunnid * OPILASE_TUNNITASU if opilane else 0)
                        is_work = True
                    except:
                        pass

            graafik_tulemused.append({"t": tunnid, "r": tasu, "nv": nv_tunnid, "work": is_work})

    # --- KOKKUVÕTE ---
    res_df = pd.DataFrame(graafik_tulemused)
    kokku_t = res_df["t"].sum()
    uletunnid = max(0, kokku_t - (norm_kuu - res_df["nv"].sum()))
    toopaevi = res_df[res_df["work"] == True].shape[0]
    kval_euro = min((toopaevi / 22) * KVAL_LISA[kval], KVAL_LISA[kval])
    bruto = res_df['r'].sum() + kval_euro + (uletunnid * baaspalk * 0.5)
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Töötatud tunde", f"{kokku_t:.2f} h")
    c2.metric("Ületunnid", f"{uletunnid:.2f} h")
    c3.metric("Ületunni lisa (0.5x)", f"{uletunnid * baaspalk * 0.5:.2f} €")
    st.success(f"### Prognoositav kuu Bruto: {bruto:.2f} €")
