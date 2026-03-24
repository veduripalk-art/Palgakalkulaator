import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Vedurijuhi Kalkulaator PRO", layout="wide")

# Sinu tabeli andmed
SHEET_ID = "1cUzXOh1EB8XH3nzm78C4TRgzDv26twRF_kLVS7pRujU"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Algväärtustamine
if 'lisa_minutid' not in st.session_state:
    st.session_state.lisa_minutid = {}

@st.cache_data(ttl=10)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip().upper() for c in df.columns]
        df['ALATES_DT'] = pd.to_datetime(df['ALATES'], format='%Y-%m-%d', errors='coerce')
        df['KUNI_DT'] = pd.to_datetime(df['KUNI'], format='%Y-%m-%d', errors='coerce')
        return df
    except:
        return None

def get_shift_details(df, tuur_nimi, kp):
    if df is None or tuur_nimi in ["-", "P", "KO"]: return None
    mask = (df['TUUR'] == tuur_nimi) & (df['ALATES_DT'] <= kp) & (df['KUNI_DT'] >= kp)
    valik = df[mask]
    if valik.empty: return None
    
    wd = kp.weekday()
    paeva_tyyp = "ER" if wd < 5 else "LP"
    
    tahne_vaste = valik[valik['PAEV'].str.upper() == paeva_tyyp]
    if not tahne_vaste.empty: return tahne_vaste.iloc[0]
    
    default_vaste = valik[valik['PAEV'].str.upper() == "DEFAULT"]
    if not default_vaste.empty: return default_vaste.iloc[0]
    return valik.iloc[0]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Seaded")
    kuu_nimi = st.selectbox("Vali kuu", ["Märts", "Aprill", "Mai", "Juuni"])
    kuu_idx = {"Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}[kuu_nimi]
    baaspalk = st.number_input("Baastasu (€/h)", value=12.42)
    opilase_lisa = 2.83
    
    st.divider()
    st.header("⏳ Aja korrigeerimine")
    p_num = st.number_input("Päev", min_value=1, max_value=31, value=1)
    minutid = st.number_input("Lisa/vähenda min", value=0, step=5)
    if st.button("Salvesta aeg"):
        st.session_state.lisa_minutid[f"{p_num}.{kuu_idx}"] = minutid
        st.toast(f"Päevale {p_num} salvestatud {minutid} min")

df = load_data()

if df is not None:
    st.title(f"🚂 {kuu_nimi} 2026")
    
    days_in_month = 31 if kuu_idx in [3, 5] else 30
    shift_results = []
    tuuri_valikud = ["-", "P", "KO"] + sorted(df['TUUR'].unique().tolist())

    # Kalendri vaade
    for row_start in range(1, days_in_month + 1, 7):
        cols = st.columns(7)
        for j in range(7):
            day_num = row_start + j
            if day_num <= days_in_month:
                with cols[j]:
                    dt = datetime(2026, kuu_idx, day_num)
                    st.write(f"**{day_num:02d}.{kuu_idx:02d}**")
                    
                    t_valik = st.selectbox("Tuur", tuuri_valikud, key=f"d{day_num}", label_visibility="collapsed")
                    is_opilane = st.checkbox("Õpilane", key=f"op{day_num}")
                    
                    lisa_m = st.session_state.lisa_minutid.get(f"{day_num}.{kuu_idx}", 0)
                    tunnid, tasu, is_work = 0.0, 0.0, False
                    
                    res = get_shift_details(df, t_valik, dt)
                    
                    if t_valik == "KO":
                        tunnid = 8.0 + (lisa_m / 60)
                        tasu = tunnid * baaspalk
                        is_work = True
                    elif res is not None:
                        try:
                            s = datetime.strptime(res['ALGUS'].replace('.', ':'), "%H:%M")
                            e = datetime.strptime(res['LOPP'].replace('.', ':'), "%H:%M")
                            if e <= s: e += timedelta(days=1)
                            
                            puhas_tunnid = (e - s).total_seconds() / 3600
                            tunnid = puhas_tunnid + (lisa_m / 60)
                            
                            kordaja = 1.2 if str(res['SPLIT']).upper() == "TRUE" else 1.0
                            tasu = (tunnid * baaspalk * kordaja)
                            if is_opilane:
                                tasu += (tunnid * opilase_lisa)
                            is_work = True
                        except:
                            st.error("Viga")
                    
                    if is_work:
                        color = "green" if lisa_m >= 0 else "red"
                        st.caption(f"{tunnid:.2f}h ({tasu:.2f}€)")
                        if lisa_m != 0:
                            st.markdown(f":{color}[Lisasid: {lisa_m}m]")
                    
                    shift_results.append({"t": tunnid, "r": tasu, "work": is_work})

    # --- KOKKUVÕTE ---
    total_h = sum(x['t'] for x in shift_results)
    total_r = sum(x['r'] for x in shift_results)
    
    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Tunnid kokku", f"{total_h:.2f} h")
    c2.metric("Prognoositav BRUTO", f"{total_r:.2f} €")
