import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Vedurijuhi Kalkulaator", layout="wide")

# Sinu tabel
SHEET_ID = "1cUzXOh1EB8XH3nzm78C4TRgzDv26twRF_kLVS7pRujU"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

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
    
    # Filtreeri nime ja kuupäeva vahemiku järgi
    mask = (df['TUUR'] == tuur_nimi) & (df['ALATES_DT'] <= kp) & (df['KUNI_DT'] >= kp)
    valik = df[mask]
    
    if valik.empty: return None
    
    # Päeva tüübi kontroll (ER/LP/Default)
    wd = kp.weekday()
    paeva_tyyp = "ER" if wd < 5 else "LP"
    
    tahne_vaste = valik[valik['PAEV'].str.upper() == paeva_tyyp]
    if not tahne_vaste.empty: return tahne_vaste.iloc[0]
    
    default_vaste = valik[valik['PAEV'].str.upper() == "DEFAULT"]
    if not default_vaste.empty: return default_vaste.iloc[0]
    
    return valik.iloc[0]

# --- UI ---
with st.sidebar:
    st.header("Seaded")
    kuu_nimi = st.selectbox("Kuu", ["Märts", "Aprill", "Mai", "Juuni"])
    kuu_idx = {"Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}[kuu_nimi]
    baaspalk = st.number_input("Tunnitasu", value=12.42)
    norm = st.number_input("Kuu norm", value=168)

df = load_data()

if df is not None:
    st.title(f"🚂 Graafik: {kuu_nimi} 2026")
    
    # Märtsis on 31 päeva
    days_in_month = 31 if kuu_idx == 3 else 30 
    if kuu_idx == 5: days_in_month = 31
    
    shift_results = []
    tuuri_valikud = ["-", "P", "KO"] + sorted(df['TUUR'].unique().tolist())

    # Fikseeritud 7 veergu, et read ei nihkuks
    for row_start in range(1, days_in_month + 1, 7):
        cols = st.columns(7)
        for j in range(7):
            day_num = row_start + j
            if day_num <= days_in_month:
                with cols[j]:
                    dt = datetime(2026, kuu_idx, day_num)
                    st.write(f"**{day_num:02d}.{kuu_idx:02d}**")
                    t_valik = st.selectbox("Tuur", tuuri_valikud, key=f"d{day_num}", label_visibility="collapsed")
                    
                    tunnid, tasu, is_work = 0.0, 0.0, False
                    res = get_shift_details(df, t_valik, dt)
                    
                    if t_valik == "KO":
                        tunnid, tasu, is_work = 8.0, 8.0 * baaspalk, True
                    elif res is not None:
                        try:
                            s = datetime.strptime(res['ALGUS'].replace('.', ':'), "%H:%M")
                            e = datetime.strptime(res['LOPP'].replace('.', ':'), "%H:%M")
                            if e <= s: e += timedelta(days=1)
                            tunnid = (e - s).total_seconds() / 3600
                            kordaja = 1.2 if str(res['SPLIT']).upper() == "TRUE" else 1.0
                            tasu = tunnid * baaspalk * kordaja
                            is_work = True
                            st.caption(f"{tunnid}h")
                        except:
                            st.caption("Viga kellaajas")
                    
                    shift_results.append({"t": tunnid, "r": tasu, "work": is_work})

    # Kokkuvõte
    total_h = sum(x['t'] for x in shift_results)
    total_pay = sum(x['r'] for x in shift_results)
    st.divider()
    st.metric("Tunnid kokku", f"{total_h:.2f} h")
    st.success(f"Prognoositav tasu: {total_pay:.2f} €")
else:
    st.error("Ei saanud tabelit kätte. Kontrolli linki!")
