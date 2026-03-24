import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. KONFIGURATSIOON JA ANDMED ---
st.set_page_config(page_title="Vedurijuhi Kalkulaator PRO", layout="wide")

# Kvalifikatsioonitasud
KVAL_LISA = {"EMU/DMU": 140, "EMU+DMU": 165, "EMU+DMU+SKODA": 205}

# UUTE TUURIDE ANDMEBAAS (Näidis Sinu saadetud failidest)
# See osa kolib tulevikus täielikult Google Sheetsi
TUURIDE_DATA = [
    # PERIOOD 1: Kuni 05.04
    {"tuur": "60/1", "algus": "11:30", "lopp": "23:20", "paev": "default", "split": True, "alates": "2026-01-01", "kuni": "2026-04-05"},
    # PERIOOD 2: Alates 06.04 (Uued tuurid)
    {"tuur": "11/1", "algus": "09:15", "lopp": "18:35", "paev": "ER", "split": True, "alates": "2026-04-06", "kuni": "2026-06-14"},
    {"tuur": "11/1", "algus": "08:00", "lopp": "18:35", "paev": "LP", "split": True, "alates": "2026-04-06", "kuni": "2026-06-14"},
    {"tuur": "15/2", "algus": "05:15", "lopp": "09:35", "paev": "E", "split": False, "alates": "2026-04-06", "kuni": "2026-06-14"},
    {"tuur": "15/2", "algus": "05:50", "lopp": "09:35", "paev": "T-R", "split": False, "alates": "2026-04-06", "kuni": "2026-06-14"},
    {"tuur": "31/1", "algus": "09:40", "lopp": "20:00", "paev": "default", "split": True, "alates": "2026-04-06", "kuni": "2026-06-14"},
]

# --- 2. ABIFUNKTSIOONID ---

def get_day_type(date):
    d = date.weekday()
    if d == 0: return "E"
    if 1 <= d <= 3: return "T-N"
    if d == 4: return "R"
    return "LP"

def get_quarter_months(month):
    if month in [1, 2, 3]: return [1, 2, 3], "Q1"
    if month in [4, 5, 6]: return [4, 5, 6], "Q2"
    if month in [7, 8, 9]: return [7, 8, 9], "Q3"
    return [10, 11, 12], "Q4"

# --- 3. SIDEBAR (SEADED) ---

with st.sidebar:
    st.header("⚙️ Seaded")
    baaspalk = st.number_input("Baastasu (€/h)", value=12.42)
    kval = st.selectbox("Kvalifikatsioon", options=list(KVAL_LISA.keys()))
    kuu_norm = st.number_input("Kuu normtunnid", value=168.0)
    
    st.divider()
    valitud_kuu_nimi = st.selectbox("Vali kuu", ["Jaanuar", "Veebruar", "Märts", "Aprill", "Mai", "Juuni"])
    kuu_map = {"Jaanuar": 1, "Veebruar": 2, "Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}
    k_num = kuu_map[valitud_kuu_nimi]
    q_months, q_name = get_quarter_months(k_num)
    st.info(f"Kvartal: {q_name}")

# --- 4. PEALEHT ---

st.title(f"🚂 {valitud_kuu_nimi} 2026 Graafik")

päevi = (pd.Timestamp(2026, k_num, 1) + pd.offsets.MonthEnd(0)).day
graafik = []

cols = st.columns(7)
for i in range(1, päevi + 1):
    dt = datetime(2026, k_num, i)
    dtype = get_day_type(dt)
    
    with cols[(i-1)%7]:
        st.write(f"**{i:02d}.{k_num:02d} ({dtype})**")
        t_valik = st.selectbox("Tuur", ["Vaba", "P", "KO", "11/1", "15/2", "31/1", "60/1"], key=f"t{i}")
        lisa_min = st.number_input("+ min", min_value=0, step=5, key=f"m{i}")
        opilane = st.checkbox("Õp", key=f"s{i}")

        # Arvutusloogika
        tunnid, tasu, norm_vahendus = 0, 0, 0
        
        if t_valik == "P":
            norm_vahendus = 8.0
        elif t_valik == "KO":
            tunnid, tasu = 8.0, 8.0 * baaspalk
        elif t_valik != "Vaba":
            # Filtreerime õige tuuri vastavalt kuupäevale ja päevale
            leitud = False
            for r in TUURIDE_DATA:
                alates = datetime.strptime(r["alates"], "%Y-%m-%d")
                kuni = datetime.strptime(r["kuni"], "%Y-%m-%d")
                
                if r["tuur"] == t_valik and alates <= dt <= kuni:
                    # Kontrollime päeva tüüpi (E, T-R, LP, default)
                    if r["paev"] == "default" or r["paev"] == dtype or \
                       (r["paev"] == "ER" and dtype != "LP") or \
                       (r["paev"] == "T-R" and dtype in ["T-N", "R"]):
                        
                        s_dt = datetime.strptime(r["algus"], "%H:%M")
                        e_dt = datetime.strptime(r["lopp"], "%H:%M")
                        if e_dt <= s_dt: e_dt += timedelta(days=1)
                        
                        tunnid = ((e_dt - s_dt).total_seconds() / 3600) + (lisa_min / 60)
                        tunnitasu = baaspalk
                        if r["split"]: tunnitasu += (baaspalk * 0.20)
                        if opilane: tunnitasu += (baaspalk * 0.20)
                        tasu = tunnid * tunnitasu
                        leitud = True
                        break
        
        graafik.append({"t": tunnid, "r": tasu, "nv": norm_vahendus, "work": t_valik not in ["Vaba", "P"]})

# --- 5. KOKKUVÕTE JA KVARTAL ---

df = pd.DataFrame(graafik)
kokku_t = df["t"].sum()
tegelik_norm = kuu_norm - df["nv"].sum()
uletunnid = max(0, kokku_t - tegelik_norm)

st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Töötatud tunde", f"{kokku_t:.2f} h")
c2.metric("Ületunnid", f"{uletunnid:.2f} h", delta=f"Norm: {tegelik_norm}h")
c3.metric("Kvartali lisa (0.5x)", f"{uletunnid * baaspalk * 0.5:.2f} €")

st.success(f"### Jooksev kuu Bruto: {(df['r'].sum() + KVAL_LISA[kval]):.2f} €")
