import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SEADISTUS ---
st.set_page_config(page_title="Vedurijuhi Kalkulaator PRO", layout="wide")

# !!! 123_0JLW-SPtFugfMLTCIvTaL80Puexw875lWOmwXvjc !!!
# Sinu ID on see pikk sümbolite rida Sheetsi URL-is d/ ja /edit vahel
SHEET_ID = "123_0JLW-SPtFugfMLTCIvTaL80Puexw875lWOmwXvjc" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

KVAL_LISA = {"EMU/DMU": 140, "EMU+DMU": 165, "EMU+DMU+SKODA": 205}
OPILASE_TUNNITASU = 2.83  # Lisaõpsu tasu tunnis

# --- 2. ANDMETE LAADIMINE ---
@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        # Veaparandus: Teeme päised suureks täheks ükshaaval
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Kuupäevade ja tekstide puhastus
        df['ALATES'] = pd.to_datetime(df['ALATES'].str.strip())
        df['KUNI'] = pd.to_datetime(df['KUNI'].str.strip())
        df['TUUR'] = df['TUUR'].astype(str).str.strip()
        df['PAEV'] = df['PAEV'].astype(str).str.strip().upper()
        return df
    except Exception as e:
        st.error(f"Viga tabeli laadimisel! Kontrolli SHEET_ID-d ja jagamise seadeid. ({e})")
        return None

# --- 3. TUURI LEIDMINE ---
def get_matching_rows(df, tuur_nimi, valitud_kuupaev):
    mask = (
        (df['TUUR'] == tuur_nimi) & 
        (df['ALATES'] <= valitud_kuupaev) & 
        (df['KUNI'] >= valitud_kuupaev)
    )
    potentsiaalsed = df[mask]
    if potentsiaalsed.empty: return None

    wd = valitud_kuupaev.weekday() 
    kp_str = valitud_kuupaev.strftime("%d.%m")
    sobivad_tahised = ["DEFAULT"]
    if wd <= 4: sobivad_tahised.append("ER")
    if wd >= 5: sobivad_tahised.append("LP")
    if wd == 0: sobivad_tahised.append("E")
    if 1 <= wd <= 4: sobivad_tahised.append("T-R")
    if wd <= 3: sobivad_tahised.append("E-N")
    if wd == 4: sobivad_tahised.append("R")
    
    eri_kp = potentsiaalsed[potentsiaalsed['PAEV'].str.contains(kp_str, na=False)]
    if not eri_kp.empty: return eri_kp.iloc[0]

    for tahis in reversed(sobivad_tahised):
        match = potentsiaalsed[potentsiaalsed['PAEV'] == tahis]
        if not match.empty: return match.iloc[0]
    return None

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Seaded")
    baaspalk = st.number_input("Baastasu (€/h)", value=12.42)
    kval = st.selectbox("Kvalifikatsioon", options=list(KVAL_LISA.keys()))
    norm_kuu = st.number_input("Kuu normtunnid", value=168.0)
    
    st.divider()
    valitud_kuu = st.selectbox("Vali kuu", ["Märts", "Aprill", "Mai", "Juuni"])
    kuu_map = {"Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}
    k_num = kuu_map[valitud_kuu]

# --- 5. TÖÖLAUD ---
df_tuurid = load_data()

if df_tuurid is not None:
    st.title(f"🚂 {valitud_kuu} 2026")
    
    paevi_kuus = (pd.Timestamp(2026, k_num, 1) + pd.offsets.MonthEnd(0)).day
    graafik_tulemused = []
    
    cols = st.columns(7) 
    
    for i in range(1, paevi_kuus + 1):
        dt = datetime(2026, k_num, i)
        with cols[(i-1)%7]:
            st.write(f"**{i:02d}.{k_num:02d}**")
            tuuri_nimed = sorted(df_tuurid['TUUR'].unique().tolist())
            t_valik = st.selectbox("T", ["Vaba", "P", "KO"] + tuuri_nimed, key=f"t{i}", label_visibility="collapsed")
            lisa_min = st.number_input("+min", min_value=0, step=5, key=f"m{i}")
            opilane = st.checkbox("Õ", key=f"s{i}", help="Lisa õpilase eest (2.83€/h)")

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
                        s_dt = datetime.strptime(str(rida['ALGUS']).strip(), "%H:%M")
                        e_dt = datetime.strptime(str(rida['LOPP']).strip(), "%H:%M")
                        if e_dt <= s_dt: e_dt += timedelta(days=1)
                        
                        tunnid = ((e_dt - s_dt).total_seconds() / 3600) + (lisa_min / 60)
                        
                        kordaja = 1.2 if str(rida['SPLIT']).upper() == "TRUE" else 1.0
                        paeva_pohitasu = tunnid * (baaspalk * kordaja)
                        paeva_opilase_lisa = (tunnid * OPILASE_TUNNITASU) if opilane else 0.0
                        
                        tasu = paeva_pohitasu + paeva_opilase_lisa
                        is_work = True
                    except:
                        st.error("Kellaaeg!")

            graafik_tulemused.append({"t": tunnid, "r": tasu, "nv": nv_tunnid, "work": is_work})

    # --- 6. KOKKUVÕTE ---
    res_df = pd.DataFrame(graafik_tulemused)
    kokku_t = res_df["t"].sum()
    uletunnid = max(0, kokku_t - (norm_kuu - res_df["nv"].sum()))
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Töötatud tunde", f"{kokku_t:.2f} h")
    c2.metric("Ületunnid", f"{uletunnid:.2f} h")
    c3.metric("Ületunni lisa (0.5x)", f"{uletunnid * baaspalk * 0.5:.2f} €")
    
    toopaevi = res_df[res_df["work"] == True].shape[0]
    kval_euro = min((toopaevi / 22) * KVAL_LISA[kval], KVAL_LISA[kval])
    
    bruto = res_df['r'].sum() + kval_euro + (uletunnid * baaspalk * 0.5)
    st.success(f"### Prognoositav kuu Bruto: {bruto:.2f} €")
    st.info(f"Selles on kval-lisa {kval_euro:.2f}€ ja kõik õpilase/spliti lisad.")
else:
    st.warning("Ootan Google Sheetsi andmeid... Kontrolli SHEET_ID-d!")
