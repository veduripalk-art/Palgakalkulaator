import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Vedurijuhi Kalkulaator PRO", layout="wide")

SHEET_ID = "1cUzXOh1EB8XH3nzm78C4TRgzDv26twRF_kLVS7pRujU"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

if 'lisa_minutid' not in st.session_state: st.session_state.lisa_minutid = {}

@st.cache_data(ttl=5)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip().upper() for c in df.columns]
        df['ALATES_DT'] = pd.to_datetime(df['ALATES'], format='%Y-%m-%d', errors='coerce')
        df['KUNI_DT'] = pd.to_datetime(df['KUNI'], format='%Y-%m-%d', errors='coerce')
        return df
    except: return None

def get_shift_details(df, tuur_nimi, kp):
    if df is None or tuur_nimi in ["-", "P", "KO"]: return None
    mask = (df['TUUR'] == tuur_nimi) & (df['ALATES_DT'] <= kp) & (df['KUNI_DT'] >= kp)
    valik = df[mask]
    if valik.empty: return None
    
    wd = kp.weekday()
    paeva_tyyp = "ER" if wd < 5 else "LP"
    
    # DMU-spetsiifiline: E-N ja R kontroll
    if wd <= 3: matches = valik[valik['PAEV'].str.upper() == "E-N"]
    elif wd == 4: matches = valik[valik['PAEV'].str.upper() == "R"]
    else: matches = pd.DataFrame()

    if matches.empty:
        matches = valik[valik['PAEV'].str.upper() == paeva_tyyp]
    if matches.empty:
        matches = valik[valik['PAEV'].str.upper() == "DEFAULT"]
    
    return matches.iloc[0] if not matches.empty else valik.iloc[0]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Seaded")
    kuu_nimi = st.selectbox("Vali kuu", ["Märts", "Aprill", "Mai", "Juuni"])
    kuu_idx = {"Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}[kuu_nimi]
    baaspalk = st.number_input("Baastasu (€/h)", value=12.42)
    
    st.header("⏳ Aja korrigeerimine")
    p_num = st.number_input("Päev", min_value=1, max_value=31, value=1)
    minutid = st.number_input("Lisa/vähenda min", value=0, step=5)
    if st.button("Salvesta aeg"):
        st.session_state.lisa_minutid[f"{p_num}.{kuu_idx}"] = minutid
        st.toast("Salvestatud!")

df = load_data()

if df is not None:
    st.title(f"🚂 {kuu_nimi} 2026")
    days_in_month = 31 if kuu_idx in [3, 5] else 30
    shift_results = []
    tuuri_valikud = ["-", "P", "KO"] + sorted(df['TUUR'].unique().tolist())

    for row_start in range(1, days_in_month + 1, 7):
        cols = st.columns(7)
        for j in range(7):
            day_num = row_start + j
            if day_num <= days_in_month:
                with cols[j]:
                    dt = datetime(2026, kuu_idx, day_num)
                    st.write(f"**{day_num:02d}.{kuu_idx:02d}**")
                    t_valik = st.selectbox("Tuur", tuuri_valikud, key=f"d{day_num}", label_visibility="collapsed")
                    opilane = st.checkbox("Õpilane", key=f"op{day_num}")
                    
                    lisa_m = st.session_state.lisa_minutid.get(f"{day_num}.{kuu_idx}", 0)
                    tunnid, tasu, is_work = 0.0, 0.0, False
                    
                    res = get_shift_details(df, t_valik, dt)
                    
                    if t_valik == "KO":
                        tunnid = 8.0 + (lisa_m/60); tasu = tunnid * baaspalk; is_work = True
                    elif res is not None:
                        try:
                            s = datetime.strptime(str(res['ALGUS']).replace('.', ':'), "%H:%M")
                            e = datetime.strptime(str(res['LOPP']).replace('.', ':'), "%H:%M")
                            if e <= s: e += timedelta(days=1)
                            tunnid = ((e - s).total_seconds() / 3600) + (lisa_m/60)
                            kordaja = 1.2 if str(res['SPLIT']).upper() == "TRUE" else 1.0
                            tasu = (tunnid * baaspalk * kordaja) + (tunnid * 2.83 if opilane else 0)
                            is_work = True
                        except: st.caption("Viga")
                    
                    if is_work: st.caption(f"{tunnid:.2f}h | {tasu:.2f}€")
                    shift_results.append({"t": tunnid, "r": tasu})

    total_h = sum(x['t'] for x in shift_results)
    total_r = sum(x['r'] for x in shift_results)
    st.divider()
    st.success(f"### Kokku: {total_h:.2f} h | {total_r:.2f} € Bruto")
